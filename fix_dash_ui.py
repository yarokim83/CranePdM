import json

def fix_dash():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    for panel in dash.get("panels", []):
        # 1. Bar Chart (ID 5): Fix X-axis labels by formatting Flux table properly
        if panel.get("id") == 5:
            # Remove transformations
            panel["transformations"] = []
            
            # Use Keep and Rename in Flux so Grafana uses crane_id for X-axis natively
            q = 'from(bucket: "cranepdm_kpis")\n  |> range(start: v.timeRangeStart, stop: v.timeRangeStop)\n  |> filter(fn: (r) => r["_measurement"] == "crane_movement")\n  |> filter(fn: (r) => r["crane_id"] =~ /${Crane_ID:regex}/)\n  |> filter(fn: (r) => r["_field"] == "peak_feedback")\n  |> group(columns: ["crane_id"])\n  |> max()\n  |> group()\n  |> keep(columns: ["crane_id", "_value"])\n  |> rename(columns: {_value: "Max Speed"})\n  |> sort(columns: ["crane_id"])'
            if "targets" in panel and len(panel["targets"]) > 0:
                panel["targets"][0]["query"] = q
                
            if "options" in panel:
                panel["options"]["xTickLabelRotation"] = -45 # Rotate nicely

        # 2. Time Series Charts (IDs 6, 7, 8): Show dots even for single data points
        if panel.get("type") == "timeseries" and panel.get("id") in [6, 7, 8]:
            if "fieldConfig" in panel and "defaults" in panel["fieldConfig"] and "custom" in panel["fieldConfig"]["defaults"]:
                custom = panel["fieldConfig"]["defaults"]["custom"]
                custom["showPoints"] = "always" # Force dots to appear
                custom["spanNulls"] = True      # Draw lines across gaps
                custom["pointSize"] = 6
                
                # Make lines slightly thicker for visibility
                custom["lineWidth"] = 2

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Dashboard fixed!")

if __name__ == "__main__":
    fix_dash()
