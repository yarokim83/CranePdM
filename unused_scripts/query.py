from influxdb_client import InfluxDBClient
client = InfluxDBClient(url='http://localhost:8086', token='my-super-secret-auth-token', org='myorg')
query = '''from(bucket: "cranepdm_kpis") 
|> range(start: 2026-04-28T00:00:00Z, stop: 2026-05-04T23:59:59Z) 
|> filter(fn: (r) => r._measurement == "crane_movement" and r._field == "reducer_damage") 
|> aggregateWindow(every: 1d, fn: mean)'''
tables = client.query_api().query(query)
for t in tables:
    for r in t.records:
        if r.get_value() is not None:
            print(f"{r.get_time()} {r.values.get('crane_id')} {r.get_value()}")
