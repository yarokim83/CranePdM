"""
Backup all InfluxDB data before April 9th to a CSV file, then delete from DB.
Original crane_kpi_log.csv is NOT touched (AI_GUIDE rule).
"""
from influxdb_client import InfluxDBClient
from influxdb_client.client.delete_api import DeleteApi
import csv
from datetime import datetime

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org, timeout=300000)
query_api = client.query_api()
delete_api = client.delete_api()

backup_file = r"c:\Users\huser\.gemini\CranePdM\backup_before_apr9.csv"

# Step 1: Export all data before April 9
print("Step 1: Exporting pre-April 9 data to backup CSV...")
q = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-03-01T00:00:00Z, stop: 2026-04-09T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
'''
tables = query_api.query(q)

records = []
for table in tables:
    for r in table.records:
        records.append(dict(r.values))

print(f"  Found {len(records)} records to backup.")

if records:
    # Get all field names
    all_keys = set()
    for rec in records:
        all_keys.update(rec.keys())
    all_keys = sorted(all_keys)
    
    with open(backup_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=all_keys)
        writer.writeheader()
        writer.writerows(records)
    print(f"  Saved to: {backup_file}")

# Step 2: Verify backup
with open(backup_file, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    line_count = sum(1 for _ in reader) - 1  # exclude header
print(f"  Backup verification: {line_count} rows in CSV.")

# Step 3: Delete from InfluxDB
print("\nStep 2: Deleting pre-April 9 data from InfluxDB...")
delete_api.delete(
    start="2026-03-01T00:00:00Z",
    stop="2026-04-09T00:00:00Z",
    predicate='_measurement="crane_movement"',
    bucket=bucket,
    org=org
)
print("  Deleted.")

# Step 4: Verify deletion
print("\nStep 3: Verifying deletion...")
q_verify = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-03-01T00:00:00Z, stop: 2026-04-09T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "shock_penalty")
  |> count()
'''
tables_v = query_api.query(q_verify)
total = 0
for table in tables_v:
    for r in table.records:
        total += r.get_value()
print(f"  Remaining records before April 9: {total}")

# Step 5: Check remaining data range
q_range = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-03-01T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "shock_penalty")
  |> keep(columns: ["_time"])
  |> first()
'''
tables_r = query_api.query(q_range)
for table in tables_r:
    for r in table.records:
        print(f"  Earliest remaining record: {r.get_time()}")

print("\nDone! Pre-April 9 data backed up and removed from DB.")
