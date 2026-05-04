import json
import sys

files = [
    r"c:\Users\huser\.gemini\CranePdM\grafana_v2_dashboard.json",
    r"c:\Users\huser\.gemini\CranePdM\grafana_v2_detail_dashboard.json"
]

for f in files:
    try:
        with open(f, 'r', encoding='utf-8') as fh:
            json.load(fh)
        print(f"OK: {f.split(chr(92))[-1]}")
    except Exception as e:
        print(f"FAIL: {f.split(chr(92))[-1]} -> {e}")
        sys.exit(1)

print("\nAll dashboard JSONs are valid!")
