from influxdb_client import InfluxDBClient

client = InfluxDBClient(url="http://localhost:8086", token="my-super-secret-auth-token", org="myorg")
query_api = client.query_api()

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "avg_pos" or r["_field"] == "reducer_damage")
  |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["avg_pos", "crane_id", "reducer_damage"])
  |> pivot(rowKey:["avg_pos"], columnKey: ["crane_id"], valueColumn: "reducer_damage")
  |> group()
'''

print("Executing wide-format pivot query...")
try:
    tables = query_api.query(query)
    count = 0
    for table in tables:
        print("Columns:", [c.label for c in table.columns])
        for row in table.records:
            count += 1
            print(f"Pos: {row.values.get('avg_pos')} | 212: {row.values.get('ARMGC_212')} | 254: {row.values.get('ARMGC_254')}")
            
    print(f"Total wide records: {count}")
except Exception as e:
    print(f"Error: {e}")
