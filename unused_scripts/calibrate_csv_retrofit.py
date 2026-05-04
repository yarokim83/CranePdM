"""csv_retrofit 데이터의 잔여 inflation 을 per-event 정밀 보정.

발견 (compute_calibration_factors.py 결과):
  - peak_shock 1.01x (정확) - raw 측정값은 잘 보존됨
  - shock_penalty 9.35x inflated - apply_v24_retroactive 가 부풀린 핵심 원인
  - curr_penalty 0.79x (정상)
  - V2.4 native vs V2.6 raw_replay 알고리즘 차이는 ~2% 만 (운영 normalize)

보정 전략 (per-event 정밀):
  1. stored peak_shock 그대로 사용 (정확)
  2. V2.6 공식으로 shock_penalty 재추정:
     - V2.6 의 speed-norm 이 cap 0.3 영역에서 사실상 일률 증폭
     - estimated_shock_penalty ≈ 1 + (peak_shock_avg - 1) / 0.3
     - 단 stored peak_shock 은 max, 평균이 아님 → fleet 통계 비율 적용
     - 4/24~25 raw_replay: peak_shock_mean=11.15, shock_penalty_mean=1.902
     - 비율: shock_penalty_mean / peak_shock_mean = 0.171
     - 즉 estimated_shock_penalty ≈ peak_shock × 0.171
  3. damage 보정:
     - damage_v6 = damage_csv × (estimated_shock_penalty / stored_shock_penalty)
                            × (V2.6_curr_penalty / stored_curr_penalty 비율)
     - curr_penalty 는 stored 가 거의 정확 (0.79x) → 보정 거의 안함
  4. 또는 단일 scale factor: damage × 0.17 (가장 단순)

이 스크립트는 두 방법 모두 비교 가능:
  --method=simple : 단일 scale factor 0.17
  --method=penalty: per-event 페널티 비율로 정교 재계산

저장: source="csv_retrofit_calibrated" + algo_version="2.6"
"""
import argparse
import sys
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

URL = "http://localhost:8086"
TOKEN = "my-super-secret-auth-token"
ORG = "myorg"
BUCKET = "cranepdm_kpis"
MEASUREMENT = "crane_movement"
BATCH_SIZE = 1000
LOG_FILE = "replay_log.txt"

# Calibration constants from compute_calibration_factors.py (4/24~25 raw_replay 통계)
RAW_REPLAY_PEAK_SHOCK_MEAN = 11.15
RAW_REPLAY_SHOCK_PENALTY_MEAN = 1.902
RAW_REPLAY_CURR_PENALTY_MEAN = 1.720

# 공식: shock_penalty 는 speed_factor 가 cap 0.3 인 V2.6 의 raw_shock 평균과 선형 관계
# V2.6 의 raw_shock = 1 + 0.06 × |ΔT/Δt|, peak_shock 도 같은 공식의 max
# fleet 통계로 추정: shock_penalty_avg / peak_shock = 0.171 (raw_replay 4/24~25 fleet)
SHOCK_PENALTY_PER_PEAK_SHOCK = RAW_REPLAY_SHOCK_PENALTY_MEAN / RAW_REPLAY_PEAK_SHOCK_MEAN  # 0.1706

# Simple scale factor (가장 단순)
SIMPLE_SCALE_FACTOR = 0.173  # raw ratio from compute_calibration_factors


