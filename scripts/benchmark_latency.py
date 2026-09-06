import sys
import os
import time
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from fastapi.testclient import TestClient
from server import app
from services.clickhouse_client import invalidate_bundle_cache
from agents import orchestrator

def run_benchmarks():
    print("=" * 70)
    print(" CONTINUITY COUNCIL LATENCY & WARMTH BENCHMARKS (3 RUNS EACH)")
    print("=" * 70)

    with TestClient(app) as client:
        # 1. Health Endpoint
        print("\n--- [1] /api/health (Cache-Control & Warmth) ---")
        for i in range(1, 4):
            t0 = time.perf_counter()
            res = client.get("/api/health")
            ms = (time.perf_counter() - t0) * 1000
            assert res.status_code == 200, f"Expected 200, got {res.status_code}"
            cc = res.headers.get("Cache-Control", "")
            data = res.json()
            mcp_warm = data.get("mcp_warm", False)
            print(f"  Run {i}: {ms:6.2f} ms | Cache-Control: {cc:15} | mcp_warm: {mcp_warm}")

        # 2. Production Bundle (/api/productions/prod_001)
        print("\n--- [2] /api/productions/prod_001 (Bundle Cache) ---")
        invalidate_bundle_cache("prod_001")  # Ensure cold start for run 1
        for i in range(1, 4):
            t0 = time.perf_counter()
            res = client.get("/api/productions/prod_001")
            ms = (time.perf_counter() - t0) * 1000
            assert res.status_code == 200
            cc = res.headers.get("Cache-Control", "")
            body = res.json()
            title = body.get("production", {}).get("title", "")
            print(f"  Run {i}: {ms:6.2f} ms | Cache-Control: {cc:25} | Title: {title}")

        # 3. Productions List (/api/productions)
        print("\n--- [3] /api/productions (List) ---")
        for i in range(1, 4):
            t0 = time.perf_counter()
            res = client.get("/api/productions")
            ms = (time.perf_counter() - t0) * 1000
            assert res.status_code == 200
            cc = res.headers.get("Cache-Control", "")
            count = len(res.json().get("productions", []))
            print(f"  Run {i}: {ms:6.2f} ms | Cache-Control: {cc:25} | items: {count}")

        # 4. Investigation Deliberation (POST /api/disruptions + GET /api/cases/{id})
        print("\n--- [4] Investigation Deliberation (Cold vs Warm Cache) ---")
        # Clear cache for first run to measure cold
        orchestrator._INVESTIGATION_CACHE.clear()
        payload = {
            "production_id": "prod_001",
            "disruption_type": "weather_delay",
            "affected_day": 12,
            "severity": "high",
            "notes": "Severe torrential downpour flooding Basecamp Stage B"
        }

        for i in range(1, 4):
            t0 = time.perf_counter()
            res = client.post("/api/disruptions", json=payload)
            assert res.status_code == 201, f"Expected 201, got {res.status_code}: {res.text}"
            case_id = res.json()["case_id"]
            status = res.json()["status"]

            # Poll until options_ready
            elapsed_ms = 0
            while status != "options_ready":
                time.sleep(0.05)
                c_res = client.get(f"/api/cases/{case_id}")
                assert c_res.status_code == 200
                case_data = c_res.json()
                status = case_data.get("status")

            total_ms = (time.perf_counter() - t0) * 1000
            c_res = client.get(f"/api/cases/{case_id}")
            case_data = c_res.json()
            meta = case_data.get("meta", {})
            cached = meta.get("cached", False)
            timings = meta.get("timings", {})
            num_options = len(case_data.get("options", []))

            print(f"  Run {i}: {total_ms:8.2f} ms | cached: {str(cached):5} | options: {num_options}")
            if timings:
                print(f"         Stage Breakdown: total={timings.get('total_ms', 0):.1f}ms, "
                      f"mcp_connect={timings.get('mcp_connect_ms', 0):.1f}ms, "
                      f"synthesis={timings.get('synthesis_ms', 0):.1f}ms, "
                      f"per_agent={timings.get('per_agent', {})}")

    print("\n" + "=" * 70)
    print(" ALL LATENCY BENCHMARKS COMPLETED SUCCESSFULLY")
    print("=" * 70)

if __name__ == "__main__":
    run_benchmarks()
