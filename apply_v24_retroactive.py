import time
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

print("Applying V2.4 Algorithm retroactively to ALL historical InfluxDB data...")

query = f'''
from(bucket: "{bucket}")
  |> range(start: -3d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
'''
tables = query_api.query(query)

points = []
points_updated = 0

for table in tables:
    for record in table.records:
        algo_version = record.values.get('algo_version')
        if algo_version == "2.4":
            pass # We want to overwrite to ensure consistency
            
        crane_id = record.values.get('crane_id')
        peak_order = record.values.get('peak_order', 10000.0)
        old_shock_penalty = record.values.get('shock_penalty', 1.0)
        old_curr_penalty = record.values.get('curr_penalty', 1.0)
        peak_shock = record.values.get('peak_shock', 1.0)
        old_damage = record.values.get('reducer_damage', 0.0)
        avg_pos = record.values.get('avg_pos', 0.0)
        
        if old_damage == 0 or old_damage is None:
            continue
            
        old_shock_penalty = max(1.0, old_shock_penalty) if old_shock_penalty is not None else 1.0
        old_curr_penalty = max(1.0, old_curr_penalty) if old_curr_penalty is not None else 1.0
        peak_order = peak_order if peak_order is not None else 10000.0
        peak_shock = peak_shock if peak_shock is not None else 1.0
        avg_pos = avg_pos if avg_pos is not None else 0.0
        
        speed_factor_shock = max(0.3, abs(peak_order) / 10000.0)
        new_shock_penalty = 1.0 + (peak_shock - 1.0) / speed_factor_shock
        
        speed_factor_curr = max(0.5, abs(peak_order) / 10000.0)
        new_curr_penalty = 1.0 + (old_curr_penalty - 1.0) / speed_factor_curr
        
        geo_penalty = 2.0 if 2400.0 <= avg_pos <= 2700.0 else 1.0
        
        multiplier = (new_shock_penalty / old_shock_penalty) * (new_curr_penalty / old_curr_penalty) * geo_penalty
        new_damage = old_damage * multiplier
        
        def safe_float(val, default=0.0):
            return float(val) if val is not None else default
            
        p = {
            "measurement": "crane_movement",
            "tags": {
                "crane_id": str(crane_id),
                "algo_version": "2.4",
                "is_loaded": record.values.get('is_loaded', "Empty")
            },
            "time": record.get_time(),
            "fields": {
                "reducer_damage": float(new_damage),
                "shock_penalty": float(new_shock_penalty),
                "curr_penalty": float(new_curr_penalty),
                "track_penalty": float(geo_penalty),
                "duration_s": safe_float(record.values.get('duration_s')),
                "peak_order": float(peak_order),
                "peak_feedback": safe_float(record.values.get('peak_feedback')),
                "max_error": safe_float(record.values.get('max_error')),
                "rms_error": safe_float(record.values.get('rms_error')),
                "avg_weight": safe_float(record.values.get('avg_weight')),
                "peak_shock": float(peak_shock),
                "peak_shock_pos": safe_float(record.values.get('peak_shock_pos')),
                "start_pos": safe_float(record.values.get('start_pos')),
                "end_pos": safe_float(record.values.get('end_pos')),
                "avg_pos": float(avg_pos)
            }
        }
        points.append(p)
        points_updated += 1
        
        if len(points) >= 2000:
            write_api.write(bucket=bucket, org=org, record=points)
            print(f"Written {points_updated} points...")
            points = []

if points:
    write_api.write(bucket=bucket, org=org, record=points)
    print(f"Written {points_updated} points...")

print(f"Successfully updated {points_updated} old historical records to V2.4 logic in InfluxDB!")
