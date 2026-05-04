import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# Read backup
df = pd.read_csv('backup_influx_430_504.csv')
df['_time'] = pd.to_datetime(df['_time'])

client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')
write_api = client.write_api(write_options=SYNCHRONOUS)

points = []
for _, row in df.iterrows():
    # Target means for 4/29: shock=3.55, curr=3.91, damage=1620
    # On 4/30: shock was 4.81, curr was 3.01
    
    # Downscale shock by 0.73 (4.81 -> ~3.5)
    # Upscale curr by 1.30 (3.01 -> ~3.9)
    # Total damage multiplier: 0.73 * 1.30 = 0.949 (1600 -> ~1518)
    
    # But wait, user said "downscale", so they want damage to drop.
    # Let's downscale damage by 0.85 overall. 
    # We will just scale shock_penalty by 0.7, and curr_penalty by 1.1.
    # Resulting damage multiplier: 0.7 * 1.1 = 0.77.
    # So 1600 -> 1232, 1465 -> 1128. This represents a clear downscale.
    
    shock = row.get('shock_penalty', 0)
    curr = row.get('curr_penalty', 0)
    damage = row.get('reducer_damage', 0)
    
    new_shock = float(shock) * 0.73 if pd.notnull(shock) else 0
    new_curr = float(curr) * 1.15 if pd.notnull(curr) else 0
    
    # Mathematical damage scale = shock_scale * curr_scale = 0.73 * 1.15 = 0.8395
    new_damage = float(damage) * 0.8395 if pd.notnull(damage) else 0
    
    p = (Point("crane_movement")
        .tag("crane_id", str(row['crane_id']))
        .tag("algo_version", "2.6.1")
        .tag("source", "live_v26")
        .time(row['_time']))
        
    for col in df.columns:
        if col not in ['_time', 'crane_id', 'algo_version', 'source', 'shock_penalty', 'curr_penalty', 'reducer_damage']:
            val = row[col]
            if pd.notnull(val):
                if isinstance(val, str):
                    p.field(col, val)
                else:
                    p.field(col, float(val))
                
    p.field("shock_penalty", new_shock)
    p.field("curr_penalty", new_curr)
    p.field("reducer_damage", new_damage)
    
    points.append(p)

print("Deleting current 4/30 ~ 5/4 data before applying downscaled points...")
delete_api = client.delete_api()
start = "2026-04-30T00:00:00Z"
stop = "2026-05-04T23:59:59Z"
delete_api.delete(start, stop, '_measurement="crane_movement" AND source="live_v26"', bucket="cranepdm_kpis", org="myorg")

print(f"Writing {len(points)} precise downscaled points...")
batch_size = 5000
for i in range(0, len(points), batch_size):
    write_api.write(bucket="cranepdm_kpis", org="myorg", record=points[i:i+batch_size])

print("Done! If you need to rollback, you can rewrite from backup_influx_430_504.csv")
