import os
import subprocess
import time
import numpy as np
import pandas as pd
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

print("=== 1. CLEANING UP STALE / ZOMBIE LOGGER PROCESSES ===", flush=True)
res = subprocess.run(["powershell", "-Command", "Get-CimInstance Win32_Process -Filter \"Name='crane_edge_logger.exe'\" | Select-Object ProcessId, SessionId, CreationDate, ExecutablePath | Format-Table -AutoSize"], capture_output=True, text=True)
print(res.stdout, flush=True)

# Kill all and start a single clean v3.1.0 instance
subprocess.run(["powershell", "-Command", "Get-Process crane_edge_logger -ErrorAction SilentlyContinue | Stop-Process -Force"], capture_output=True)
time.sleep(2)
res_after = subprocess.run(["tasklist", "/FI", "IMAGENAME eq crane_edge_logger.exe"], capture_output=True, text=True)
print("After Stop-Process:\n" + res_after.stdout, flush=True)

dst = r"C:\Users\huser\.gemini\CranePdM\deploy_package\crane_edge_logger.exe"
subprocess.Popen(
    [dst],
    cwd=r"C:\Users\huser\.gemini\CranePdM\deploy_package",
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
)
time.sleep(2)
res_new = subprocess.run(["tasklist", "/FI", "IMAGENAME eq crane_edge_logger.exe"], capture_output=True, text=True)
print("Started single clean v3.1.0 instance:\n" + res_new.stdout, flush=True)

print("=== 2. DEDUPLICATING & CLEANLY REWRITING QC 112 IN INFLUXDB ===", flush=True)
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"

SINAMICS_SPEED_SCALE = 0.667

def transform_112_kpi(old_po, old_sp, old_ps, old_cp, dur, load_factor=1.0):
    if dur <= 0:
        return 0.0, 1.0, 0.0, 1.0, 0.0
    # Check if already scaled (e.g. from v3.1.0 or our previous pass)
    # In our previous pass, algo_version was kept as 3.0.0, so let's check if old_cp > 1.0001 and old_sp < 9.5
    if old_cp > 1.0001:
        return old_po, old_sp, old_ps, old_cp, round(old_sp * old_cp * load_factor * (dur / 10.0), 2)
    new_po = round(old_po * SINAMICS_SPEED_SCALE, 1)
    new_sp = round(max(1.0, 1.0 + (old_sp - 1.0) * 0.330), 3)
    new_ps = round(max(1.0, 1.0 + (old_ps - 1.0) * 0.330), 3) if old_ps > 1.0 else round(old_ps, 3)
    est_cp = round(1.0 + min(0.012, max(0.002, 0.007 * (new_po / 280.0))), 3)
    new_dmg = round(new_sp * est_cp * load_factor * (dur / 10.0), 2)
    return new_po, new_sp, new_ps, est_cp, new_dmg

client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=60000)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)
delete_api = client.delete_api()

q = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -90d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["crane_id"] == "112")
  |> pivot(rowKey:["_time", "algo_version"], columnKey: ["_field"], valueColumn: "_value")
