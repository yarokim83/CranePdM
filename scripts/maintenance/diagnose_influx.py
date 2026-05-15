import requests

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"

# Test 1: Confirm what fields crane 256 actually has in live_v26
query1 = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["crane_id"] == "256")
  |> filter(fn: (r) => r["source"] == "live_v26")
  |> distinct(column: "_field")
  |> keep(columns: ["_value"])
'''
r1 = requests.post(
    f'{INFLUX_URL}/api/v2/query',
    params={'org': INFLUX_ORG},
    headers={'Authorization': f'Token {INFLUX_TOKEN}', 'Content-Type': 'application/vnd.flux'},
    data=query1.encode('utf-8')
)
print("=== Available fields for crane 256 (live_v26, 7d) ===")
print(r1.status_code, r1.text[:2000])

# Test 2: Sample raw rows - check if peak_shock_pos is written
query2 = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["crane_id"] == "256")
  |> filter(fn: (r) => r["source"] == "live_v26")
  |> filter(fn: (r) => r["_field"] == "peak_shock" or r["_field"] == "peak_shock_pos")
  |> limit(n: 20)
'''
r2 = requests.post(
    f'{INFLUX_URL}/api/v2/query',
    params={'org': INFLUX_ORG},
    headers={'Authorization': f'Token {INFLUX_TOKEN}', 'Content-Type': 'application/vnd.flux'},
    data=query2.encode('utf-8')
)
print("\n=== Raw peak_shock / peak_shock_pos rows (crane 256, 7d) ===")
print(r2.status_code)
for line in r2.text.strip().split('\n')[:30]:
    print(line)

# Test 3: Check if peak_shock values > 30 exist without pivot
query3 = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["crane_id"] == "256")
  |> filter(fn: (r) => r["source"] == "live_v26")
  |> filter(fn: (r) => r["_field"] == "peak_shock")
  |> filter(fn: (r) => r["_value"] >= 30.0)
  |> limit(n: 10)
'''
r3 = requests.post(
    f'{INFLUX_URL}/api/v2/query',
    params={'org': INFLUX_ORG},
    headers={'Authorization': f'Token {INFLUX_TOKEN}', 'Content-Type': 'application/vnd.flux'},
    data=query3.encode('utf-8')
)
print("\n=== peak_shock >= 30 rows (no pivot, 7d) ===")
print(r3.status_code)
for line in r3.text.strip().split('\n')[:30]:
    print(line)
