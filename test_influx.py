from influxdb_client import InfluxDBClient
import sys

client = InfluxDBClient(url="http://localhost:8086", token="my-super-secret-auth-token", org="myorg")
query_api = client.query_api()

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -3h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "reducer_damage")
  |> keep(columns: ["_time", "_value", "crane_id"])
  |> limit(n: 10)
'''

print("Executing query...")
tables = query_api.query(query)
count = 0
for table in tables:
    for row in table.records:
        count += 1
        print(f"{row.values.get('_time')} | {row.values.get('crane_id')} | {row.values.get('_value')}")
        
if count == 0:
    print("No data found!")
else:
    print(f"Total {count} records found.")
