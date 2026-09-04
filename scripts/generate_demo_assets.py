import urllib.request
import json
import time
import base64
from pathlib import Path

backend_url = "http://127.0.0.1:8000"
demo_dir = Path(__file__).resolve().parent.parent / "docs" / "demo"
demo_dir.mkdir(parents=True, exist_ok=True)

# We want to test a location that has image bytes generated or cached
# loc_002 / stage_a / loft_interior / harbor_exterior
location_id = "loc_002"

print("=" * 70)
print(f"MOODBOARD DEMO: Fetching moodboard for '{location_id}'")
print("=" * 70)

# 1. First Call (Generation or Disk/Mem Fetch)
t0 = time.perf_counter()
req1 = urllib.request.Request(f"{backend_url}/api/locations/{location_id}/moodboard")
with urllib.request.urlopen(req1, timeout=15.0) as resp1:
    elapsed1 = time.perf_counter() - t0
    data1 = json.loads(resp1.read().decode("utf-8"))

print(f"[1] First Call: status={resp1.status} in {elapsed1:.4f}s ({elapsed1*1000:.2f}ms)")
print(f"    location_name: {data1.get('location_name')}")
print(f"    cached: {data1.get('cached')}")
print(f"    prompt length: {len(data1.get('prompt', ''))}")
print(f"    image_base64 length: {len(data1.get('image_base64', ''))}")

# 2. Second Call (Memory Cache Hit)
t1 = time.perf_counter()
req2 = urllib.request.Request(f"{backend_url}/api/locations/{location_id}/moodboard")
with urllib.request.urlopen(req2, timeout=15.0) as resp2:
    elapsed2 = time.perf_counter() - t1
    data2 = json.loads(resp2.read().decode("utf-8"))

print(f"[2] Second Call (Cache Hit): status={resp2.status} in {elapsed2:.4f}s ({elapsed2*1000:.3f}ms)")
print(f"    cached: {data2.get('cached')}")

# 3. Save Assets
# a. Save image bytes
b64_str = data1.get("image_base64", "")
if b64_str:
    raw_img_bytes = base64.b64decode(b64_str)
    sample_path = demo_dir / "moodboard_sample.png"
    sample_path.write_bytes(raw_img_bytes)
    print(f"[3a] Saved {len(raw_img_bytes)} bytes image -> {sample_path}")

# b. Save prompt string
prompt_str = data1.get("prompt", "")
prompt_path = demo_dir / "moodboard_prompt.txt"
prompt_path.write_text(prompt_str, encoding="utf-8")
print(f"[3b] Saved prompt ({len(prompt_str)} chars) -> {prompt_path}")

# c. Save API JSON response
api_path = demo_dir / "moodboard_api.txt"
# Format JSON nicely with image_base64 preview
data_summary = dict(data1)
if len(data_summary.get("image_base64", "")) > 64:
    data_summary["image_base64"] = data_summary["image_base64"][:32] + "..." + data_summary["image_base64"][-16:] + f" ({len(data1['image_base64'])} base64 chars)"

api_path.write_text(json.dumps(data_summary, indent=2), encoding="utf-8")
print(f"[3c] Saved API response summary -> {api_path}")

# Print summary
print("\n" + "=" * 70)
print("TIMINGS SUMMARY:")
print(f"  First call:  {elapsed1*1000:.2f} ms")
print(f"  Second call: {elapsed2*1000:.3f} ms")
print("=" * 70)
