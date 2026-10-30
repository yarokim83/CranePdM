import glob
import os
import gzip
import csv
import numpy as np

dp_raws = sorted(glob.glob("deploy_package/raw_plc_data/*"))

events = {'102': [], '110': [], '111': [], '112': []}
for d in reversed(dp_raws):
    for c in events.keys():
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
                if len(ev_s) > 5 and sum(ev_dt) > 1.5:
                    events[c].append((ev_s, ev_c, ev_t, ev_dt))
            except Exception:
                pass

def eval_kpis(ev_list, is_sinamics=False, spd_scale=0.667, cur_scale=1.65, trq_scale=3.50, shock_damp=0.42):
    po_l, sp_l, ps_l, cp_l, dm_l = [], [], [], [], []
    for ev_s, ev_c, ev_t, ev_dt in ev_list:
        dur = sum(ev_dt)
        if is_sinamics:
            speeds = [s * spd_scale for s in ev_s]
            currents = [c * cur_scale for c in ev_c]
            torques = [t * trq_scale for t in ev_t]
            s_coeff = 0.02 * shock_damp
            t_coeff = 0.02 * shock_damp
        else:
            speeds = ev_s
            currents = ev_c
            torques = ev_t
            s_coeff = 0.02
            t_coeff = 0.02
            
        peak_speed = round(max(abs(s) for s in speeds), 1)
        dt_arr = np.where(np.array(ev_dt) <= 0, 0.1, np.array(ev_dt))
        t_arr = np.array(torques, dtype=float)
        s_arr = np.array(speeds, dtype=float)
        
        d_t = np.abs(np.diff(t_arr, prepend=t_arr[0])) / dt_arr
        d_s = np.abs(np.diff(s_arr, prepend=s_arr[0])) / dt_arr
        
        raw_shock_list = 1.0 + t_coeff * d_t + s_coeff * d_s
        shock_penalty = float(np.percentile(raw_shock_list, 95))
        peak_shock = float(np.max(raw_shock_list))
        
        curr_ratios = []
        for c_val, t_val in zip(currents, torques):
            adj_curr = max(0.0, abs(c_val) - 30.0)
            t_abs = abs(t_val) + 1.0
            curr_ratios.append(adj_curr / t_abs)
        avg_curr_ratio = sum(curr_ratios) / len(curr_ratios)
        curr_penalty = min(5.0, max(1.0, 1.0 + 0.15 * avg_curr_ratio))
        load_factor = 1.0
        dmg = round(shock_penalty * curr_penalty * load_factor * (dur / 10.0), 2)
        
        po_l.append(peak_speed)
        sp_l.append(shock_penalty)
        ps_l.append(peak_shock)
        cp_l.append(curr_penalty)
        dm_l.append(dmg)
    return {k: np.array(v) for k, v in zip(['po', 'sp', 'ps', 'cp', 'dm'], [po_l, sp_l, ps_l, cp_l, dm_l])}

for c in ['102', '110', '111']:
    r = eval_kpis(events[c], is_sinamics=False)
    print(f"Master QC {c} -> PeakSpd(Med/P95/Max): {np.median(r['po']):5.1f}/{np.percentile(r['po'],95):5.1f}/{np.max(r['po']):5.1f} | ShockPen(Med/P95): {np.median(r['sp']):5.2f}/{np.percentile(r['sp'],95):5.2f} | PeakShock(Med/P95): {np.median(r['ps']):5.2f}/{np.percentile(r['ps'],95):5.2f} | CurrPen(Med/P95/Max): {np.median(r['cp']):5.3f}/{np.percentile(r['cp'],95):5.3f}/{np.max(r['cp']):5.3f} | Dmg(Med/Mean/P95): {np.median(r['dm']):5.2f}/{np.mean(r['dm']):5.2f}/{np.percentile(r['dm'],95):5.2f}")

print("-" * 140)
for damp in [0.40, 0.42, 0.45, 0.48]:
    for c_sc in [1.60, 1.65]:
        r = eval_kpis(events['112'], is_sinamics=True, spd_scale=0.667, cur_scale=c_sc, trq_scale=3.50, shock_damp=damp)
        print(f"QC 112 (damp={damp:.2f}, cur={c_sc:.2f}) -> PeakSpd: {np.median(r['po']):5.1f}/{np.percentile(r['po'],95):5.1f}/{np.max(r['po']):5.1f} | ShockPen: {np.median(r['sp']):5.2f}/{np.percentile(r['sp'],95):5.2f} | PeakShock: {np.median(r['ps']):5.2f}/{np.percentile(r['ps'],95):5.2f} | CurrPen: {np.median(r['cp']):5.3f}/{np.percentile(r['cp'],95):5.3f}/{np.max(r['cp']):5.3f} | Dmg: {np.median(r['dm']):5.2f}/{np.mean(r['dm']):5.2f}/{np.percentile(r['dm'],95):5.2f}")
