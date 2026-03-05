import json

def replace_bargauge_with_barchart():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    for i, panel in enumerate(dash.get("panels", [])):
        if panel.get("id") == 3:
            # Completely replace Panel 3 (the stubborn bargauge) with a Bar Chart
            new_panel = {
              "datasource": {
                "uid": "col_cranepdm"
              },
              "fieldConfig": {
                "defaults": {
                  "color": {
                    "mode": "thresholds"
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
                    "gradientMode": "opacity",
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
                "h": 14,
                "w": 24,
                "x": 0,
                "y": 8
              },
              "id": 3,
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
                  "query": "from(bucket: \"cranepdm_kpis\")\r\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\r\n  |> filter(fn: (r) => r[\"_measurement\"] == \"crane_movement\")\r\n  |> filter(fn: (r) => r[\"_field\"] == \"reducer_damage\")\r\n  |> group(columns: [\"crane_id\"])\r\n  |> mean()\r\n  |> group()\r\n  |> keep(columns: [\"crane_id\", \"_value\"])\r\n  |> rename(columns: {_value: \"Avg Damage\"})\r\n  |> sort(columns: [\"crane_id\"])",
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
                      "Avg Damage": {
                        "aggregations": [
                          "mean"
                        ],
                        "operation": "aggregate"
                      }
                    }
                  }
                }
              ],
              "title": "Fleet Outlier Detection (Avg Reducer Stress by Crane)",
              "type": "barchart"
            }
            dash["panels"][i] = new_panel
            break

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Bargauge replaced with Barchart!")

if __name__ == "__main__":
    replace_bargauge_with_barchart()
