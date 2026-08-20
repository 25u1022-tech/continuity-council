"""Geographic, Nominatim Geocoding & Global Economic Costing Service.

Provides:
- Haversine great-circle distance calculation (pure Python, 0ms)
- OpenStreetMap Nominatim geocoding with population & extratags extraction
- World Bank GDP PPP per capita (NY.GDP.PCAP.PP.CD) country factor calculation
- City Tier calculation (tier_1: 1.0, tier_2: 0.5, tier_3: 0.35)
- Static ISO 4217 country_code -> currency mapping
- 30-day ClickHouse & in-memory caching tier

Attributions:
- World Bank open data (CC-BY 4.0)
- (c) OpenStreetMap contributors (ODbL)
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import time
from typing import Any, Dict, Optional, Tuple

import httpx

logger = logging.getLogger("continuity.geo")

_GEOCODE_CACHE: Dict[str, Dict[str, Any]] = {}
_LAST_NOMINATIM_CALL = 0.0
_NOMINATIM_LOCK = asyncio.Lock()

# 30-day in-memory TTL cache for World Bank data: country_code -> (timestamp, data_dict)
_WB_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_WB_CACHE_TTL = 2592000.0  # 30 days in seconds

US_GDP_PPP_BENCHMARK = 80000.0

TIER_MULTIPLIERS: Dict[str, float] = {
    "tier_1": 1.0,
    "tier_2": 0.5,
    "tier_3": 0.35,
}

# Embedded static fallback table of ~40 major countries (GDP PPP in USD)
FALLBACK_COUNTRY_GDP_PPP: Dict[str, float] = {
    "US": 80000.0,
    "IN": 10120.0,   # India -> ~0.29x
    "GB": 58200.0,   # UK -> ~0.83x
    "BR": 20200.0,   # Brazil -> ~0.44x
    "NG": 6150.0,    # Nigeria -> ~0.21 -> clamped to 0.25x
    "CA": 60100.0,   # Canada -> ~0.84x
    "AU": 65400.0,   # Australia -> ~0.89x
    "DE": 69300.0,   # Germany -> ~0.92x
    "FR": 60800.0,   # France -> ~0.85x
    "JP": 50200.0,   # Japan -> ~0.76x
    "CN": 24500.0,   # China -> ~0.49x
    "MX": 25100.0,   # Mexico -> ~0.50x
    "ZA": 16100.0,   # South Africa -> ~0.38x
    "ES": 52400.0,   # Spain -> ~0.78x
    "IT": 56900.0,   # Italy -> ~0.81x
    "KR": 54000.0,   # South Korea -> ~0.79x
    "AE": 92000.0,   # UAE -> 1.09x
    "SA": 62000.0,   # Saudi Arabia -> ~0.86x
    "JO": 11400.0,   # Jordan -> ~0.31x
    "ID": 15800.0,   # Indonesia -> ~0.38x
    "EG": 17100.0,   # Egypt -> ~0.40x
    "TR": 43600.0,   # Turkey -> ~0.69x
    "AR": 29400.0,   # Argentina -> ~0.55x
    "CO": 20300.0,   # Colombia -> ~0.44x
    "TH": 23400.0,   # Thailand -> ~0.48x
    "VN": 15400.0,   # Vietnam -> ~0.37x
    "PH": 12100.0,   # Philippines -> ~0.32x
    "PK": 6900.0,    # Pakistan -> 0.25x (clamped)
    "BD": 8700.0,    # Bangladesh -> ~0.26x
    "MY": 39000.0,   # Malaysia -> ~0.65x
    "SG": 141000.0,  # Singapore -> 1.10x (clamped)
    "NZ": 54100.0,   # New Zealand -> ~0.79x
    "IE": 137000.0,  # Ireland -> 1.10x (clamped)
    "NL": 78500.0,   # Netherlands -> ~0.99x
    "SE": 71200.0,   # Sweden -> ~0.93x
    "CH": 92000.0,   # Switzerland -> 1.09x
    "PL": 49400.0,   # Poland -> ~0.75x
    "AT": 73700.0,   # Austria -> ~0.95x
    "BE": 71100.0,   # Belgium -> ~0.93x
    "IL": 58300.0,   # Israel -> ~0.83x
    "CL": 33400.0,   # Chile -> ~0.59x
    "PE": 17000.0,   # Peru -> ~0.40x
    "MA": 10400.0,   # Morocco -> ~0.29x
    "KE": 6400.0,    # Kenya -> 0.25x (clamped)
    "GH": 7300.0,    # Ghana -> 0.25x (clamped)
    "NO": 89000.0,   # Norway -> 1.07x
    "DK": 76000.0,   # Denmark -> ~0.97x
    "FI": 62000.0,   # Finland -> ~0.86x
    "PT": 47000.0,   # Portugal -> ~0.73x
    "GR": 41000.0,   # Greece -> ~0.67x
    "CZ": 53000.0,   # Czechia -> ~0.78x
    "HU": 45000.0,   # Hungary -> ~0.71x
    "RO": 44000.0,   # Romania -> ~0.70x
}

# ISO 3166-1 alpha-2 / alpha-3 -> ISO 4217 Currency mapping (comprehensive)
ISO_COUNTRY_CURRENCY: Dict[str, str] = {
    "IN": "INR", "IND": "INR",
    "US": "USD", "USA": "USD",
    "GB": "GBP", "GBR": "GBP", "UK": "GBP",
    "BR": "BRL", "BRA": "BRL",
    "NG": "NGN", "NGA": "NGN",
    "CA": "CAD", "CAN": "CAD",
    "AU": "AUD", "AUS": "AUD",
    "JP": "JPY", "JPN": "JPY",
    "AE": "AED", "ARE": "AED",
    "JO": "JOD", "JOR": "JOD",
    "CN": "CNY", "CHN": "CNY",
    "KR": "KRW", "KOR": "KRW",
    "MX": "MXN", "MEX": "MXN",
    "ZA": "ZAR", "ZAF": "ZAR",
    "SG": "SGD", "SGP": "SGD",
    "NZ": "NZD", "NZL": "NZD",
    "CH": "CHF", "CHE": "CHF",
    "SE": "SEK", "SWE": "SEK",
    "NO": "NOK", "NOR": "NOK",
    "DK": "DKK", "DNK": "DKK",
    "PL": "PLN", "POL": "PLN",
    "TH": "THB", "THA": "THB",
    "ID": "IDR", "IDN": "IDR",
    "MY": "MYR", "MYS": "MYR",
    "PH": "PHP", "PHL": "PHP",
    "VN": "VND", "VNM": "VND",
    "EG": "EGP", "EGY": "EGP",
    "TR": "TRY", "TUR": "TRY",
    "SA": "SAR", "SAU": "SAR",
    "AR": "ARS", "ARG": "ARS",
    "CO": "COP", "COL": "COP",
    "CL": "CLP", "CHL": "CLP",
    "PE": "PEN", "PER": "PEN",
    "PK": "PKR", "PAK": "PKR",
    "BD": "BDT", "BGD": "BDT",
    "LK": "LKR", "LKA": "LKR",
    "KE": "KES", "KEN": "KES",
    "GH": "GHS", "GHA": "GHS",
    "MA": "MAD", "MAR": "MAD",
    "IL": "ILS", "ISR": "ILS",
    "CZ": "CZK", "CZE": "CZK",
    "HU": "HUF", "HUN": "HUF",
    "RO": "RON", "ROU": "RON",
    "BG": "BGN", "BGR": "BGN",
    "QA": "QAR", "QAT": "QAR",
    "KW": "KWD", "KWT": "KWD",
    "OM": "OMR", "OMN": "OMR",
    "BH": "BHD", "BHR": "BHD",
    "IS": "ISK", "ISL": "ISK",
    "TW": "TWD", "TWN": "TWD",
    "HK": "HKD", "HKG": "HKD",
    # Eurozone members
    "DE": "EUR", "DEU": "EUR",
    "FR": "EUR", "FRA": "EUR",
    "IT": "EUR", "ITA": "EUR",
    "ES": "EUR", "ESP": "EUR",
    "NL": "EUR", "NLD": "EUR",
    "BE": "EUR", "BEL": "EUR",
    "AT": "EUR", "AUT": "EUR",
    "IE": "EUR", "IRL": "EUR",
    "PT": "EUR", "PRT": "EUR",
    "GR": "EUR", "GRC": "EUR",
    "FI": "EUR", "FIN": "EUR",
    "EE": "EUR", "EST": "EUR",
    "LV": "EUR", "LVA": "EUR",
    "LT": "EUR", "LTU": "EUR",
    "SK": "EUR", "SVK": "EUR",
    "SI": "EUR", "SVN": "EUR",
    "CY": "EUR", "CYP": "EUR",
    "MT": "EUR", "MLT": "EUR",
    "LU": "EUR", "LUX": "EUR",
    "HR": "EUR", "HRV": "EUR",
}

# Curated global capitals and major megacities for tier fallback
WORLD_CAPITALS = {
    "london", "washington", "washington, d.c.", "new delhi", "delhi", "tokyo", "beijing",
    "paris", "berlin", "madrid", "rome", "brasilia", "abuja", "ottawa", "canberra", "cairo",
    "riyadh", "abu dhabi", "jakarta", "bangkok", "seoul", "pretoria", "buenos aires",
    "bogota", "santiago", "lima", "islamabad", "dhaka", "kuala lumpur", "singapore",
    "wellington", "dublin", "amsterdam", "stockholm", "bern", "warsaw", "vienna", "brussels",
    "jerusalem", "rabat", "nairobi", "accra", "oslo", "copenhagen", "helsinki", "lisbon",
    "athens", "prague", "budapest", "bucharest", "doha", "kuwait city", "manama", "muscat",
}

TOP_MEGACITIES = {
    "tokyo", "delhi", "shanghai", "sao paulo", "mexico city", "cairo", "mumbai", "beijing",
    "dhaka", "osaka", "new york", "karachi", "buenos aires", "chongqing", "istanbul",
    "kolkata", "manila", "lagos", "rio de janeiro", "tianjin", "kinshasa", "guangzhou",
    "los angeles", "moscow", "shenzhen", "lahore", "bangalore", "bengaluru", "paris",
    "bogota", "jakarta", "chennai", "lima", "bangkok", "seoul", "nagoya", "hyderabad",
    "london", "tehran", "chicago", "chengdu", "nanjing", "wuhan", "ho chi minh city",
    "luanda", "ahmedabad", "kuala lumpur", "hong kong", "toronto", "sydney", "dubai",
    "singapore", "johannesburg", "san francisco", "vancouver",
}


def haversine_miles(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great circle distance between two points in statute miles."""
    if (lat1 == lat2 and lon1 == lon2) or (not lat1 and not lon1) or (not lat2 and not lon2):
        return 0.0

    radius = 3958.8  # Earth radius in miles
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


