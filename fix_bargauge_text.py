import json

def fix_bargauge_text():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    for panel in dash.get("panels", []):
        if panel.get("id") == 3:
            # Force text sizing for layout
            if "options" not in panel:
                panel["options"] = {}
                
            panel["options"]["text"] = {
              "valueSize": 14,
              "titleSize": 16
            }
            # For horizontal bar gauges, sometimes Grafana squishes the name if the value bar is long
            if "minVizWidth" not in panel["options"]:
                panel["options"]["minVizWidth"] = 0
            
            # The most robust way to give the titles space in Bar Gauge is "nameSize" 
            # (which behaves as the label width when orientation is horizontal)
            # or simply using "text: titleSize"
            
            # Additional trick: Ensure "displayName" is exactly what we want without any prefixes
            if "fieldConfig" in panel and "defaults" in panel["fieldConfig"]:
                panel["fieldConfig"]["defaults"]["displayName"] = "${__field.labels.crane_id}"

            # Ensure reduce options use all series properly
            if "reduceOptions" in panel["options"]:
                 panel["options"]["reduceOptions"]["limit"] = 100

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Bargauge name width forcefully expanded!")

if __name__ == "__main__":
    fix_bargauge_text()
