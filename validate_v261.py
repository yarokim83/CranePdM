"""V2.6 vs V2.6.1 비교 검증.

raw PLC 데이터 (232호 4/24) 를 두 알고리즘으로 재계산해서
shock/curr/track 및 stress 변화를 비교한다.

V2.6.1 변경:
  A) speed_factor cap 0.3→0.05 (shock), 0.5→0.10 (curr)
  B) peak-weighted aggregation: 0.7*max + 0.3*mean
"""
import csv
import gzip
import math
import os
from pathlib import Path

CURR_THRESHOLD = 0.2
TRACK_EPSILON = 50.0
TRACK_SCALE = 5.0
TRACK_GATE = 500
MAX_INDIVIDUAL_PENALTY = 10.0


def calc_v26_original(rows):
    """기존 V2.6: speed cap 0.3/0.5, mean aggregation."""
    if len(rows) < 2:
        return None
    sum_shock = sum_curr = sum_track = 0.0
    n = 0
    for i in range(1, len(rows)):
        dt = max(rows[i]['dt'], 0.001)
        order = rows[i]['order']; fb = rows[i]['feedback']
        speed = rows[i]['reel_speed']; current = rows[i]['reel_current']
        torque = rows[i]['reel_torque']; prev_torque = rows[i-1]['reel_torque']

        torque_deriv = (torque - prev_torque) / dt
        raw_shock = 1.0 + 0.06 * abs(torque_deriv)
        sf = max(0.3, abs(speed) / 10000.0)
        shock_penalty = 1.0 + (raw_shock - 1.0) / sf

        if abs(torque) > 10.0:
            r = abs(current) / (abs(torque) + 0.1)
            raw_cp = 1.0 + 5.0 * max(0, r - CURR_THRESHOLD)
            sfc = max(0.5, abs(speed) / 10000.0)
            curr_penalty = 1.0 + (raw_cp - 1.0) / sfc
        else:
            curr_penalty = 1.0

        if abs(order) > TRACK_GATE:
            err = abs(order - fb)
            ratio = err / (abs(order) + TRACK_EPSILON)
            track_penalty = 1.0 + TRACK_SCALE * max(0, ratio - 0.05)
        else:
            track_penalty = 1.0

        sum_shock += shock_penalty
        sum_curr += curr_penalty
        sum_track += track_penalty
        n += 1
    if n == 0:
        return None
    s = sum_shock / n; c = sum_curr / n; t = sum_track / n
    return {'shock': s, 'curr': c, 'track': t, 'stress': s * c * t}


def calc_v261(rows):
    """V2.6.1: A (speed cap 0.05/0.10) + per-sample penalty cap 10.0, mean aggregation."""
    if len(rows) < 2:
        return None
    shock_list, curr_list, track_list = [], [], []
    for i in range(1, len(rows)):
        dt = max(rows[i]['dt'], 0.001)
        order = rows[i]['order']; fb = rows[i]['feedback']
        speed = rows[i]['reel_speed']; current = rows[i]['reel_current']
        torque = rows[i]['reel_torque']; prev_torque = rows[i-1]['reel_torque']

        torque_deriv = (torque - prev_torque) / dt
        raw_shock = 1.0 + 0.06 * abs(torque_deriv)
        sf = max(0.05, abs(speed) / 10000.0)            # A
        shock_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + (raw_shock - 1.0) / sf)

        if abs(torque) > 10.0:
            r = abs(current) / (abs(torque) + 0.1)
            raw_cp = 1.0 + 5.0 * max(0, r - CURR_THRESHOLD)
            sfc = max(0.10, abs(speed) / 10000.0)       # A
            curr_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + (raw_cp - 1.0) / sfc)
        else:
            curr_penalty = 1.0

        if abs(order) > TRACK_GATE:
            err = abs(order - fb)
            ratio = err / (abs(order) + TRACK_EPSILON)
            track_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + TRACK_SCALE * max(0, ratio - 0.05))
        else:
            track_penalty = 1.0

        shock_list.append(shock_penalty)
        curr_list.append(curr_penalty)
        track_list.append(track_penalty)

    if not shock_list:
        return None
    # B 미적용: 단순 평균
    s = sum(shock_list) / len(shock_list)
    c = sum(curr_list)  / len(curr_list)
    t = sum(track_list) / len(track_list)
    return {'shock': s, 'curr': c, 'track': t, 'stress': s * c * t}


def load_raw_event(path):
    rows = []
    with gzip.open(path, 'rt', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for r in reader:
            try:
                rows.append({
                    'dt': float(r['dt']),
                    'order': float(r['order']),
                    'feedback': float(r['feedback']),
                    'reel_speed': float(r['reel_speed']),
                    'reel_current': float(r['reel_current']),
                    'reel_torque': float(r['reel_torque']),
                })
            except (KeyError, ValueError):
                continue
    return rows


def process_day(crane_id, date_dir):
    files = sorted(Path(date_dir).glob(f"{crane_id}_*.csv.gz"))
    print(f"\n=== {date_dir} crane {crane_id} : {len(files)} events ===")

    v26_stress, v261_stress = [], []
    for f in files:
        rows = load_raw_event(f)
        if len(rows) < 2:
            continue
        a = calc_v26_original(rows)
        b = calc_v261(rows)
        if a and b:
            v26_stress.append(a['stress'])
            v261_stress.append(b['stress'])

    if v26_stress:
        m26 = sum(v26_stress) / len(v26_stress)
        m261 = sum(v261_stress) / len(v261_stress)
        max26 = max(v26_stress)
        max261 = max(v261_stress)
        print(f"  V2.6   mean stress: {m26:7.2f}   max: {max26:7.2f}   n={len(v26_stress)}")
        print(f"  V2.6.1 mean stress: {m261:7.2f}   max: {max261:7.2f}   ratio: {m261/m26:.2f}x")


if __name__ == "__main__":
    # 232호 핵심 검증: 4/24 (파손 직후, 92.5 V2.4 baseline)
    for date in ["2026-04-24", "2026-04-25", "2026-04-26", "2026-04-27", "2026-04-28"]:
        d = Path("raw_plc_data") / date
        if d.exists():
            process_day("232", d)

    # Fleet 평균 비교: 4/27 다양한 호기
    print("\n=== Fleet 비교: 4/27 ===")
    fleet_dir = Path("raw_plc_data/2026-04-27")
    if fleet_dir.exists():
        cranes = set()
        for f in fleet_dir.glob("*.csv.gz"):
            cranes.add(f.name.split("_")[0])
        for c in sorted(cranes)[:5]:
            process_day(c, fleet_dir)
