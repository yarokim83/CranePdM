from influxdb_client import InfluxDBClient

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org)
query_api = client.query_api()

query = f'''
from(bucket: "{bucket}")
  |> range(start: -3h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "track_penalty" or r["_field"] == "curr_penalty")
  |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
  |> limit(n: 20)
'''
tables = query_api.query(query)
for table in tables:
    for r in table.records:
        print(f"Time: {r.get_time()}, Track: {r.values.get('track_penalty')}, Curr: {r.values.get('curr_penalty')}")
