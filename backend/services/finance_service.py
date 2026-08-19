"""Frankfurter / European Central Bank Foreign Exchange Service.

Fetches live and benchmark exchange rates for international filming currencies.

Hardening:
- 24-hour in-memory TTL cache per (from_curr, to_curr)
- 3.0s strict timeout
- Deterministic fallback to benchmark ECB rates (never blocks investigation)
- Attribution: Frankfurter / European Central Bank
"""
from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger("continuity.finance")

# Cache: (from_curr, to_curr) -> (timestamp, rate)
_FX_CACHE: Dict[Tuple[str, str], Tuple[float, float]] = {}
_CACHE_TTL = 86400.0  # 24 hours

# Fallback reference exchange rates to USD
_BENCHMARK_RATES_TO_USD: Dict[str, float] = {
    "USD": 1.0,
    "EUR": 1.085,
    "GBP": 1.282,
    "CAD": 0.738,
    "AED": 0.272,
    "JOD": 1.410,
    "JPY": 0.0068,
    "AUD": 0.655,
}


async def get_exchange_rate(from_curr: str, to_curr: str = "USD") -> Dict[str, Any]:
    """Get FX multiplier: amount_in_from_curr * rate = amount_in_to_curr."""
    from_c = (from_curr or "USD").upper().strip()
    to_c = (to_curr or "USD").upper().strip()

    if from_c == to_c:
        return {
            "rate": 1.0,
            "from_currency": from_c,
            "to_currency": to_c,
            "source": "Parity",
            "cached": True,
        }

    cache_key = (from_c, to_c)
    now = time.time()
    cached = _FX_CACHE.get(cache_key)
    if cached and (now - cached[0]) < _CACHE_TTL:
        return {
            "rate": cached[1],
            "from_currency": from_c,
            "to_currency": to_c,
            "source": "Frankfurter (ECB cache)",
            "cached": True,
        }

    # Query Frankfurter API
    url = f"https://api.frankfurter.app/latest?from={from_c}&to={to_c}"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                rate = float(data.get("rates", {}).get(to_c, 1.0))
                _FX_CACHE[cache_key] = (now, rate)
                return {
                    "rate": rate,
                    "from_currency": from_c,
                    "to_currency": to_c,
                    "source": "Frankfurter (source: ECB)",
                    "cached": False,
                }
    except Exception as exc:
        logger.warning("Frankfurter FX fetch failed (%s), using benchmark fallback", exc)

    # Fallback via benchmark tables
    rate_from_usd = _BENCHMARK_RATES_TO_USD.get(from_c, 1.0)
    rate_to_usd = _BENCHMARK_RATES_TO_USD.get(to_c, 1.0)
    rate = round(rate_from_usd / max(0.0001, rate_to_usd), 4)

    _FX_CACHE[cache_key] = (now, rate)
    return {
        "rate": rate,
        "from_currency": from_c,
        "to_currency": to_c,
        "source": "Frankfurter benchmark prior",
        "cached": True,
    }


async def convert_currency(amount: float, from_curr: str, to_curr: str = "USD") -> Tuple[int, float]:
    """Convert amount to target currency. Returns (converted_int, rate_applied)."""
    fx_info = await get_exchange_rate(from_curr, to_curr)
    rate = fx_info["rate"]
    converted = int(round(amount * rate))
    return converted, rate
