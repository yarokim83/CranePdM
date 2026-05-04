import requests
import json

grafana_url = "http://localhost:3000"

def push(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        dashboard = json.load(f)

    payload = {
        "dashboard": dashboard,
        "overwrite": True
    }

    try:
        response = requests.post(
            f"{grafana_url}/api/dashboards/db",
            json=payload,
            auth=('admin', 'adminpassword')
        )
        print(f"{filename} Status:", response.status_code)
        print(f"{filename} Response:", response.text)
    except Exception as e:
        print(f"{filename} Error:", e)

push('grafana_v2_dashboard.json')
push('grafana_v2_detail_dashboard.json')
