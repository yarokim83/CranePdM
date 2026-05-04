import json
import requests

with open('grafana/dashboards/crane_pdm.json', 'r', encoding='utf-8') as f:
    dashboard = json.load(f)

dashboard['id'] = None
dashboard['version'] = None

payload = {
    "dashboard": dashboard,
    "overwrite": True,
    "message": "Update thresholds: 25=orange, 30=red; gauge max=40"
}

r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json=payload
)

print(f"Status: {r.status_code}")
print(f"Response: {r.text}")
