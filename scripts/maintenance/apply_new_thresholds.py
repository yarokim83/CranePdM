import json
import requests

with open('grafana/dashboards/crane_pdm.json', 'r', encoding='utf-8') as f:
    dash = json.load(f)

for p in dash.get('panels', []):
    if 'fieldConfig' in p and 'defaults' in p['fieldConfig'] and 'thresholds' in p['fieldConfig']['defaults']:
        steps = p['fieldConfig']['defaults']['thresholds'].get('steps', [])
        for step in steps:
            if step['color'] == 'orange':
                step['value'] = 40
            elif step['color'] == 'red':
                step['value'] = 50

# Ensure ID is None so it creates/overwrites the existing one by UID
dash['id'] = None

r = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={'dashboard': dash, 'overwrite': True, 'message': 'Update thresholds to Red:50, Orange:40'}
)
print('Status:', r.status_code)
print('Response:', r.text)

# Save changes locally too
with open('grafana/dashboards/crane_pdm.json', 'w', encoding='utf-8') as f:
    json.dump(dash, f, indent=2, ensure_ascii=False)
