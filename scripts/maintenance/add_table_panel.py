import json
import requests

with open('grafana/dashboards/crane_position_detail.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

# The existing xychart panel is at index 0.
xy_panel = dash['panels'][0]
xy_panel['gridPos'] = {"h": 12, "w": 24, "x": 0, "y": 0}

# Create a Table panel to debug the data output
table_panel = {
  "datasource": {"type": "influxdb", "uid": "P951FEA4DE68E13C5"},
  "fieldConfig": {
    "defaults": {
      "custom": {"align": "auto", "cellOptions": {"type": "auto"}},
      "color": {"mode": "thresholds"}
    },
    "overrides": []
  },
  "gridPos": {"h": 10, "w": 24, "x": 0, "y": 12},
  "id": 2,
  "options": {"showHeader": True},
  "targets": xy_panel['targets'], # Use the exact same query
  "title": "Raw Data Debug Table (데이터가 테이블에는 나오는지 확인)",
  "type": "table"
}

# Ensure there's only 2 panels to avoid duplicates if run multiple times
dash['panels'] = [xy_panel, table_panel]
dash['id'] = None

r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Add Table panel for debugging'}
)
print('Status:', r.status_code)
print('Response:', r.text)

with open('grafana/dashboards/crane_position_detail.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
