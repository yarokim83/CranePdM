import glob
import os
import gzip
import csv
import numpy as np

print("Dashboards:", glob.glob("grafana/dashboards/*"))
print("Maintenance scripts:", glob.glob("scripts/maintenance/*"))

dp_raws = sorted(glob.glob("deploy_package/raw_plc_data/*"))

def sim_kpis(events, spd_scale=1.0, cur_scale=1.0, trq_scale=1.0):
    po_list, sp_list, ps_list, cp_list, dm_list = [], [], [], [], []
    for ev_s, ev_c, ev_t, ev_dt in events:
        if len(ev_s) < 2:
            continue
        dur = sum(ev_dt)
        if dur <= 1.5:
            continue
        speeds = [s * spd_scale for s in ev_s]
        currents = [c * cur_scale for c in ev_c]
        torques = [t * trq_scale for t in ev_t]
        
        peak_speed = max(abs(s) for s in speeds)
        dt_arr = np.array(ev_dt)
        dt_arr = np.where(dt_arr <= 0, 0.1, dt_arr)
        
        torque_arr = np.array(torques, dtype=float)
        speed_arr = np.array(speeds, dtype=float)
        
        d_torque = np.abs(np.diff(torque_arr, prepend=torque_arr[0])) / dt_arr
        d_speed = np.abs(np.diff(speed_arr, prepend=speed_arr[0])) / dt_arr
        
        raw_shock_list = 1.0 + 0.02 * d_torque + 0.02 * d_speed
        shock_penalty = float(np.percentile(raw_shock_list, 95))
        peak_shock = float(np.max(raw_shock_list))
        
        curr_ratios = []
        for c, t in zip(currents, torques):
            adj_curr = max(0.0, abs(c) - 30.0)
            t_abs = abs(t) + 1.0
            curr_ratios.append(adj_curr / t_abs)
        avg_curr_ratio = sum(curr_ratios) / len(curr_ratios)
        curr_penalty = min(5.0, max(1.0, 1.0 + 0.15 * avg_curr_ratio))
        load_factor = 1.0
        dmg = round(shock_penalty * curr_penalty * load_factor * (dur / 10.0), 2)
        
        po_list.append(peak_speed)
        sp_list.append(shock_penalty)
        ps_list.append(peak_shock)
        cp_list.append(curr_penalty)
        dm_list.append(dmg)
    return {
        'po': np.array(po_list),
        'sp': np.array(sp_list),
        'ps': np.array(ps_list),
        'cp': np.array(cp_list),
        'dm': np.array(dm_list)
    }

events = {'110': [], '111': [], '112': []}
for d in reversed(dp_raws):
    for c in ['110', '111', '112']:
        if len(events[c]) >= 500:
            continue
        for fpath in glob.glob(os.path.join(d, f"{c}_*.csv.gz")):
            if len(events[c]) >= 500:
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
                events[c].append((ev_s, ev_c, ev_t, ev_dt))
            except Exception:
                pass

for c in ['110', '111']:
    res = sim_kpis(events[c], 1.0, 1.0, 1.0)
    print(f"Ref QC {c} (1.0, 1.0, 1.0) -> PeakSpd Med/P95/Max: {np.median(res['po']):6.1f}/{np.percentile(res['po'],95):6.1f}/{np.max(res['po']):6.1f} | ShockPen Med/P95: {np.median(res['sp']):5.2f}/{np.percentile(res['sp'],95):5.2f} | CurrPen Med/P95/Max: {np.median(res['cp']):5.3f}/{np.percentile(res['cp'],95):5.3f}/{np.max(res['cp']):5.3f} | Dmg Med/Mean/P95: {np.median(res['dm']):5.2f}/{np.mean(res['dm']):5.2f}/{np.percentile(res['dm'],95):5.2f}")

print("-" * 120)
for s_sc, c_sc, t_sc in [
    (1.0, 1.0, 1.0),
    (0.65, 1.60, 3.50),
    (0.667, 1.65, 3.50),
    (0.667, 1.70, 3.60),
    (0.65, 1.70, 3.50),
    (0.60, 1.65, 3.30),
]:
    res = sim_kpis(events['112'], s_sc, c_sc, t_sc)
    print(f"QC 112 ({s_sc:5.3f}, {c_sc:4.2f}, {t_sc:4.2f}) -> PeakSpd Med/P95/Max: {np.median(res['po']):6.1f}/{np.percentile(res['po'],95):6.1f}/{np.max(res['po']):6.1f} | ShockPen Med/P95: {np.median(res['sp']):5.2f}/{np.percentile(res['sp'],95):5.2f} | CurrPen Med/P95/Max: {np.median(res['cp']):5.3f}/{np.percentile(res['cp'],95):5.3f}/{np.max(res['cp']):5.3f} | Dmg Med/Mean/P95: {np.median(res['dm']):5.2f}/{np.mean(res['dm']):5.2f}/{np.percentile(res['dm'],95):5.2f}")
