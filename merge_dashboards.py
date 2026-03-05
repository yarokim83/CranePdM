import json

def merge():
    print("Loading dashboards...")
    with open("grafana_fleet_dashboard.json", "r", encoding="utf-8") as f:
        fleet = json.load(f)

    with open("grafana_dashboard.json", "r", encoding="utf-8") as f:
        pdm = json.load(f)

    unified = fleet.copy()
    unified["title"] = "Total Control Tower (Fleet Overview + PdM Details)"
    unified["uid"] = "total_control_tower_v1"

    # 1. Copy the Crane_ID template variable from the PdM dashboard
    if "templating" in pdm and "list" in pdm["templating"]:
        unified["templating"] = pdm["templating"]

    # 2. Find the lowest point of the Fleet dashboard to append below it
    max_id = max([p.get("id", 0) for p in unified.get("panels", [])])
    max_y = max([p.get("gridPos", {}).get("y", 0) + p.get("gridPos", {}).get("h", 0) for p in unified.get("panels", [])])

    # 3. Add a Divider Title Row
    max_id += 1
    row_panel = {
        "id": max_id,
        "gridPos": {"x": 0, "y": max_y, "w": 24, "h": 1},
        "type": "row",
        "title": "🔍 DETAILED ASSET DIAGNOSTICS (Select 'Crane_ID' variable at the top left)"
    }
    unified["panels"].append(row_panel)
    max_y += 1
    
    # 4. Append the PdM panels
    for p in pdm.get("panels", []):
        max_id += 1
        p["id"] = max_id
        
        # Shift down
        if "gridPos" in p:
            p["gridPos"]["y"] += max_y
            
        # 5. Inject the template variable filter into the Flux queries
        # so that 38 lines don't clutter the timeseries graphs
        if "targets" in p:
            for t in p["targets"]:
                if "query" in t:
                    q = t["query"]
                    if "crane_movement" in q and "Crane_ID" not in q:
                        # Insert the regex filter right after the measurement filter
                        q = q.replace(
                            '|> filter(fn: (r) => r["_measurement"] == "crane_movement")',
                            '|> filter(fn: (r) => r["_measurement"] == "crane_movement")\r\n  |> filter(fn: (r) => r["crane_id"] =~ /^${Crane_ID:regex}$/)'
                        )
                        t["query"] = q

        unified["panels"].append(p)

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(unified, f, indent=2, ensure_ascii=False)
    
    print("Merged successfully into 'grafana_unified_dashboard.json'")

if __name__ == "__main__":
    merge()
