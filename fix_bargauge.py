import json

def fix_bargauge_labels():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    # We need to increase the height of Panel 3 (Bargauge) to give the 38 labels enough vertical room.
    # Currently h=12. We will increase it to h=24.
    # We will also add minVizHeight=14 to force scrolling if space is still tight.
    height_increase = 12

    for panel in dash.get("panels", []):
        if panel.get("id") == 3:
            panel["gridPos"]["h"] += height_increase
            if "options" not in panel:
                panel["options"] = {}
            panel["options"]["minVizHeight"] = 16 # Forces scrollbar, prevents font squishing
            
        elif panel.get("id") > 3:
            # Shift all panels below panel 3 down
            panel["gridPos"]["y"] += height_increase

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Bargauge height increased and minVizHeight applied!")

if __name__ == "__main__":
    fix_bargauge_labels()
