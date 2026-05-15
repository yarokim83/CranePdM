"""3/30 ~ 4/27 모든 데이터를 V2.4 (apply_v24_retroactive 정의) 로 통일.

목적: 사용자 지시 - 평균 stress ~20 매끄러운 그래프
  Phase 2 of "변경 1": geo-fence 포함 V2.4 정의로 모든 시기 통일.
  4/28 이후는 V2.6 (라이브 logger) 그대로 둠.

V2.4 공식:
  shock_penalty = 1 + (peak_shock - 1) / max(0.3, |peak_order|/10000)
  curr_penalty  = 1 + (avg_curr - 1) / max(0.5, |peak_order|/10000)
  track_penalty = 2.0 if 2400 <= avg_pos <= 2700 else 1.0
  damage_v24    = base_damage × multiplier × geo_penalty

작업:
  1. 4/24~27 raw_plc_data → V2.4 알고리즘으로 직접 처리 → InfluxDB
  2. 4/9~21 V2.3 csv (deploy_package) → V2.4 변환 → InfluxDB
  3. 4/22~23 V2.4 csv (deploy_package) → 그대로 import (이미 V2.4)
  4. 3/30~4/8 backup_v24 → source 만 통일

저장 태그: algo_version="2.4", source="v24_unified"

read-only: deploy_package csv, backup_before_apr9.csv, raw_plc_data 모두 보존
"""
import csv
import gzip
import os
import sys
from pathlib import Path
from datetime import datetime, timezone
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

URL = "http://localhost:8086"
TOKEN = "my-super-secret-auth-token"
ORG = "myorg"
BUCKET = "cranepdm_kpis"
MEASUREMENT = "crane_movement"
BATCH_SIZE = 5000
LOG_FILE = "replay_log.txt"
ALGO_TAG = "2.4"
SOURCE_TAG = "v24_unified"

DEPLOY_CSV = "deploy_package/crane_kpi_log.csv"
RAW_DIR = "raw_plc_data"

DEPLOY_FIELDS = ['timestamp', 'crane_id', 'algo_version', 'event_duration_s',
                 'peak_order', 'peak_feedback', 'max_error', 'rms_error',
                 'reducer_damage', 'avg_weight', 'is_loaded',
                 'shock_penalty', 'peak_shock', 'curr_penalty', 'track_penalty',
                 'start_pos', 'end_pos', 'avg_pos']


def parse_ts(s):
    return datetime.strptime(s, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)


def v24_geo_penalty(avg_pos):
    try:
        p = float(avg_pos)
        return 2.0 if 2400.0 <= p <= 2700.0 else 1.0
    except Exception:
        return 1.0


def v24_transform(peak_shock, peak_order, old_curr, avg_pos):
    """V2.3/V2.0 데이터를 V2.4 정의로 변환."""
    peak_shock = max(1.0, float(peak_shock or 1.0))
    peak_order = float(peak_order or 10000.0)
    old_curr = max(1.0, float(old_curr or 1.0))

    speed_factor_shock = max(0.3, abs(peak_order) / 10000.0)
    new_shock = 1.0 + (peak_shock - 1.0) / speed_factor_shock

    speed_factor_curr = max(0.5, abs(peak_order) / 10000.0)
    new_curr = 1.0 + (old_curr - 1.0) / speed_factor_curr

    geo = v24_geo_penalty(avg_pos)

    return new_shock, new_curr, geo


