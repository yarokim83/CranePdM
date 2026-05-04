"""
replay_raw_to_influx.py — Raw PLC 데이터를 현재 calculate_kpis()로 재계산하여 InfluxDB에 기록

용도:
  알고리즘이 V2.5 → V2.6, V2.7 등으로 바뀌었을 때 raw_plc_data/에 남아있는 10Hz
  PLC 원본 샘플(reel_speed, reel_current, reel_torque, position 등)을 입력으로
  새 알고리즘을 통과시켜 KPI를 재계산한다.

안전 원칙 (AI_GUIDE.md 준수):
  - 기본 동작: replay 레코드는 'source="raw_replay"' 태그를 달아 실시간 원본과 분리
    저장. algo_version 태그도 명시해 병렬 버전 비교 가능.
  - CSV 파일은 건드리지 않음 (crane_kpi_log.csv는 수정 금지 원칙).
  - replay_log.txt 에 각 실행의 audit trail을 append.
  - --dry-run 지원: 실제 InfluxDB 쓰기 없이 요약만 출력.

사용 예:
  # 4/24 데이터 전체를 현재 알고리즘(calculate_kpis의 algo_version)으로 replay
  python replay_raw_to_influx.py --start-date 2026-04-24

  # 날짜 범위 + 특정 크레인만
  python replay_raw_to_influx.py --start-date 2026-04-20 --end-date 2026-04-24 --cranes 231,232

  # Dry-run (쓰기 없이 집계만)
  python replay_raw_to_influx.py --start-date 2026-04-24 --dry-run

  # algo_version 태그를 수동 지정 (예: 기존 V2.5 실시간과 구분)
  python replay_raw_to_influx.py --start-date 2026-04-24 --algo-tag 2.5-replay
"""
import argparse
import gzip
import csv
import os
import sys
import glob
from datetime import datetime, timezone

sys.path.insert(0, '.')
from crane_edge_logger import calculate_kpis
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

URL = "http://localhost:8086"
TOKEN = "my-super-secret-auth-token"
ORG = "myorg"
BUCKET = "cranepdm_kpis"
MEASUREMENT = "crane_movement"
BATCH_SIZE = 500
LOG_FILE = "replay_log.txt"
RAW_ROOT = "raw_plc_data"


