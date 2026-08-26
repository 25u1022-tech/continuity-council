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
import io
import logging
import os
import re
import time
import wave
from typing import Any, Dict, Optional

from services import gemini_client

logger = logging.getLogger("continuity.tts")

DEFAULT_TTS_MODEL = os.getenv("TTS_MODEL", "gemini-2.5-flash-preview-tts")
DEFAULT_VOICE = os.getenv("TTS_VOICE", "Kore")
TTS_TIMEOUT_SECONDS = float(os.getenv("TTS_TIMEOUT_SECONDS", "25.0"))
CACHE_TTL_SECONDS = 3600  # 1 hour

# In-memory cache: text_hash -> {audio_base64, mime_type, created_at, expires_at}
_TTS_CACHE: Dict[str, Dict[str, Any]] = {}


def prepare_spoken_text(text: str, max_chars: int = 220) -> str:
    """Extract a natural, concise spoken summary for speech synthesis.

    Strips markdown formatting, citations, and dense bullet lists to keep
    audio synthesis fast, conversational, and natural without altering
    the full visual response rendered in the UI.
    """
    if not text or not text.strip():
        return ""

    # Clean markdown formatting & annotations
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\(n=[^)]+\)", "", cleaned)
    cleaned = cleaned.replace("~", "about ")

    paragraphs = [p.strip() for p in cleaned.split("\n") if p.strip()]

    # If the response contains bullet points or numbered lists, extract lead-in + concluding takeaway
    non_bullets = [
        p for p in paragraphs
        if not p.startswith("•") and not p.startswith("-") and not re.match(r"^\d+\.", p)
    ]

    if len(non_bullets) >= 2 and any(p.startswith("•") or p.startswith("-") or re.match(r"^\d+\.", p) for p in paragraphs):
        lead_in = non_bullets[0].rstrip(":")
        verdict = non_bullets[1]
        spoken = f"{lead_in}. {verdict}"
    elif non_bullets:
        spoken = " ".join(non_bullets[:2])
    else:
        spoken = " ".join(paragraphs[:2])

    spoken = re.sub(r"\s+", " ", spoken).strip()
    if len(spoken) > max_chars:
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", spoken) if s.strip()]
        out = []
        for s in sentences:
            if sum(len(x) + 1 for x in out) + len(s) <= max_chars:
                out.append(s)
            else:
                break
        spoken = " ".join(out) if out else spoken[:max_chars]

    return spoken


def pcm_to_wav(
    pcm_bytes: bytes,
    sample_rate: int = 24000,
    channels: int = 1,
    sample_width: int = 2,
) -> bytes:
    """Wrap raw PCM samples into standard RIFF/WAV audio for browser playback."""
    wav_io = io.BytesIO()
    with wave.open(wav_io, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm_bytes)
    return wav_io.getvalue()


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
    spoken_text = prepare_spoken_text(text) or text

    try:
        from google.genai import types

        client = gemini_client._get_client()

        resp = await asyncio.wait_for(
            client.aio.models.generate_content(
                model=DEFAULT_TTS_MODEL,
                contents=spoken_text,
                config=types.GenerateContentConfig(
                    response_modalities=["AUDIO"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice,
                            ),
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
                raw_mime = audio_part.inline_data.mime_type or "audio/l16"

                # Convert raw PCM (audio/l16) to standard browser-playable WAV if needed
                if not audio_bytes.startswith(b"RIFF"):
                    rate = 24000
                    if "rate=" in raw_mime.lower():
                        try:
                            rate = int(raw_mime.lower().split("rate=")[1].split(";")[0].split()[0])
                        except Exception:
                            rate = 24000
                    audio_bytes = pcm_to_wav(audio_bytes, sample_rate=rate, channels=1, sample_width=2)

                mime_type = "audio/wav"
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
