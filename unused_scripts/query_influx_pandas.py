from influxdb_client import InfluxDBClient
import pandas as pd

client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')
query = '''from(bucket: "cranepdm_kpis") 
|> range(start: 2026-04-26T00:00:00Z, stop: 2026-05-04T23:59:59Z) 
|> filter(fn: (r) => r._measurement == "crane_movement" and r._field == "reducer_damage")'''

tables = client.query_api().query(query)
data = []
for t in tables:
    for r in t.records:
        if r.get_value() is not None:
            data.append({'time': r.get_time(), 'damage': r.get_value()})

if data:
    df = pd.DataFrame(data)
    df['date'] = df['time'].dt.date
    print(df.groupby('date')['damage'].mean())
else:
    print("No data")
