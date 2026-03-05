from influxdb_client import InfluxDBClient

client = InfluxDBClient(url="http://localhost:8086", token="my-super-secret-auth-token", org="myorg")
query_api = client.query_api()

print("--- Testing Bar Chart Query ---")
query_bar = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "reducer_damage")
  |> group(columns: ["crane_id"])
  |> mean()
  |> group()
  |> keep(columns: ["crane_id", "_value"])
'''
try:
    tables = query_api.query(query_bar)
    for table in tables:
        print("Columns:", [c.label for c in table.columns])
        for row in table.records:
            print(f"crane_id: {row.values.get('crane_id')} (type: {type(row.values.get('crane_id'))}) | value: {row.values.get('_value')} (type: {type(row.values.get('_value'))})")
except Exception as e:
    print(f"Error: {e}")

print("\n--- Testing Stat Query ---")
query_stat = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -1h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "reducer_damage")
  |> group(columns: ["crane_id"])
  |> mean()
  |> rename(columns: {_value: "damage"})
  |> yield(name: "crane_id")
'''
try:
    tables = query_api.query(query_stat)
    for table in tables:
        print("Columns:", [c.label for c in table.columns])
        for row in table.records:
            print(row.values)
except Exception as e:
    print(f"Error: {e}")
