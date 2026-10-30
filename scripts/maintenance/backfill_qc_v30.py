import time
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import numpy as np

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)

print("=== STARTING QC SCR V3.0 DATA BACKFILL / MIGRATION ===")

# Query all QC movement records in past 30 days
query = f'''
from(bucket: "{INFLUX_BUCKET}")
    |> range(start: -30d)
    |> filter(fn: (r) => r["_measurement"] == "crane_movement")
    |> filter(fn: (r) => r["crane_type"] == "QC" or r["component"] == "SpreaderCable" or r["crane_id"] =~ /^1.*/)
    |> pivot(rowKey:["_time", "crane_id"], columnKey:["_field"], valueColumn:"_value")
'''

tables = query_api.query(query)
updated_count = 0

points_to_write = []

for t in tables:
    for r in t.records:
        vals = r.values
        crane_id = vals.get("crane_id", "102")
        timestamp = r.get_time()
        
        duration = float(vals.get("duration_s", 1.0))
        old_shock = float(vals.get("shock_penalty", 1.0))
        old_curr = float(vals.get("curr_penalty", 1.0))
        peak_shock = float(vals.get("peak_shock", 0.0))
        avg_weight = float(vals.get("avg_weight", 1.0))
        is_loaded_tag = vals.get("is_loaded", "Empty")
        is_loaded = True if is_loaded_tag == "Loaded" or is_loaded_tag == True else False

        # V3.0 QC SCR Rescaling Logic:
        # 1. Adjust curr_penalty from old GCR scale to Hoist scale
        new_curr = max(1.0, min(5.0, 1.0 + (old_curr - 1.0) * 0.25))
        
        # 2. Calculate load_factor
        w_eff = avg_weight if is_loaded else 1.0
        load_factor = min(3.0, max(1.0, 1.0 + 0.02 * max(0.0, w_eff - 10.0)))
        
        # 3. Shock penalty tuning
        new_shock = max(1.0, old_shock)
        
        # 4. Recalculate Reducer Damage
        new_damage = round(new_shock * new_curr * load_factor * (duration / 10.0), 2)
        
        # Build Point with V3.0 tags and updated fields
        point = (
            Point("crane_movement")
            .time(timestamp)
            .tag("crane_id", crane_id)
            .tag("crane_type", "QC")
            .tag("component", "SpreaderCable")
            .tag("source", "live_qc_v30")
            .tag("algo_version", "3.0.0")
            .tag("is_loaded", "Loaded" if is_loaded else "Empty")
            .field("duration_s", duration)
            .field("peak_order", float(vals.get("peak_order", 0.0)))
            .field("peak_feedback", float(vals.get("peak_feedback", 0.0)))
            .field("max_error", 0.0)
            .field("rms_error", 0.0)
            .field("reducer_damage", new_damage)
            .field("avg_weight", avg_weight)
            .field("shock_penalty", round(new_shock, 3))
            .field("peak_shock", round(peak_shock, 3))
            .field("curr_penalty", round(new_curr, 3))
            .field("track_penalty", round(load_factor, 3)) # CSV/GCR fallback compatibility
            .field("load_factor", round(load_factor, 3))
            .field("start_pos", 0.0)
            .field("end_pos", 0.0)
            .field("avg_pos", 0.0)
            .field("peak_shock_pos", 0.0)
        )
        points_to_write.append(point)
        updated_count += 1

print(f"Parsed {updated_count} historical QC movement records. Writing to InfluxDB with V3.0 formula...")

# Write in batches of 500
batch_size = 500
for i in range(0, len(points_to_write), batch_size):
    batch = points_to_write[i:i + batch_size]
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=batch)
    print(f"Written batch {i // batch_size + 1} / {(len(points_to_write) + batch_size - 1) // batch_size}")

print(f"=== BACKFILL COMPLETED SUCCESSFULLY! Total {updated_count} records migrated to V3.0 ===")
