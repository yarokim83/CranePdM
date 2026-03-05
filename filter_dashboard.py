import json

def filter_dashboard():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    # Keep only Fleet panels, the Row, and the Reducer Damage XY chart
    # ID 1, 2, 3: Fleet (Reducer)
    # ID 4: Row
    # ID 9: Rail Mapping (Reducer)
    
    kept_panels = []
    
    for panel in dash.get("panels", []):
        if panel.get("id") in [1, 2, 3, 4]:
            kept_panels.append(panel)
        elif panel.get("id") == 9: # Rail Health Mapping (Position vs Reducer Damage)
            # Make it full width again
            panel["gridPos"]["w"] = 24
            panel["gridPos"]["x"] = 0
            panel["gridPos"]["y"] = 21 # Move it up, right below the row
            kept_panels.append(panel)

    # Add a new Time Series panel specifically targeting Reducer Damage over time for the selected crane
    reducer_trend_panel = {
      "datasource": {
        "uid": "col_cranepdm"
      },
      "fieldConfig": {
        "defaults": {
          "color": {
            "mode": "palette-classic"
          },
          "custom": {
            "axisBorderShow": False,
            "axisCenteredZero": False,
            "axisColorMode": "text",
            "axisLabel": "",
            "axisPlacement": "auto",
            "barAlignment": 0,
            "drawStyle": "line",
            "fillOpacity": 10,
            "gradientMode": "none",
            "hideFrom": {
              "legend": False,
              "tooltip": False,
              "viz": False
            },
            "insertNulls": False,
            "lineInterpolation": "linear",
            "lineWidth": 2,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "always",
            "spanNulls": True,
            "stacking": {
              "group": "A",
              "mode": "none"
            },
            "thresholdsStyle": {
              "mode": "off"
            }
          },
          "mappings": [],
          "thresholds": {
            "mode": "absolute",
            "steps": [
              {
                "color": "green",
                "value": None
              },
              {
                "color": "orange",
                "value": 20000
              },
              {
                "color": "red",
                "value": 30000
              }
            ]
          },
          "displayName": "${__field.labels.crane_id}"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 10,
        "w": 24,
        "x": 0,
        "y": 33
      },
      "id": 11,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": True
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        }
      },
      "targets": [
        {
          "query": "from(bucket: \"cranepdm_kpis\")\r\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\r\n  |> filter(fn: (r) => r[\"_measurement\"] == \"crane_movement\")\r\n  |> filter(fn: (r) => r[\"crane_id\"] =~ /${Crane_ID:regex}/)\r\n  |> filter(fn: (r) => r[\"_field\"] == \"reducer_damage\")\r\n  |> aggregateWindow(every: v.windowPeriod, fn: mean, createEmpty: false)\r\n  |> yield(name: \"mean\")",
          "refId": "A"
        }
      ],
      "title": "Reducer Damage Trend over Time",
      "type": "timeseries"
    }
    
    kept_panels.append(reducer_trend_panel)
    
    dash["panels"] = kept_panels

    # Update Row Title to reflect current focus
    for panel in dash.get("panels", []):
        if panel.get("type") == "row":
            panel["title"] = "🔍 DETAILED REDUCER DIAGNOSTICS (Select 'Crane_ID' variable at the top left)"

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Dashboard filtered for Reducer Damage ONLY!")

if __name__ == "__main__":
    filter_dashboard()
