import os
import shutil
import csv
from datetime import datetime

# Path Configuration
BASE_DIR = r"c:\Users\huser\.gemini\CranePdM"
DEPLOY_DIR = os.path.join(BASE_DIR, "deploy_package")
BACKUP_DIR = os.path.join(BASE_DIR, "backups")
RAW_DATA_DIR = os.path.join(DEPLOY_DIR, "raw_plc_data")
RAW_BACKUP_DIR = os.path.join(BACKUP_DIR, "raw_plc_data")
KPI_LOG_FILE = os.path.join(DEPLOY_DIR, "crane_kpi_log.csv")
KPI_BACKUP_FILE = os.path.join(BACKUP_DIR, "crane_kpi_log_pre_may15.csv")

def main():
    cutoff_date = datetime(2026, 5, 15)
    print(f"Starting archiving process for data before {cutoff_date.strftime('%Y-%m-%d')}...")

    # 1. Back up raw_plc_data directories
    os.makedirs(RAW_BACKUP_DIR, exist_ok=True)
    moved_dirs = 0

    if os.path.exists(RAW_DATA_DIR):
        for entry in os.listdir(RAW_DATA_DIR):
            dir_path = os.path.join(RAW_DATA_DIR, entry)
            if os.path.isdir(dir_path):
                try:
                    dir_date = datetime.strptime(entry, "%Y-%m-%d")
                    if dir_date < cutoff_date:
                        dest_path = os.path.join(RAW_BACKUP_DIR, entry)
                        if os.path.exists(dest_path):
                            shutil.rmtree(dest_path)
                        shutil.move(dir_path, dest_path)
                        print(f"[RAW BACKUP] Moved directory: {entry}")
                        moved_dirs += 1
                except ValueError:
                    # Skips directories that do not match YYYY-MM-DD
                    pass
        print(f"[RAW BACKUP] Successfully archived {moved_dirs} raw directories.")
    else:
        print(f"[RAW BACKUP] Directory not found: {RAW_DATA_DIR}")

    # 2. Split crane_kpi_log.csv
    if os.path.exists(KPI_LOG_FILE):
        pre_records = []
        post_records = []
        header = None
        
        print(f"Reading {KPI_LOG_FILE}...")
        with open(KPI_LOG_FILE, 'r', newline='', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if not row:
                    continue
                try:
                    # Parsing date from first column: e.g., '2026-03-30 11:10:49'
                    row_date = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    if row_date < cutoff_date:
                        pre_records.append(row)
                    else:
                        post_records.append(row)
                except ValueError:
                    # If parsing fails, treat it as a header
                    header = row

        # Write to backup KPI log file
        if pre_records:
            # If backup file already exists, we will append (though typically it's run once)
            mode = 'a' if os.path.exists(KPI_BACKUP_FILE) else 'w'
            with open(KPI_BACKUP_FILE, mode, newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                if mode == 'w' and header:
                    writer.writerow(header)
                writer.writerows(pre_records)
            print(f"[KPI BACKUP] Archived {len(pre_records)} rows to {KPI_BACKUP_FILE}")
            
        # Write remaining records to a temporary file
        tmp_kpi_file = KPI_LOG_FILE + ".tmp"
        with open(tmp_kpi_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            writer.writerows(post_records)
        
        # Replace the original file atomically
        if os.path.exists(KPI_LOG_FILE):
            os.remove(KPI_LOG_FILE)
        os.rename(tmp_kpi_file, KPI_LOG_FILE)
        print(f"[KPI LOG] Successfully updated {KPI_LOG_FILE}. Remaining rows: {len(post_records)}")
    else:
        print(f"[KPI LOG] File not found: {KPI_LOG_FILE}")

if __name__ == "__main__":
    main()
