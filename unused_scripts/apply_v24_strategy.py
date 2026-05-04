import time
from influxdb_client import InfluxDBClient

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org, timeout=300000)
query_api = client.query_api()

print("Executing Flux script to retroactively apply V2.4 shock amplification...")

# This flux query will:
# 1. Read all crane_movement data from the past 30 days.
# 2. Pivot to get fields in rows.
# 3. Calculate new_shock_penalty = 1.0 + (peak_shock - 1.0) / max(0.3, abs(peak_order)/10000.0)
# 4. Calculate new_reducer_damage = reducer_damage * (new_shock_penalty / max(1.0, shock_penalty))
# 5. Unpivot back to field format.
# 6. Write back to the exact same bucket!

# Wait, Flux math operations can be complex.
# And unpivoting is tricky.
# What if we just query, compute in Python, and delete the original point and write the new point?
# BUT we can't delete by nanosecond timestamp easily.

# Wait, if Python truncates nanoseconds, we have duplicates.
# BUT we ALREADY deleted all V2.4 data.
# The only data left is the V2.3 data.
# What if we just delete ALL V2.3 data after we read it?
# Yes! We can read it (truncating to microseconds in Python), compute the new fields, write it as a NEW point,
# and then DELETE the original V2.3 points using `_measurement="crane_movement" AND algo_version="2.3"`!
# Wait, if we delete ALL V2.3 points, then ONLY the new ones will remain!
# And the new ones will have whatever tags we want, and microsecond precision (which is perfectly fine for Grafana)!
# This is a bulletproof way to clean the data without duplicates!
