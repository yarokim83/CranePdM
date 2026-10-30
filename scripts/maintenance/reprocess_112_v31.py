import os
import glob
import gzip
import csv
import numpy as np
import pandas as pd
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"

SINAMICS_SPEED_SCALE = 0.667
SINAMICS_CURR_SCALE = 1.65
SINAMICS_TORQUE_SCALE = 3.50
SINAMICS_SHOCK_DAMPING = 0.43

print("=== 1. INDEXING RAW PLC FILES FOR QC 112 ===", flush=True)
raw_files = sorted(glob.glob("deploy_package/raw_plc_data/*/112_*.csv.gz"))
print(f"Found {len(raw_files)} raw PLC event files for QC 112.", flush=True)

# Map (date_str, hhmmss_str) -> computed KPIs from raw file
def compute_112_from_raw(fpath):
    try:
        ev_s, ev_c, ev_t, ev_dt = [], [], [], []
        with gzip.open(fpath, 'rt', encoding='utf-8') as f:
            r = csv.DictReader(f)
            for row in r:
                ev_s.append(float(row['reel_speed']))
                ev_c.append(float(row['reel_current']))
                ev_t.append(float(row['reel_torque']))
                ev_dt.append(float(row['dt']))
        if not ev_s or sum(ev_dt) <= 0:
            return None
        dur = sum(ev_dt)
        speeds = [s * SINAMICS_SPEED_SCALE for s in ev_s]
        currents = [c * SINAMICS_CURR_SCALE for c in ev_c]
        torques = [t * SINAMICS_TORQUE_SCALE for t in ev_t]
        shock_coeff = 0.02 * SINAMICS_SHOCK_DAMPING
        
        peak_speed = round(max(abs(s) for s in speeds), 1)
        dt_arr = np.where(np.array(ev_dt) <= 0, 0.1, np.array(ev_dt))
        t_arr = np.array(torques, dtype=float)
        s_arr = np.array(speeds, dtype=float)
        
        d_t = np.abs(np.diff(t_arr, prepend=t_arr[0])) / dt_arr
        d_s = np.abs(np.diff(s_arr, prepend=s_arr[0])) / dt_arr
        
        raw_shock_list = 1.0 + shock_coeff * d_t + shock_coeff * d_s
        shock_penalty = round(float(np.percentile(raw_shock_list, 95)), 3)
        peak_shock = round(float(np.max(raw_shock_list)), 3)
        
        curr_ratios = []
        for c_val, t_val in zip(currents, torques):
            adj_curr = max(0.0, abs(c_val) - 30.0)
            t_abs = abs(t_val) + 1.0
            curr_ratios.append(adj_curr / t_abs)
        avg_curr_ratio = sum(curr_ratios) / len(curr_ratios) if curr_ratios else 0.0
        curr_penalty = round(min(5.0, max(1.0, 1.0 + 0.15 * avg_curr_ratio)), 3)
        load_factor = 1.0
        dmg = round(shock_penalty * curr_penalty * load_factor * (dur / 10.0), 2)
        return {
            'peak_order': peak_speed,
            'peak_fb': peak_speed,
            'shock_penalty': shock_penalty,
            'peak_shock': peak_shock,
            'curr_penalty': curr_penalty,
            'reducer_damage': dmg
        }
    except Exception:
        return None

raw_kpi_map = {}
for idx, fp in enumerate(raw_files):
    day_str = os.path.basename(os.path.dirname(fp)) # YYYY-MM-DD
    bname = os.path.basename(fp) # 112_HHMMSS.csv.gz
    hhmmss = bname.split("_")[1].split(".")[0]
    k = compute_112_from_raw(fp)
    if k:
        raw_kpi_map[(day_str, hhmmss)] = k
    if (idx + 1) % 3000 == 0:
        print(f"  Processed {idx+1}/{len(raw_files)} raw files...", flush=True)

print(f"Successfully computed exact V3.1 KPIs from {len(raw_kpi_map)} raw 112 files.", flush=True)

def fallback_transform_112(old_po, old_sp, old_ps, old_cp, dur, load_factor=1.0):
    if dur <= 0:
        return 0.0, 1.0, 0.0, 1.0, 0.0
    new_po = round(old_po * SINAMICS_SPEED_SCALE, 1)
    # In V3.0 unscaled: raw_shock = 1.0 + 0.02*(d_t_raw + d_s_raw).
    # With speed*0.667, torque*3.5, damping*0.43 -> effective derivative scale is ~0.328 of V3.0 unscaled excess above 1.0
    new_sp = round(max(1.0, 1.0 + (old_sp - 1.0) * 0.328), 3)
    new_ps = round(max(1.0, 1.0 + (old_ps - 1.0) * 0.328), 3) if old_ps > 1.0 else round(old_ps, 3)
    # Estimate curr_penalty based on speed regime if old_cp was stuck at 1.0
    if old_cp <= 1.0001:
        est_cp = round(1.0 + min(0.014, 0.007 * (new_po / 500.0)), 3)
    else:
        est_cp = round(old_cp, 3)
    new_dmg = round(new_sp * est_cp * load_factor * (dur / 10.0), 2)
    return new_po, new_sp, new_ps, est_cp, new_dmg

print("\n=== 2. REPROCESSING INFLUXDB QC 112 HISTORICAL RECORDS ===", flush=True)
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=60000)
query_api = client.query_api()
write_api = client.write_api(write_options=SYNCHRONOUS)

q = f'''
from(bucket: "{INFLUX_BUCKET}")
  |> range(start: -90d)
  |> filter(fn: (r) => r["_measurement"] == "crane_movement")
  |> filter(fn: (r) => r["crane_id"] == "112")
  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
'''
tables = query_api.query(q)
records = []
for t in tables:
    for r in t.records:
        records.append(r.values)

