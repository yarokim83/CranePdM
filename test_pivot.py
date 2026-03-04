from influxdb_client import InfluxDBClient
import sys

client = InfluxDBClient(url="http://localhost:8086", token="my-super-secret-auth-token", org="myorg")
query_api = client.query_api()

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -15m)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "avg_pos" or r["_field"] == "reducer_damage")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group()
  |> keep(columns: ["avg_pos", "reducer_damage", "crane_id"])
'''

print("Executing sanitized pivot query...")
try:
    tables = query_api.query(query)
    count = 0
    for table in tables:
        print("Columns:", [c.label for c in table.columns])
        for row in table.records:
            count += 1
            print(f"{row.values.get('crane_id')} | pos: {row.values.get('avg_pos')} | dmg: {row.values.get('reducer_damage')}")
            
    print(f"Total sanitized records: {count}")
except Exception as e:
    print(f"Error: {e}")