def country_to_currency(country_code: str) -> str:
    """Map ISO 3166 country code (2- or 3-letter) to ISO 4217 currency. Fallback USD."""
    code = (country_code or "US").upper().strip()
    return ISO_COUNTRY_CURRENCY.get(code, "USD")


def clamp_country_mult(gdp_ppp: float, us_gdp_ppp: float = US_GDP_PPP_BENCHMARK) -> float:
    """Compute country factor: clamp((gdp_ppp / us_gdp_ppp) ** 0.6, 0.25, 1.10)."""
    if gdp_ppp <= 0 or us_gdp_ppp <= 0:
        return 1.0
    ratio = gdp_ppp / us_gdp_ppp
    raw_mult = ratio ** 0.6
    clamped = max(0.25, min(1.10, raw_mult))
    return round(clamped, 2)


def determine_city_tier(
    population: Optional[int],
    is_capital: bool = False,
    city_name: str = "",
) -> Tuple[str, float]:
    """Determine city tier and tier multiplier from population or capital/top-city status.

    Rules:
    - pop >= 5M -> tier_1 (1.0x)
    - pop 1M-5M -> tier_1 (1.0x) if capital else tier_2 (0.5x)
    - pop 200K-1M -> tier_2 (0.5x)
    - pop < 200K -> tier_3 (0.35x)
    Fallback when population missing:
    - capital or curated top-city list -> tier_1; else tier_2.
    """
    clean_name = (city_name or "").strip().lower()

    if population is not None and population > 0:
        if population >= 5_000_000:
            tier = "tier_1"
        elif population >= 1_000_000:
            tier = "tier_1" if (is_capital or clean_name in WORLD_CAPITALS) else "tier_2"
        elif population >= 200_000:
            tier = "tier_2"
        else:
            tier = "tier_3"
    else:
        # Fallback when population is missing
        if is_capital or clean_name in WORLD_CAPITALS or clean_name in TOP_MEGACITIES:
            tier = "tier_1"
        else:
            tier = "tier_2"

    return tier, TIER_MULTIPLIERS.get(tier, 0.5)


