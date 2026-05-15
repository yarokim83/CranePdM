import pandas as pd
from influxdb_client import InfluxDBClient

client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')

# Check crane 235 curr_penalty across dates
query = '''from(bucket: "cranepdm_kpis") 
|> range(start: 2026-04-20T00:00:00Z, stop: 2026-05-04T23:59:59Z) 
|> filter(fn: (r) => r._measurement == "crane_movement" and r.crane_id == "235" and r.source == "live_v26")
|> filter(fn: (r) => r._field == "shock_penalty" or r._field == "curr_penalty" or r._field == "track_penalty")
|> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'''

tables = client.query_api().query(query)
data = []
for t in tables:
    for r in t.records:
        data.append({
            'date': r.get_time().date(),
            'shock': r.values.get('shock_penalty'),
            'curr': r.values.get('curr_penalty'),
            'track': r.values.get('track_penalty'),
        })

df = pd.DataFrame(data)
df['stress_index'] = df['shock'] * df['curr'] * df['track']

print("=== Crane 235 - Daily Averages ===")
print(df.groupby('date')[['shock', 'curr', 'track', 'stress_index']].mean().to_string())
print("\n=== Crane 235 - Daily Count ===")
print(df.groupby('date').size())
