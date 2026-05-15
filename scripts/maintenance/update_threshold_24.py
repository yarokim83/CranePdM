import json
import requests

with open('grafana/dashboards/crane_position_detail.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

# Update threshold in title
xy_panel = dash['panels'][0]
xy_panel['title'] = "호기 ${Crane_ID} - Gantry Position별 고위험 충격량 (Shock >= 24)"

# Update threshold in query
old_query = xy_panel['targets'][0]['query']
new_query = old_query.replace('r["peak_shock"] >= 20.0', 'r["peak_shock"] >= 24.0')
xy_panel['targets'][0]['query'] = new_query

dash['id'] = None

r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Change threshold to 24'}
)
print('Status:', r.status_code)
print('Response:', r.text)

with open('grafana/dashboards/crane_position_detail.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
