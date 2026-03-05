import json

def fix_unified():
    print("Loading unified dashboard...")
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    # Global data source replacement
    for panel in dash.get("panels", []):
        if "datasource" in panel and isinstance(panel["datasource"], dict):
            panel["datasource"]["uid"] = "col_cranepdm"
            
        # Fix Flux query variable syntax
        if "targets" in panel:
            for t in panel["targets"]:
                if "query" in t:
                    q = t["query"]
                    # Replace the broken regex syntax with simple array/string match
                    q = q.replace(
                        '|> filter(fn: (r) => r["crane_id"] =~ /^${Crane_ID:regex}$/)',
                        '|> filter(fn: (r) => contains(value: r["crane_id"], set: ${Crane_ID:json}))'
                    )
                    t["query"] = q
                    
    # Fix templating data source
    if "templating" in dash and "list" in dash["templating"]:
        for var in dash["templating"]["list"]:
            if "datasource" in var and isinstance(var["datasource"], dict):
                var["datasource"]["uid"] = "col_cranepdm"

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Fixed data sources and variables!")

if __name__ == "__main__":
    fix_unified()
