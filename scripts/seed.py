#!/usr/bin/env python3
"""
Continuity Council — Seeder Wrapper
Executes the main grounded seeder (clickhouse/seed.py).
Supports running via:
  python scripts/seed.py
  python clickhouse/seed.py
"""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SEED_SCRIPT = ROOT / "clickhouse" / "seed.py"

if not SEED_SCRIPT.exists():
    print(f"Error: Seed script not found at {SEED_SCRIPT}")
    sys.exit(1)

if __name__ == "__main__":
    runpy.run_path(str(SEED_SCRIPT), run_name="__main__")
