import pandas as pd
from influxdb_client import InfluxDBClient
client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')
query = '''from(bucket: "cranepdm_kpis") 
|> range(start: 2026-04-30T00:00:00Z, stop: 2026-05-04T23:59:59Z) 
|> filter(fn: (r) => r._measurement == "crane_movement" and r.source == "live_v26")
|> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")'''
tables = client.query_api().query(query)
data = []
for t in tables:
    for r in t.records:
        row = {'_time': r.get_time(), 'crane_id': r.values.get('crane_id'), 'algo_version': r.values.get('algo_version')}
        for k, v in r.values.items():
            if k not in ['_time', 'crane_id', 'algo_version', 'result', 'table', '_start', '_stop', '_measurement', 'source']:
                row[k] = v
        data.append(row)

df = pd.DataFrame(data)
df.to_csv('backup_influx_430_504.csv', index=False)
print(f"Backed up {len(df)} records to backup_influx_430_504.csv")
