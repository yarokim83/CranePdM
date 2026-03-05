import json

def style_table():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    for panel in dash.get("panels", []):
        if panel.get("id") == 1 and panel.get("type") == "table":
            if "fieldConfig" not in panel:
                panel["fieldConfig"] = {"defaults": {}, "overrides": []}
            
            # Clear existing overrides to avoid duplicates
            panel["fieldConfig"]["overrides"] = []
            
            # 1. Override for 'crane_id' column
            panel["fieldConfig"]["overrides"].append({
                "matcher": {
                    "id": "byName",
                    "options": "crane_id"
                },
                "properties": [
                    {
                        "id": "displayName",
                        "value": "Crane ID"
                    },
                    {
                        "id": "custom.align",
                        "value": "center"
                    }
                ]
            })

            # 2. Override for '_value' column
            panel["fieldConfig"]["overrides"].append({
                "matcher": {
                    "id": "byName",
                    "options": "_value"
                },
                "properties": [
                    {
                        "id": "displayName",
                        "value": "Avg Stress Level"
                    },
                    {
                        "id": "custom.cellOptions",
                        "value": {
                            "mode": "gradient",
                            "type": "gauge",
                            "valueDisplayMode": "text"
                        }
                    },
                    {
                        "id": "custom.align",
                        "value": "center"
                    }
                ]
            })

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
        
    print("Table styled successfully!")

if __name__ == "__main__":
    style_table()
