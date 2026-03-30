import influxdb_client
import pandas as pd

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"

client = influxdb_client.InfluxDBClient(url=url, token=token, org=org, timeout=60000)
query_api = client.query_api()

print("1. Find movements with max_error > 9500")
q1 = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "max_error" and r["_value"] > 9500.0)
  |> sort(columns: ["_time"], desc: true)
  |> limit(n: 1)
'''
tables = query_api.query(q1)
if not tables:
    print("No large gap found.")
    exit(0)

# Found the movement
movement = tables[0].records[0]
end_time = movement.get_time()
crane_id = movement.values.get("crane_id")
print(f"Found movement ending at {end_time} on crane {crane_id}")

# Fetch raw data around that time
# The edge logger chunks movements when db170_start_cmd changes or db11_gantry_speed > 0
print("2. Fetching raw data for that movement...")
# Let's get -2 mins to +1 min from the movement end time
q2 = f'''
from(bucket: "cranepdm_raw")
  |> range(start: 2026-03-01T00:00:00Z, stop: now())
  |> filter(fn: (r) => r["_measurement"] == "crane_data")
  |> filter(fn: (r) => r["crane_id"] == "{crane_id}")
  |> filter(fn: (r) => r["_field"] == "db11_gantry_fbspeed" or r["_field"] == "db11_gantry_speed" or r["_field"] == "db170_run_cmd" or r["_field"] == "db170_fault" or r["_field"] == "db170_inverter_status")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
'''

try:
    df = query_api.query_data_frame(q2)
    if isinstance(df, list):
        df = pd.concat(df)
    
    # filter around end time
    df['_time'] = pd.to_datetime(df['_time'])
    end_dt = pd.to_datetime(end_time)
    mask = (df['_time'] >= end_dt - pd.Timedelta(seconds=120)) & (df['_time'] <= end_dt + pd.Timedelta(seconds=10))
    df = df[mask]
    
    df = df.sort_values('_time')
    
    # Let's find exactly the points where difference > 9500
    df['diff'] = abs(df['db11_gantry_speed'] - df['db11_gantry_fbspeed'])
    
    gap_points = df[df['diff'] > 9500]
    
    print("\n--- Rows where abs(Order - Feedback) > 9500 ---")
    print(gap_points[['_time', 'db11_gantry_speed', 'db11_gantry_fbspeed', 'diff', 'db170_run_cmd', 'db170_inverter_status']].to_string(index=False))
    
    # Print the 5 seconds before and after the FIRST huge gap point
    if not gap_points.empty:
        first_gap_time = gap_points['_time'].iloc[0]
        context = df[(df['_time'] >= first_gap_time - pd.Timedelta(seconds=5)) & (df['_time'] <= first_gap_time + pd.Timedelta(seconds=5))]
        print("\n--- Context (5s before/after the 10000 gap) ---")
        print(context[['_time', 'db11_gantry_speed', 'db11_gantry_fbspeed', 'diff', 'db170_run_cmd']].to_string(index=False))

except Exception as e:
    print("Error getting dataframe:", e)
