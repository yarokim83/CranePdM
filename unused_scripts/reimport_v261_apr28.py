"""4/28 11:00 ~ 15:35 KST (= UTC 02:00 ~ 06:35) raw_plc_data 를 V2.6.1 으로 재계산해서 InfluxDB 덮어쓰기.

작업:
  1. raw_plc_data/2026-04-28/ 의 _110000 ~ _153550 사이 파일을 V2.6.1 으로 재계산
  2. InfluxDB 에서 algo_version=2.6 source=live_v26, time 4/28T02:00:00Z~T06:36:00Z 삭제
  3. V2.6.1 결과를 line protocol 로 import (algo_version=2.6.1)

라이브 로거 (PID 23708, KST 15:35:50 시작) 가 V2.6.1 으로 가동 중이므로,
KST 15:35:50 이후 데이터는 이미 V2.6.1 임. 그 이전 V2.6 구간만 재계산.
"""
import csv
import gzip
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
import requests

KST = timezone(timedelta(hours=9))
INFLUX_URL = "http://localhost:8086"
TOKEN = "my-super-secret-auth-token"
ORG = "myorg"
BUCKET = "cranepdm_kpis"

# V2.6.1 상수
CURR_THRESHOLD = 0.2
TRACK_EPSILON = 50.0
TRACK_SCALE = 5.0
TRACK_GATE = 500
MAX_INDIVIDUAL_PENALTY = 10.0

# 처리 범위 (KST)
CUT_START_KST = datetime(2026, 4, 28, 11, 0, 0, tzinfo=KST)
CUT_END_KST   = datetime(2026, 4, 28, 15, 35, 50, tzinfo=KST)

print(f"KST range : {CUT_START_KST} ~ {CUT_END_KST}")
print(f"UTC range : {CUT_START_KST.astimezone(timezone.utc)} ~ {CUT_END_KST.astimezone(timezone.utc)}")


def calc_v261(rows):
    if len(rows) < 2:
        return None
    shock_list, curr_list, track_list = [], [], []
    peak_shock = 0.0
    sum_sq_err = 0
    for i in range(1, len(rows)):
        dt = max(rows[i]['dt'], 0.001)
        order = rows[i]['order']; fb = rows[i]['feedback']
        speed = rows[i]['reel_speed']; current = rows[i]['reel_current']
        torque = rows[i]['reel_torque']; prev_torque = rows[i-1]['reel_torque']

        err = order - fb
        sum_sq_err += err ** 2

        torque_deriv = (torque - prev_torque) / dt
        raw_shock = 1.0 + 0.06 * abs(torque_deriv)
        sf = max(0.05, abs(speed) / 10000.0)
        shock_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + (raw_shock - 1.0) / sf)

        if abs(torque) > 10.0:
            r = abs(current) / (abs(torque) + 0.1)
            raw_cp = 1.0 + 5.0 * max(0, r - CURR_THRESHOLD)
            sfc = max(0.10, abs(speed) / 10000.0)
            curr_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + (raw_cp - 1.0) / sfc)
        else:
            curr_penalty = 1.0

        if abs(order) > TRACK_GATE:
            ratio = abs(err) / (abs(order) + TRACK_EPSILON)
            track_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + TRACK_SCALE * max(0, ratio - 0.05))
        else:
            track_penalty = 1.0

        shock_list.append(shock_penalty)
        curr_list.append(curr_penalty)
        track_list.append(track_penalty)
        if raw_shock > peak_shock:
            peak_shock = raw_shock

    if not shock_list:
        return None
    return {
        'shock_penalty': sum(shock_list) / len(shock_list),
        'curr_penalty':  sum(curr_list)  / len(curr_list),
        'track_penalty': sum(track_list) / len(track_list),
        'peak_shock':    peak_shock,
        'rms_error':     math.sqrt(sum_sq_err / len(rows)),
    }


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


