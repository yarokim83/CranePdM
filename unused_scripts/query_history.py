import pandas as pd
from influxdb_client import InfluxDBClient
client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')
query = '''from(bucket: "cranepdm_kpis") 
|> range(start: 2026-04-20T00:00:00Z, stop: 2026-05-04T23:59:59Z) 
|> filter(fn: (r) => r._measurement == "crane_movement" and r._field == "reducer_damage") 
|> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")'''
tables = client.query_api().query(query)
data = [{'date': r.get_time().date(), 'damage': r.values.get('reducer_damage')} for t in tables for r in t.records]
df = pd.DataFrame(data)
print('Mean:\n', df.groupby('date').mean())
print('Count:\n', df.groupby('date').count())
