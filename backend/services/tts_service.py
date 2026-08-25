"""Gemini TTS Service — Text-to-Speech via Google GenAI SDK.

Provides on-demand voice synthesis for chatbot responses:
- Native Google GenAI SDK TTS (`gemini-3.1-flash-tts` default)
- 10-second hard timeout; on failure returns None
- In-memory cache keyed by text hash; TTL 1 hour
- Non-blocking: audio generation happens AFTER text response returns
"""
from __future__ import annotations

import asyncio
import base64
import hashlib
import logging
import os
import time
from typing import Any, Dict, Optional

from services import gemini_client

logger = logging.getLogger("continuity.tts")

DEFAULT_TTS_MODEL = os.getenv("TTS_MODEL", "gemini-3.1-flash-tts")
DEFAULT_VOICE = os.getenv("TTS_VOICE", "Kore")
TTS_TIMEOUT_SECONDS = 10.0
CACHE_TTL_SECONDS = 3600  # 1 hour

# In-memory cache: text_hash -> {audio_base64, mime_type, created_at, expires_at}
_TTS_CACHE: Dict[str, Dict[str, Any]] = {}


def text_hash(text: str) -> str:
    """Compute a stable SHA-256 hash of the text for cache keying."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def _evict_expired() -> None:
    """Remove expired entries from in-memory cache."""
    now = time.time()
    expired = [k for k, v in _TTS_CACHE.items() if now >= v.get("expires_at", 0)]
    for k in expired:
        del _TTS_CACHE[k]


def get_cached(hash_key: str) -> Optional[Dict[str, Any]]:
    """Retrieve cached audio by hash. Returns None if miss or expired."""
    _evict_expired()
    entry = _TTS_CACHE.get(hash_key)
    if entry is None:
        return None
    if time.time() >= entry.get("expires_at", 0):
        _TTS_CACHE.pop(hash_key, None)
        return None
    return entry


async def text_to_speech(
    text: str,
    voice_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Generate speech audio from text using Gemini TTS.

    Returns dict with {audio_base64, mime_type, hash} on success, None on failure.
    Audio is cached in memory keyed by text hash for 1 hour.
    """
    if not text or not text.strip():
        return None

    h = text_hash(text)

    # Check cache first
    cached = get_cached(h)
    if cached is not None:
        logger.info("TTS cache hit for hash=%s", h)
        return {**cached, "cached": True}

    # Check if Gemini is configured
    if not gemini_client.is_configured() or gemini_client.quota_hit():
        logger.warning("TTS skipped: Gemini not configured or quota hit")
        return None

    voice = voice_id or DEFAULT_VOICE

    try:
        from google.genai import types

        client = gemini_client._get_client()

        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=DEFAULT_TTS_MODEL,
                contents=text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_id=voice,
                        ),
                    ),
                ),
            ),
            timeout=TTS_TIMEOUT_SECONDS,
        )

        # Extract audio data from response
        if (
            resp
            and resp.candidates
            and resp.candidates[0].content
            and resp.candidates[0].content.parts
        ):
            audio_part = resp.candidates[0].content.parts[0]
            if audio_part.inline_data and audio_part.inline_data.data:
                audio_bytes = audio_part.inline_data.data
                mime_type = audio_part.inline_data.mime_type or "audio/wav"
                audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")

                entry = {
                    "hash": h,
                    "audio_base64": audio_b64,
                    "mime_type": mime_type,
                    "created_at": time.time(),
                    "expires_at": time.time() + CACHE_TTL_SECONDS,
                }
                _TTS_CACHE[h] = entry
                logger.info(
                    "TTS generated for hash=%s voice=%s model=%s bytes=%d",
                    h, voice, DEFAULT_TTS_MODEL, len(audio_bytes),
                )
                gemini_client._record_result(None)
                return {**entry, "cached": False}

        logger.warning("TTS response empty for hash=%s", h)
        return None

    except asyncio.TimeoutError:
        logger.warning("TTS generation timed out after %.1fs for hash=%s", TTS_TIMEOUT_SECONDS, h)
        return None
    except Exception as exc:
        gemini_client._record_result(exc)
        logger.warning("TTS generation failed for hash=%s: %s", h, exc)
        return None
