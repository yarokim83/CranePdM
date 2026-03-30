import csv
import statistics
import collections
from datetime import datetime

CSV_FILE = 'crane_kpi_log.csv'

def deep_analyze():
    print(f"🔬 Deep Analysis of V2.2 GCR Data from {CSV_FILE}...")
    
    data = []
    with open(CSV_FILE, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        for row in reader:
            if len(row) >= 18:
                data.append(row)

    if not data:
        print("ℹ️ No data records found.")
        return

    def sf(val):
        try: return float(val)
        except: return 0.0

    records = []
    # V2.1+ Schema
    # 0:ts, 1:id, 2:v, 3:dur, 4:pk_ord, 5:pk_fb, 6:mx_err, 7:rms, 8:dmg, 9:wt, 10:lod, 11:shk, 12:pk_shk, 13:cur, 14:trk, 15:st, 16:en, 17:av_pos
    for r in data:
        kpi = {
            'ts': r[0],
            'id': r[1],
            'dur': sf(r[3]),
            'pk_ord': sf(r[4]),
            'pk_fb': sf(r[5]),
            'rms_err': sf(r[7]),
            'dmg': sf(r[8]),
            'is_loaded': r[10] == '1',
            'shk': sf(r[11]),
            'pk_shk': sf(r[12]),
            'cur': sf(r[13]),
            'trk': sf(r[14])
        }
        records.append(kpi)

    total = len(records)
    print(f"\n✅ Total Records Processed: {total}")

    # 1. Penalty Capping Analysis (Is the 10.0 cap too low/high?)
    print("\n--- 1. Penalty Capping & Distribution Analysis ---")
    
    shk_vals = [r['shk'] for r in records]
    pk_shk_vals = [r['pk_shk'] for r in records]
    cur_vals = [r['cur'] for r in records]
    trk_vals = [r['trk'] for r in records]

    capped_shk = sum(1 for v in shk_vals if v >= 9.9)
    capped_pk_shk = sum(1 for v in pk_shk_vals if v >= 9.9)
    capped_cur = sum(1 for v in cur_vals if v >= 9.9)
    capped_trk = sum(1 for v in trk_vals if v >= 9.9)

    print(f"Avg Shock Penalty:   {statistics.mean(shk_vals):.2f} | Max: {max(shk_vals):.2f} | Capped at 10.0: {capped_shk} ({capped_shk/total*100:.2f}%)")
    print(f"Max Peak Shock:      {max(pk_shk_vals):.2f} | Capped at 10.0: {capped_pk_shk} ({capped_pk_shk/total*100:.2f}%)")
    print(f"Avg Friction/Curr:   {statistics.mean(cur_vals):.2f} | Max: {max(cur_vals):.2f} | Capped at 10.0: {capped_cur} ({capped_cur/total*100:.2f}%)")
    print(f"Avg Tracking Factor: {statistics.mean(trk_vals):.2f} | Max: {max(trk_vals):.2f} | Capped at 10.0: {capped_trk} ({capped_trk/total*100:.2f}%)")

    # 2. Total Damage Anomaly Analysis
    print("\n--- 2. Damage (Stress) Outlier Analysis ---")
    dmg_vals = [r['dmg'] for r in records]
    
    mean_dmg = statistics.mean(dmg_vals)
    median_dmg = statistics.median(dmg_vals)
    sigma = statistics.stdev(dmg_vals)
    
    print(f"Mean Stress: {mean_dmg:.2f}")
    print(f"Median Stress: {median_dmg:.2f}")
    print(f"Standard Deviation: {sigma:.2f}")
    
    # 3 Sigma outliers
    outliers = [r for r in records if r['dmg'] > mean_dmg + 3*sigma]
    print(f"Number of Extreme Outliers (> Mean + 3 Sigma): {len(outliers)} ({len(outliers)/total*100:.2f}%)")
    if outliers:
        top_outliers = sorted(outliers, key=lambda x: x['dmg'], reverse=True)[:5]
        print("Top 5 Extreme Outliers:")
        for o in top_outliers:
             print(f"  - Time: {o['ts']}, Crane: {o['id']}, Stress: {o['dmg']:.2f}, Dur: {o['dur']:.1f}s, PeakOrder: {o['pk_ord']}, PkShk: {o['pk_shk']}, Curr: {o['cur']:.2f}, Trk: {o['trk']:.2f}")

    # 3. Short Duration Filtering Check
    print("\n--- 3. Short Duration vs High Stress Correlation ---")
    short_events = [r for r in records if r['dur'] <= 5.0]
    long_events = [r for r in records if r['dur'] > 5.0]
    
    if short_events and long_events:
         print(f"Avg Stress for events <= 5s ({len(short_events)}): {statistics.mean(r['dmg'] for r in short_events):.2f}")
         print(f"Avg Stress for events > 5s ({len(long_events)}): {statistics.mean(r['dmg'] for r in long_events):.2f}")

    # 4. Friction/Current Dependency on Load
    print("\n--- 4. Load Dependency of Current (Friction) Penalty ---")
    loaded_cur = [r['cur'] for r in records if r['is_loaded']]
    empty_cur = [r['cur'] for r in records if not r['is_loaded']]
    
    if loaded_cur and empty_cur:
        print(f"Avg Friction Penalty (Loaded): {statistics.mean(loaded_cur):.2f}")
        print(f"Avg Friction Penalty (Empty):  {statistics.mean(empty_cur):.2f}")

if __name__ == "__main__":
    deep_analyze()
