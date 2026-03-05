import json

def restore():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    max_y = 0
    for p in dash.get("panels", []):
        y_val = p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0)
        if y_val > max_y:
            max_y = y_val

    slack_fault_panel = {
      "datasource": {
        "uid": "col_cranepdm"
      },
      "fieldConfig": {
        "defaults": {
          "custom": {
            "pointSize": {
              "fixed": 12
            }
          }
        },
        "overrides": []
      },
      "gridPos": {
        "h": 12,
        "w": 24, # Let's make it full width since there's plenty of space at the bottom now
        "x": 0,
        "y": max_y
      },
      "id": 12, # Unique ID
      "options": {
        "seriesMapping": "auto"
      },
      "targets": [
        {
          "query": "from(bucket: \"cranepdm_kpis\")\r\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\r\n  |> filter(fn: (r) => r[\"_measurement\"] == \"crane_faults\")\r\n  |> filter(fn: (r) => r[\"crane_id\"] =~ /${Crane_ID:regex}/)\r\n  |> filter(fn: (r) => r[\"_field\"] == \"position\")\r\n  |> map(fn: (r) => ({ _time: r._time, crane_id: r.crane_id, position: r._value, fault_trigger: 1 }))\r\n  |> keep(columns: [\"position\", \"crane_id\", \"fault_trigger\"])\r\n  |> pivot(rowKey:[\"position\"], columnKey: [\"crane_id\"], valueColumn: \"fault_trigger\")",
          "refId": "A"
        }
      ],
      "title": "Fault Hotspot Mapping (Position vs Slack)",
      "type": "xychart"
    }
    
    dash["panels"].append(slack_fault_panel)
    
    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
        
    print("Slack Fault Panel Restored!")

if __name__ == "__main__":
    restore()
