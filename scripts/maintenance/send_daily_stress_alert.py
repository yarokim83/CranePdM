import os
import sys
import time
import smtplib
import argparse
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import numpy as np
import pandas as pd
from datetime import datetime, timedelta, timezone
from influxdb_client import InfluxDBClient

# Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"

SMTP_SERVER = "mail.hpnt.co.kr"
SMTP_PORT = 25
SENDER_EMAIL = "CranePdM_Alert <baewoong.kim@hpnt.co.kr>"
RECIPIENT_EMAIL = "baewoong.kim@hpnt.co.kr"
GRAFANA_BASE_URL = "http://10.200.19.104:3000"

ARMGC_STRESS_THRESHOLD = 50.0   # Daily average Stress Index threshold for ARMGC GCR
QC_STRESS_THRESHOLD = 6.0       # Daily average Stress Index threshold for QC SCR

LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "outlook_alert_history.log")

def log_msg(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    try:
        print(line, flush=True)
    except UnicodeEncodeError:
        print(line.encode('cp949', errors='replace').decode('cp949'), flush=True)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def diagnose_armgc_cause(shock, curr, track):
    causes = []
    if curr >= 6.5:
        causes.append(f"<b>과전류 주도형(Curr={curr:.2f})</b>: 케이블 릴 감속기/가이드롤러 기계적 회전 저항 또는 인버터 토크 대비 전류 과다 점검")
    if shock >= 5.5:
        causes.append(f"<b>충격 주도형(Shock={shock:.2f})</b>: 다발 충격 구간 레일 단차·이음매 상태 및 가감속 장력 급변 점검")
    if track >= 1.55:
        causes.append(f"<b>추종오차 동반(Track={track:.2f})</b>: 고속 주행 가감속 시 지령-피드백 속도 편차 확대")
    if not causes:
        causes.append(f"<b>복합 부하 상승</b> (Shock={shock:.2f} × Curr={curr:.2f} × Track={track:.2f})")
    return "<br>".join(causes)

def diagnose_qc_cause(shock, curr, load_f):
    causes = []
    if shock >= 6.0:
        causes.append(f"<b>호이스트 급가감속 충격 주도형(Shock={shock:.2f})</b>: 수동 조작 급가감속 또는 스프레더 리듀서 충격 부하 점검")
    if curr >= 1.05:
        causes.append(f"<b>과전류 동반(Curr={curr:.3f})</b>: 정격 대기전류 대비 구동 전류 상승 점검")
    if not causes:
        causes.append(f"<b>일일 평균 충격 상승</b> (Shock={shock:.2f} × Curr={curr:.3f})")
    return "<br>".join(causes)

def find_hotspot_pos_str(pos_series, shock_series):
    valid = pd.DataFrame({'pos': pos_series, 'shock': shock_series}).dropna()
    valid = valid[valid['pos'] > 0]
    if valid.empty:
        return "-"
    high = valid[valid['shock'] >= 15.0]
    target = high['pos'] if len(high) >= 3 else valid['pos']
    p25 = int(round(np.percentile(target, 25), -1))
    p75 = int(round(np.percentile(target, 75), -1))
    if p25 == p75:
        return f"Pos {p25:,}"
    return f"Pos {p25:,} ~ {p75:,}"

def query_yesterday_kpis(target_date_str=None):
    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=KST)
    else:
        yesterday = (now_kst - timedelta(days=1)).date()
        target_date = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=KST)
        
    start_kst = target_date
    stop_kst = target_date + timedelta(days=1)
    start_utc = start_kst.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stop_utc = stop_kst.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_label = start_kst.strftime("%Y-%m-%d")

    client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=60000)
    query_api = client.query_api()

    # 1. ARMGC GCR Query (200-series cranes)
    q_armgc = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start_utc}, stop: {stop_utc})
      |> filter(fn: (r) => r["_measurement"] == "crane_movement")
      |> filter(fn: (r) => r["crane_id"] =~ /^2.*/)
      |> filter(fn: (r) => r["_field"] == "shock_penalty" or r["_field"] == "curr_penalty" or r["_field"] == "track_penalty" or r["_field"] == "peak_shock" or r["_field"] == "peak_shock_pos" or r["_field"] == "reducer_damage" or r["_field"] == "duration_s")
      |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
    '''
    t_armgc = query_api.query(q_armgc)
    recs_a = [r.values for t in t_armgc for r in t.records]
    df_a = pd.DataFrame(recs_a)
    armgc_alerts = []
    armgc_near = []
    if not df_a.empty:
        df_a = df_a[df_a['duration_s'] > 0]
        df_a['stress'] = df_a['shock_penalty'] * df_a['curr_penalty'] * df_a['track_penalty']
        for cid, g in df_a.groupby('crane_id'):
            avg_s = float(g['stress'].mean())
            item = {
                'crane_id': cid,
                'events': len(g),
                'avg_stress': avg_s,
                'max_stress': float(g['stress'].max()),
                'avg_shock': float(g['shock_penalty'].mean()),
                'avg_curr': float(g['curr_penalty'].mean()),
                'avg_track': float(g['track_penalty'].mean()),
                'max_peak_shock': float(g['peak_shock'].max()),
                'hotspot': find_hotspot_pos_str(g.get('peak_shock_pos', pd.Series(dtype=float)), g['peak_shock']),
                'cause': diagnose_armgc_cause(float(g['shock_penalty'].mean()), float(g['curr_penalty'].mean()), float(g['track_penalty'].mean()))
            }
            if avg_s >= ARMGC_STRESS_THRESHOLD:
                armgc_alerts.append(item)
            elif avg_s >= ARMGC_STRESS_THRESHOLD * 0.90:
                armgc_near.append(item)
        armgc_alerts.sort(key=lambda x: x['avg_stress'], reverse=True)
        armgc_near.sort(key=lambda x: x['avg_stress'], reverse=True)

    # 2. QC SCR Query (100-series cranes, v3.1.1 isolated)
    q_qc = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start_utc}, stop: {stop_utc})
      |> filter(fn: (r) => r["_measurement"] == "crane_movement")
      |> filter(fn: (r) => r["crane_type"] == "QC" and r["component"] == "SpreaderCable" and r["algo_version"] == "3.1.1")
      |> filter(fn: (r) => r["_field"] == "shock_penalty" or r["_field"] == "curr_penalty" or r["_field"] == "load_factor" or r["_field"] == "track_penalty" or r["_field"] == "peak_shock" or r["_field"] == "reducer_damage" or r["_field"] == "duration_s")
      |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
    '''
    t_qc = query_api.query(q_qc)
    recs_q = [r.values for t in t_qc for r in t.records]
    df_q = pd.DataFrame(recs_q)
    qc_alerts = []
    qc_near = []
    if not df_q.empty:
        df_q = df_q[df_q['duration_s'] > 0]
        load_col = df_q['load_factor'].fillna(1.0) if 'load_factor' in df_q.columns else 1.0
        df_q['stress'] = df_q['shock_penalty'] * df_q['curr_penalty'] * load_col
        for cid, g in df_q.groupby('crane_id'):
            avg_s = float(g['stress'].mean())
            lf = float(g['load_factor'].mean()) if 'load_factor' in g.columns else 1.0
            item = {
                'crane_id': cid,
                'events': len(g),
                'avg_stress': avg_s,
                'max_stress': float(g['stress'].max()),
                'avg_shock': float(g['shock_penalty'].mean()),
                'avg_curr': float(g['curr_penalty'].mean()),
                'avg_load': lf,
                'max_peak_shock': float(g['peak_shock'].max()),
                'cause': diagnose_qc_cause(float(g['shock_penalty'].mean()), float(g['curr_penalty'].mean()), lf)
            }
            if avg_s >= QC_STRESS_THRESHOLD:
                qc_alerts.append(item)
            elif avg_s >= QC_STRESS_THRESHOLD * 0.90:
                qc_near.append(item)
        qc_alerts.sort(key=lambda x: x['avg_stress'], reverse=True)
        qc_near.sort(key=lambda x: x['avg_stress'], reverse=True)

    return date_label, armgc_alerts, armgc_near, qc_alerts, qc_near