def calc_kpis_v24_from_raw(orders, feedbacks, loads, weights, positions, dt_list, db170_list):
    """raw 데이터로부터 V2.4 KPI 직접 계산 (apply_v24_retroactive 와 같은 정의)."""
    if not orders or len(orders) < 2 or not db170_list:
        return None
    if not all(v is not None for v in db170_list) or len(db170_list) != len(orders):
        return None

    avg_weight = max(0.0, min(sum(weights) / len(weights) if weights else 0, 60.0))
    is_loaded = (sum(loads) > len(loads) // 2) or (avg_weight > 5.0)
    avg_pos = sum(positions) / len(positions) if positions else 0
    peak_order = max(map(abs, orders))
    peak_shock = 0.0

    sum_curr = 0.0
    sum_track = 0.0
    n = 0
    sum_sq_err = 0
    total_damage = 0.0

    for i in range(1, len(orders)):
        dt = dt_list[i] if dt_list[i] > 0 else 0.1
        order = orders[i]
        fb = feedbacks[i]
        error = order - fb
        sum_sq_err += error ** 2

        v2_speed, v2_current, v2_torque = db170_list[i]
        prev_v2_torque = db170_list[i-1][2] if i > 0 else v2_torque

        torque_deriv = (v2_torque - prev_v2_torque) / dt
        raw_shock = 1.0 + 0.06 * abs(torque_deriv)
        if raw_shock > peak_shock:
            peak_shock = raw_shock

        # per-sample curr (V2.4 공식)
        if abs(v2_torque) > 10.0:
            curr_ratio = abs(v2_current) / (abs(v2_torque) + 0.1)
            raw_curr = 1.0 + 5.0 * max(0, curr_ratio - 0.2)
            speed_factor = max(0.5, abs(v2_speed) / 10000.0)
            curr_penalty = 1.0 + (raw_curr - 1.0) / speed_factor
        else:
            curr_penalty = 1.0

        if abs(order) > 500:
            ratio = abs(error) / (abs(order) + 50.0)
            track = 1.0 + 5.0 * max(0, ratio - 0.05)
        else:
            track = 1.0

        sum_curr += curr_penalty
        sum_track += track
        n += 1

        # base fatigue × per-sample shock × curr × track
        base_fatigue = (abs(v2_torque) ** 3) * abs(v2_speed) / 1000000.0
        speed_factor_shock = max(0.3, abs(v2_speed) / 10000.0)
        sample_shock = 1.0 + (raw_shock - 1.0) / speed_factor_shock
        total_damage += base_fatigue * sample_shock * curr_penalty * track * 0.001

    if n == 0:
        return None

    avg_curr = sum_curr / n
    avg_track = sum_track / n

    # V2.4 retroactive 정의로 페널티 산출 (peak_shock 기반)
    speed_factor_event = max(0.3, abs(peak_order) / 10000.0)
    event_shock = 1.0 + (peak_shock - 1.0) / speed_factor_event
    speed_factor_curr_event = max(0.5, abs(peak_order) / 10000.0)
    event_curr = 1.0 + (avg_curr - 1.0) / speed_factor_curr_event
    geo = v24_geo_penalty(avg_pos)

    # damage 에 geo 곱 (V2.4 deploy 의 geo-fence)
    final_damage = total_damage * geo

    import math
    rms_error = math.sqrt(sum_sq_err / len(orders))
    event_duration = sum(dt_list)

    return {
        'duration_s': round(event_duration, 2),
        'peak_order': peak_order,
        'rms_error': round(rms_error, 2),
        'reducer_damage': round(final_damage, 2),
        'avg_weight': round(avg_weight, 1),
        'is_loaded': "Loaded" if is_loaded else "Empty",
        'shock_penalty': round(event_shock, 3),
        'peak_shock': round(peak_shock, 3),
        'curr_penalty': round(event_curr, 3),
        'track_penalty': round(geo, 3),  # geo penalty 를 track 으로 저장 (apply_v24_retroactive 와 동일)
        'avg_pos': round(avg_pos, 1),
    }


def load_raw_event(path):
    """raw_plc_data csv.gz 파일 → 이벤트 데이터."""
    orders, feedbacks, loads, weights, positions, dt_list, db170_list = [], [], [], [], [], [], []
    try:
        with gzip.open(path, 'rt', encoding='utf-8', newline='') as f:
            rd = csv.DictReader(f)
            for row in rd:
                orders.append(int(row['order']))
                feedbacks.append(int(row['feedback']))
                loads.append(int(row['loaded']) == 1)
                weights.append(float(row['weight']))
                positions.append(int(row['position']))
                dt_list.append(float(row['dt']))
                db170_list.append((int(row['reel_speed']), int(row['reel_current']), int(row['reel_torque'])))
    except Exception as e:
        return None
    return orders, feedbacks, loads, weights, positions, dt_list, db170_list


def main():
    print("=" * 72)
    print("V2.4 통일 작업 (3/30~4/27 → algo_version=2.4, source=v24_unified)")
    print("=" * 72)

    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=180000)
    write_api = client.write_api(write_options=SYNCHRONOUS)

    points_buffer = []
    n_4to8 = n_9to21 = n_22to23 = n_24to27 = n_skip = 0

    def flush():
        nonlocal points_buffer
        if points_buffer:
            write_api.write(bucket=BUCKET, org=ORG, record=points_buffer)
            points_buffer = []

    # ============================================================
    # 1. deploy_package csv 처리: V2.0/V2.3 (3/30~4/8 backup), V2.3 (4/9~21), V2.4 (4/22~23)
    # ============================================================
    print("\n[1] deploy_package/crane_kpi_log.csv 처리")
    with open(DEPLOY_CSV, "r", encoding="utf-8") as f:
        rd = csv.DictReader(f, fieldnames=DEPLOY_FIELDS)
        for r in rd:
            try:
                ts = r["timestamp"]
                if not ts:
                    continue
                date_part = ts[:10]
                if date_part < "2026-03-30" or date_part >= "2026-04-24":
                    continue

                t = parse_ts(ts)
                algo = r["algo_version"] or "?"
                crane_id = str(r["crane_id"])
                avg_pos = float(r["avg_pos"] or 0)

                if algo == "2.4" and date_part >= "2026-04-22":
                    # V2.4 라이브 출력 (4/22~23): track_penalty 를 geo 로 덮어씀 (apply_v24_retroactive 와 통일)
                    peak_shock = float(r["peak_shock"] or 1.0)
                    peak_order = float(r["peak_order"] or 10000.0)
                    old_curr = float(r["curr_penalty"] or 1.0)
                    geo = v24_geo_penalty(avg_pos)
                    # V2.4 라이브 logger 의 shock_penalty 가 이미 V2.4 정의 (per-sample avg) 임
                    # 그러나 통일을 위해 peak_shock 기반으로 재산출
                    speed_factor_shock = max(0.3, abs(peak_order) / 10000.0)
                    new_shock = 1.0 + (peak_shock - 1.0) / speed_factor_shock
                    speed_factor_curr = max(0.5, abs(peak_order) / 10000.0)
                    new_curr = 1.0 + (max(1.0, old_curr) - 1.0) / speed_factor_curr
                    new_track = geo  # ★ B: track_penalty 를 geo 로 강제
                    old_damage = float(r["reducer_damage"] or 0)
                    if old_damage <= 0:
                        n_skip += 1
                        continue
                    old_shock = max(1.0, float(r["shock_penalty"] or 1.0))
                    new_damage = old_damage * (new_shock / old_shock) * (new_curr / old_curr) * geo
                    n_22to23 += 1
                elif algo in ("2.3", "2.2", "2.0"):
                    # V2.3 → V2.4 변환 (★ C: 4/22 V2.3 도 포함되도록 4/24 까지 확장)
                    peak_shock = float(r["peak_shock"] or 1.0)
                    peak_order = float(r["peak_order"] or 10000.0)
                    old_curr = float(r["curr_penalty"] or 1.0)
                    new_shock, new_curr, geo = v24_transform(peak_shock, peak_order, old_curr, avg_pos)
                    new_track = geo  # ★ B: track 항상 geo 로 (V2.3 의 큰 track 값 무시)
                    old_damage = float(r["reducer_damage"] or 0)
                    if old_damage <= 0:
                        n_skip += 1
                        continue
                    old_shock = max(1.0, float(r["shock_penalty"] or 1.0))
                    new_damage = old_damage * (new_shock / old_shock) * (new_curr / old_curr) * geo
                    if date_part >= "2026-04-22":
                        n_22to23 += 1  # V2.3 시기인 4/22 도 22to23 카운트로
                    elif date_part >= "2026-04-09":
                        n_9to21 += 1
                    else:
                        n_4to8 += 1
                else:
                    n_skip += 1
                    continue

                is_loaded_raw = r["is_loaded"]
                is_loaded = "Loaded" if is_loaded_raw in ("1", "Loaded", "True") else "Empty"

                p = Point(MEASUREMENT) \
                    .tag("crane_id", crane_id) \
                    .tag("algo_version", ALGO_TAG) \
                    .tag("is_loaded", is_loaded) \
                    .tag("source", SOURCE_TAG) \
                    .field("reducer_damage", float(new_damage)) \
                    .field("shock_penalty", float(new_shock)) \
                    .field("curr_penalty", float(new_curr)) \
                    .field("track_penalty", float(new_track)) \
                    .field("peak_shock", float(r["peak_shock"] or 1.0)) \
                    .field("peak_order", float(r["peak_order"] or 0)) \
                    .field("avg_pos", float(avg_pos)) \
                    .field("duration_s", float(r["event_duration_s"] or 0)) \
                    .time(t)
                points_buffer.append(p)
                if len(points_buffer) >= BATCH_SIZE:
                    flush()
            except Exception:
                n_skip += 1

    flush()
    print(f"  3/30~4/8 (V2.3/V2.0 → V2.4 변환): {n_4to8}")
    print(f"  4/9~21 (V2.3 → V2.4 변환): {n_9to21}")
    print(f"  4/22~23 (V2.4 그대로): {n_22to23}")
    print(f"  skip: {n_skip}")

    # ============================================================
    # 2. raw_plc_data 4/24~27 처리 → V2.4 알고리즘으로 직접 계산
    # ============================================================
    print("\n[2] raw_plc_data/2026-04-24 ~ 27 → V2.4 알고리즘 처리")
    raw_dir = Path(RAW_DIR)
    n_raw = 0
    n_raw_fail = 0
    for date_str in ("2026-04-24", "2026-04-25", "2026-04-26", "2026-04-27"):
        day_dir = raw_dir / date_str
        if not day_dir.exists():
            continue
        for f in sorted(day_dir.glob("*.csv.gz")):
            try:
                fname = f.stem.replace(".csv", "")
                parts = fname.split("_")
                crane_id = parts[0]
                ts_str = parts[1]
                # raw 파일 시간 = mtime, 또는 파일명의 HHMMSS
                t = datetime.strptime(f"{date_str} {ts_str[:2]}:{ts_str[2:4]}:{ts_str[4:6]}",
                                       "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)

                event = load_raw_event(f)
                if event is None:
                    n_raw_fail += 1
                    continue
                kpis = calc_kpis_v24_from_raw(*event)
                if kpis is None:
                    n_raw_fail += 1
                    continue

                p = Point(MEASUREMENT) \
                    .tag("crane_id", crane_id) \
                    .tag("algo_version", ALGO_TAG) \
                    .tag("is_loaded", kpis['is_loaded']) \
                    .tag("source", SOURCE_TAG) \
                    .field("reducer_damage", float(kpis['reducer_damage'])) \
                    .field("shock_penalty", float(kpis['shock_penalty'])) \
                    .field("curr_penalty", float(kpis['curr_penalty'])) \
                    .field("track_penalty", float(kpis['track_penalty'])) \
                    .field("peak_shock", float(kpis['peak_shock'])) \
                    .field("peak_order", float(kpis['peak_order'])) \
                    .field("avg_pos", float(kpis['avg_pos'])) \
                    .field("duration_s", float(kpis['duration_s'])) \
                    .time(t)
                points_buffer.append(p)
                n_raw += 1
                n_24to27 += 1
                if len(points_buffer) >= BATCH_SIZE:
                    flush()
                    print(f"    progress: {n_raw} raw events processed")
            except Exception:
                n_raw_fail += 1

    flush()
    print(f"  4/24~27 raw (V2.4 algorithm): {n_raw} ok, {n_raw_fail} fail")

    print("\n" + "=" * 72)
    print(f"Summary: total imported as algo_version={ALGO_TAG} source={SOURCE_TAG}")
    print(f"  3/30~4/8 (csv V2.3/2.0 → V2.4): {n_4to8}")
    print(f"  4/9~21   (csv V2.3 → V2.4)    : {n_9to21}")
    print(f"  4/22~23  (csv V2.4 그대로)    : {n_22to23}")
    print(f"  4/24~27  (raw → V2.4)         : {n_24to27}")
    print(f"  skip: {n_skip + n_raw_fail}")

    ts_now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(LOG_FILE, 'a', encoding='utf-8') as logf:
        logf.write(f"[{ts_now}] V2.4 unify (3/30~4/27): "
                   f"3to8={n_4to8} 9to21={n_9to21} 22to23={n_22to23} "
                   f"24to27={n_24to27} skip={n_skip + n_raw_fail}\n")

    client.close()


if __name__ == '__main__':
    main()
