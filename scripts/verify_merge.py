import urllib.request
import json
import time

BASE = 'http://127.0.0.1:8000/api'

# 1. Health check
with urllib.request.urlopen(f'{BASE}/health') as resp:
    health = json.loads(resp.read().decode('utf-8'))
    print(f"[1] Health Check: status={health['status']} | ClickHouse connected={health['clickhouse']['connected']}")
    assert health['status'] == 'ok'
    assert health['clickhouse']['connected'] is True

# 2. Warm Investigation on prod_001
payload = {
    'production_id': 'prod_001',
    'disruption_type': 'lead_actor_unavailable',
    'affected_day': 2,
    'affected_cast_id': 'lead_001',
    'affected_location_id': '',
    'severity': 'medium',
    'reported_by': '1st AD Marcus Sterling',
    'notes': 'Lead actor unavailable test run'
}
req = urllib.request.Request(f'{BASE}/disruptions', data=json.dumps(payload).encode('utf-8'), headers={'Content-Type': 'application/json'})
t0 = time.perf_counter()
with urllib.request.urlopen(req) as resp:
    case_info = json.loads(resp.read().decode('utf-8'))

case_id = case_info['case_id']
while True:
    with urllib.request.urlopen(f'{BASE}/cases/{case_id}') as resp:
        c = json.loads(resp.read().decode('utf-8'))
        if c['status'] in ('options_ready', 'error'):
            t1 = time.perf_counter()
            elapsed = t1 - t0
            print(f"[2] Investigation on prod_001: status={c['status']} elapsed={elapsed:.2f}s options={len(c.get('options', []))}")
            break
    time.sleep(0.05)

# 3. Chatbot answers 'Hi' kindly
chat_req = urllib.request.Request(
    f'{BASE}/chat',
    data=json.dumps({'message': 'Hi', 'production_id': 'prod_001'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(chat_req) as resp:
    chat_res = json.loads(resp.read().decode('utf-8'))
    print(f"[3] Chatbot Greeting Response:\n    \"{chat_res['answer'][:140]}...\"")
    assert len(chat_res['answer']) > 10
    assert len(chat_res.get('sources', [])) == 0  # no raw SQL/sources on greeting

# 4. Option cards show justifications / rationales
rec_opt = next((o for o in c['options'] if o['recommended']), c['options'][0])
print(f"[4] Recommendation Rationale:\n    \"{c['recommendation_rationale'][:140]}...\"")
assert len(c['recommendation_rationale']) > 10

# 5. MCP Live panel data streams
print(f"[5] MCP Live Calls: {len(c.get('mcp_calls', []))} calls logged")
assert len(c.get('mcp_calls', [])) >= 1

# 6. Approve & Decision Ledger
top_opt_id = rec_opt['option_id']
app_req = urllib.request.Request(
    f'{BASE}/cases/{case_id}/approve',
    data=json.dumps({'option_id': top_opt_id, 'approved_by': 'Executive Producer'}).encode('utf-8'),
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(app_req) as resp:
    app_res = json.loads(resp.read().decode('utf-8'))
    print(f"[6] Decision Ledger Write: decision_id={app_res.get('decision_id')} status={app_res.get('status')}")
    assert app_res.get('status') == 'written'

print('\nALL MERGED TREE VERIFICATIONS PASSED SUCCESSFULLY!')