def parse_filename_ts(path):
    """raw_plc_data/2026-04-28/232_110423.csv.gz → KST datetime"""
    date = path.parent.name
    fname = path.stem.replace('.csv', '')
    parts = fname.split('_')
    if len(parts) != 2:
        return None, None
    crane_id = parts[0]
    hhmmss = parts[1]
    if len(hhmmss) != 6 or not hhmmss.isdigit():
        return None, None
    try:
        dt = datetime.strptime(f"{date} {hhmmss}", "%Y-%m-%d %H%M%S").replace(tzinfo=KST)
        return crane_id, dt
    except ValueError:
        return None, None


def step1_recalculate():
    raw_dir = Path("raw_plc_data/2026-04-28")
    if not raw_dir.exists():
        print(f"ERROR: {raw_dir} not found")
        return []

    files = sorted(raw_dir.glob("*.csv.gz"))
    print(f"\n[Step 1] Recalculating V2.6.1 from {len(files)} files")

    records = []
    for f in files:
        crane_id, ts_kst = parse_filename_ts(f)
        if not crane_id or not ts_kst:
            continue
        if ts_kst < CUT_START_KST or ts_kst > CUT_END_KST:
            continue
        rows = load_raw_event(f)
        kpi = calc_v261(rows)
        if not kpi:
            continue
        records.append({
            'crane_id': crane_id,
            'ts_utc': ts_kst.astimezone(timezone.utc),
            'kpi': kpi,
        })
    print(f"  Recomputed: {len(records)} events")
    return records


def step2_delete_v26():
    """4/28 02:00 ~ 06:36 UTC 의 algo_version=2.6 source=live_v26 데이터 삭제."""
    print(f"\n[Step 2] Delete V2.6 in cutoff window")

    delete_payload = {
        "start": "2026-04-28T02:00:00Z",
        "stop":  "2026-04-28T06:36:00Z",
        "predicate": '_measurement="crane_movement" AND source="live_v26" AND algo_version="2.6"'
    }
    r = requests.post(
        f"{INFLUX_URL}/api/v2/delete?org={ORG}&bucket={BUCKET}",
        headers={
            "Authorization": f"Token {TOKEN}",
            "Content-Type": "application/json"
        },
        json=delete_payload
    )
    print(f"  Delete response: {r.status_code} {r.text[:200]}")
    return r.status_code == 204


def step3_import(records):
    """V2.6.1 결과를 line protocol 로 import."""
    print(f"\n[Step 3] Import {len(records)} records as algo_version=2.6.1")

    lines = []
    for rec in records:
        ts_ns = int(rec['ts_utc'].timestamp() * 1e9)
        kpi = rec['kpi']
        crane_id = rec['crane_id']
        line = (
            f'crane_movement,'
            f'crane_id={crane_id},'
            f'source=live_v26,'
            f'algo_version=2.6.1 '
            f'shock_penalty={kpi["shock_penalty"]:.6f},'
            f'curr_penalty={kpi["curr_penalty"]:.6f},'
            f'track_penalty={kpi["track_penalty"]:.6f},'
            f'peak_shock={kpi["peak_shock"]:.6f},'
            f'rms_error={kpi["rms_error"]:.6f} '
            f'{ts_ns}'
        )
        lines.append(line)

    body = "\n".join(lines)
    r = requests.post(
        f"{INFLUX_URL}/api/v2/write?org={ORG}&bucket={BUCKET}&precision=ns",
        headers={
            "Authorization": f"Token {TOKEN}",
            "Content-Type": "text/plain; charset=utf-8"
        },
        data=body.encode("utf-8")
    )
    print(f"  Write response: {r.status_code}")
    if r.status_code != 204:
        print(f"  Error body: {r.text[:300]}")
    return r.status_code == 204


def main():
    records = step1_recalculate()
    if not records:
        print("No records to import")
        return

    if not step2_delete_v26():
        print("ERROR: delete failed")
        return

    if not step3_import(records):
        print("ERROR: import failed")
        return

    print("\nDone.")


if __name__ == "__main__":
    main()