async def get_country_factor(country_code: str) -> Dict[str, Any]:
    """Resolve World Bank GDP PPP country factor with 30-day ClickHouse & memory caching.

    Returns {
        "country_code": "IN",
        "country_mult": 0.29,
        "gdp_ppp": 10120.0,
        "source_note": "World Bank open data (CC-BY 4.0)",
        "is_fallback": False,
        "warning": ""
    }
    """
    code = (country_code or "US").upper().strip()
    now = time.time()

    # 1. Check in-memory TTL cache
    cached_entry = _WB_CACHE.get(code)
    if cached_entry and (now - cached_entry[0]) < _WB_CACHE_TTL:
        return cached_entry[1]

    # 2. Check ClickHouse geo_cost_index table cache
    try:
        from services import clickhouse_client
        if clickhouse_client.is_configured():
            ch_data = await clickhouse_client.get_cached_country_factor(code)
            if ch_data:
                _WB_CACHE[code] = (now, ch_data)
                return ch_data
    except Exception as exc:
        logger.debug("ClickHouse country factor cache read skipped: %s", exc)

    # 3. Live fetch from World Bank API: NY.GDP.PCAP.PP.CD
    url = f"https://api.worldbank.org/v2/country/{code}/indicator/NY.GDP.PCAP.PP.CD?format=json&mrnev=1"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            resp = await client.get(url)
            if resp.status_code == 200:
                payload = resp.json()
                if (
                    isinstance(payload, list)
                    and len(payload) >= 2
                    and isinstance(payload[1], list)
                    and len(payload[1]) > 0
                ):
                    item = payload[1][0]
                    val = item.get("value")
                    if val is not None and isinstance(val, (int, float)) and val > 0:
                        gdp_ppp = float(val)
                        country_mult = clamp_country_mult(gdp_ppp)
                        result = {
                            "country_code": code,
                            "country_mult": country_mult,
                            "gdp_ppp": round(gdp_ppp, 2),
                            "source_note": "World Bank open data (CC-BY 4.0)",
                            "is_fallback": False,
                            "warning": "",
                        }
                        _WB_CACHE[code] = (now, result)

                        # Write to ClickHouse async cache
                        try:
                            from services import clickhouse_client
                            if clickhouse_client.is_configured():
                                await clickhouse_client.cache_country_factor(
                                    code, country_mult, gdp_ppp, "World Bank open data (CC-BY 4.0)"
                                )
                        except Exception as write_exc:
                            logger.debug("ClickHouse cache write failed: %s", write_exc)

                        return result
    except Exception as exc:
        logger.warning("World Bank API fetch failed for %s (%s), falling back to static table", code, exc)

    # 4. Embedded static table fallback
    if code in FALLBACK_COUNTRY_GDP_PPP:
        gdp_ppp = FALLBACK_COUNTRY_GDP_PPP[code]
        country_mult = clamp_country_mult(gdp_ppp)
        result = {
            "country_code": code,
            "country_mult": country_mult,
            "gdp_ppp": gdp_ppp,
            "source_note": "World Bank benchmark prior (CC-BY 4.0 fallback)",
            "is_fallback": False,
            "warning": "",
        }
        _WB_CACHE[code] = (now, result)
        return result

    # 5. Unknown Country fallback -> 1.0 with warning badge
    result = {
        "country_code": code,
        "country_mult": 1.0,
        "gdp_ppp": US_GDP_PPP_BENCHMARK,
        "source_note": "Unknown country fallback (1.0x baseline)",
        "is_fallback": True,
        "warning": f"Unknown country code '{code}' — using default 1.0x factor",
    }
    _WB_CACHE[code] = (now, result)
    return result


