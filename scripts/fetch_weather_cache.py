#!/usr/bin/env python3
"""
Continuity Council — Fetch Weather Cache from Open-Meteo Historical Archive
Downloads daily weather data (rain_sum, wind_speed_10m_max, temperature_2m_max)
from 2019-01-01 to 2024-12-31 for all 60 filming hubs in real_locations.json.
Caches results as JSON in scripts/data/weather_cache/{city_slug}.json.
Deterministic and reproducible — committed to git so seeder runs offline.
"""
import json
import re
import sys
import time
import unicodedata
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "scripts" / "data"
LOCATIONS_FILE = DATA_DIR / "real_locations.json"
CACHE_DIR = DATA_DIR / "weather_cache"

START_DATE = "2019-01-01"
END_DATE = "2024-12-31"
EXPECTED_DAYS = 2192  # 6 years including leap years 2020 and 2024

def slugify(name: str) -> str:
    normalized = unicodedata.normalize('NFKD', name).encode('ascii', 'ignore').decode('ascii').lower()
    return re.sub(r'[^a-z0-9]+', '_', normalized).strip('_')

def fetch_weather_for_location(loc: dict, max_retries: int = 5) -> dict:
    city = loc["city"]
    lat = loc["lat"]
    lon = loc["lon"]
    
    url = (
        f"https://archive-api.open-meteo.com/v1/archive"
        f"?latitude={lat}&longitude={lon}"
        f"&start_date={START_DATE}&end_date={END_DATE}"
        f"&daily=rain_sum,wind_speed_10m_max,temperature_2m_max"
        f"&timezone=auto"
    )
    headers = {"User-Agent": "ContinuityCouncil-FilmingArchive/1.0"}
    
    for attempt in range(1, max_retries + 1):
        try:
            resp = requests.get(url, headers=headers, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                daily = data.get("daily", {})
                times = daily.get("time", [])
                if len(times) >= EXPECTED_DAYS:
                    return data
                else:
                    print(f"  [WARN] Incomplete days for {city}: {len(times)} < {EXPECTED_DAYS}. Retrying...")
            elif resp.status_code in (429, 500, 502, 503, 504):
                print(f"  [WAIT] HTTP {resp.status_code} on attempt {attempt}/{max_retries} for {city}. Retrying in {attempt * 2}s...")
                time.sleep(attempt * 2)
            else:
                print(f"  [ERROR] HTTP {resp.status_code} for {city}: {resp.text[:120]}")
                time.sleep(2)
        except Exception as e:
            print(f"  [ERROR] Attempt {attempt}/{max_retries} failed for {city}: {e}")
            time.sleep(attempt * 2)
            
    raise RuntimeError(f"Failed to fetch weather for {city} after {max_retries} attempts.")

def main():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    if not LOCATIONS_FILE.exists():
        print(f"Error: {LOCATIONS_FILE} does not exist!")
        sys.exit(1)
        
    with open(LOCATIONS_FILE, "r", encoding="utf-8") as f:
        locations = json.load(f)
        
    print(f"Loaded {len(locations)} locations from {LOCATIONS_FILE.name}")
    print(f"Target date range: {START_DATE} to {END_DATE} ({EXPECTED_DAYS} days)")
    print(f"Cache directory: {CACHE_DIR}")
    
    total = len(locations)
    fetched = 0
    skipped = 0
    
    for idx, loc in enumerate(locations, start=1):
        city = loc["city"]
        slug = slugify(city)
        cache_file = CACHE_DIR / f"{slug}.json"
        
        # Check if already cached and valid
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as cf:
                    existing = json.load(cf)
                    if len(existing.get("daily", {}).get("time", [])) >= EXPECTED_DAYS:
                        skipped += 1
                        print(f"[{idx:02d}/{total:02d}] {city} ({slug}) -> already cached ({cache_file.stat().st_size // 1024} KB)")
                        continue
            except Exception:
                pass
                
        print(f"[{idx:02d}/{total:02d}] Fetching {city} (lat={loc['lat']}, lon={loc['lon']})...")
        t0 = time.time()
        data = fetch_weather_for_location(loc)
        elapsed = time.time() - t0
        
        with open(cache_file, "w", encoding="utf-8") as cf:
            json.dump(data, cf, separators=(',', ':'))
            
        size_kb = cache_file.stat().st_size / 1024
        fetched += 1
        print(f"  Saved {slug}.json ({size_kb:.1f} KB in {elapsed:.1f}s)")
        
        # Polite delay to respect Open-Meteo fair use rate limit
        time.sleep(1.0)
        
    print(f"\nWeather cache fetch complete: {fetched} fetched, {skipped} already cached, {total} total.")
    
    # Verify all 60 files exist
    all_slugs = [slugify(l["city"]) for l in locations]
    missing = [s for s in all_slugs if not (CACHE_DIR / f"{s}.json").exists()]
    if missing:
        print(f"ERROR: Missing cache files for: {missing}")
        sys.exit(1)
    else:
        total_bytes = sum(f.stat().st_size for f in CACHE_DIR.glob("*.json"))
        print(f"All {len(all_slugs)} weather cache files verified! Total size: {total_bytes / (1024 * 1024):.2f} MB")

if __name__ == "__main__":
    main()
