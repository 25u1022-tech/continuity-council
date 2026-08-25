import io
import json
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"

results = {}
timings = {}

def get(path):
    url = f"{BASE_URL}{path}"
    t0 = time.perf_counter()
    req = urllib.request.Request(url)
    try:
        with urllib.request.urlopen(req) as resp:
            elapsed = time.perf_counter() - t0
            body = resp.read()
            data = None
            if "application/json" in resp.headers.get("Content-Type", ""):
                data = json.loads(body.decode("utf-8"))
            return resp.status, data, elapsed, body
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        return e.code, e.read().decode("utf-8"), elapsed, None

def post_json(path, payload):
    url = f"{BASE_URL}{path}"
    data_bytes = json.dumps(payload).encode("utf-8")
    t0 = time.perf_counter()
    req = urllib.request.Request(url, data=data_bytes, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req) as resp:
            elapsed = time.perf_counter() - t0
            body = resp.read()
            data = None
            if "application/json" in resp.headers.get("Content-Type", ""):
                data = json.loads(body.decode("utf-8"))
            return resp.status, data, elapsed, body
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        return e.code, e.read().decode("utf-8"), elapsed, None

def post_multipart_csv(path, csv_content, filename="import.csv"):
    url = f"{BASE_URL}{path}"
    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: text/csv\r\n\r\n"
        f"{csv_content}\r\n"
        f"--{boundary}--\r\n"
    ).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    t0 = time.perf_counter()
    try:
        with urllib.request.urlopen(req) as resp:
            elapsed = time.perf_counter() - t0
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        return e.code, e.read().decode("utf-8"), elapsed

print("======================================================================")
print("CONTINUITY COUNCIL -- API ENDPOINT SMOKE TEST & BENCHMARKING")
print("======================================================================")

# 1. GET /api/health
status, data, elapsed, _ = get("/api/health")
print(f"[1] GET /api/health: status={status} in {elapsed:.3f}s | ClickHouse connected={data.get('clickhouse', {}).get('connected') if data else False}")
assert status == 200 and data.get("clickhouse", {}).get("connected") == True
timings["cold_or_health_ms"] = elapsed * 1000

# 2. POST /api/disruptions
payload = {
    "production_id": "prod_001",
    "disruption_type": "lead_actor_unavailable",
    "affected_day": 2,
    "affected_cast_id": "lead_001",
    "severity": "medium",
    "notes": "Lead actor unavailable for interrogation scene",
}
status, data, elapsed, _ = post_json("/api/disruptions", payload)
case_id = data.get("case_id") if data else None
print(f"[2] POST /api/disruptions: status={status} in {elapsed:.3f}s | case_id={case_id}")
assert status in (200, 201) and case_id is not None

# 3. GET /api/cases/{case_id} -> warm investigation SLA
warm_timings = []
for run_i in range(3):
    status, data, elapsed, _ = get(f"/api/cases/{case_id}")
    warm_timings.append(elapsed)
    print(f"    Run {run_i+1}: status={status} case_status={data.get('status') if data else None} in {elapsed:.3f}s options={len(data.get('options', [])) if data else 0}")
avg_warm = sum(warm_timings) / len(warm_timings)
print(f"[3] GET /api/cases/{case_id}: Avg warm latency={avg_warm:.3f}s (SLA <= 2.1s: {avg_warm <= 2.1})")
assert status == 200 and avg_warm <= 2.1
timings["warm_investigation_avg_s"] = avg_warm

# 4. POST /api/chat
status, data, elapsed, _ = post_json("/api/chat", {"message": "Hi", "production_id": "prod_001"})
print(f"[4] POST /api/chat: status={status} in {elapsed:.3f}s | answer={data.get('answer', '')[:60]}...")
assert status == 200 and len(data.get("answer", "")) > 0
timings["chatbot_response_s"] = elapsed

# 5. POST /api/disruptions/parse-nl
status, data, elapsed, _ = post_json("/api/disruptions/parse-nl", {
    "description": "Sarah broke her wrist, cannot shoot on Tuesday",
    "production_id": "prod_001",
})
print(f"[5] POST /api/disruptions/parse-nl: status={status} in {elapsed:.3f}s | type={data.get('disruption_type')} day={data.get('affected_day')}")
assert status == 200
timings["nl_parser_s"] = elapsed

# 6. GET /api/locations/{id}/moodboard
# Test cache miss/fallback
t0 = time.perf_counter()
status_miss, data_miss, elapsed_miss, _ = get("/api/locations/loc_999/moodboard")
elapsed_miss = time.perf_counter() - t0
print(f"[6a] GET /api/locations/loc_999/moodboard (miss/fallback): status={status_miss} in {elapsed_miss:.3f}s")
assert status_miss in (200, 202)

# Test cache hit (loc_002 was seeded earlier)
status_hit, data_hit, elapsed_hit, _ = get("/api/locations/loc_002/moodboard")
print(f"[6b] GET /api/locations/loc_002/moodboard (hit): status={status_hit} in {elapsed_hit:.3f}s cached={data_hit.get('cached') if isinstance(data_hit, dict) else False}")
assert status_hit in (200, 202)
timings["moodboard_miss_s"] = elapsed_miss
timings["moodboard_hit_s"] = elapsed_hit

# 7. POST /api/chat/tts/generate
status, data, elapsed, _ = post_json("/api/chat/tts/generate", {"text": "Test speech playback"})
print(f"[7] POST /api/chat/tts/generate: status={status} in {elapsed:.3f}s | hash={data.get('hash') if data else None}")
assert status == 200 and data.get("hash") is not None
timings["tts_generate_s"] = elapsed

# 8. POST /api/productions/{id}/import-history (CSV import)
sample_csv = (
    "case_id,disruption_type,resolution_strategy,cost_overrun_usd,schedule_delay_hours,success_score,occurred_at\n"
    "test_c01,lead_actor_unavailable,shoot_cover_scenes,12500,2.5,0.85,2026-01-01 10:00:00\n"
    "test_c02,weather_delay,swap_locations,18000,4.0,0.72,2026-01-02 12:00:00\n"
)
status, data, elapsed = post_multipart_csv("/api/productions/prod_001/import-history", sample_csv)
print(f"[8] POST /api/productions/prod_001/import-history: status={status} in {elapsed:.3f}s | accepted={data.get('accepted_count') if isinstance(data, dict) else None} rejected={data.get('rejected_count') if isinstance(data, dict) else None}")
assert status == 200
timings["csv_import_s"] = elapsed

# 9. GET /api/productions/{id}/risk-radar (or /api/productions/{id}/studio-cohort)
status, data, elapsed, _ = get("/api/productions/prod_001/studio-cohort")
print(f"[9] GET /api/productions/prod_001/studio-cohort: status={status} in {elapsed:.3f}s | studio={data.get('studio_id') if data else None} count={data.get('cohort_count') if data else None}")
assert status == 200

# 10. GET /api/cases/{id}/report.html
status, data, elapsed, body = get(f"/api/cases/{case_id}/report.html")
html_str = body.decode("utf-8") if body else ""
print(f"[10] GET /api/cases/{case_id}/report.html: status={status} in {elapsed:.3f}s | length={len(html_str)} bytes has_html={'<html' in html_str.lower()}")
assert status == 200 and "<html" in html_str.lower()

print("\n======================================================================")
print("ALL 10 API ENDPOINTS PASSED SMOKE TEST!")
print("======================================================================")
