from influxdb_client import InfluxDBClient
import pandas as pd

client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')
query = '''from(bucket: "cranepdm_kpis") 
|> range(start: 2026-04-28T00:00:00Z, stop: 2026-05-04T23:59:59Z) 
|> filter(fn: (r) => r._measurement == "crane_movement" and r._field == "reducer_damage")
|> pivot(rowKey:["_time", "crane_id", "algo_version"], columnKey: ["_field"], valueColumn: "_value")'''

tables = client.query_api().query(query)
data = []
for t in tables:
    for r in t.records:
        data.append({
            'time': r.get_time(),
            'algo': r.values.get('algo_version'),
            'damage': r.values.get('reducer_damage')
        })

df = pd.DataFrame(data)
df['date'] = df['time'].dt.date
print(df.groupby(['date', 'algo'])['damage'].mean())
