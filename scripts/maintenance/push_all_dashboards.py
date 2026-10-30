import json
import requests
import os

BASE_URL = 'http://localhost:3000/api/dashboards/db'
AUTH = ('admin', 'adminpassword')
HEADERS = {'Content-Type': 'application/json'}

def push_dashboard(filepath, message):
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return
    with open(filepath, 'r', encoding='utf-8') as f:
        dashboard = json.load(f)
    
    dashboard['id'] = None
    dashboard['version'] = None
    
    payload = {
        "dashboard": dashboard,
        "overwrite": True,
        "message": message
    }
    
    r = requests.post(BASE_URL, headers=HEADERS, auth=AUTH, json=payload)
    print(f"Pushed {os.path.basename(filepath)} - Status: {r.status_code}, Response: {r.text}")

def main():
    push_dashboard('grafana/dashboards/crane_pdm.json', 'Restrict query to May 15 onwards')
    push_dashboard('grafana/dashboards/crane_position_detail.json', 'Restrict query to May 15 onwards')

if __name__ == "__main__":
    main()
