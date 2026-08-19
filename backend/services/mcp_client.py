"""Official mcp-clickhouse MCP client (stdio) — THE ClickHouse track requirement.

The FastAPI backend spawns the official `mcp-clickhouse` server as a persistent stdio
subprocess and maintains a real MCP ClientSession over it. The Budget Sentinel
agent executes every historical-evidence query through this layer at runtime in <200ms.

Hardening:
- Persistent singleton session started once and reused
- Automatic reconnect on failure or broken pipe
- Timeout + one fast retry (demo never hangs)
- Read-only: CLICKHOUSE_ALLOW_WRITE_ACCESS=false
- Every call logged: tool, SQL, rows, latency
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import sys
import time
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger("continuity.mcp")


def _server_params():
    from mcp import StdioServerParameters

    env = {
        **os.environ,
        "CLICKHOUSE_HOST": os.environ.get("CLICKHOUSE_HOST", ""),
        "CLICKHOUSE_PORT": os.environ.get("CLICKHOUSE_PORT", "8443"),
        "CLICKHOUSE_USER": os.environ.get("CLICKHOUSE_USER", "default"),
        "CLICKHOUSE_PASSWORD": os.environ.get("CLICKHOUSE_PASSWORD", ""),
        "CLICKHOUSE_SECURE": "true",
        "CLICKHOUSE_VERIFY": "true",
        "CLICKHOUSE_MCP_SERVER_TRANSPORT": "stdio",
        "CLICKHOUSE_ALLOW_WRITE_ACCESS": "false",  # MCP layer is strictly read-only
        "CLICKHOUSE_MCP_QUERY_TIMEOUT": "25",
    }
    binary = shutil.which("mcp-clickhouse") or shutil.which(
        "mcp-clickhouse", path=os.path.dirname(sys.executable)
    )
    if binary:
        return StdioServerParameters(command=binary, args=[], env=env)
    return StdioServerParameters(
        command=sys.executable, args=["-m", "mcp_clickhouse.main"], env=env
    )


def _parse_tool_payload(result) -> Dict[str, Any]:
    """Tolerant parser for mcp-clickhouse run_query result payloads."""
    # 1) structured content
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        inner = structured.get("result", structured)
        if isinstance(inner, str):
            try:
                inner = json.loads(inner)
            except json.JSONDecodeError:
                inner = None
        if isinstance(inner, dict) and "rows" in inner:
            return inner
    # 2) text content
    for item in (result.content or []):
        text = getattr(item, "text", None)
        if not text:
            continue
        try:
            data = json.loads(text)
            if isinstance(data, str):
                data = json.loads(data)
            if isinstance(data, dict) and "rows" in data:
                return data
        except json.JSONDecodeError:
            continue
    return {"columns": [], "rows": []}


class PersistentMCPClient:
    """Manages a single long-lived stdio connection to mcp-clickhouse."""

    def __init__(self):
        self._lock = asyncio.Lock()
        self._session = None
        self._stdio_ctx = None
        self._session_ctx = None
        self._query_tool: Optional[str] = None

    async def _connect(self) -> None:
        if self._session is not None:
            return
        from mcp import ClientSession
        from mcp.client.stdio import stdio_client

        params = _server_params()
        self._stdio_ctx = stdio_client(params)
        read_stream, write_stream = await self._stdio_ctx.__aenter__()
        try:
            self._session_ctx = ClientSession(read_stream, write_stream)
            self._session = await self._session_ctx.__aenter__()
            await self._session.initialize()
            tools = await self._session.list_tools()
            names = {t.name for t in tools.tools}
            self._query_tool = (
                "run_select_query" if "run_select_query" in names else "run_query"
            )
            logger.info(
                "Persistent mcp-clickhouse connected. Tools: %s -> using %s",
                sorted(names),
                self._query_tool,
            )
        except Exception:
            await self._close()
            raise

    async def _close(self) -> None:
        if self._session_ctx:
            try:
                await self._session_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._session_ctx = None
        if self._stdio_ctx:
            try:
                await self._stdio_ctx.__aexit__(None, None, None)
            except Exception:
                pass
            self._stdio_ctx = None
        self._session = None
        self._query_tool = None

    async def warm(self) -> None:
        """Pre-warm connection at app startup."""
        async with self._lock:
            try:
                await self._connect()
            except Exception as exc:
                logger.warning("MCP client startup warm skipped: %s", exc)

    async def close(self) -> None:
        async with self._lock:
            await self._close()

    async def run_query(
        self, sql: str, timeout: float = 15.0
    ) -> Tuple[Dict[str, Any], int, str]:
        async with self._lock:
            try:
                if self._session is None:
                    await self._connect()
                t0 = time.perf_counter()
                result = await asyncio.wait_for(
                    self._session.call_tool(self._query_tool, {"query": sql}),
                    timeout=timeout,
                )
                latency_ms = int((time.perf_counter() - t0) * 1000)
                if result.isError:
                    raw = "; ".join(
                        getattr(c, "text", "") for c in (result.content or [])
                    )
                    raise RuntimeError(f"MCP tool error: {raw[:400]}")
                return _parse_tool_payload(result), latency_ms, self._query_tool
            except Exception as exc:
                logger.warning(
                    "MCP query failed on persistent session (resetting connection): %s", exc
                )
                await self._close()
                raise


_POOL = PersistentMCPClient()


async def start_mcp_client() -> None:
    """Warm the persistent MCP client."""
    await _POOL.warm()


async def stop_mcp_client() -> None:
    """Cleanly close persistent MCP client."""
    await _POOL.close()


async def mcp_run_query(sql: str, timeout: float = 15.0) -> Dict[str, Any]:
    """Execute a SELECT through the official mcp-clickhouse server.

    Reuses persistent ClientSession. Returns {columns, rows, latency_ms, tool}.
    """
    last_exc: Optional[Exception] = None
    for attempt in (1, 2):
        try:
            data, latency_ms, tool = await _POOL.run_query(sql, timeout)
            rows = data.get("rows", [])
            logger.info(
                "MCP %s OK attempt=%d latency=%dms rows=%d sql=%s",
                tool, attempt, latency_ms, len(rows), sql[:220],
            )
            try:
                from services import activity_log

                source = (
                    "strategy_performance_mv"
                    if "strategy_performance_mv" in sql
                    else "disruption_history"
                )
                activity_log.record("mcp-clickhouse", f"{tool} · {source}", len(rows), latency_ms)
            except Exception:  # noqa: BLE001
                pass
            return {
                "columns": data.get("columns", []),
                "rows": rows,
                "latency_ms": latency_ms,
                "tool": tool,
            }
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            logger.warning("MCP query attempt %d failed: %s", attempt, exc)
            await asyncio.sleep(0.1)
    raise RuntimeError(f"MCP ClickHouse query failed after retry: {last_exc}")