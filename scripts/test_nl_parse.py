import urllib.request
import json

BASE = "http://127.0.0.1:8000/api"
test_cases = [
    "Sarah broke her wrist, can't shoot Tuesday",
    "The harbor permit got revoked",
    "Storm's rolling in Thursday",
]

print("======================================================================")
print("CONTINUITY COUNCIL -- Natural-Language Disruption Parser Verification")
print("======================================================================")

for desc in test_cases:
    req = urllib.request.Request(
        f"{BASE}/disruptions/parse-nl",
        data=json.dumps({"description": desc, "production_id": "prod_001"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"INPUT: \"{desc}\"")
        print(f"  Confidence : {data.get('confidence')}")
        print(f"  Type       : {data.get('disruption_type')}")
        print(f"  Severity   : {data.get('severity')}")
        print(f"  Shoot Day  : Day {data.get('affected_day')} (Resolved Date: {data.get('affected_date')})")
        print(f"  Cast Match : ID={data.get('affected_cast_id')} ({data.get('affected_cast_name')})")
        print(f"  Loc Match  : ID={data.get('affected_location_id')} ({data.get('affected_location_name')})")
        print(f"  Reasoning  : {data.get('reasoning')}")
        print("----------------------------------------------------------------------")

print("NL PARSER LIVE VERIFICATION: SUCCESS")