def _parse_population_str(pop_val: Any) -> Optional[int]:
    """Safely parse population from OSM extratags string."""
    if pop_val is None:
        return None
    if isinstance(pop_val, (int, float)):
        return int(pop_val)
    s = str(pop_val).replace(",", "").replace(" ", "").strip()
    match = re.search(r"(\d+)", s)
    if match:
        try:
            return int(match.group(1))
        except ValueError:
            return None
    return None


async def resolve_geo_economics(
    query: str,
    fallback_lat: float = 34.05,
    fallback_lon: float = -118.25,
) -> Dict[str, Any]:
    """Resolve full geographic and economic factors from OpenStreetMap + World Bank.

    Resolves once at location creation:
    - Coordinates: (lat, lon)
    - Country code & name
    - City / locality name
    - City population & capital status
    - City tier: tier_1 / tier_2 / tier_3
    - Tier multiplier: 1.0 / 0.5 / 0.35
    - Country multiplier: from World Bank GDP PPP clamp [0.25, 1.10]
    - Geo multiplier: country_mult * tier_mult
    - Currency code: ISO 4217 mapping
    - Attribution: World Bank open data (CC-BY 4.0) + OSM Nominatim
    """
    global _LAST_NOMINATIM_CALL
    q = (query or "").strip()

    if not q:
        country_factor = await get_country_factor("US")
        tier, tier_mult = determine_city_tier(None, is_capital=False, city_name="")
        geo_mult = round(country_factor["country_mult"] * tier_mult, 4)
        return {
            "latitude": fallback_lat,
            "longitude": fallback_lon,
            "country_code": "US",
            "country_name": "United States",
            "city_name": "Los Angeles",
            "population": 3800000,
            "is_capital": False,
            "city_tier": "tier_1",
            "tier_mult": 1.0,
            "country_mult": country_factor["country_mult"],
            "geo_mult": geo_mult,
            "currency_code": "USD",
            "source_note": "World Bank open data (CC-BY 4.0) + OSM Nominatim",
            "is_fallback": False,
            "warning": "",
        }

    if q in _GEOCODE_CACHE:
        return _GEOCODE_CACHE[q]

    lat = fallback_lat
    lon = fallback_lon
    country_code = "US"
    country_name = "United States"
    city_name = q.split(",")[0].strip()
    pop: Optional[int] = None
    is_capital = False

    async with _NOMINATIM_LOCK:
        now = time.time()
        elapsed = now - _LAST_NOMINATIM_CALL
        if elapsed < 1.0:
            await asyncio.sleep(1.0 - elapsed)
        _LAST_NOMINATIM_CALL = time.time()

        url = "https://nominatim.openstreetmap.org/search"
        headers = {"User-Agent": "ContinuityCouncil-Hackathon/1.0"}
        params = {
            "q": q,
            "format": "json",
            "addressdetails": 1,
            "extratags": 1,
            "limit": 1,
        }

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                resp = await client.get(url, params=params, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    if data and isinstance(data, list) and len(data) > 0:
                        first = data[0]
                        lat = float(first.get("lat", fallback_lat))
                        lon = float(first.get("lon", fallback_lon))
                        addr = first.get("address", {})
                        extratags = first.get("extratags", {})

                        country_code = (addr.get("country_code") or "US").upper()
                        country_name = addr.get("country") or country_code
                        city_name = (
                            addr.get("city")
                            or addr.get("town")
                            or addr.get("municipality")
                            or addr.get("village")
                            or addr.get("county")
                            or q.split(",")[0].strip()
                        )

                        # Extract population
                        pop_str = (
                            extratags.get("population")
                            or extratags.get("population:2021")
                            or extratags.get("population:2020")
                            or extratags.get("population:2022")
                            or extratags.get("population:2023")
                        )
                        pop = _parse_population_str(pop_str)

                        # Extract capital status
                        cap_tag = str(extratags.get("capital", "")).lower()
                        is_capital = (
                            cap_tag in ("yes", "1", "2", "3", "4", "primary")
                            or city_name.lower() in WORLD_CAPITALS
                        )
        except Exception as exc:
            logger.warning("Nominatim geo economics resolve failed for '%s' (%s), using fallbacks", q, exc)

    # Resolve country factor from World Bank
    country_factor = await get_country_factor(country_code)
    country_mult = country_factor["country_mult"]

    # Resolve city tier
    city_tier, tier_mult = determine_city_tier(pop, is_capital=is_capital, city_name=city_name)

    # Compute compound geo multiplier
    geo_mult = round(country_mult * tier_mult, 4)

    # Resolve currency
    curr = country_to_currency(country_code)

    res = {
        "latitude": lat,
        "longitude": lon,
        "country_code": country_code,
        "country_name": country_name,
        "city_name": city_name,
        "population": pop,
        "is_capital": is_capital,
        "city_tier": city_tier,
        "tier_mult": tier_mult,
        "country_mult": country_mult,
        "geo_mult": geo_mult,
        "currency_code": curr,
        "source_note": "World Bank open data (CC-BY 4.0) + OSM Nominatim",
        "is_fallback": country_factor.get("is_fallback", False),
        "warning": country_factor.get("warning", ""),
    }

    _GEOCODE_CACHE[q] = res
    return res


async def geocode_location(
    query: str,
    fallback_lat: float = 34.05,
    fallback_lon: float = -118.25,
) -> Tuple[float, float]:
    """Compatibility wrapper returning (latitude, longitude)."""
    info = await resolve_geo_economics(query, fallback_lat, fallback_lon)
    return info["latitude"], info["longitude"]
