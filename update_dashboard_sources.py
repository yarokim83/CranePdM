"""Grafana 대시보드 (total_control_tower_v1) 의 모든 패널 source 필터를 변경.

Before: r["source"] == "csv_backup_before_apr9_v24"
After : r["source"] == "v24_unified" or r["source"] == "live_v26"

backup: 변경 전 대시보드 JSON 을 backup_20260428/dashboard_total_control_tower_v1.json 에 저장
"""
import json
import sys
import requests
import re
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

GRAFANA_URL = "http://localhost:3000"
USER = "admin"
PASS = "admin"
DASH_UID = "total_control_tower_v1"
BACKUP_DIR = Path("backup_20260428")

OLD_FILTER = 'r["source"] == "csv_backup_before_apr9_v24"'
NEW_FILTER = '(r["source"] == "v24_unified" or r["source"] == "live_v26")'


def main():
    # 1. 현재 대시보드 가져오기
    r = requests.get(f"{GRAFANA_URL}/api/dashboards/uid/{DASH_UID}", auth=(USER, PASS))
    r.raise_for_status()
    data = r.json()
    dash = data["dashboard"]

    # 2. backup
    BACKUP_DIR.mkdir(exist_ok=True)
    backup_path = BACKUP_DIR / f"dashboard_{DASH_UID}.json"
    with open(backup_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"backup: {backup_path}")

    # 3. 패널 쿼리 수정
    n_changed = 0
    for p in dash.get("panels", []):
        title = p.get("title", "")
        for t in p.get("targets", []):
            q = t.get("query", "") or ""
            if OLD_FILTER in q:
                t["query"] = q.replace(OLD_FILTER, NEW_FILTER)
                n_changed += 1
                print(f"  [PATCH] {title[:55]}")

    print(f"  total panels patched: {n_changed}")

    # 4. id 와 version 처리 (Grafana POST 요구)
    payload = {
        "dashboard": dash,
        "overwrite": True,
        "message": "patch source filter: v24_unified + live_v26 (2026-04-28)",
    }

    r2 = requests.post(f"{GRAFANA_URL}/api/dashboards/db",
                       auth=(USER, PASS),
                       json=payload)
    if r2.status_code == 200:
        print(f"\nOK: {r2.json()}")
    else:
        print(f"\nERROR {r2.status_code}: {r2.text}")


if __name__ == "__main__":
    main()
