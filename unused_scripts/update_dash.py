import json

file_path = r'c:\Users\huser\.gemini\CranePdM\grafana_v2_detail_dashboard.json'

with open(file_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

for panel in data.get('panels', []):
    if 'id' in panel and panel['id'] == 14:
        for target in panel.get('targets', []):
            query = target.get('query', '')
            
            # Replace field filter
            query = query.replace('r["_field"] == "avg_pos"', 'r["_field"] == "avg_pos" or r["_field"] == "peak_shock_pos"')
            
            # Replace exists filter
            query = query.replace('exists r.avg_pos', 'exists r.avg_pos or exists r.peak_shock_pos')
            
            # Replace mapping
            query = query.replace('"0. Gantry Position (m)": r.avg_pos', '"0. Gantry Position (m)": if exists r.peak_shock_pos then r.peak_shock_pos else r.avg_pos')
            
            target['query'] = query
        break

with open(file_path, 'w', encoding='utf-8') as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("Dashboard updated successfully.")
