import urllib.request
import json
import time

BASE = "http://127.0.0.1:8000/api"

TINY_PDF_BYTES = (
    b"%PDF-1.4\n"
    b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
    b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
    b"3 0 obj<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<<>>>>endobj\n"
    b"xref\n0 4\n0000000000 65535 f\n0000000010 00000 n\n0000000053 00000 n\n0000000102 00000 n\n"
    b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n180\n%%EOF\n"
    b"SCENE 1 - EXT. HARBOR PIER 7 - DAY\n"
    b"SCENE 2 - INT. DOWNTOWN LOFT - NIGHT\n"
    b"SCENE 3 - INT. STAGE A - DAY\n"
)

boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
body = (
    f"--{boundary}\r\n"
    f'Content-Disposition: form-data; name="file"; filename="iron_horizon_schedule.pdf"\r\n'
    f"Content-Type: application/pdf\r\n\r\n"
).encode("utf-8") + TINY_PDF_BYTES + f"\r\n--{boundary}--\r\n".encode("utf-8")

print("======================================================================")
print("CONTINUITY COUNCIL -- PDF Shooting Schedule Ingestion Verification")
print("======================================================================")

# 1. Upload schedule PDF
req = urllib.request.Request(
    f"{BASE}/productions/prod_001/import-schedule",
    data=body,
    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    method="POST",
)

with urllib.request.urlopen(req) as resp:
    upload_res = json.loads(resp.read().decode("utf-8"))
    job_id = upload_res["job_id"]
    print(f"[1] PDF Uploaded -> Job ID: {job_id} (Status: {upload_res['status']})")

# 2. Poll for extraction results
print("[2] Polling import job for Gemini extraction / preview...")
for attempt in range(15):
    time.sleep(1.0)
    with urllib.request.urlopen(f"{BASE}/imports/{job_id}") as resp:
        job_state = json.loads(resp.read().decode("utf-8"))
        print(f"    Attempt {attempt + 1}: Status = {job_state['status']}")
        if job_state["status"] in ("ready", "failed"):
            break

assert job_state["status"] == "ready", f"Job failed: {job_state.get('error')}"
preview = job_state.get("preview", {})
print("\n[3] Extraction Preview Received:")
print(f"    Shoot Days : {preview.get('days_count')}")
print(f"    Scenes     : {preview.get('scenes_count')}")
print(f"    Cast       : {preview.get('cast_count')} ({', '.join(preview.get('sample_cast', []))})")
print(f"    Locations  : {preview.get('locations_count')} ({', '.join(preview.get('sample_locations', []))})")
print(f"    Sample Rows: {len(preview.get('sample_scenes', []))} sample scenes extracted")

# 3. Confirm import
print("\n[4] Confirming import and persisting to ClickHouse...")
confirm_req = urllib.request.Request(
    f"{BASE}/imports/{job_id}/confirm",
    data=b"{}",
    headers={"Content-Type": "application/json"},
    method="POST",
)
with urllib.request.urlopen(confirm_req) as resp:
    confirm_res = json.loads(resp.read().decode("utf-8"))
    print(f"    Result: {confirm_res}")

# 4. Verify updated production bundle
print("\n[5] Verifying ClickHouse production schedule update...")
with urllib.request.urlopen(f"{BASE}/productions/prod_001") as resp:
    prod_bundle = json.loads(resp.read().decode("utf-8"))
    print(f"    Production '{prod_bundle['production']['title']}' has {len(prod_bundle['scenes'])} scenes in schedule.")

print("\n======================================================================")
print("PDF SCHEDULE INGESTION PIPELINE: SUCCESS")
print("======================================================================")
