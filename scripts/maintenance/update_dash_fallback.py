import json
import requests

with open('grafana/dashboards/crane_position_detail.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

new_query = """from(bucket: "cranepdm_kpis")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => (r["source"] == "v24_unified" or r["source"] == "live_v26"))
  |> filter(fn: (r) => r["crane_id"] == "${Crane_ID}")
  |> filter(fn: (r) => r["_field"] == "peak_shock" or r["_field"] == "peak_shock_pos" or r["_field"] == "avg_pos")
  |> group(columns: ["_time", "crane_id"])
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> map(fn: (r) => ({ r with peak_shock_pos: if exists r.peak_shock_pos then r.peak_shock_pos else r.avg_pos }))
  |> filter(fn: (r) => exists r["peak_shock"] and exists r["peak_shock_pos"])
  |> filter(fn: (r) => r["peak_shock"] >= 20.0)
  |> keep(columns: ["_time", "peak_shock_pos", "peak_shock"])"""

dash['panels'][0]['targets'][0]['query'] = new_query
dash['id'] = None

r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Support old data using avg_pos'}
)

print('Status:', r.status_code)
print('Response:', r.text)

with open('grafana/dashboards/crane_position_detail.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
