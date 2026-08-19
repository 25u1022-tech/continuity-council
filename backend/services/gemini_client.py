"""Gemini via the OFFICIAL google-genai SDK (hard hackathon requirement).

All agent LLM reasoning goes through this module. Every call is strictly budgeted:
- Hard request timeout (<=8s)
- max_output_tokens capped (<=1024)
- Instant deterministic fallback on timeout or quota exhaustion
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
from typing import Any, Dict, List, Optional

logger = logging.getLogger("continuity.gemini")

_client = None
_quota_hit = False


def quota_hit() -> bool:
    """True if the most recent Gemini failure was a quota/rate-limit (429)."""
    return _quota_hit


def _record_result(exc: Exception | None) -> None:
    global _quota_hit
    if exc is None:
        _quota_hit = False
        return
    text = str(exc)
    if "429" in text or "RESOURCE_EXHAUSTED" in text or "quota" in text.lower():
        _quota_hit = True
        logger.warning("Gemini quota reached — switching to deterministic fast path")


def is_configured() -> bool:
    return bool(os.environ.get("GEMINI_API_KEY", "").strip())


def model_name() -> str:
    # Prefer fast flash model; allow env override
    return os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def _get_client():
    global _client
    if _client is None:
        from google import genai

        _client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _client


def _thinking():
    """Low thinking level for Gemini 3.x/2.5 flash = fast demo-grade latency."""
    from google.genai import types

    try:
        return types.ThinkingConfig(thinking_level="low")
    except Exception:  # noqa: BLE001
        return None


async def generate_text(prompt: str, timeout: float = 6.0, temperature: float = 0.3) -> Optional[str]:
    """Plain text generation; returns None immediately on any failure (caller falls back)."""
    if not is_configured() or _quota_hit:
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
        logger.warning("Gemini generate_text skipped: %s", exc)
        _record_result(exc)
        return None


async def generate_json(prompt: str, timeout: float = 6.0, max_tokens: int = 512) -> Optional[Any]:
    """JSON-mode generation with hard timeout; returns parsed object or None on failure."""
    if not is_configured() or _quota_hit:
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
        if not text:
            return None
        _record_result(None)
        return json.loads(text)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini generate_json skipped (fallback used): %s", exc)
        _record_result(exc)
        return None


async def request_tool_calls(
    prompt: str,
    tool_declarations: List[Dict[str, Any]],
    tool_executor,
    timeout: float = 6.0,
) -> int:
    """SINGLE Gemini turn that requests tool calls, then executes each one."""
    if not is_configured() or _quota_hit:
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
        calls = resp.function_calls or []
        executed = 0
        for call in calls:
            try:
                await tool_executor(call.name, dict(call.args or {}))
                executed += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning("tool execution failed for %s: %s", call.name, exc)
        if executed:
            _record_result(None)
        return executed
    except Exception as exc:  # noqa: BLE001
        logger.warning("Gemini request_tool_calls skipped (direct MCP used): %s", exc)
        _record_result(exc)
        return 0

