import json

def fix_query_regex():
    with open("grafana_unified_dashboard.json", "r", encoding="utf-8") as f:
        dash = json.load(f)

    for panel in dash.get("panels", []):
        if "targets" in panel:
            for t in panel["targets"]:
                if "query" in t:
                    q = t["query"]
                    # This is the ONLY 100% reliable way to handle Grafana multi-value / All variables in Flux
                    if 'r["crane_id"] =~ /^${Crane_ID:regex}$/' in q:
                        q = q.replace(
                            '|> filter(fn: (r) => r["crane_id"] =~ /^${Crane_ID:regex}$/)',
                            '|> filter(fn: (r) => r["crane_id"] =~ /${Crane_ID:regex}/)'
                        )
                        t["query"] = q

    # Also make sure the variable definition handles ALL correctly
    if "templating" in dash and "list" in dash["templating"]:
        for var in dash["templating"]["list"]:
            if var["name"] == "Crane_ID":
                # Grafana Custom All value for Regex
                var["current"] = {"selected": False, "text": "All", "value": "$__all"}
                var["includeAll"] = True
                var["customAllValue"] = ".*" # This is the missing piece!! It forces $__all to be .* for the regex

    with open("grafana_unified_dashboard.json", "w", encoding="utf-8") as f:
        json.dump(dash, f, indent=2, ensure_ascii=False)
    
    print("Fixed Flux regex and Custom All Value!")

if __name__ == "__main__":
    fix_query_regex()
