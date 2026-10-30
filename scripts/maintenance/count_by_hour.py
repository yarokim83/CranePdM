import requests

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-05-13T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "peak_shock")
  |> aggregateWindow(every: 6h, fn: count, createEmpty: true)
  |> group(columns: ["_time"])
  |> sum()
'''

r = requests.post(
    'http://localhost:8086/api/v2/query',
    params={'org': 'myorg'},
    headers={'Authorization': 'Token my-super-secret-auth-token', 'Content-Type': 'application/vnd.flux'},
    data=query.encode('utf-8')
)
print("Count by 6 hours since May 13:")
print(r.text)
