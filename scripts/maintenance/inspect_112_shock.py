import glob
import os
import gzip
import csv
import numpy as np

dp_raws = sorted(glob.glob("deploy_package/raw_plc_data/*"))

events = {'110': [], '111': [], '112': []}
for d in reversed(dp_raws):
    for c in ['110', '111', '112']:
        if len(events[c]) >= 300:
            continue
        for fpath in glob.glob(os.path.join(d, f"{c}_*.csv.gz")):
            if len(events[c]) >= 300:
                break
            try:
                ev_s, ev_c, ev_t, ev_dt = [], [], [], []
                with gzip.open(fpath, 'rt', encoding='utf-8') as f:
                    r = csv.DictReader(f)
                    for row in r:
                        ev_s.append(float(row['reel_speed']))
                        ev_c.append(float(row['reel_current']))
                        ev_t.append(float(row['reel_torque']))
                        ev_dt.append(float(row['dt']))
                if len(ev_s) > 5 and sum(ev_dt) > 1.5:
                    events[c].append((ev_s, ev_c, ev_t, ev_dt))
            except Exception:
                pass

for c in ['110', '111', '112']:
    ds_p95, dt_p95, ds_max, dt_max, dt_med = [], [], [], [], []
    zero_step_ratios = []
    for ev_s, ev_c, ev_t, ev_dt in events[c]:
        dt_arr = np.where(np.array(ev_dt) <= 0, 0.1, np.array(ev_dt))
        s_arr = np.array(ev_s, dtype=float)
        t_arr = np.array(ev_t, dtype=float)
        
        diff_s = np.abs(np.diff(s_arr, prepend=s_arr[0]))
        diff_t = np.abs(np.diff(t_arr, prepend=t_arr[0]))
        
        ds = diff_s / dt_arr
        dt = diff_t / dt_arr
        
        ds_p95.append(np.percentile(ds, 95))
        dt_p95.append(np.percentile(dt, 95))
        ds_max.append(np.max(ds))
        dt_max.append(np.max(dt))
        dt_med.append(np.median(dt_arr))
        zero_step_ratios.append(np.mean(diff_s == 0))
        
    print(f"QC {c} ({len(events[c])} evs): dt_med={np.median(dt_med):.3f}s | zero_diff_s_ratio={np.mean(zero_step_ratios):.2f} | d_speed P95(Med/P95)={np.median(ds_p95):.1f}/{np.percentile(ds_p95,95):.1f} | d_torque P95(Med/P95)={np.median(dt_p95):.1f}/{np.percentile(dt_p95,95):.1f}")

print("\nSample raw trajectory of QC 112 (first 25 rows of a typical event):")
for ev_s, ev_c, ev_t, ev_dt in events['112'][:3]:
    if len(ev_s) >= 20:
        print(f"Event len={len(ev_s)}, dur={sum(ev_dt):.1f}s:")
        for i in range(min(20, len(ev_s))):
            print(f"  [{i:2d}] dt={ev_dt[i]:.3f}s | Spd={ev_s[i]:6.0f} | Cur={ev_c[i]:4.0f} | Trq={ev_t[i]:4.0f}")
        break

print("\nSample raw trajectory of QC 110 (first 25 rows of a typical event):")
for ev_s, ev_c, ev_t, ev_dt in events['110'][:3]:
    if len(ev_s) >= 20:
        print(f"Event len={len(ev_s)}, dur={sum(ev_dt):.1f}s:")
        for i in range(min(20, len(ev_s))):
            print(f"  [{i:2d}] dt={ev_dt[i]:.3f}s | Spd={ev_s[i]:6.0f} | Cur={ev_c[i]:4.0f} | Trq={ev_t[i]:4.0f}")
        break
