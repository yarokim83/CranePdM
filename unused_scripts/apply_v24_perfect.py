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
delete_api = client.delete_api()

print("1. Reading all historical V2.3 data...")

query = f'''
from(bucket: "{bucket}")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["algo_version"] == "2.3")
'''
tables = query_api.query(query)

points_dict = {}

for table in tables:
    for record in table.records:
        # We group by timestamp, crane_id, is_loaded
        ts = record.get_time()
        crane_id = record.values.get('crane_id')
        is_loaded = record.values.get('is_loaded')
        field = record.get_field()
        value = record.get_value()
        
        key = (ts, crane_id, is_loaded)
        if key not in points_dict:
            points_dict[key] = {}
        points_dict[key][field] = value

print(f"Read {len(points_dict)} unique historical trips.")
print("2. Computing V2.4 amplified shock and writing new points...")

points = []
points_written = 0

for key, fields in points_dict.items():
    ts, crane_id, is_loaded = key
    
    peak_shock = fields.get('peak_shock', 1.0)
    peak_order = fields.get('peak_order', 10000.0)
    old_shock_penalty = fields.get('shock_penalty', 1.0)
    old_damage = fields.get('reducer_damage', 0.0)
    
    # V2.4 Speed-Normalized Shock Amplification
    speed_factor_shock = max(0.3, abs(peak_order) / 10000.0)
    new_shock_penalty = 1.0 + (peak_shock - 1.0) / speed_factor_shock
    
    # Adjust damage
    multiplier = new_shock_penalty / max(1.0, old_shock_penalty)
    new_damage = old_damage * multiplier
    
    def safe_float(val, default=0.0):
        return float(val) if val is not None else default
        
    p = {
        "measurement": "crane_movement",
        "tags": {
            "crane_id": str(crane_id),
            "algo_version": "2.4",  # Upgrade tag to 2.4
            "is_loaded": str(is_loaded)
        },
        "time": ts, # Python datetime (microsecond precision)
        "fields": {
            "reducer_damage": float(new_damage),
            "shock_penalty": float(new_shock_penalty),
            # KEEP curr and track as original (AVERAGE from V2.3)
            "curr_penalty": safe_float(fields.get('curr_penalty')),
            "track_penalty": safe_float(fields.get('track_penalty')),
            
            "duration_s": safe_float(fields.get('duration_s')),
            "peak_order": safe_float(fields.get('peak_order')),
            "peak_feedback": safe_float(fields.get('peak_feedback')),
            "max_error": safe_float(fields.get('max_error')),
            "rms_error": safe_float(fields.get('rms_error')),
            "avg_weight": safe_float(fields.get('avg_weight')),
            "peak_shock": safe_float(fields.get('peak_shock')),
            "peak_shock_pos": safe_float(fields.get('peak_shock_pos')),
            "start_pos": safe_float(fields.get('start_pos')),
            "end_pos": safe_float(fields.get('end_pos')),
            "avg_pos": safe_float(fields.get('avg_pos'))
        }
    }
    points.append(p)
    points_written += 1
    
    if len(points) >= 2000:
        write_api.write(bucket=bucket, org=org, record=points)
        points = []

if points:
    write_api.write(bucket=bucket, org=org, record=points)

print(f"Successfully wrote {points_written} upgraded V2.4 records!")

print("3. Deleting old V2.3 data to prevent duplication...")
start = "2020-01-01T00:00:00Z"
stop = "2026-04-24T03:03:00Z"
predicate = '_measurement="crane_movement" AND algo_version="2.3"'
delete_api.delete(start, stop, predicate, bucket=bucket, org=org)
print("Delete successful! Database upgrade to V2.4 is complete.")
