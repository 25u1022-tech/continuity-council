import urllib.request
import json
import time
import sys

def get(path):
    t0 = time.perf_counter()
    req = urllib.request.Request("http://127.0.0.1:8000" + path)
    try:
        with urllib.request.urlopen(req, timeout=12.0) as resp:
            elapsed = time.perf_counter() - t0
            data = json.loads(resp.read().decode("utf-8"))
            return resp.status, data, elapsed
    except urllib.error.HTTPError as e:
        elapsed = time.perf_counter() - t0
        try:
            data = json.loads(e.read().decode("utf-8"))
        except Exception:
            data = {}
        return e.code, data, elapsed
    except Exception as exc:
        elapsed = time.perf_counter() - t0
        return 500, {"error": str(exc)}, elapsed

print("=" * 70)
print("VERIFYING LIVE MOODBOARD ENDPOINTS")
print("=" * 70)

# 1. Test live GET /api/locations/loc_002/moodboard (hit)
status1, data1, elapsed1 = get("/api/locations/loc_002/moodboard")
print(f"[1] GET /api/locations/loc_002/moodboard: status={status1} elapsed={elapsed1*1000:.2f}ms cached={data1.get('cached')}")
print(f"    location_name: {data1.get('location_name')}")
print(f"    image_base64 len: {len(data1.get('image_base64', ''))}")
assert status1 == 200, f"Expected 200, got {status1}"
assert len(data1.get("image_base64", "")) > 0

# 2. Second call -> cache hit timing (<1ms)
status2, data2, elapsed2 = get("/api/locations/loc_002/moodboard")
print(f"[2] GET /api/locations/loc_002/moodboard (2nd call): status={status2} elapsed={elapsed2*1000:.3f}ms cached={data2.get('cached')}")
assert status2 == 200
assert data2.get("cached") is True

# 3. Test fallback / 202 path on unseeded location
status3, data3, elapsed3 = get("/api/locations/loc_unavailable_999/moodboard")
print(f"[3] GET /api/locations/loc_unavailable_999/moodboard: status={status3} in {elapsed3:.3f}s status_field={data3.get('status')} detail='{data3.get('detail')}'")
assert status3 == 202, f"Expected 202, got {status3}"
assert data3.get("status") == "unavailable"
assert "unavailable" in data3.get("detail", "").lower()

# 4. Smoke test all endpoints
print("\n" + "=" * 70)
print("RUNNING SMOKE TEST ON ALL ENDPOINTS")
print("=" * 70)