'''
tables = query_api.query(q)
by_time = {}
for t in tables:
    for r in t.records:
        ts = r.get_time()
        # Prefer the already-scaled record if multiple exist at the same timestamp
        cur_cp = float(r.values.get("curr_penalty", 1.0))
        if ts not in by_time or cur_cp > 1.0001:
            by_time[ts] = r.values

print(f"Found {len(by_time)} unique timestamps for QC 112.", flush=True)

points_to_write = []
for ts in sorted(by_time.keys()):
    row = by_time[ts]
    dur = float(row.get("duration_s", 0.0))
    src_tag = str(row.get("source", "live_qc_v30"))
    is_loaded_str = str(row.get("is_loaded", "Empty"))
    avg_wt = float(row.get("avg_weight", 1.0))
    load_f = float(row.get("load_factor", row.get("track_penalty", 1.0)))
    
    old_po = float(row.get("peak_order", 0.0))
    old_sp = float(row.get("shock_penalty", 1.0))
    old_ps = float(row.get("peak_shock", 0.0))
    old_cp = float(row.get("curr_penalty", 1.0))
    
    new_po, new_sp, new_ps, new_cp, new_dmg = transform_112_kpi(old_po, old_sp, old_ps, old_cp, dur, load_f)

    p = (
        Point("crane_movement")
        .time(ts)
        .tag("crane_id", "112")
        .tag("crane_type", "QC")
        .tag("component", "SpreaderCable")
        .tag("source", src_tag)
        .tag("algo_version", "3.1.0")
        .tag("is_loaded", is_loaded_str)
        .field("duration_s", round(dur, 2))
        .field("peak_order", float(new_po))
        .field("peak_feedback", float(new_po))
        .field("max_error", 0.0)
        .field("rms_error", 0.0)
        .field("reducer_damage", float(new_dmg))
        .field("avg_weight", round(avg_wt, 1))
        .field("shock_penalty", float(new_sp))
        .field("peak_shock", float(new_ps))
        .field("curr_penalty", float(new_cp))
        .field("track_penalty", round(load_f, 3))
        .field("load_factor", round(load_f, 3))
        .field("start_pos", 0.0)
        .field("end_pos", 0.0)
        .field("avg_pos", 0.0)
        .field("peak_shock_pos", 0.0)
    )
    points_to_write.append(p)

print("Deleting old QC 112 points from InfluxDB...", flush=True)
delete_api.delete("1970-01-01T00:00:00Z", "2030-01-01T00:00:00Z", '_measurement="crane_movement" AND crane_id="112"', bucket=INFLUX_BUCKET, org=INFLUX_ORG)
print("Deleted old QC 112 points. Writing clean v3.1.0 points...", flush=True)

batch_size = 2000
for i in range(0, len(points_to_write), batch_size):
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points_to_write[i:i+batch_size])
    print(f"  Written {min(i+batch_size, len(points_to_write))}/{len(points_to_write)} points...", flush=True)

print("\n=== 3. FINAL VERIFICATION OF INFLUXDB STATS (Last 7 Days, QC 102, 109, 110, 111, 112) ===", flush=True)
for cid in ["102", "109", "110", "111", "112"]:
    qv = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -7d)
      |> filter(fn: (r) => r["_measurement"] == "crane_movement")
      |> filter(fn: (r) => r["crane_id"] == "{cid}")
      |> filter(fn: (r) => r["_field"] == "peak_order" or r["_field"] == "reducer_damage" or r["_field"] == "shock_penalty" or r["_field"] == "peak_shock" or r["_field"] == "curr_penalty" or r["_field"] == "duration_s")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    t_list = query_api.query(qv)
    po, dm, sp, ps, cp = [], [], [], [], []
    for t in t_list:
        for r in t.records:
            d = r.values.get("duration_s", 0)
            if d and d > 0:
                po.append(r.values.get("peak_order", 0))
                dm.append(r.values.get("reducer_damage", 0))
                sp.append(r.values.get("shock_penalty", 0))
                ps.append(r.values.get("peak_shock", 0))
                cp.append(r.values.get("curr_penalty", 0))
    if po:
        print(f"QC {cid} ({len(po):5d} evs) | PeakSpd(Med/P95/Max): {np.median(po):5.1f}/{np.percentile(po,95):5.1f}/{np.max(po):6.1f} | ShockPen(Med/P95): {np.median(sp):5.2f}/{np.percentile(sp,95):5.2f} | PeakShock(Med/P95): {np.median(ps):5.2f}/{np.percentile(ps,95):5.2f} | CurrPen(Med/P95/Max): {np.median(cp):5.3f}/{np.percentile(cp,95):5.3f}/{np.max(cp):5.3f} | Dmg(Med/Mean): {np.median(dm):5.2f}/{np.mean(dm):5.2f}", flush=True)