print(f"Fetched {len(records)} QC 112 records from InfluxDB.", flush=True)

points_to_write = []
matched_raw_cnt = 0
fallback_cnt = 0

for row in records:
    ts = row.get("_time")
    dur = float(row.get("duration_s", 0.0))
    algo_v = str(row.get("algo_version", "3.0.0"))
    src_tag = str(row.get("source", "live_qc_v30"))
    is_loaded_str = str(row.get("is_loaded", "Empty"))
    avg_wt = float(row.get("avg_weight", 1.0))
    load_f = float(row.get("load_factor", row.get("track_penalty", 1.0)))
    
    # Convert UTC timestamp to local KST (+09:00) to match raw filename (YYYY-MM-DD, HHMMSS)
    local_dt = ts.astimezone()
    day_str = local_dt.strftime('%Y-%m-%d')
    
    # Check exact second or ±1 second in raw_kpi_map
    matched_kpi = None
    for delta_s in [0, -1, 1, -2, 2]:
        cand_dt = pd.to_datetime(local_dt) + pd.Timedelta(seconds=delta_s)
        key = (cand_dt.strftime('%Y-%m-%d'), cand_dt.strftime('%H%M%S'))
        if key in raw_kpi_map:
            matched_kpi = raw_kpi_map[key]
            break
            
    if dur <= 0:
        new_po, new_sp, new_ps, new_cp, new_dmg = 0.0, 1.0, 0.0, 1.0, 0.0
    elif matched_kpi is not None:
        matched_raw_cnt += 1
        new_po = matched_kpi['peak_order']
        new_sp = matched_kpi['shock_penalty']
        new_ps = matched_kpi['peak_shock']
        new_cp = matched_kpi['curr_penalty']
        new_dmg = round(new_sp * new_cp * load_f * (dur / 10.0), 2)
    else:
        fallback_cnt += 1
        old_po = float(row.get("peak_order", 0.0))
        old_sp = float(row.get("shock_penalty", 1.0))
        old_ps = float(row.get("peak_shock", 0.0))
        old_cp = float(row.get("curr_penalty", 1.0))
        # Avoid double-scaling if already v3.1.0
        if algo_v == "3.1.0":
            new_po, new_sp, new_ps, new_cp, new_dmg = old_po, old_sp, old_ps, old_cp, float(row.get("reducer_damage", 0.0))
        else:
            new_po, new_sp, new_ps, new_cp, new_dmg = fallback_transform_112(old_po, old_sp, old_ps, old_cp, dur, load_f)

    p = (
        Point("crane_movement")
        .time(ts)
        .tag("crane_id", "112")
        .tag("crane_type", "QC")
        .tag("component", "SpreaderCable")
        .tag("source", src_tag)
        .tag("algo_version", algo_v)
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

print(f"Prepared {len(points_to_write)} points (Exact Raw Match: {matched_raw_cnt}, Fallback Formula: {fallback_cnt}). Writing to InfluxDB in batches...", flush=True)
batch_size = 1000
for i in range(0, len(points_to_write), batch_size):
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=points_to_write[i:i+batch_size])
    if (i // batch_size + 1) % 5 == 0 or i + batch_size >= len(points_to_write):
        print(f"  Written {min(i+batch_size, len(points_to_write))}/{len(points_to_write)} points...", flush=True)

print("\n=== 3. UPDATING DEPLOY_PACKAGE/CRANE_KPI_LOG.CSV FOR QC 112 ===", flush=True)
dp_csv = "deploy_package/crane_kpi_log.csv"
dp_tmp = "deploy_package/crane_kpi_log.csv.tmp"
updated_csv_rows = 0
if os.path.exists(dp_csv):
    with open(dp_csv, "r", encoding="utf-8", errors="ignore", newline="") as fin, \
         open(dp_tmp, "w", encoding="utf-8", newline="") as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout)
        for row in reader:
            if len(row) >= 15 and row[1] == "112":
                try:
                    ts_str = row[0] # YYYY-MM-DD HH:MM:SS
                    algo_v = row[2]
                    dur = float(row[3])
                    if dur > 0 and algo_v != "3.1.0":
                        day_str = ts_str[:10]
                        hhmmss = ts_str[11:19].replace(":", "")
                        matched_kpi = raw_kpi_map.get((day_str, hhmmss))
                        load_f = float(row[14]) if row[14] else 1.0
                        if matched_kpi:
                            new_po = matched_kpi['peak_order']
                            new_sp = matched_kpi['shock_penalty']
                            new_ps = matched_kpi['peak_shock']
                            new_cp = matched_kpi['curr_penalty']
                            new_dmg = round(new_sp * new_cp * load_f * (dur / 10.0), 2)
                        else:
                            old_po = float(row[4])
                            old_sp = float(row[11])
                            old_ps = float(row[12])
                            old_cp = float(row[13])
                            new_po, new_sp, new_ps, new_cp, new_dmg = fallback_transform_112(old_po, old_sp, old_ps, old_cp, dur, load_f)
                        row[2] = "3.1.0"
                        row[4] = new_po
                        row[5] = new_po
                        row[8] = new_dmg
                        row[11] = new_sp
                        row[12] = new_ps
                        row[13] = new_cp
                        updated_csv_rows += 1
                except Exception:
                    pass
            writer.writerow(row)
    os.replace(dp_tmp, dp_csv)
    print(f"Updated {updated_csv_rows} QC 112 rows in {dp_csv}!", flush=True)

print("=== ALL QC 112 REPROCESSING COMPLETED SUCCESSFULLY ===", flush=True)
