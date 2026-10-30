import json
import requests

with open('grafana/dashboards/crane_pdm.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

for p in dash.get('panels', []):
    if p.get('id') in [1, 12]:  # Panel 1: Bar Gauge (All 38 Cranes), Panel 12: Table
        if 'fieldConfig' not in p:
            p['fieldConfig'] = {}
        if 'defaults' not in p['fieldConfig']:
            p['fieldConfig']['defaults'] = {}
            
        p['fieldConfig']['defaults']['links'] = [
            {
                "title": "호기 상세 Gantry 분석 열기",
                "url": "/d/crane_pos_detail/crane-position-impact-detail?var-Crane_ID=${__field.labels.crane_id}",
                "targetBlank": False
            }
        ]

dash['id'] = None

r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Restore Data Links'}
)
print('Status:', r.status_code)
print('Response:', r.text)

with open('grafana/dashboards/crane_pdm.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
