"""
Manual runner for the daily Stress alert. The alert logic lives in crane_edge_logger.py
(run_daily_stress_alert_check) so there is a single source of truth.

Usage:
  python scripts/maintenance/send_daily_stress_alert.py [--date YYYY-MM-DD] [--force]
"""
import os
import sys
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import crane_edge_logger as logger


def main():
    parser = argparse.ArgumentParser(description="Crane PdM daily Stress alert (manual run)")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--force", action="store_true", help="Send even if no crane exceeds threshold")
    args = parser.parse_args()
    logger.run_daily_stress_alert_check(args.date, force_send=args.force)


if __name__ == "__main__":
    main()
