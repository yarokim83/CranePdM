from influxdb_client import InfluxDBClient
import numpy as np

# InfluxDB Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

query = '''
from(bucket: "cranepdm_kpis")
  |> range(start: -12h)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["_field"] == "reducer_damage" or r["_field"] == "mean_stress" or r["_field"] == "peak_feedback")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
  |> keep(columns: ["crane_id", "reducer_damage", "mean_stress", "peak_feedback"])
'''

tables = query_api.query(query)

data = {"ARMGC_212": {"damage": [], "stress": [], "speed": []}, "ARMGC_254": {"damage": [], "stress": [], "speed": []}}

for table in tables:
    for row in table.records:
        cid = row.values.get("crane_id")
        dmg = row.values.get("reducer_damage")
        stress = row.values.get("mean_stress")
        speed = row.values.get("peak_feedback")
        
        if cid in data:
            if dmg is not None: data[cid]["damage"].append(dmg)
            if stress is not None: data[cid]["stress"].append(stress)
            if speed is not None: data[cid]["speed"].append(speed)

for cid, metrics in data.items():
    print(f"--- {cid} ---")
    if metrics["damage"]:
        print(f"Movements Recorded: {len(metrics['damage'])}")
        print(f"Avg Reducer Damage: {np.mean(metrics['damage']):.2f}")
        print(f"Max Reducer Damage: {np.max(metrics['damage']):.2f}")
        print(f"Avg Cable Stress  : {np.mean(metrics['stress']):.2f}")
        print(f"Max Gantry Speed  : {np.max(metrics['speed']):.2f} %")
    else:
        print("No data collected yet.")