def build_email_content(date_label, armgc_alerts, armgc_near, qc_alerts, qc_near):
    armgc_names = ", ".join([f"{x['crane_id']}호" for x in armgc_alerts]) if armgc_alerts else "없음"
    qc_names = ", ".join([f"{x['crane_id']}호" for x in qc_alerts]) if qc_alerts else "없음"
    
    subject = f"[주장비 감속기 Stress 이상 감지 알림] 전일({date_label}) 일평균 기준 초과 호기 - ARMGC {len(armgc_alerts)}대({armgc_names}) / QC {len(qc_alerts)}대({qc_names})"

    armgc_dash_path = "/d/total_control_tower_v1/cranepdm-v2-6-reducer-damage-diagnostics?orgId=1"
    qc_dash_path = "/d/qc_spreader_pdm/274bdbc?orgId=1"
    armgc_url_lan = f"{GRAFANA_BASE_URL}{armgc_dash_path}"
    qc_url_lan = f"{GRAFANA_BASE_URL}{qc_dash_path}"
    armgc_url_local = f"http://localhost:3000{armgc_dash_path}"
    qc_url_local = f"http://localhost:3000{qc_dash_path}"

    if armgc_alerts:
        armgc_rows = ""
        for x in armgc_alerts:
            crane_url = f"{armgc_url_lan}&var-Crane_ID={x['crane_id']}"
            armgc_rows += f"""
            <tr>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center; font-weight:bold; font-size:14px;">
                    <a href="{crane_url}" target="_blank" rel="noopener noreferrer" style="color:#0969da; text-decoration:underline;">ARMGC {x['crane_id']}호</a>
                </td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center; background-color:#ffebe9; color:#cf222e; font-weight:bold; font-size:15px;">
                    {x['avg_stress']:.2f}
                </td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">{x['max_stress']:.1f}</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">{x['events']:,}회</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">
                    Shock <b>{x['avg_shock']:.2f}</b> / Curr <b>{x['avg_curr']:.2f}</b> / Track <b>{x['avg_track']:.2f}</b>
                </td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">{x['max_peak_shock']:.1f} G</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center; font-weight:bold;">{x['hotspot']}</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:left; font-size:12.5px; line-height:1.4;">{x['cause']}</td>
            </tr>
            """
    else:
        armgc_rows = """
        <tr>
            <td colspan="8" style="padding:14px; border:1px solid #d0d7de; text-align:center; color:#1a7f37; background-color:#dafbe1;">
                전일 기준치(50.0) 초과 ARMGC 호기 없음 (정상)
            </td>
        </tr>
        """

    if qc_alerts:
        qc_rows = ""
        for x in qc_alerts:
            crane_url = f"{qc_url_lan}&var-Crane_ID={x['crane_id']}"
            qc_rows += f"""
            <tr>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center; font-weight:bold; font-size:14px;">
                    <a href="{crane_url}" target="_blank" rel="noopener noreferrer" style="color:#0969da; text-decoration:underline;">QC {x['crane_id']}호</a>
                </td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center; background-color:#ffebe9; color:#cf222e; font-weight:bold; font-size:15px;">
                    {x['avg_stress']:.2f}
                </td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">{x['max_stress']:.1f}</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">{x['events']:,}회</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">
                    Shock <b>{x['avg_shock']:.2f}</b> / Curr <b>{x['avg_curr']:.3f}</b> / Load <b>{x['avg_load']:.2f}</b>
                </td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:center;">{x['max_peak_shock']:.1f} G</td>
                <td style="padding:10px; border:1px solid #d0d7de; text-align:left; font-size:12.5px; line-height:1.4;">{x['cause']}</td>
            </tr>
            """
    else:
        qc_rows = """
        <tr>
            <td colspan="7" style="padding:14px; border:1px solid #d0d7de; text-align:center; color:#1a7f37; background-color:#dafbe1;">
                전일 기준치(6.0) 초과 QC 호기 없음 (정상)
            </td>
        </tr>
        """

    near_html = ""
    if armgc_near or qc_near:
        parts = []
        if armgc_near:
            parts.append("ARMGC 주의 관찰(45.0~49.9): " + ", ".join([f"<b>{x['crane_id']}호</b>({x['avg_stress']:.2f})" for x in armgc_near]))
        if qc_near:
            parts.append("QC 주의 관찰(5.4~5.99): " + ", ".join([f"<b>{x['crane_id']}호</b>({x['avg_stress']:.2f})" for x in qc_near]))
        near_html = f"""
        <div style="margin-top:12px; padding:10px 14px; background-color:#fff8c5; border-left:4px solid #d4a72c; font-size:13px; color:#4d2d00;">
            <b>임계치 근접(주의 관찰) 호기 안내:</b> {" &nbsp;|&nbsp; ".join(parts)}
        </div>
        """

    html_body = f"""
    <html>
    <body style="font-family:'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; color:#24292f; line-height:1.5; margin:0; padding:16px;">
        <div style="max-width:980px; border:1px solid #d0d7de; border-radius:8px; overflow:hidden;">
            <div style="background-color:#1f2328; color:#ffffff; padding:16px 20px;">
                <h2 style="margin:0; font-size:18px;">주장비 감속기 Stress 이상 감지 알림</h2>
                <p style="margin:6px 0 0 0; font-size:13px; color:#d0d7de;">
                    집계 대상일: <b>{date_label} (00:00 ~ 24:00 KST)</b> &nbsp;|&nbsp;
                    알람 기준: <b>ARMGC GCR 일평균 ≥ {ARMGC_STRESS_THRESHOLD:.1f}</b> / <b>QC SCR 일평균 ≥ {QC_STRESS_THRESHOLD:.1f}</b>
                </p>
            </div>

            <div style="padding:20px;">
                <h3 style="margin:0 0 10px 0; font-size:15px; color:#cf222e;">
                    1. ARMGC GCR (야드 크레인 케이블 릴 감속기) — 기준({ARMGC_STRESS_THRESHOLD:.1f}) 초과: {len(armgc_alerts)}대
                </h3>
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead>
                        <tr style="background-color:#f6f8fa; color:#24292f;">
                            <th style="padding:10px; border:1px solid #d0d7de; width:90px;">호기</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:95px;">전일 평균<br>Stress</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:75px;">최고<br>Stress</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:75px;">주행<br>횟수</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:210px;">세부 평균 페널티<br>(Shock / Curr / Track)</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:85px;">최고 충격<br>(Peak Shock)</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:125px;">충격 다발 구간<br>(Rail Pos)</th>
                            <th style="padding:10px; border:1px solid #d0d7de;">주요 추정 원인 및 권장 점검 포인트</th>
                        </tr>
                    </thead>
                    <tbody>
                        {armgc_rows}
                    </tbody>
                </table>

                <h3 style="margin:24px 0 10px 0; font-size:15px; color:#0969da;">
                    2. QC SCR (안벽 크레인 스프레더 케이블 감속기) — 기준({QC_STRESS_THRESHOLD:.1f}) 초과: {len(qc_alerts)}대
                </h3>
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead>
                        <tr style="background-color:#f6f8fa; color:#24292f;">
                            <th style="padding:10px; border:1px solid #d0d7de; width:90px;">호기</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:95px;">전일 평균<br>Stress</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:75px;">최고<br>Stress</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:75px;">운전<br>횟수</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:210px;">세부 평균 페널티<br>(Shock / Curr / Load)</th>
                            <th style="padding:10px; border:1px solid #d0d7de; width:85px;">최고 충격<br>(Peak Shock)</th>
                            <th style="padding:10px; border:1px solid #d0d7de;">주요 추정 원인 및 권장 점검 포인트</th>
                        </tr>
                    </thead>
                    <tbody>
                        {qc_rows}
                    </tbody>
                </table>

                {near_html}

                <div style="margin-top:20px; padding:14px 16px; background-color:#f6f8fa; border:1px solid #d0d7de; border-radius:6px; font-size:13px; line-height:1.8;">
                    <b>Grafana 실시간 대시보드 바로가기</b> (장비망 PC 접속 필요)<br>
                    &bull; <b>ARMGC GCR 대시보드:</b>
                    <a href="{armgc_url_lan}" target="_blank" rel="noopener noreferrer" style="color:#0969da; font-weight:bold; text-decoration:underline;">[장비망 접속 (10.200.19.104)]</a> &nbsp;|&nbsp;
                    <a href="{armgc_url_local}" target="_blank" rel="noopener noreferrer" style="color:#0969da; text-decoration:underline;">[모니터링 서버 본체 접속 (localhost)]</a><br>
                    &bull; <b>QC SCR 대시보드:</b>
                    <a href="{qc_url_lan}" target="_blank" rel="noopener noreferrer" style="color:#0969da; font-weight:bold; text-decoration:underline;">[장비망 접속 (10.200.19.104)]</a> &nbsp;|&nbsp;
                    <a href="{qc_url_local}" target="_blank" rel="noopener noreferrer" style="color:#0969da; text-decoration:underline;">[모니터링 서버 본체 접속 (localhost)]</a>
                </div>
            </div>
        </div>
    </body>
    </html>
    """
    return subject, html_body

