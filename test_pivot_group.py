from influxdb_client import InfluxDBClient

client = InfluxDBClient(url="http://localhost:8086", token="my-super-secret-auth-token", org="myorg")
query_api = client.query_api()

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "avg_pos" or r["_field"] == "reducer_damage")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> group(columns: ["crane_id"])
  |> keep(columns: ["avg_pos", "reducer_damage", "crane_id"])
'''

print("Executing test pivot query grouped by crane_id...")
try:
    tables = query_api.query(query)
    count = 0
    t_count = 0
    for table in tables:
        t_count += 1
        print(f"--- Table {t_count} ---")
        for row in table.records:
            count += 1
            print(f"{row.values.get('crane_id')} | pos: {row.values.get('avg_pos')} | dmg: {row.values.get('reducer_damage')}")
            
    print(f"Total pivoted records: {count}")
except Exception as e:
    print(f"Error: {e}")
