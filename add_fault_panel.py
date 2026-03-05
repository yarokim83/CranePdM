import json

def update_dashboard():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    # 1. Resize the existing XY Chart from w:24 to w:12 to make room
    for panel in dash.get("panels", []):
        if panel.get("title") == "Rail Health Mapping (Position vs Reducer Damage)" and panel.get("type") == "xychart":
            panel["gridPos"]["w"] = 12
            y_pos = panel["gridPos"]["y"]
            break

    # 2. Create the new Fault Hotspot Panel
    new_panel = {
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
        "w": 12,
        "x": 12,
        "y": y_pos
      },
      "id": 10,
      "options": {
        "seriesMapping": "auto"
      },
      "targets": [
        {
          "query": 'from(bucket: "cranepdm_kpis")\r\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\r\n  |> filter(fn: (r) => r["_measurement"] == "crane_faults")\r\n  |> filter(fn: (r) => r["crane_id"] =~ /${Crane_ID:regex}/)\r\n  |> filter(fn: (r) => r["_field"] == "position")\r\n  |> map(fn: (r) => ({ _time: r._time, crane_id: r.crane_id, position: r._value, fault_trigger: 1 }))\r\n  |> keep(columns: ["position", "crane_id", "fault_trigger"])\r\n  |> pivot(rowKey:["position"], columnKey: ["crane_id"], valueColumn: "fault_trigger")',
          "refId": "A"
        }
      ],
      "title": "Fault Hotspot Mapping (Position vs Overtension)",
      "type": "xychart"
    }

    # Append to dashboard
    dash["panels"].append(new_panel)

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("New panel added!")

if __name__ == "__main__":
    update_dashboard()