def send_via_smtp(to_addr, subject, html_body):
    """
    Sends HTML email directly via HPNT internal Exchange SMTP server (mail.hpnt.co.kr:25)
    without opening Outlook GUI or requiring any interactive login credentials.
    """
    msg = MIMEMultipart('alternative')
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_addr
    msg.attach(MIMEText(html_body, 'html', 'utf-8'))

    with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.sendmail(to_addr, [to_addr], msg.as_string())

def main():
    parser = argparse.ArgumentParser(description="Daily 08:00 KST Crane PdM Outlook Alert Sender")
    parser.add_argument("--date", type=str, default=None, help="Target date YYYY-MM-DD (default: yesterday)")
    parser.add_argument("--force", action="store_true", help="Send email even if no crane exceeds threshold")
    parser.add_argument("--dry-run", action="store_true", help="Print summary without sending email")
    args = parser.parse_args()

    date_label, armgc_alerts, armgc_near, qc_alerts, qc_near = query_yesterday_kpis(args.date)
    log_msg(f"Checked date={date_label}: ARMGC alerts(>={ARMGC_STRESS_THRESHOLD})={len(armgc_alerts)}, QC alerts(>={QC_STRESS_THRESHOLD})={len(qc_alerts)}")

    if not armgc_alerts and not qc_alerts and not args.force:
        log_msg(f"No cranes exceeded thresholds on {date_label}. Skipping email (per policy: send only when exceeded).")
        return

    subject, html_body = build_email_content(date_label, armgc_alerts, armgc_near, qc_alerts, qc_near)
    if args.dry_run:
        log_msg(f"[DRY-RUN] Subject: {subject}")
        return

    send_via_smtp(RECIPIENT_EMAIL, subject, html_body)
    log_msg(f"SUCCESS: Sent SMTP alert email via {SMTP_SERVER}:{SMTP_PORT} to {RECIPIENT_EMAIL} | Subject: {subject}")

if __name__ == "__main__":
    main()
