import time
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import pandas as pd
import numpy as np

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)
delete_api = client.delete_api()

print("=== REPROCESSING ALL HISTORICAL QC DATA TO V3.0 ALGORITHM ===")

# 1. Query all QC movement records from the past 90 days
query = f'''
from(bucket: "{INFLUX_BUCKET}")
    |> range(start: -90d)
    |> filter(fn: (r) => r["_measurement"] == "crane_movement")
    |> filter(fn: (r) => r["crane_type"] == "QC" or r["component"] == "SpreaderCable" or r["crane_id"] =~ /^1.*/)
    |> pivot(rowKey:["_time", "crane_id"], columnKey:["_field"], valueColumn:"_value")
'''

print("Fetching historical QC records from InfluxDB...")
tables = query_api.query(query)

records = []
for t in tables:
    for r in t.records:
        records.append(r.values)

df_all = pd.DataFrame(records)
print(f"Total QC records found across all versions: {len(df_all)}")

if df_all.empty:
    print("No historical QC records found.")
    exit(0)

# Deduplicate by (_time, crane_id) to avoid duplicate points from previous partial backfills
df_all = df_all.sort_values(by=['_time']).drop_duplicates(subset=['_time', 'crane_id'], keep='last')
print(f"Unique movement events to reprocess: {len(df_all)}")

points_to_write = []

for idx, row in df_all.iterrows():
    crane_id = str(row.get("crane_id", "102"))
    timestamp = row.get("_time")
    
    duration = float(row.get("duration_s", 1.0))
    old_shock = float(row.get("shock_penalty", 1.0))
    old_curr = float(row.get("curr_penalty", 1.0))
    peak_shock = float(row.get("peak_shock", 0.0))
    avg_weight = float(row.get("avg_weight", 1.0))
    
    is_loaded_val = row.get("is_loaded", "Empty")
    is_loaded = True if is_loaded_val in ["Loaded", True, 1, "1"] else False
    
    algo_ver = str(row.get("algo_version", ""))
    
    # Check if this record already has V3.0 curr_penalty scale (i.e. <= 5.0)
    # If old_curr > 5.0, it was calculated using old V2.6 GCR formula
    if old_curr > 5.0:
        new_curr = max(1.0, min(5.0, 1.0 + (old_curr - 1.0) * 0.25))
    else:
        new_curr = max(1.0, min(5.0, old_curr))
        
    # Calculate V3.0 load_factor
    w_eff = avg_weight if is_loaded else 1.0
    load_factor = min(3.0, max(1.0, 1.0 + 0.02 * max(0.0, w_eff - 10.0)))
    
    # Calculate V3.0 shock_penalty
    new_shock = max(1.0, old_shock)
    
    # Calculate V3.0 Reducer Damage
    # V3.0 Formula: shock_penalty * curr_penalty * load_factor * (duration_s / 10.0)
    new_damage = round(new_shock * new_curr * load_factor * (duration / 10.0), 2)
    
    point = (
        Point("crane_movement")
        .time(timestamp)
        .tag("crane_id", crane_id)
        .tag("crane_type", "QC")
        .tag("component", "SpreaderCable")
        .tag("source", "live_qc_v30")
        .tag("algo_version", "3.0.0")
        .tag("is_loaded", "Loaded" if is_loaded else "Empty")
        .field("duration_s", round(duration, 2))
        .field("peak_order", float(row.get("peak_order", 0.0)))
        .field("peak_feedback", float(row.get("peak_feedback", 0.0)))
        .field("max_error", 0.0)
        .field("rms_error", 0.0)
        .field("reducer_damage", new_damage)
        .field("avg_weight", round(avg_weight, 1))
        .field("shock_penalty", round(new_shock, 3))
        .field("peak_shock", round(peak_shock, 3))
        .field("curr_penalty", round(new_curr, 3))
        .field("track_penalty", round(load_factor, 3))
        .field("load_factor", round(load_factor, 3))
        .field("start_pos", 0.0)
        .field("end_pos", 0.0)
        .field("avg_pos", 0.0)
        .field("peak_shock_pos", 0.0)
    )
    points_to_write.append(point)

print("Clearing old QC records from InfluxDB (live_v26 QC and live_qc_v26)...")
start_time = "1970-01-01T00:00:00Z"
stop_time = "2030-01-01T00:00:00Z"

try:
    delete_api.delete(start_time, stop_time, '_measurement="crane_movement" AND source="live_qc_v26"', bucket=INFLUX_BUCKET, org=INFLUX_ORG)
    print("Deleted live_qc_v26 records.")
except Exception as e:
    print("Error deleting live_qc_v26:", e)

try:
    delete_api.delete(start_time, stop_time, '_measurement="crane_movement" AND crane_type="QC" AND source="live_v26"', bucket=INFLUX_BUCKET, org=INFLUX_ORG)
    print("Deleted live_v26 QC records.")
except Exception as e:
    print("Error deleting live_v26 QC:", e)

print(f"Writing {len(points_to_write)} recalculated V3.0 points to InfluxDB...")

batch_size = 500
for i in range(0, len(points_to_write), batch_size):
    batch = points_to_write[i:i + batch_size]
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=batch)
    if (i // batch_size + 1) % 20 == 0 or i + batch_size >= len(points_to_write):
        print(f"Batch {i // batch_size + 1} / {(len(points_to_write) + batch_size - 1) // batch_size} written.")

print("=== REPROCESSING COMPLETE! All historical QC records migrated to V3.0 ===")
