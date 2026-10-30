import json
import requests
import copy

with open('grafana/dashboards/crane_pdm.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

base_panel = None
for p in dash.get('panels', []):
    if p.get('id') == 2:  # Copy "Top 5 Risk Cranes" panel
        base_panel = copy.deepcopy(p)
        break

if not base_panel:
    print("Could not find base panel ID 2")
    exit(1)

# Panel 1: Outlier Count
outlier_panel = copy.deepcopy(base_panel)
outlier_panel['id'] = 101
outlier_panel['title'] = "극단치(Outlier) 발생 빈도 (Shock >= 25G)"
if 'targets' in outlier_panel and len(outlier_panel['targets']) > 0:
    outlier_panel['targets'][0]['query'] = """
from(bucket: "cranepdm_kpis")
  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "peak_shock")
  |> filter(fn: (r) => r["_value"] >= 25.0)
  |> group(columns: ["crane_id"])
  |> count()
"""
outlier_panel['gridPos'] = {"h": 8, "w": 12, "x": 0, "y": 20}
if 'fieldConfig' in outlier_panel and 'defaults' in outlier_panel['fieldConfig'] and 'thresholds' in outlier_panel['fieldConfig']['defaults']:
    outlier_panel['fieldConfig']['defaults']['thresholds']['steps'] = [
        {"color": "green", "value": None},
        {"color": "orange", "value": 5},
        {"color": "red", "value": 15}
    ]

# Panel 2: Rolling Max Shock
max_panel = copy.deepcopy(base_panel)
max_panel['id'] = 102
max_panel['title'] = "최근 7일 최고 위험도 (Max Peak Shock)"
if 'targets' in max_panel and len(max_panel['targets']) > 0:
    max_panel['targets'][0]['query'] = """
from(bucket: "cranepdm_kpis")
  |> range(start: -7d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "peak_shock")
  |> group(columns: ["crane_id"])
  |> max()
"""
max_panel['gridPos'] = {"h": 8, "w": 12, "x": 12, "y": 20}
if 'fieldConfig' in max_panel and 'defaults' in max_panel['fieldConfig'] and 'thresholds' in max_panel['fieldConfig']['defaults']:
    max_panel['fieldConfig']['defaults']['thresholds']['steps'] = [
        {"color": "green", "value": None},
        {"color": "orange", "value": 24},
        {"color": "red", "value": 30}
    ]

# Remove existing appended panels if any
dash['panels'] = [p for p in dash['panels'] if p.get('id') not in (101, 102)]

dash['panels'].append(outlier_panel)
dash['panels'].append(max_panel)

dash['id'] = None
r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Add Outlier and Rolling Max panels'}
)
print('Status:', r.status_code)
print('Response:', r.text)

with open('grafana/dashboards/crane_pdm.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
