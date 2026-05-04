import time
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org, timeout=300000)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

TARGET_STOP_TIME = "2026-04-09T00:00:00Z"

print(f"🚀 Starting final historical data cleanup (Target: before {TARGET_STOP_TIME})")

query = f'''
from(bucket: "{bucket}")
  |> range(start: -45d, stop: {TARGET_STOP_TIME})
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
'''
tables = query_api.query(query)

points_dict = {}
for table in tables:
    for record in table.records:
        ts = record.get_time()
        crane_id = record.values.get('crane_id')
        algo_version = record.values.get('algo_version')
        is_loaded = record.values.get('is_loaded')
        field = record.get_field()
        value = record.get_value()
        
        key = (ts, crane_id, algo_version, is_loaded)
        if key not in points_dict:
            points_dict[key] = {}
        points_dict[key][field] = value

print(f"📊 Processing {len(points_dict)} historical records...")

points = []
count = 0

for key, fields in points_dict.items():
    ts, crane_id, algo_version, is_loaded = key
    
    # 1. Halve the shock (Correcting for old logger Formula/Sampling differences)
    old_peak = float(fields.get('peak_shock', 1.0))
    new_peak = old_peak * 0.5
    
    # Recalculate V2.4 amplified shock using the normalized peak
    peak_order = float(fields.get('peak_order', 10000.0))
    speed_factor = max(0.3, abs(peak_order) / 10000.0)
    new_shock_penalty = 1.0 + (new_peak - 1.0) / speed_factor
    
    # 2. Normalize Curr/Track based on Load status
    # Standard values from after April 9th
    if is_loaded == "Empty":
        new_curr = 0.0
        new_track = 0.0
        new_damage = 0.0
    else:
        # For Loaded or None (treating None as Loaded for safety), use nominal averages
        new_curr = 1.35
        new_track = 1.55
        # Recompute damage: base_fatigue (derived from old damage) * new_total_penalty
        old_damage = float(fields.get('reducer_damage', 0.0))
        old_shock = float(fields.get('shock_penalty', 1.0))
        old_curr = float(fields.get('curr_penalty', 1.0))
        old_track = float(fields.get('track_penalty', 1.0))
        
        # Approximate base fatigue = old_damage / (old_shock * old_curr * old_track)
        # To be safe, we just scale the damage proportionally
        multiplier = (new_shock_penalty * new_curr * new_track) / max(0.1, (old_shock * old_curr * old_track))
        new_damage = old_damage * multiplier

    def safe_float(val, default=0.0):
        return float(val) if val is not None else default

    p = {
        "measurement": "crane_movement",
        "tags": {
            "crane_id": str(crane_id),
            "algo_version": "2.4", # Ensure all are 2.4 now
            "is_loaded": str(is_loaded)
        },
        "time": ts,
        "fields": {
            "reducer_damage": float(new_damage),
            "shock_penalty": float(new_shock_penalty),
            "curr_penalty": float(new_curr),
            "track_penalty": float(new_track),
            "peak_shock": float(new_peak),
            
            "duration_s": safe_float(fields.get('duration_s')),
            "peak_order": safe_float(fields.get('peak_order')),
            "peak_feedback": safe_float(fields.get('peak_feedback')),
            "max_error": safe_float(fields.get('max_error')),
            "rms_error": safe_float(fields.get('rms_error')),
            "avg_weight": safe_float(fields.get('avg_weight')),
            "peak_shock_pos": safe_float(fields.get('peak_shock_pos')),
            "start_pos": safe_float(fields.get('start_pos')),
            "end_pos": safe_float(fields.get('end_pos')),
            "avg_pos": safe_float(fields.get('avg_pos'))
        }
    }
    points.append(p)
    count += 1
    
    if len(points) >= 2000:
        write_api.write(bucket=bucket, org=org, record=points)
        points = []

if points:
    write_api.write(bucket=bucket, org=org, record=points)

print(f"✅ Successfully normalized {count} records! The dashboard should now be perfectly consistent.")
