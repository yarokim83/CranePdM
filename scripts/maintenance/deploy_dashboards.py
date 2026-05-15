import json
import requests

# 1. Update the Main Dashboard to add Data Links
with open('grafana/dashboards/crane_pdm.json', 'r', encoding='utf-8') as f:
    main_dash = json.load(f)

for panel in main_dash.get('panels', []):
    if panel.get('title') == "🔥 Top 5 Risk Cranes (Stress Index)":
        for override in panel['fieldConfig']['overrides']:
            if override['matcher']['options'] == 'crane_id':
                # Add link to the detail dashboard
                has_links = False
                for prop in override['properties']:
                    if prop['id'] == 'links':
                        has_links = True
                        prop['value'] = [{
                            "title": "위치별 충격량 보기",
                            "url": "/d/crane_pos_detail/crane-position-impact-detail?var-Crane_ID=${__value.text}&from=${__url.timeRange.from}&to=${__url.timeRange.to}",
                            "targetBlank": True
                        }]
                if not has_links:
                    override['properties'].append({
                        "id": "links",
                        "value": [{
                            "title": "위치별 충격량 보기",
                            "url": "/d/crane_pos_detail/crane-position-impact-detail?var-Crane_ID=${__value.text}&from=${__url.timeRange.from}&to=${__url.timeRange.to}",
                            "targetBlank": True
                        }]
                    })
    elif panel.get('title') == "🛰️ ARMGC 38대 (Stress Index Stress)":
        panel['fieldConfig']['defaults']['links'] = [{
            "title": "위치별 충격량 보기",
            "url": "/d/crane_pos_detail/crane-position-impact-detail?var-Crane_ID=${__field.labels.crane_id}&from=${__url.timeRange.from}&to=${__url.timeRange.to}",
            "targetBlank": True
        }]

main_dash['id'] = None
main_dash['version'] = None

r_main = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={"dashboard": main_dash, "overwrite": True, "message": "Add detail dashboard links"}
)
print("Main Dashboard Push:", r_main.status_code, r_main.text)


# 2. Create the Detail Dashboard
detail_dash = {
  "annotations": {"list": []},
  "editable": True,
  "fiscalYearStartMonth": 0,
  "graphTooltip": 1,
  "id": None,
  "links": [],
  "panels": [
    {
      "datasource": {"type": "influxdb", "uid": "P951FEA4DE68E13C5"},
      "fieldConfig": {
        "defaults": {
          "color": {"mode": "fixed", "fixedColor": "red"},
          "custom": {
            "hideFrom": {"legend": False, "tooltip": False, "viz": False},
            "lineStyle": {"fill": "solid"},
            "lineWidth": 0,
            "pointSize": 8,
            "showPoints": "always"
          }
        },
        "overrides": []
      },
      "gridPos": {"h": 20, "w": 24, "x": 0, "y": 0},
      "id": 1,
      "options": {
        "legend": {"calcs": [], "displayMode": "list", "placement": "bottom"},
        "tooltip": {"mode": "single", "sort": "none"}
      },
      "targets": [
        {
          "query": "from(bucket: \"cranepdm_kpis\")\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n  |> filter(fn: (r) => r[\"_measurement\"] == \"crane_movement\")\n  |> filter(fn: (r) => (r[\"source\"] == \"v24_unified\" or r[\"source\"] == \"live_v26\"))\n  |> filter(fn: (r) => r[\"crane_id\"] == \"${Crane_ID}\")\n  |> filter(fn: (r) => r[\"_field\"] == \"peak_shock\" or r[\"_field\"] == \"peak_shock_pos\")\n  |> pivot(rowKey:[\"_time\"], columnKey: [\"_field\"], valueColumn: \"_value\")\n  |> filter(fn: (r) => r[\"peak_shock\"] >= 30.0)\n  |> keep(columns: [\"_time\", \"peak_shock_pos\", \"peak_shock\"])",
          "refId": "A",
          "datasource": {"type": "influxdb", "uid": "P951FEA4DE68E13C5"}
        }
      ],
      "title": "호기 ${Crane_ID} - Gantry Position별 고위험 충격량 (Shock >= 30)",
      "type": "xychart"
    }
  ],
  "schemaVersion": 39,
  "style": "dark",
  "tags": ["Detail", "Position"],
  "templating": {
    "list": [
      {
        "current": {"selected": False, "text": "256", "value": "256"},
        "datasource": {"type": "influxdb", "uid": "P951FEA4DE68E13C5"},
        "definition": "import \"influxdata/influxdb/schema\"\nschema.tagValues(bucket: \"cranepdm_kpis\", tag: \"crane_id\")",
        "hide": 0,
        "includeAll": False,
        "multi": False,
        "name": "Crane_ID",
        "options": [],
        "query": "import \"influxdata/influxdb/schema\"\nschema.tagValues(bucket: \"cranepdm_kpis\", tag: \"crane_id\")",
        "refresh": 1,
        "regex": "",
        "skipUrlSync": False,
        "sort": 0,
        "type": "query"
      }
    ]
  },
  "time": {"from": "now-30d", "to": "now"},
  "timepicker": {},
  "timezone": "browser",
  "title": "Crane Position Impact Detail",
  "uid": "crane_pos_detail",
  "version": 1
}

r_detail = requests.post(
    'http://localhost:3000/api/dashboards/db',
    headers={'Content-Type': 'application/json'},
    auth=('admin', 'adminpassword'),
    json={"dashboard": detail_dash, "overwrite": True, "message": "Initial deploy"}
)
print("Detail Dashboard Push:", r_detail.status_code, r_detail.text)

with open('grafana/dashboards/crane_pdm.json', 'w', encoding='utf-8') as f:
    json.dump(main_dash, f, indent=2, ensure_ascii=False)

with open('grafana/dashboards/crane_position_detail.json', 'w', encoding='utf-8') as f:
    json.dump(detail_dash, f, indent=2, ensure_ascii=False)
