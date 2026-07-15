import json
import requests
import os

dashboards = [
    'grafana/dashboards/crane_pdm.json',
    'grafana/dashboards/qc_spreader_pdm.json'
]

for dash_path in dashboards:
    if not os.path.exists(dash_path):
        print(f"File not found: {dash_path}")
        continue
        
    print(f"Pushing dashboard: {dash_path} ...")
    with open(dash_path, 'r', encoding='utf-8') as f:
        dashboard = json.load(f)

    dashboard['id'] = None
    dashboard['version'] = None

    payload = {
        "dashboard": dashboard,
        "overwrite": True,
        "message": f"Auto-push from deploy script: {os.path.basename(dash_path)}"
    }

    r = requests.post(
        'http://localhost:3000/api/dashboards/db',
        headers={'Content-Type': 'application/json'},
        auth=('admin', 'adminpassword'),
        json=payload
    )

    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}\n")
