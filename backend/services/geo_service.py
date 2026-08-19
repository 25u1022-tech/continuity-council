"""Geographic & Transit Distance Service.

Calculates Haversine great-circle distance between locations and provides
OpenStreetMap Nominatim geocoding for new production locations.

Hardening:
- Haversine formula computed locally in pure Python (0ms)
- Nominatim geocoding: User-Agent header + 1 req/s rate-limiting
- 3.0s timeout with fallback
- Attribution: (c) OpenStreetMap contributors
"""
from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger("continuity.geo")

_GEOCODE_CACHE: Dict[str, Tuple[float, float]] = {}
_LAST_NOMINATIM_CALL = 0.0
_NOMINATIM_LOCK = asyncio.Lock()


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great circle distance between two points in statute miles."""
    if (lat1 == lat2 and lon1 == lon2) or (not lat1 and not lon1) or (not lat2 and not lon2):
        return 0.0

    # Earth radius in miles
    radius = 3958.8

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2.0) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(radius * c, 1)


async def geocode_location(query: str, fallback_lat: float = 34.05, fallback_lon: float = -118.25) -> Tuple[float, float]:
    """Resolve location string to (latitude, longitude) via Nominatim OpenStreetMap."""
    global _LAST_NOMINATIM_CALL
    q = (query or "").strip()
    if not q:
        return fallback_lat, fallback_lon

    if q in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[q]

    async with _NOMINATIM_LOCK:
        # Respect Nominatim policy: 1 request per second
        now = time.time()
        elapsed = now - _LAST_NOMINATIM_CALL
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _LAST_NOMINATIM_CALL = time.time()

        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "ContinuityCouncil-Hackathon/1.0"}
        params = {"q": q, "format": "json", "limit": 1}

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        lat = float(data[0]["lat"])
                        lon = float(data[0]["lon"])
                        _GEOCODE_CACHE[q] = (lat, lon)
                        return lat, lon
        except Exception as exc:
            logger.warning("Nominatim geocoding failed for '%s' (%s), using fallback", q, exc)

    _GEOCODE_CACHE[q] = (fallback_lat, fallback_lon)
    return fallback_lat, fallback_lon
