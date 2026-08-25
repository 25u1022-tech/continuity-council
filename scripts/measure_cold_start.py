import json
import time
import urllib.request

t0 = time.perf_counter()
req = urllib.request.Request("http://127.0.0.1:8000/api/health")
with urllib.request.urlopen(req) as resp:
    data = json.loads(resp.read().decode("utf-8"))
    elapsed = time.perf_counter() - t0
    print(f"Health response in {elapsed:.3f}s: ClickHouse connected={data.get('clickhouse', {}).get('connected')}")
