import json
import requests

with open('grafana/dashboards/crane_pdm.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

for p in dash.get('panels', []):
    if p.get('id') == 101:
        p['targets'][0]['query'] = """
from(bucket: "cranepdm_kpis")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "peak_shock")
  |> filter(fn: (r) => r["_value"] >= 25.0)
  |> group(columns: ["crane_id"])
  |> count()
  |> rename(columns: {_value: "Count"})
  |> keep(columns: ["crane_id", "Count"])
  |> group()
  |> sort(columns: ["Count"], desc: true)
"""
    elif p.get('id') == 102:
        p['targets'][0]['query'] = """
from(bucket: "cranepdm_kpis")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "peak_shock")
  |> group(columns: ["crane_id"])
  |> max()
  |> rename(columns: {_value: "Max Shock"})
  |> keep(columns: ["crane_id", "Max Shock"])
  |> group()
  |> sort(columns: ["Max Shock"], desc: true)
"""

dash['id'] = None
r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Sort outlier and max panels descending'}
)
print('Status:', r.status_code)
print('Response:', r.text)

with open('grafana/dashboards/crane_pdm.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
