import json
import glob

for f in glob.glob('*.json') + glob.glob('grafana/dashboards/*.json') + glob.glob('deploy_package/*.json'):
    try:
        with open(f, 'r', encoding='utf-8') as file:
            data = json.load(file)
            
        def walk_and_update(node):
            changed = False
            if isinstance(node, dict):
                # Check for thresholds
                if "color" in node and "value" in node:
                    if node["color"] == "orange" and node["value"] == 20.0:
                        node["value"] = 25.0
                        changed = True
                    elif node["color"] == "red" and node["value"] == 25.0:
                        node["value"] = 30.0
                        changed = True
                    # Also check for integer values just in case
                    elif node["color"] == "orange" and node["value"] == 20:
                        node["value"] = 25
                        changed = True
                    elif node["color"] == "red" and node["value"] == 25:
                        node["value"] = 30
                        changed = True
                
                for k, v in node.items():
                    if walk_and_update(v):
                        changed = True
            elif isinstance(node, list):
                for item in node:
                    if walk_and_update(item):
                        changed = True
            return changed
            
        if walk_and_update(data):
            with open(f, 'w', encoding='utf-8') as file:
                json.dump(data, file, indent=2)
            print(f"Updated {f}")
            
    except Exception as e:
        print(f"Error processing {f}: {e}")
