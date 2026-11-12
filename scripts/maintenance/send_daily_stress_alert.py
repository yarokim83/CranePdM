"""
Runner for the daily Stress alert (CLI & Scheduled Task fallback).
Uses crane_edge_logger.run_daily_stress_alert_check() with v3.2.4 isolated InfluxDBClient (enable_gzip=False).

Usage:
  python scripts/maintenance/send_daily_stress_alert.py [--date YYYY-MM-DD] [--force] [--scheduled]
"""
import os
import sys
import argparse
from datetime import datetime, timedelta, timezone

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEPLOY_DIR = os.path.join(ROOT_DIR, "deploy_package")
sys.path.insert(0, ROOT_DIR)

if os.path.isdir(DEPLOY_DIR):
    os.chdir(DEPLOY_DIR)

import crane_edge_logger as logger


def main():
    parser = argparse.ArgumentParser(description="Crane PdM daily Stress alert")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--force", action="store_true", help="Send even if no crane exceeds threshold")
    parser.add_argument("--scheduled", action="store_true", help="Check state file to avoid duplicate send on same day")
    args = parser.parse_args()

    if args.scheduled and not args.date and not args.force:
        KST = timezone(timedelta(hours=9))
        today_str = datetime.now(KST).strftime("%Y-%m-%d")
        if os.path.exists(logger.ALERT_STATE_FILE):
            try:
                with open(logger.ALERT_STATE_FILE, "r", encoding="utf-8") as f:
                    if f.read().strip() == today_str:
                        return
            except Exception:
                pass
        logger.run_daily_stress_alert_check(None, force_send=False)
        with open(logger.ALERT_STATE_FILE, "w", encoding="utf-8") as f:
            f.write(today_str)
    else:
        logger.run_daily_stress_alert_check(args.date, force_send=args.force)


if __name__ == "__main__":
    main()
