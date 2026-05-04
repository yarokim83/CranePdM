"""
Remove CSV-origin duplicate records from April 22.
Strategy: 
1. Query ALL April 22 data
2. Separate real-time (has microseconds) from CSV-origin (no microseconds)
3. Delete entire April 22 date range
4. Re-insert only real-time records
"""
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS
from influxdb_client.client.delete_api import DeleteApi
import pandas as pd

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org, timeout=300000)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)
delete_api = client.delete_api()

# Step 1: Backup all April 22 real-time data (microsecond > 0)
print("Step 1: Backing up real-time April 22 data...")
q = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-04-22T00:00:00Z, stop: 2026-04-23T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
'''
tables = query_api.query(q)

realtime_records = []
csv_records = []
all_fields = set()

for table in tables:
    for r in table.records:
        rec = dict(r.values)
        if r.get_time().microsecond > 0:
            realtime_records.append(rec)
        else:
            csv_records.append(rec)

print(f"  Real-time records: {len(realtime_records)}")
print(f"  CSV-origin records to remove: {len(csv_records)}")

# Step 2: Delete ALL April 22 data
print("\nStep 2: Deleting ALL April 22 data...")
delete_api.delete(
    start="2026-04-22T00:00:00Z",
    stop="2026-04-23T00:00:00Z",
    predicate='_measurement="crane_movement"',
    bucket=bucket,
    org=org
)
print("  Deleted.")

# Step 3: Re-insert only real-time records
print("\nStep 3: Re-inserting real-time records...")

# Build InfluxDB points from the backed up records
points = []
field_names = ['duration_s', 'peak_order', 'peak_feedback', 'max_error', 'rms_error',
               'reducer_damage', 'avg_weight', 'shock_penalty', 'peak_shock',
               'curr_penalty', 'track_penalty', 'start_pos', 'end_pos', 'avg_pos',
               'peak_shock_pos', 'peak_order']

for rec in realtime_records:
    fields = {}
    for fn in field_names:
        if fn in rec and rec[fn] is not None:
            try:
                fields[fn] = float(rec[fn])
            except (ValueError, TypeError):
                pass
    
    if not fields:
        continue
    
    tags = {
        'crane_id': str(rec.get('crane_id', '')),
        'algo_version': str(rec.get('algo_version', '2.4')),
        'is_loaded': str(rec.get('is_loaded', 'Empty'))
    }
    
    p = {
        "measurement": "crane_movement",
        "tags": tags,
        "time": rec['_time'],
        "fields": fields
    }
    points.append(p)

# Write in batches
batch_size = 500
for i in range(0, len(points), batch_size):
    batch = points[i:i+batch_size]
    write_api.write(bucket=bucket, org=org, record=batch)

print(f"  Re-inserted {len(points)} real-time records.")

# Step 4: Verify
print("\nStep 4: Verifying...")
q_verify = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-04-22T00:00:00Z, stop: 2026-04-23T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "shock_penalty")
  |> count()
'''
tables_v = query_api.query(q_verify)
for table in tables_v:
    for r in table.records:
        print(f"  Remaining records: {r.get_value()}")

print("\nDone! CSV duplicate data removed from April 22.")
