import csv
import statistics
import collections
from datetime import datetime

CSV_FILE = 'crane_kpi_log.csv'

def analyze():
    print(f"📊 Analyzing V2.1+ Data from {CSV_FILE}...")
    
    if not os.path.exists(CSV_FILE):
        print("❌ Error: CSV file not found.")
        return

    data = []
    with open(CSV_FILE, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        # Handle cases with potentially different column counts across versions
        for row in reader:
            if len(row) >= 17:
                data.append(row)

    if not data:
        print("ℹ️ No data records found.")
        return

    # Columns based on 18-col V2.1+ schema:
    # 0:ts, 1:id, 2:v, 3:dur, 4:pk_ord, 5:pk_fb, 6:mx_err, 7:rms, 8:dmg, 9:wt, 10:lod, 11:shk, 12:pk_shk, 13:cur, 14:trk, 15:st, 16:en, 17:av_pos
    
    # Check column count to be safe
    is_v21_plus = len(data[0]) >= 18
    print(f"Detected {'V2.1+' if is_v21_plus else 'V2.1 (Legacy)'} schema.")

    # Data transformation
    # Helper to safe-float
    def sf(val):
        try: return float(val)
        except: return 0.0

    records = []
    for r in data:
        kpi = {
            'ts': r[0],
            'id': r[1],
            'v': r[2],
            'dur': sf(r[3]),
            'err': sf(r[7]), # RMS Error
            'dmg': sf(r[8]), # Stress
            'wt': sf(r[9]),
            'is_loaded': r[10] == '1',
            'shock': sf(r[11]),
            'peak_shock': sf(r[12]) if is_v21_plus else sf(r[11]),
            'curr': sf(r[13]) if is_v21_plus else sf(r[12]),
            'pos': sf(r[17]) if is_v21_plus else sf(r[16])
        }
        records.append(kpi)

    # 1. Overall Statistics
    total_events = len(records)
    total_damage = sum(r['dmg'] for r in records)
    avg_damage = total_damage / total_events if total_events else 0
    max_damage_rec = max(records, key=lambda x: x['dmg'])
    max_peak_shock_rec = max(records, key=lambda x: x['peak_shock'])

    print(f"\n[General Summary]")
    print(f"- Total Movement Cycles: {total_events}")
    print(f"- Avg Stress per Cycle: {avg_damage:.2f}")
    print(f"- Max Record Stress: {max_damage_rec['dmg']} (Crane {max_damage_rec['id']})")
    print(f"- Max Peak Shock: {max_peak_shock_rec['peak_shock']} (Crane {max_peak_shock_rec['id']})")

    # 2. Risk Ranking (Total Stress)
    crane_stress = collections.defaultdict(float)
    crane_counts = collections.defaultdict(int)
    crane_high_shock = collections.defaultdict(int)
    for r in records:
        crane_stress[r['id']] += r['dmg']
        crane_counts[r['id']] += 1
        if r['peak_shock'] > 5.0:
            crane_high_shock[r['id']] += 1

    sorted_risk = sorted(crane_stress.items(), key=lambda x: x[1], reverse=True)

    print(f"\n[Fleet Risk Distribution]")
    for cid, stress in sorted_risk[:10]:
        avg = stress / crane_counts[cid]
        high_shocks = crane_high_shock[cid]
        print(f"Crane {cid}: Total Stress {stress:.1f} | Avg {avg:.1f} | High Impacts (>5.0): {high_shocks}")

    # 3. Component Insight (Friction vs Shock vs Control)
    # Check if any specific area is dominant across fleet
    avg_fleet_shock = statistics.mean(r['shock'] for r in records)
    avg_fleet_curr = statistics.mean(r['curr'] for r in records)
    avg_fleet_err = statistics.mean(r['err'] for r in records)

    print(f"\n[Diagnostic Distribution]")
    print(f"- Fleet Avg Friction Penalty: {avg_fleet_curr:.2f}")
    print(f"- Fleet Avg Shock Penalty: {avg_fleet_shock:.2f}")
    print(f"- Fleet Avg Speed Error (RMS): {avg_fleet_err:.1f}")

    # 4. Load Balancing Verification
    loaded_dmg = [r['dmg'] for r in records if r['is_loaded']]
    empty_dmg = [r['dmg'] for r in records if not r['is_loaded']]
    
    if loaded_dmg and empty_dmg:
        print(f"\n[Load Scaling Check]")
        print(f"- Loaded Cycles ({len(loaded_dmg)}): Avg Stress {statistics.mean(loaded_dmg):.2f}")
        print(f"- Empty Cycles ({len(empty_dmg)}): Avg Stress {statistics.mean(empty_dmg):.2f}")
        print(f"- Ratio: {statistics.mean(loaded_dmg)/statistics.mean(empty_dmg):.2f}x higher stress on loaded.")

if __name__ == "__main__":
    import os
    analyze()
