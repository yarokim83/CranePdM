import time
from influxdb_client import InfluxDBClient
from influxdb_client.client.write_api import SYNCHRONOUS

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org)
write_api = client.write_api(write_options=SYNCHRONOUS)
query_api = client.query_api()

print("Applying V2.4 Shock Amplification to Historical Data (Overwriting exactly)...")

# We query without pivot so we don't lose nanoseconds and tags!
query = f'''
from(bucket: "{bucket}")
  |> range(start: -30d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
'''
tables = query_api.query(query)

points_dict = {}

for table in tables:
    for record in table.records:
        # Get raw timestamp (as datetime, we will rely on write_api to format it)
        # Wait, if we use datetime, Python will truncate nanoseconds!
        # But we previously determined that the original historical data was logged
        # with nanoseconds. IF we read with datetime and write with datetime, it will 
        # CREATE DUPLICATES!
        
        # ACTUALLY, if we just want to update shock_penalty and reducer_damage without duplicates,
        # we can't use python datetime if the original had nanoseconds.
        pass

# Since Python datetime truncates nanoseconds, creating duplicate points, 
# the ONLY way to perfectly update fields without duplication is to use Flux's map function 
# and write back using the `to()` function directly inside InfluxDB!
