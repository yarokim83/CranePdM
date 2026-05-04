"""
Calculate per-crane normalization factors and generate Flux query.
For each crane, factor = new_period_mean / old_period_mean
Then apply this factor in the Grafana query for data before 4/9.
"""
from influxdb_client import InfluxDBClient
import pandas as pd
import json

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
bucket = "cranepdm_kpis"
client = InfluxDBClient(url=url, token=token, org=org, timeout=120000)
query_api = client.query_api()

q = '''
from(bucket: "cranepdm_kpis")
  |> range(start: 2026-03-29T00:00:00Z, stop: 2026-04-22T00:00:00Z)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "shock_penalty" or r["_field"] == "curr_penalty" or r["_field"] == "track_penalty")
  |> drop(columns: ["algo_version"])
  |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
  |> map(fn: (r) => ({ r with _value: r.shock_penalty * r.curr_penalty * r.track_penalty }))
  |> keep(columns: ["_time", "crane_id", "_value"])
'''
tables = query_api.query(q)
records = []
for table in tables:
    for r in table.records:
        records.append({
            'time': r.get_time(),
            'crane': r.values.get('crane_id'),
            'stress': r.get_value()
        })

df = pd.DataFrame(records)
df['date'] = pd.to_datetime(df['time']).dt.date

old = df[(df['date'] >= pd.Timestamp('2026-03-29').date()) & 
         (df['date'] <= pd.Timestamp('2026-04-08').date())]
new = df[(df['date'] >= pd.Timestamp('2026-04-09').date()) & 
         (df['date'] <= pd.Timestamp('2026-04-21').date())]

old_crane = old.groupby('crane')['stress'].mean()
new_crane = new.groupby('crane')['stress'].mean()

# Global average factor as fallback
global_factor = new['stress'].mean() / old['stress'].mean()
print(f"Global factor: {global_factor:.2f}")

# For the Flux query, we'll use a simpler approach:
# Just multiply old data by the global factor since per-crane is too complex for Flux
# But first let's check what the result looks like
print(f"\nSimulated result with global factor ({global_factor:.2f}):")
old_adj = old.copy()
old_adj['stress'] = old_adj['stress'] * global_factor
combined = pd.concat([old_adj, new])
combined['date'] = pd.to_datetime(combined['time']).dt.date
daily = combined.groupby('date')['stress'].mean().round(2)
print(daily)
print(f"\nOld period adjusted mean: {old_adj['stress'].mean():.2f}")
print(f"New period mean: {new['stress'].mean():.2f}")