def load_raw_event(path):
    """Parse one gzipped raw event CSV. Returns (samples_tuple | None, err_msg | None)."""
    orders, feedbacks, loads, weights, positions, dt_list, db170_list = [], [], [], [], [], [], []
    try:
        with gzip.open(path, 'rt', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                orders.append(int(row['order']))
                feedbacks.append(int(row['feedback']))
                loads.append(row['loaded'] == '1')
                weights.append(int(row['weight']))
                positions.append(int(row['position']))
                dt_list.append(float(row['dt']))
                db170_list.append((
                    int(row['reel_speed']),
                    int(row['reel_current']),
                    int(row['reel_torque']),
                ))
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"
    return (orders, feedbacks, loads, weights, positions, dt_list, db170_list), None


def extract_metadata(path):
    """Derive crane_id and event UTC timestamp from file path + filename."""
    basename = os.path.basename(path).replace('.csv.gz', '')  # e.g. '232_220918'
    parts = basename.split('_')
    crane_id = parts[0]
    time_str = parts[1]  # 'HHMMSS'
    date_str = os.path.basename(os.path.dirname(path))  # '2026-04-24'
    yyyy, MM, dd = map(int, date_str.split('-'))
    hh, mi, ss = int(time_str[0:2]), int(time_str[2:4]), int(time_str[4:6])
    # 파일명 HHMMSS는 로컬 타임존. astimezone() 으로 UTC 변환.
    local_dt = datetime(yyyy, MM, dd, hh, mi, ss)
    utc_dt = local_dt.astimezone(timezone.utc)
    return crane_id, utc_dt


def build_point(crane_id, event_utc, kpis, algo_tag, source_tag):
    """Build InfluxDB Point from KPI dict. Matches log_event() field set + V2.5 extras."""
    p = (
        Point(MEASUREMENT)
        .tag("crane_id", crane_id)
        .tag("algo_version", algo_tag)
        .tag("is_loaded", "Loaded" if kpis['is_loaded'] else "Empty")
        .tag("source", source_tag)
        .field("duration_s", float(kpis['duration']))
        .field("peak_order", float(kpis['peak_order']))
        .field("peak_feedback", float(kpis['peak_fb']))
        .field("max_error", float(kpis['max_error']))
        .field("rms_error", float(kpis['rms_error']))
        .field("reducer_damage", float(kpis['reducer_damage']))
        .field("avg_weight", float(kpis['avg_weight']))
        .field("shock_penalty", float(kpis['shock_penalty']))
        .field("peak_shock", float(kpis['peak_shock']))
        .field("curr_penalty", float(kpis['curr_penalty']))
        .field("track_penalty", float(kpis['track_penalty']))
        .field("start_pos", float(kpis['start_pos']))
        .field("end_pos", float(kpis['end_pos']))
        .field("avg_pos", float(kpis['avg_pos']))
        .field("peak_shock_pos", float(kpis['peak_shock_pos']))
        .time(event_utc)
    )
    return p


def find_raw_files(start_date, end_date, cranes=None):
    """List all .csv.gz under raw_plc_data/{YYYY-MM-DD}/ within range."""
    files = []
    for day_dir in sorted(glob.glob(os.path.join(RAW_ROOT, '*'))):
        dn = os.path.basename(day_dir)
        if not (start_date <= dn <= end_date):
            continue
        for f in sorted(glob.glob(os.path.join(day_dir, '*.csv.gz'))):
            if cranes:
                crane_id = os.path.basename(f).split('_')[0]
                if crane_id not in cranes:
                    continue
            files.append(f)
    return files


def append_audit(lines):
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        for line in lines:
            f.write(line + '\n')


def main():
    parser = argparse.ArgumentParser(
        description="Bulk raw replay to InfluxDB with current calculate_kpis()",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument('--start-date', required=True, help='YYYY-MM-DD (inclusive)')
    parser.add_argument('--end-date', default=None, help='YYYY-MM-DD (default = start-date)')
    parser.add_argument('--cranes', default=None, help='Comma-separated crane IDs (default: all)')
    parser.add_argument('--algo-tag', default=None,
                        help='Override algo_version tag. Default: use kpis["algo_version"]. '
                             'Use a distinct tag (e.g. "2.5-replay") to avoid colliding with realtime data.')
    parser.add_argument('--source-tag', default='raw_replay',
                        help='Override source tag. Default: raw_replay')
    parser.add_argument('--dry-run', action='store_true', help='No DB writes; summary only')
    parser.add_argument('--min-duration', type=float, default=3.0,
                        help='Minimum event duration in seconds (default 3.0, matches live logger)')
    args = parser.parse_args()

    end_date = args.end_date or args.start_date
    cranes_filter = set(args.cranes.split(',')) if args.cranes else None

    print("=" * 72)
    print("Bulk Raw Replay → InfluxDB")
    print(f"  date range : {args.start_date} ~ {end_date}")
    print(f"  cranes     : {sorted(cranes_filter) if cranes_filter else 'ALL'}")
    print(f"  algo_tag   : {args.algo_tag or '(from calculate_kpis)'}")
    print(f"  source_tag : {args.source_tag}")
    print(f"  dry_run    : {args.dry_run}")
    print(f"  min_duration: {args.min_duration}s")
    print("=" * 72)

    files = find_raw_files(args.start_date, end_date, cranes_filter)
    print(f"\nFound {len(files)} raw file(s).")
    if not files:
        print("아무것도 할 일 없음. 종료.")
        return

    client = None
    write_api = None
    if not args.dry_run:
        client = InfluxDBClient(url=URL, token=TOKEN, org=ORG, timeout=120000)
        write_api = client.write_api(write_options=SYNCHRONOUS)

    n_ok = n_fail = n_short = n_empty = 0
    sum_damage = 0.0
    by_crane = {}
    points_buffer = []
    failures = []

    t_start = datetime.now()

    for i, path in enumerate(files):
        if i % 100 == 0 and i > 0:
            print(f"  progress: {i}/{len(files)}  ok={n_ok} fail={n_fail} short={n_short}")

        samples, err = load_raw_event(path)
        if err is not None:
            n_fail += 1
            failures.append((path, err))
            continue

        orders, feedbacks, loads, weights, positions, dt_list, db170_list = samples
        if not orders:
            n_empty += 1
            continue

        crane_id, event_utc = extract_metadata(path)
        kpis = calculate_kpis(orders, feedbacks, loads, weights, positions,
                              dt_list, db170_list)
        if kpis is None:
            n_fail += 1
            failures.append((path, 'calculate_kpis returned None (DB170 missing?)'))
            continue
        if kpis['duration'] <= args.min_duration:
            n_short += 1
            continue

        n_ok += 1
        sum_damage += kpis['reducer_damage']
        by_crane.setdefault(crane_id, []).append(kpis['reducer_damage'])

        algo_tag = args.algo_tag or kpis['algo_version']
        pt = build_point(crane_id, event_utc, kpis, algo_tag, args.source_tag)
        points_buffer.append(pt)

        if len(points_buffer) >= BATCH_SIZE:
            if not args.dry_run:
                write_api.write(bucket=BUCKET, org=ORG, record=points_buffer)
            points_buffer = []

    if points_buffer and not args.dry_run:
        write_api.write(bucket=BUCKET, org=ORG, record=points_buffer)

    elapsed = (datetime.now() - t_start).total_seconds()

    # Summary
    print(f"\n{'=' * 72}")
    print(f"Summary (elapsed {elapsed:.1f}s)")
    print(f"{'=' * 72}")
    print(f"  OK           : {n_ok}")
    print(f"  Fail         : {n_fail}")
    print(f"  Short (<{args.min_duration}s) : {n_short}")
    print(f"  Empty        : {n_empty}")
    print(f"  total_damage : {sum_damage:,.2f}")
    if n_ok > 0:
        print(f"  mean_damage  : {sum_damage / n_ok:.2f}")

    # Top 10 by crane
    if by_crane:
        print(f"\n  Top 10 cranes by sum_damage:")
        ranking = [(c, sum(v), len(v)) for c, v in by_crane.items()]
        for c, s, n in sorted(ranking, key=lambda x: -x[1])[:10]:
            print(f"    {c}: sum={s:>10.0f}  events={n:>4d}  mean={s / n:>6.0f}")

    if failures[:5]:
        print(f"\n  First 5 failures:")
        for p, e in failures[:5]:
            print(f"    {p}: {e}")
        if len(failures) > 5:
            print(f"    ... and {len(failures) - 5} more")

    # Audit
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    append_audit([
        f"[{ts}] replay run: range={args.start_date}~{end_date} "
        f"cranes={sorted(cranes_filter) if cranes_filter else 'ALL'} "
        f"algo_tag={args.algo_tag or 'auto'} dry_run={args.dry_run}",
        f"           files={len(files)} ok={n_ok} fail={n_fail} short={n_short} empty={n_empty} "
        f"total_damage={sum_damage:.2f} elapsed={elapsed:.1f}s",
    ])

    print(f"\n(audit trail appended to {LOG_FILE})")
    if args.dry_run:
        print("(dry-run -- NO InfluxDB writes)")

    if client:
        client.close()


if __name__ == '__main__':
    main()
