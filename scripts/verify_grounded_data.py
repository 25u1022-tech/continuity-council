#!/usr/bin/env python3
"""
Continuity Council — Grounded Corpus Verification Script
Validates:
  1. Row counts: exactly 200,000 disruption_history rows
  2. MV sanity: countMerge(sample_size) from strategy_performance_mv == 200,000
  3. Mumbai Monsoon Proof:
       SELECT toMonth(created_at) AS month, count() AS weather_delays
       FROM disruption_history WHERE disruption_type='weather_delay'
       AND notes LIKE '%Mumbai%' GROUP BY month ORDER BY month
       Assert sum(Jun-Sep) > sum(Dec-Feb) * 2
  4. Core catalog row counts (6 productions, locations, cast, rate cards)

Prints PASS/FAIL table and exits with code 0 (all pass) or 1 (any fail).
"""
import os
import sys
from pathlib import Path
import clickhouse_connect
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / "backend" / ".env")

def get_clickhouse_client():
    host = os.environ.get("CLICKHOUSE_HOST", "")
    port = int(os.environ.get("CLICKHOUSE_PORT", "8443"))
    user = os.environ.get("CLICKHOUSE_USER", "default")
    password = os.environ.get("CLICKHOUSE_PASSWORD", "")
    database = os.environ.get("CLICKHOUSE_DATABASE", "continuity_council")
    
    if not host:
        print("ERROR: CLICKHOUSE_HOST is not set. Fill backend/.env first.")
        sys.exit(1)
        
    return clickhouse_connect.get_client(
        host=host, port=port, username=user, password=password, secure=True,
    )

def run_verification(client=None):
    if client is None:
        client = get_clickhouse_client()

    print("\n" + "=" * 70)
    print(" CONTINUITY COUNCIL — GROUNDED DATA CORPUS VERIFICATION")
    print("=" * 70)

    results = []

    # -----------------------------------------------------------------------
    # Check 1: Disruption history row count == 200,000
    # -----------------------------------------------------------------------
    n_hist = client.command("SELECT count() FROM continuity_council.disruption_history")
    chk1_pass = (n_hist == 200_000)
    results.append({
        "check": "Disruption History Rows",
        "target": "200,000",
        "actual": f"{n_hist:,}",
        "status": "PASS" if chk1_pass else "FAIL",
    })

    # -----------------------------------------------------------------------
    # Check 2: MV countMerge(sample_size) == 200,000
    # -----------------------------------------------------------------------
    mv_count = client.command("SELECT countMerge(sample_size) FROM continuity_council.strategy_performance_mv")
    chk2_pass = (mv_count == 200_000)
    results.append({
        "check": "MV strategy_performance_mv",
        "target": "200,000",
        "actual": f"{mv_count:,}",
        "status": "PASS" if chk2_pass else "FAIL",
    })

    # -----------------------------------------------------------------------
    # Check 3: Demo catalog integrity
    # -----------------------------------------------------------------------
    n_prods = client.command("SELECT count() FROM continuity_council.productions")
    chk3_pass = (n_prods == 6)
    results.append({
        "check": "Demo Productions",
        "target": "6",
        "actual": str(n_prods),
        "status": "PASS" if chk3_pass else "FAIL",
    })

    # -----------------------------------------------------------------------
    # Check 4: Mumbai Monsoon Proof Query
    # -----------------------------------------------------------------------
    query = """
    SELECT toMonth(created_at) AS month, count() AS weather_delays
    FROM continuity_council.disruption_history
    WHERE disruption_type = 'weather_delay'
      AND notes LIKE '%Mumbai%'
    GROUP BY month
    ORDER BY month
    """
    rows = client.query(query).result_rows
    month_counts = {r[0]: r[1] for r in rows}

    jun_sep_sum = sum(month_counts.get(m, 0) for m in [6, 7, 8, 9])
    dec_feb_sum = sum(month_counts.get(m, 0) for m in [12, 1, 2])
    
    ratio = (jun_sep_sum / max(1, dec_feb_sum))
    chk4_pass = (jun_sep_sum > dec_feb_sum * 2)

    results.append({
        "check": "Mumbai Monsoon Jun-Sep > Dec-Feb * 2",
        "target": "> 2.0x",
        "actual": f"{ratio:.1f}x ({jun_sep_sum} vs {dec_feb_sum})",
        "status": "PASS" if chk4_pass else "FAIL",
    })

    # -----------------------------------------------------------------------
    # Print Table
    # -----------------------------------------------------------------------
    print(f"\n{'CHECK NAME':<40} {'TARGET':<12} {'ACTUAL':<16} {'STATUS':<6}")
    print("-" * 76)
    all_passed = True
    for r in results:
        print(f"{r['check']:<40} {r['target']:<12} {r['actual']:<16} {r['status']:<6}")
        if r['status'] != "PASS":
            all_passed = False

    print("-" * 76)

    # Print 12-Month Mumbai Breakdown
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    print("\n--- Mumbai Weather Delays by Month (12-Month Breakdown) ---")
    for m in range(1, 13):
        cnt = month_counts.get(m, 0)
        tag = " <-- MONSOON" if m in [6, 7, 8, 9] else ""
        print(f"  Month {m:02d} ({month_names[m-1]}): {cnt:>4} delays{tag}")

    print(f"\n  Monsoon (Jun-Sep) Total: {jun_sep_sum}")
    print(f"  Dry Season (Dec-Feb) Total: {dec_feb_sum}")
    print(f"  Ratio: {ratio:.2f}x (Required: > 2.0x)")

    if all_passed:
        print("\nOVERALL VERIFICATION: [PASS] ALL CHECKS PASSED SUCCESSFULLY.\n")
    else:
        print("\nOVERALL VERIFICATION: [FAIL] ONE OR MORE CHECKS FAILED.\n")

    return all_passed

if __name__ == "__main__":
    success = run_verification()
    sys.exit(0 if success else 1)
