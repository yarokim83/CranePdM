from influxdb_client import InfluxDBClient
import sys

client = InfluxDBClient(url="http://localhost:8086", token="my-super-secret-auth-token", org="myorg")
query_api = client.query_api()

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "avg_pos")
  |> keep(columns: ["_time", "_value", "crane_id"])
'''

print("Checking recent avg_pos values in InfluxDB...")
try:
    tables = query_api.query(query)
    count = 0
    for table in tables:
        for row in table.records:
            count += 1
            print(f"{row.values.get('_time')} | {row.values.get('crane_id')} | avg_pos: {row.values.get('_value')}")
            
    if count == 0:
        print("No movement events recorded in the last 15 minutes, or avg_pos field is missing.")
    else:
        print(f"Total {count} records found.")
except Exception as e:
    print(f"Error querying InfluxDB: {e}")
