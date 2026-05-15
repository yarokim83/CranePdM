import json
import requests

with open('grafana/dashboards/crane_position_detail.json', 'r', encoding='utf-8') as f:
    detail_dash = json.load(f)

# Update options for xychart to explicitly map X and Y axes
detail_dash['panels'][0]['options']['dims'] = {
    "frame": 0,
    "x": "peak_shock_pos",
    "exclude": ["_time", "Time", "time"]
}
detail_dash['panels'][0]['options']['series'] = [
    {
        "show": True,
        "y": "peak_shock",
        "pointSize": 5,
        "lineColor": {"fixedColor": "red", "mode": "fixed"}
    }
]

# Push the updated detail dashboard
r_detail = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={"dashboard": detail_dash, "overwrite": True, "message": "Add dims to xychart"}
)
print("Detail Dashboard Push:", r_detail.status_code, r_detail.text)

with open('grafana/dashboards/crane_position_detail.json', 'w', encoding='utf-8') as f:
    json.dump(detail_dash, f, indent=2, ensure_ascii=False)