def append_audit(lines):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--start-date', default='2026-03-29')
    parser.add_argument('--end-date', default='2026-04-23')
    parser.add_argument('--method', choices=['simple', 'penalty'], default='penalty',
                        help='simple: 단일 scale factor 0.173 / penalty: per-event 페널티 비율 재계산')
    parser.add_argument('--cranes', default=None)
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    cranes_filter = set(args.cranes.split(',')) if args.cranes else None

    print("=" * 72)
    print("csv_retrofit Calibration -- 정밀 보정")
    print(f"  date range : {args.start_date} ~ {args.end_date}")
    print(f"  cranes     : {sorted(cranes_filter) if cranes_filter else 'ALL'}")
    print(f"  method     : {args.method}")
    print(f"  dry_run    : {args.dry_run}")
    if args.method == 'simple':
        print(f"  scale      : {SIMPLE_SCALE_FACTOR}")
    else:
        print(f"  estimated_shock_penalty = peak_shock × {SHOCK_PENALTY_PER_PEAK_SHOCK:.4f}")
        print(f"  curr ref   : {RAW_REPLAY_CURR_PENALTY_MEAN:.3f}")
    print("=" * 72)

    client = InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=180000)
    query_api = client.query_api()
    write_api = client.write_api(write_options=SYNCHRONOUS) if not args.dry_run else None

    crane_filter = ''
    if cranes_filter:
        ids = ' or '.join(f'r.crane_id == "{c}"' for c in cranes_filter)
        crane_filter = f'  |> filter(fn:(r)=>{ids})\n'

    # csv_retrofit 데이터만 가져옴 (raw_replay 는 이미 정확하므로 보정 불필요)
    q = f'''
from(bucket:"{BUCKET}")
  |> range(start: {args.start_date}T00:00:00Z, stop: {args.end_date}T00:00:00Z)
  |> filter(fn:(r)=>r._measurement=="{MEASUREMENT}" and r.algo_version=="2.6" and r.source=="csv_retrofit")
{crane_filter}  |> pivot(rowKey:["_time", "crane_id", "is_loaded"], columnKey:["_field"], valueColumn:"_value")
'''
    print("Querying csv_retrofit events...")
    tables = query_api.query(q)

    n_total = n_calibrated = 0
    sum_orig = sum_new = 0.0
    points_buffer = []

    for tab in tables:
        for rec in tab.records:
            n_total += 1
            v = rec.values
            crane_id = v.get('crane_id')
            t = rec.get_time()
            damage_orig = v.get('reducer_damage')
            shock_pen = v.get('shock_penalty')
            curr_pen = v.get('curr_penalty')
            peak_shock = v.get('peak_shock')

            if damage_orig is None or damage_orig <= 0:
                continue

            damage_orig = float(damage_orig)

            if args.method == 'simple':
                damage_new = damage_orig * SIMPLE_SCALE_FACTOR
                method_factor = SIMPLE_SCALE_FACTOR
            else:  # penalty
                # peak_shock 으로 V2.6 shock_penalty 추정
                if peak_shock and peak_shock > 0:
                    est_shock_pen = float(peak_shock) * SHOCK_PENALTY_PER_PEAK_SHOCK
                else:
                    est_shock_pen = RAW_REPLAY_SHOCK_PENALTY_MEAN

                # shock_penalty correction factor
                shock_correction = est_shock_pen / float(shock_pen) if shock_pen and shock_pen > 0 else 1.0

                # curr_penalty 는 거의 정확 (0.79x), 큰 보정 없음
                # 단 fleet 평균 이상 차이가 있으면 약간 조정
                curr_correction = 1.0
                if curr_pen and curr_pen > 0:
                    # csv_retrofit 평균 curr=1.363 vs raw 1.720 → 1.262x 조정
                    curr_correction = RAW_REPLAY_CURR_PENALTY_MEAN / 1.363  # = 1.262

                method_factor = shock_correction * curr_correction
                damage_new = damage_orig * method_factor

            n_calibrated += 1
            sum_orig += damage_orig
            sum_new += damage_new

            # Build point
            p = Point(MEASUREMENT) \
                .tag("crane_id", str(crane_id)) \
                .tag("algo_version", "2.6") \
                .tag("is_loaded", str(v.get('is_loaded', 'Empty'))) \
                .tag("source", "csv_retrofit_calibrated") \
                .field("reducer_damage", float(damage_new)) \
                .field("reducer_damage_orig_csv", float(damage_orig)) \
                .field("calibration_factor", float(method_factor)) \
                .time(t)
            for fld in ('duration_s', 'peak_order', 'peak_feedback', 'max_error', 'rms_error',
                        'avg_weight', 'shock_penalty', 'peak_shock', 'curr_penalty',
                        'track_penalty', 'start_pos', 'end_pos', 'avg_pos', 'peak_shock_pos'):
                fv = v.get(fld)
                if fv is not None:
                    try:
                        p = p.field(fld, float(fv))
                    except (TypeError, ValueError):
                        pass
            points_buffer.append(p)

            if len(points_buffer) >= BATCH_SIZE:
                if not args.dry_run:
                    write_api.write(bucket=BUCKET, org=ORG, record=points_buffer)
                points_buffer = []

    if points_buffer and not args.dry_run:
        write_api.write(bucket=BUCKET, org=ORG, record=points_buffer)

    # Summary
    print(f"\n{'=' * 72}")
    print(f"Summary")
    print(f"{'=' * 72}")
    print(f"  total queried   : {n_total}")
    print(f"  calibrated      : {n_calibrated}")
    print(f"  sum_damage orig : {sum_orig:>14,.2f}")
    print(f"  sum_damage new  : {sum_new:>14,.2f}")
    if sum_orig > 0:
        print(f"  ratio           : {sum_new/sum_orig:.4f}")
        print(f"  mean orig       : {sum_orig/n_calibrated:>10.2f}")
        print(f"  mean new        : {sum_new/n_calibrated:>10.2f}")

    if args.dry_run:
        print("\n(dry-run -- NO InfluxDB writes)")
    else:
        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        append_audit([
            f"[{ts}] csv-retrofit CALIBRATION run: range={args.start_date}~{args.end_date} "
            f"cranes={sorted(cranes_filter) if cranes_filter else 'ALL'} "
            f"method={args.method} calibrated={n_calibrated} "
            f"sum_ratio={sum_new/sum_orig if sum_orig else 0:.4f}",
        ])
        print(f"\n(audit trail appended to {LOG_FILE})")

    client.close()


if __name__ == '__main__':
    main()
