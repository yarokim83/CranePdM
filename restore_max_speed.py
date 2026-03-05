import json

def restore():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    # Find max Y pos
    max_y = 0
    for p in dash.get("panels", []):
        y_val = p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0)
        if y_val > max_y:
            max_y = y_val

    max_speed_panel = {
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
            "drawStyle": "bars",
            "fillOpacity": 80,
            "gradientMode": "none",
            "hideFrom": {
              "legend": False,
              "tooltip": False,
              "viz": False
            },
            "insertNulls": False,
            "lineInterpolation": "linear",
            "lineWidth": 1,
            "pointSize": 5,
            "scaleDistribution": {
              "type": "linear"
            },
            "showPoints": "auto",
            "spanNulls": False,
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
                "value": 1500
              },
              {
                "color": "red",
                "value": 2000
              }
            ]
          },
          "unit": "short",
          "displayName": "${__field.labels.crane_id}"
        },
        "overrides": []
      },
      "gridPos": {
        "h": 12,
        "w": 24,
        "x": 0,
        "y": max_y
      },
      "id": 5,
      "options": {
        "legend": {
          "calcs": [],
          "displayMode": "list",
          "placement": "bottom",
          "showLegend": False
        },
        "tooltip": {
          "mode": "single",
          "sort": "none"
        },
        "barRadius": 0,
        "barWidth": 0.8,
        "fullHighlight": False,
        "groupWidth": 0.7,
        "orientation": "auto",
        "showValue": "auto",
        "stacking": "none",
        "text": {},
        "xTickLabelRotation": -45,
        "xTickLabelSpacing": 0
      },
      "targets": [
        {
          "query": "from(bucket: \"cranepdm_kpis\")\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n  |> filter(fn: (r) => r[\"_measurement\"] == \"crane_movement\")\n  |> filter(fn: (r) => r[\"crane_id\"] =~ /${Crane_ID:regex}/)\n  |> filter(fn: (r) => r[\"_field\"] == \"peak_feedback\")\n  |> group(columns: [\"crane_id\"])\n  |> max()\n  |> group()\n  |> keep(columns: [\"crane_id\", \"_value\"])\n  |> rename(columns: {_value: \"Max Speed\"})\n  |> sort(columns: [\"crane_id\"])",
          "refId": "A"
        }
      ],
      "transformations": [
        {
          "id": "organize",
          "options": {
            "excludeByName": {},
            "indexByName": {},
            "renameByName": {
              "crane_id": "Crane ID"
            }
          }
        },
        {
          "id": "groupBy",
          "options": {
            "fields": {
              "crane_id": {
                "aggregations": [],
                "operation": "groupby"
              },
              "Max Speed": {
                "aggregations": [
                  "max"
                ],
                "operation": "aggregate"
              }
            }
          }
        }
      ],
      "title": "Daily Max Speed by Crane (peak_feedback)",
      "type": "barchart"
    }
    
    dash["panels"].append(max_speed_panel)
    
    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
        
    print("Max Speed Panel Restored!")

if __name__ == "__main__":
    restore()
