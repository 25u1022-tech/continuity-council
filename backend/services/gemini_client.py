"""Gemini via the OFFICIAL google-genai SDK (hard hackathon requirement).

All agent LLM reasoning goes through this module. Every call is strictly budgeted:
- Hard request timeout (<=8s)
- max_output_tokens capped (<=1024)
- Instant deterministic fallback on timeout or quota exhaustion
- Time-based quota cooldown with auto-recovery
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("continuity.gemini")

DEFAULT_QUOTA_COOLDOWN_SECONDS: float = 60.0

_client = None
_quota_reset_at: Optional[float] = None


def quota_hit() -> bool:
    """True if quota/rate-limit cooldown is currently active."""
    global _quota_reset_at
    if _quota_reset_at is None:
        return False
    now = time.time()
    if now >= _quota_reset_at:
        _quota_reset_at = None
        logger.info("Gemini quota cooldown expired — resuming API calls")
        return False
    return True


def _extract_retry_delay(exc: Exception) -> float:
    """Extract retry delay from exception if available, else default to 60s."""
    for attr in ("retry_delay", "retry_after", "retry_after_seconds"):
        val = getattr(exc, attr, None)
        if val is not None:
            if hasattr(val, "total_seconds"):
                return max(1.0, min(300.0, float(val.total_seconds())))
            if hasattr(val, "seconds"):
                return max(1.0, min(300.0, float(val.seconds)))
            try:
                numeric = float(val)
                if numeric > 0:
                    return max(1.0, min(300.0, numeric))
            except (ValueError, TypeError):
                pass

    match = re.search(r"retry[-_\s]?(?:after|in|delay)[^\d]*(\d+(?:\.\d+)?)", str(exc), re.IGNORECASE)
    if match:
        try:
            val = float(match.group(1))
            if val > 0:
                return max(1.0, min(300.0, val))
        except (ValueError, TypeError):
            pass

    return DEFAULT_QUOTA_COOLDOWN_SECONDS


def _record_result(exc: Exception | None) -> None:
    global _quota_reset_at
    if exc is None:
        _quota_reset_at = None
        return
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        cooldown = _extract_retry_delay(exc)
        _quota_reset_at = time.time() + cooldown
        logger.warning(
            "Gemini quota reached (cooldown %.1fs, active until %.1f) — switching to deterministic fast path",
            cooldown,
            _quota_reset_at,
        )


def is_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def model_name() -> str:
    # Prefer fast flash model; allow env override
    return os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _thinking():
    """Low thinking level for Gemini 3.6 flash = fast demo-grade latency."""
    from google.genai import types

    try:
        return types.ThinkingConfig(thinking_level="low")
    except Exception:  # noqa: BLE001
        return None


async def generate_text(prompt: str, timeout: float = 6.0, temperature: float = 0.3) -> Optional[str]:
    """Plain text generation; returns None immediately on any failure (caller falls back)."""
    if not is_configured():
        return None
    if quota_hit():
        remaining = max(0.0, (_quota_reset_at or 0.0) - time.time())
        logger.info("Quota cooldown active (%.1fs remaining) — skipping Gemini generate_text", remaining)
        return None
    try:
        from google.genai import types

        client = _get_client()
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model_name(),
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=512,
                    thinking_config=_thinking(),
                ),
            ),
            timeout=timeout,
        )
        _record_result(None)
        return (resp.text or "").strip() or None
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini generate_text API call failed: %s", exc)
        _record_result(exc)
        return None


async def generate_json(prompt: str, timeout: float = 6.0, max_tokens: int = 512) -> Optional[Any]:
    """JSON-mode generation with hard timeout; returns parsed object or None on failure."""
    if not is_configured():
        return None
    if quota_hit():
        remaining = max(0.0, (_quota_reset_at or 0.0) - time.time())
        logger.info("Quota cooldown active (%.1fs remaining) — skipping Gemini generate_json", remaining)
        return None
    try:
        from google.genai import types

        client = _get_client()
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model_name(),
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.1,
                    max_output_tokens=max_tokens,
                    thinking_config=_thinking(),
                ),
            ),
            timeout=timeout,
        )
        text = (resp.text or "").strip()
        _record_result(None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini generate_json API call failed (fallback used): %s", exc)
        _record_result(exc)
        return None

    if not text:
        return None

    try:
        return json.loads(text)
    except json.JSONDecodeError as jde:
        logger.warning("Gemini returned unparsable JSON response (%s), falling back: %.200s", jde, text)
        return None


async def request_tool_calls(
    prompt: str,
    tool_declarations: List[Dict[str, Any]],
    tool_executor,
    timeout: float = 6.0,
) -> int:
    """SINGLE Gemini turn that requests tool calls, then executes each one."""
    if not is_configured():
        return 0
    if quota_hit():
        remaining = max(0.0, (_quota_reset_at or 0.0) - time.time())
        logger.info("Quota cooldown active (%.1fs remaining) — skipping Gemini request_tool_calls", remaining)
        return 0
    try:
        from google.genai import types

        client = _get_client()
        tools = [types.Tool(function_declarations=[
            types.FunctionDeclaration(**decl) for decl in tool_declarations
        ])]
        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=model_name(),
                contents=prompt,
                config=types.GenerateContentConfig(
                    tools=tools,
                    temperature=0,
                    max_output_tokens=512,
                    thinking_config=_thinking(),
                ),
            ),
            timeout=timeout,
        )
        _record_result(None)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini request_tool_calls API call failed (direct MCP used): %s", exc)
        _record_result(exc)
        return 0

    calls = resp.function_calls or []
    executed = 0
    for call in calls:
        try:
            await tool_executor(call.name, dict(call.args or {}))
            executed += 1
        except Exception as exc:  # noqa: BLE001
            logger.warning("tool execution failed for %s: %s", call.name, exc)
    return executed

