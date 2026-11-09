import snap7
from snap7.util import get_int, get_bool
import time
import math
import csv
import gzip
import glob
import os
from datetime import datetime, timedelta
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import threading
import numpy as np
import sys
import pystray
from PIL import Image
try:
    import winreg
except ImportError:
    winreg = None # For non-windows dev/test

# PLC Configurations
CRANES = [
    # Block 1
    {"id": "211", "ip": "10.200.71.11", "rack": 0, "slot": 2},
    {"id": "212", "ip": "10.200.71.12", "rack": 0, "slot": 2},
    {"id": "213", "ip": "10.200.71.13", "rack": 0, "slot": 2},
    {"id": "214", "ip": "10.200.72.14", "rack": 0, "slot": 2},
    {"id": "215", "ip": "10.200.72.15", "rack": 0, "slot": 2},
    {"id": "216", "ip": "10.200.72.16", "rack": 0, "slot": 2},
    # Block 2
    {"id": "221", "ip": "10.200.71.17", "rack": 0, "slot": 2},
    {"id": "222", "ip": "10.200.71.18", "rack": 0, "slot": 2},
    {"id": "223", "ip": "10.200.71.19", "rack": 0, "slot": 2},
    {"id": "224", "ip": "10.200.72.20", "rack": 0, "slot": 2},
    {"id": "225", "ip": "10.200.72.21", "rack": 0, "slot": 2},
    {"id": "226", "ip": "10.200.72.22", "rack": 0, "slot": 2},
    # Block 3
    {"id": "231", "ip": "10.200.71.23", "rack": 0, "slot": 2},
    {"id": "232", "ip": "10.200.71.24", "rack": 0, "slot": 2},
    {"id": "233", "ip": "10.200.71.25", "rack": 0, "slot": 2},
    {"id": "234", "ip": "10.200.72.26", "rack": 0, "slot": 2},
    {"id": "235", "ip": "10.200.72.27", "rack": 0, "slot": 2},
    {"id": "236", "ip": "10.200.72.28", "rack": 0, "slot": 2},
    # Block 4
    {"id": "241", "ip": "10.200.71.29", "rack": 0, "slot": 2},
    {"id": "242", "ip": "10.200.71.30", "rack": 0, "slot": 2},
    {"id": "243", "ip": "10.200.71.31", "rack": 0, "slot": 2},
    {"id": "244", "ip": "10.200.72.32", "rack": 0, "slot": 2},
    {"id": "245", "ip": "10.200.72.33", "rack": 0, "slot": 2},
    {"id": "246", "ip": "10.200.72.34", "rack": 0, "slot": 2},
    # Block 5
    {"id": "251", "ip": "10.200.71.35", "rack": 0, "slot": 2},
    {"id": "252", "ip": "10.200.71.36", "rack": 0, "slot": 2},
    {"id": "253", "ip": "10.200.71.37", "rack": 0, "slot": 2},
    {"id": "254", "ip": "10.200.72.38", "rack": 0, "slot": 2},
    {"id": "255", "ip": "10.200.72.39", "rack": 0, "slot": 2},
    {"id": "256", "ip": "10.200.72.40", "rack": 0, "slot": 2},
    # Block 6
    {"id": "261", "ip": "10.200.71.47", "rack": 0, "slot": 2},
    {"id": "262", "ip": "10.200.71.41", "rack": 0, "slot": 2},
    {"id": "263", "ip": "10.200.71.42", "rack": 0, "slot": 2},
    {"id": "264", "ip": "10.200.72.43", "rack": 0, "slot": 2},
    {"id": "265", "ip": "10.200.72.44", "rack": 0, "slot": 2},
    {"id": "266", "ip": "10.200.72.45", "rack": 0, "slot": 2},
    # Block 7
    {"id": "271", "ip": "10.200.72.48", "rack": 0, "slot": 2},
    {"id": "272", "ip": "10.200.72.46", "rack": 0, "slot": 2},
    # QC Cranes (Full Deployment)
    {"id": "101", "ip": "10.200.73.11", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "102", "ip": "10.200.73.12", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "103", "ip": "10.200.73.13", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "104", "ip": "10.200.73.14", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "105", "ip": "10.200.73.15", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "106", "ip": "10.200.73.16", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "107", "ip": "10.200.73.17", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "108", "ip": "10.200.73.18", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "109", "ip": "10.200.73.19", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "110", "ip": "10.200.73.20", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "111", "ip": "10.200.73.21", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "112", "ip": "10.200.73.22", "rack": 0, "slot": 2, "type": "QC", "drive": "SINAMICS"}
]

# Logging Configuration
CSV_FILE = 'crane_kpi_log.csv'
RAW_DATA_DIR = 'raw_plc_data'  # Raw PLC samples saved here (gzip compressed)
RAW_RETENTION_DAYS = 90        # Auto-move raw files older than this to backups
IDLE_POLL_RATE = 0.5    # Seconds between checks when idle
APP_VERSION = "3.2.2"   # Version 3.2.2 - Simplified alert table + top Peak Shock crane (ARMGC); prev 3.2.1 Updated Alert Title & Fixed Grafana Dashboard Links (SMTP mail.hpnt.co.kr)
ACTIVE_POLL_RATE = 0.1  # Version 3.2.2 - QC 112 SINAMICS Scale Normalization + Daily 08:00 Alert Mailer
SPEED_THRESHOLD = 50    # Minimum speed to trigger 'movement' event

# V2.6: Geo-fence / hotspot map removed. Position is observational only.
# Rail condition is surfaced via Grafana Rail Heatmap + anomaly alerts, not
# baked into the damage formula. The measured shock/current penalties already
# encode the physical stress; layering position multipliers on top was double-counting
# and prevented auto-detection of new sag sites / reduction after repair.

# InfluxDB Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"

# Initialize InfluxDB Client
influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

def init_csv():
    # Write header if file doesn't exist
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'crane_id', 'algo_version', 'event_duration_s',
                'peak_order', 'peak_feedback', 'max_error', 'rms_error',
                'reducer_damage', 'avg_weight', 'is_loaded',
                'shock_penalty', 'peak_shock', 'curr_penalty', 'track_penalty',
                'start_pos', 'end_pos', 'avg_pos'
            ])

def save_raw_event(crane_id, orders, feedbacks, loads, weights, positions, dt_list, db170_list):
    """Save raw PLC samples to daily gzip-compressed CSV file."""
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        day_dir = os.path.join(RAW_DATA_DIR, today)
        os.makedirs(day_dir, exist_ok=True)
        
        ts = datetime.now().strftime('%H%M%S')
        filename = os.path.join(day_dir, f"{crane_id}_{ts}.csv.gz")
        
        with gzip.open(filename, 'wt', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['dt', 'order', 'feedback', 'loaded', 'weight', 'position',
                             'reel_speed', 'reel_current', 'reel_torque'])
            for i in range(len(orders)):
                db170 = db170_list[i] if db170_list and db170_list[i] else (0, 0, 0)
                writer.writerow([
                    round(dt_list[i], 4) if i < len(dt_list) else 0,
                    orders[i], feedbacks[i],
                    1 if loads[i] else 0,
                    weights[i], positions[i],
                    db170[0], db170[1], db170[2]
                ])
    except Exception as e:
        sync_print(f"[!] [{crane_id}] Raw save error: {e}")

def cleanup_old_raw_data():
    """Move raw data directories older than RAW_RETENTION_DAYS to backups folder."""
    backup_base = os.path.join("..", "backups", "raw_plc_data")
    while not stop_event.is_set():
        try:
            if os.path.exists(RAW_DATA_DIR):
                cutoff = datetime.now() - timedelta(days=RAW_RETENTION_DAYS)
                for entry in os.listdir(RAW_DATA_DIR):
                    dir_path = os.path.join(RAW_DATA_DIR, entry)
                    if os.path.isdir(dir_path):
                        try:
                            dir_date = datetime.strptime(entry, '%Y-%m-%d')
                            if dir_date < cutoff:
                                import shutil
                                os.makedirs(backup_base, exist_ok=True)
                                backup_path = os.path.join(backup_base, entry)
                                if not os.path.exists(backup_path):
                                    shutil.move(dir_path, backup_base)
                                    sync_print(f"[CLEANUP] Moved old raw data to backups: {entry}")
                                else:
                                    # If already exists in backup, just remove the local one to save space
                                    shutil.rmtree(dir_path)
                                    sync_print(f"[CLEANUP] Removed old raw data (already backed up): {entry}")
                        except ValueError:
                            pass
        except Exception as e:
            sync_print(f"[!] Cleanup error: {e}")
        # Run cleanup once per day
        stop_event.wait(86400)
            
# Thread-safe lock for printing
print_lock = threading.Lock()

def sync_print(msg):
    with print_lock:
        print(msg)

# --- Auto-start & Tray Logic ---
REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
APP_NAME = "CranePdMLogger"

def set_autostart(enabled):
    if not winreg: return
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_SET_VALUE)
        if enabled:
            # Get absolute path of current executable
            if getattr(sys, 'frozen', False):
                exe_path = f'"{os.path.realpath(sys.executable)}"'
            else:
                exe_path = f'"{sys.executable}" "{os.path.realpath(__file__)}"'
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, exe_path)
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass
        winreg.CloseKey(key)
    except Exception as e:
        sync_print(f"[!] Failed to set autostart: {e}")

def is_autostart_enabled():
    if not winreg: return False
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH, 0, winreg.KEY_READ)
        winreg.QueryValueEx(key, APP_NAME)
        winreg.CloseKey(key)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False

stop_event = threading.Event()

def on_quit(icon, item):
    sync_print("Exiting...")
    stop_event.set()
    icon.stop()

def on_autostart_toggle(icon, item):
    new_state = not item.checked
    set_autostart(new_state)

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

def setup_tray():
    icon_path = resource_path('crane_icon.ico')
    try:
        if os.path.exists(icon_path):
            image = Image.open(icon_path)
        else:
            image = Image.new('RGB', (64, 64), color=(73, 109, 137))
    except Exception as e:
        sync_print(f"[!] Failed to load icon: {e}")
        image = Image.new('RGB', (64, 64), color=(73, 109, 137))

    menu = pystray.Menu(
        pystray.MenuItem("Auto-start on Boot", on_autostart_toggle, checked=lambda item: is_autostart_enabled()),
        pystray.MenuItem("Exit", on_quit)
    )
    
    icon = pystray.Icon(APP_NAME, image, f"Crane PdM Logger v{APP_VERSION}", menu)
    return icon

def calculate_kpis(orders, feedbacks, loads, weights, positions, dt_list, db170_list=None):
    """
    V2.6 Physical Model — Pure measurement-driven damage, no position weighting.
    Cable Reel Drive Data (Torque, Speed, Current) only.
    If db170_list is unavailable (DB not mapped), event is skipped.
    Rail hotspots are diagnosed at the Grafana layer (Rail Heatmap) using the
    `peak_shock` × `peak_shock_pos` fields, not via in-formula penalties.
    """
    if not orders or len(orders) < 2:
        return None

    # Require DB170 data to compute V2.0 damage
    # If any sample is None, skip this event (DB not mapped yet)
    if not db170_list or not all(v is not None for v in db170_list) or len(db170_list) != len(orders):
        return None

    avg_weight = sum(weights) / len(weights) if weights else 0
    # V2.1: Weight Clamping (Ignore sensor noise <0 or >60t)
    avg_weight = max(0.0, min(avg_weight, 60.0))
    
    # V2.2: Weight factor removed for GCR (Cable Reel Reducer).
    # Cable Reel load is independent of container weight.
    weight_factor = 1.0

    # Identify dominant load state (Twistlock bit OR weight threshold)
    is_loaded = (sum(loads) > len(loads) // 2) or (avg_weight > 5.0)
    avg_pos = sum(positions) / len(positions) if positions else 0

    # Identifiers and thresholds for refined V2.1 formula
    # TRACK_EPSILON: Higher value reduces noise at low speeds
    # TRACK_SCALE: V2.1 reduced from 10.0 to 5.0 to balance with other penalties
    # TRACK_GATE: V2.1 increased from 100 to 500 to ignore jitter at very low speeds
    # CURR_THRESHOLD: Lowered to 0.2 to catch mechanical resistance earlier
    TRACK_EPSILON = 50.0
    TRACK_SCALE = 5.0
    TRACK_GATE = 500
    CURR_THRESHOLD = 0.2
    MAX_INDIVIDUAL_PENALTY = 10.0
    MAX_TOTAL_PENALTY = 20.0

    max_err = 0
    sum_sq_err = 0
    total_reducer_damage = 0
    shock_list, curr_list, track_list = [], [], []
    # V2.5 fix (retained): init peak_shock=0 so the first sample (raw_shock >= 1.0)
    # always updates peak_shock_pos. Previously raw_shock==1.0 samples left pos at
    # positions[0] (often 0).
    peak_shock = 0.0
    peak_shock_pos = positions[0] if positions else 0.0
    peak_order = max(map(abs, orders))
    peak_fb = max(map(abs, feedbacks))

    for i in range(1, len(orders)):
        dt = dt_list[i] if dt_list[i] > 0 else 0.1
        order = orders[i]
        fb = feedbacks[i]

        # Speed tracking error
        error = order - fb
        abs_err = abs(error)
        sum_sq_err += error ** 2
        if abs_err > max_err:
            max_err = abs_err

        # V2.0 Physical Model
        v2_speed, v2_current, v2_torque = db170_list[i]
        prev_v2_torque = db170_list[i-1][2] if i > 0 else v2_torque

        # Base Fatigue (Miner's Rule) + V2.2 GCR Profile (Weight factor is 1.0)
        base_fatigue = (abs(v2_torque) ** 3) * abs(v2_speed) / 1000000.0 * weight_factor

        # V2.6.1 (A): Speed-Normalized Shock Penalty — cap 0.3 → 0.05 for true low-speed amplification
        # outlier 보호: per-sample penalty 를 MAX_INDIVIDUAL_PENALTY 로 cap (정의된 상수 활용)
        torque_deriv = (v2_torque - prev_v2_torque) / dt
        raw_shock = 1.0 + 0.06 * abs(torque_deriv)
        speed_factor_shock = max(0.05, abs(v2_speed) / 10000.0)
        shock_penalty = min(MAX_INDIVIDUAL_PENALTY,
                            1.0 + (raw_shock - 1.0) / speed_factor_shock)

        # V2.6.1 (A): Speed-Normalized Current Penalty — cap 0.5 → 0.10
        if abs(v2_torque) > 10.0:
            curr_ratio = abs(v2_current) / (abs(v2_torque) + 0.1)
            raw_curr_penalty = 1.0 + 5.0 * max(0, curr_ratio - CURR_THRESHOLD)
            speed_factor_curr = max(0.10, abs(v2_speed) / 10000.0)
            curr_penalty = min(MAX_INDIVIDUAL_PENALTY,
                               1.0 + (raw_curr_penalty - 1.0) / speed_factor_curr)
        else:
            curr_penalty = 1.0

        # Control Anomaly Penalty B — Speed tracking error (Cap at MAX_INDIVIDUAL_PENALTY)
        if abs(order) > TRACK_GATE:
            tracking_error_ratio = abs_err / (abs(order) + TRACK_EPSILON)
            tracking_penalty = min(MAX_INDIVIDUAL_PENALTY,
                                   1.0 + TRACK_SCALE * max(0, tracking_error_ratio - 0.05))
        else:
            tracking_penalty = 1.0

        # V2.6: Damage is purely measurement-driven. Position is recorded via
        # peak_shock_pos/avg_pos for diagnostic use at the Grafana layer, but no
        # location-based multiplier is applied to the damage formula.
        total_penalty = shock_penalty * curr_penalty * tracking_penalty
        instant_damage = base_fatigue * total_penalty * 0.001
        total_reducer_damage += instant_damage
        
        shock_list.append(shock_penalty)
        curr_list.append(curr_penalty)
        track_list.append(tracking_penalty)
        # V2.3: Record the TRUE unbounded shock severity for maintenance insight
        if raw_shock > peak_shock:
            peak_shock = raw_shock
            peak_shock_pos = positions[i]

    rms_error = math.sqrt(sum_sq_err / len(orders))
    event_duration = sum(dt_list)
    # V2.6.1: per-sample 평균 (B 가중 집계 미적용, A 만 유지)
    if shock_list:
        avg_shock = sum(shock_list) / len(shock_list)
        avg_curr  = sum(curr_list)  / len(curr_list)
        avg_track = sum(track_list) / len(track_list)
    else:
        avg_shock = avg_curr = avg_track = 1.0

    return {
        'algo_version': '3.1.1',
        'duration': round(event_duration, 2),
        'peak_order': peak_order,
        'peak_fb': peak_fb,
        'max_error': max_err,
        'rms_error': round(rms_error, 2),
        'reducer_damage': round(total_reducer_damage, 2),
        'avg_weight': round(avg_weight, 1),
        'is_loaded': is_loaded,
        'shock_penalty': round(avg_shock, 3),
        'peak_shock': round(peak_shock, 3),
        'peak_shock_pos': round(peak_shock_pos, 1),
        'curr_penalty': round(avg_curr, 3),
        'track_penalty': round(avg_track, 3),
        'start_pos': positions[0],
        'end_pos': positions[-1],
        'avg_pos': round(avg_pos, 1)
    }

# QC 112 (Siemens SINAMICS Drive) -> Masterdrive (QC 101~111) Normalization Scale Factors
# Raw PLC DB180 files (raw_plc_data) preserve unscaled PLC values; normalization is applied only in calculate_kpis_qc().
QC_SINAMICS_CRANES = {"112"}
SINAMICS_SPEED_SCALE = 0.667    # SINAMICS speed range (~1350-1600) -> Masterdrive (~850-1000)
SINAMICS_CURR_SCALE = 1.65      # SINAMICS current range (idle ~20, max ~28) -> Masterdrive (idle ~30, max ~46)
SINAMICS_TORQUE_SCALE = 3.50    # SINAMICS torque range (idle ~27, max ~40) -> Masterdrive (idle ~90, max ~140)
SINAMICS_SHOCK_DAMPING = 0.43   # SINAMICS ramp d(Speed)/dt & d(Torque)/dt damping to match Masterdrive baseline (~5.0)

def calculate_kpis_qc(orders, feedbacks, loads, weights, positions, dt_list, db180_list, crane_id=None):
    """
    QC SCR V3.1 Dedicated KPI calculation function.
    Tailored for Hoist (Vertical Lifting) mechanism & Manual Driver Operation.
    Includes scale normalization for QC 112 (Siemens SINAMICS drive) while keeping raw PLC logs unscaled.
    """
    if not orders or not dt_list or not db180_list:
        return None
        
    event_duration = sum(dt_list)
    if event_duration <= 0:
        return None

    valid_db180 = [v for v in db180_list if v is not None]
    if not valid_db180:
        return None

    is_sinamics = (str(crane_id) in QC_SINAMICS_CRANES)
    if is_sinamics:
        speeds = [v[0] * SINAMICS_SPEED_SCALE for v in valid_db180]
        currents = [v[1] * SINAMICS_CURR_SCALE for v in valid_db180]
        torques = [v[2] * SINAMICS_TORQUE_SCALE for v in valid_db180]
        shock_coeff = 0.02 * SINAMICS_SHOCK_DAMPING
    else:
        speeds = [float(v[0]) for v in valid_db180]
        currents = [float(v[1]) for v in valid_db180]
        torques = [float(v[2]) for v in valid_db180]
        shock_coeff = 0.02
    
    peak_speed = round(max([abs(s) for s in speeds]), 1) if speeds else 0.0
    avg_weight = sum(weights) / len(weights) if weights else 1.0
    is_loaded = any(loads) if loads else False

    # 1. Manual Operation Shock Penalty:
    # Captures manual joystick dynamic spikes in torque d(Torque)/dt & speed acceleration d(Speed)/dt
    dt_arr = np.array(dt_list[:len(valid_db180)])
    dt_arr = np.where(dt_arr <= 0, 0.1, dt_arr)
    
    torque_arr = np.array(torques, dtype=float)
    speed_arr = np.array(speeds, dtype=float)
    
    d_torque = np.abs(np.diff(torque_arr, prepend=torque_arr[0])) / dt_arr
    d_speed = np.abs(np.diff(speed_arr, prepend=speed_arr[0])) / dt_arr
    
    raw_shock_list = 1.0 + shock_coeff * d_torque + shock_coeff * d_speed
    shock_penalty = float(np.percentile(raw_shock_list, 95))
    peak_shock = float(np.max(raw_shock_list))

    # 2. Hoist Drive Current Penalty:
    # Offset base idling/holding current (~30 Amps) and evaluate over-current ratio
    curr_ratios = []
    for c, t in zip(currents, torques):
        adj_curr = max(0.0, abs(c) - 30.0)
        t_abs = abs(t) + 1.0
        curr_ratios.append(adj_curr / t_abs)
        
    avg_curr_ratio = sum(curr_ratios) / len(curr_ratios) if curr_ratios else 0.0
    curr_penalty = min(5.0, max(1.0, 1.0 + 0.15 * avg_curr_ratio))

    # 3. Hoist Load Factor (Replaces track_penalty):
    # Weight load factor: 1.0 base, increases slightly if load/weight is heavy
    w_effective = avg_weight if is_loaded else 1.0
    load_factor = min(3.0, max(1.0, 1.0 + 0.02 * max(0.0, w_effective - 10.0)))

    return {
        'algo_version': '3.1.1',
        'duration': round(event_duration, 2),
        'peak_order': peak_speed,
        'peak_fb': peak_speed,
        'max_error': 0.0,
        'rms_error': 0.0,
        'reducer_damage': round(shock_penalty * curr_penalty * load_factor * (event_duration / 10.0), 2),
        'avg_weight': round(avg_weight, 1),
        'is_loaded': is_loaded,
        'shock_penalty': round(shock_penalty, 3),
        'peak_shock': round(peak_shock, 3),
        'peak_shock_pos': 0.0,
        'curr_penalty': round(curr_penalty, 3),
        'track_penalty': round(load_factor, 3), # Log CSV compatibility
        'load_factor': round(load_factor, 3),
        'start_pos': 0.0,
        'end_pos': 0.0,
        'avg_pos': 0.0
    }

def log_event(crane_id, kpis):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([
            ts,
            crane_id,
            kpis['algo_version'],
            kpis['duration'],
            kpis['peak_order'],
            kpis['peak_fb'],
            kpis['max_error'],
            kpis['rms_error'],
            kpis['reducer_damage'],
            kpis['avg_weight'],
            1 if kpis['is_loaded'] else 0,
            kpis['shock_penalty'],
            kpis['peak_shock'],
            kpis['curr_penalty'],
            kpis['track_penalty'],
            kpis['start_pos'],
            kpis['end_pos'],
            kpis['avg_pos'],
            kpis['peak_shock_pos']
        ])
        
    try:
        crane_type = "QC" if crane_id.startswith("1") else "ARMGC"
        component = "SpreaderCable" if crane_type == "QC" else "CableReel"
        source_tag = "live_qc_v31" if crane_type == "QC" else "live_v26"
        load_val = float(kpis.get('load_factor', kpis.get('track_penalty', 1.0)))
        
        point = (
            Point("crane_movement")
            .tag("crane_id", crane_id)
            .tag("crane_type", crane_type)
            .tag("component", component)
            .tag("source", source_tag)
            .tag("algo_version", kpis['algo_version'])
            .tag("is_loaded", "Loaded" if kpis['is_loaded'] else "Empty")
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
            .field("load_factor", load_val)
            .field("start_pos", float(kpis['start_pos']))
            .field("end_pos", float(kpis['end_pos']))
            .field("avg_pos", float(kpis['avg_pos']))
            .field("peak_shock_pos", float(kpis['peak_shock_pos']))
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        influx_status = "InfluxDB OK"
    except Exception as e:
        influx_status = f"InfluxDB Error: {e}"

    sync_print(f"[{ts}] [{crane_id}] Logged [v{kpis['algo_version']}] | Dur: {kpis['duration']}s | Pos: {kpis['start_pos']}->{kpis['end_pos']} | Dmg: {kpis['reducer_damage']} | {influx_status}")

def log_fault_event(crane_id, fault_name, position):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        point = (
            Point("crane_faults")
            .tag("crane_id", crane_id)
            .tag("fault_name", fault_name)
            .field("occurred", 1)
            .field("position", float(position))
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        sync_print(f"[FAULT] [{ts}] [{crane_id}] {fault_name} Triggered! Logged at Pos: {position}")
    except Exception as e:
        sync_print(f"[!] [{crane_id}] Fault InfluxDB Error: {e}")

def monitor_qc_spreader(crane_config):
    crane_id = crane_config['id']
    ip = crane_config['ip']
    rack = crane_config['rack']
    slot = crane_config['slot']
    
    QC_SPEED_THRESHOLD = 3  # Sensitive trigger for slower QC spreader reel (tuned from 10 to 3)
    client = snap7.client.Client()
    import struct
    prev_slack = False # Not used but declared for parity
    
    while not stop_event.is_set():
        try:
            if not client.get_connected():
                sync_print(f"[{datetime.now().strftime('%H:%M:%S')}] [{crane_id}] Connecting to QC PLC {ip}...")
                client.connect(ip, rack, slot)
                time.sleep(1)
                continue
            
            # Check IDLE state (Poll slowly from DB180)
            try:
                data = client.db_read(180, 0, 12)
                current_speed = struct.unpack('>h', data[6:8])[0]
            except Exception as read_err:
                sync_print(f"[!] [{crane_id}] QC Idle read error: {read_err}")
                time.sleep(IDLE_POLL_RATE)
                continue
                
            if abs(current_speed) < QC_SPEED_THRESHOLD:
                # Spreader is idle
                time.sleep(IDLE_POLL_RATE)
                continue
                
            # Movement Detected -> Switch to Active Logging
            sync_print(f"\n[MOVE] [{crane_id}] QC Spreader Movement! Speed: {current_speed}. Recording...")
            orders, feedbacks, loads, weights, positions, dt_list, db180_list = [], [], [], [], [], [], []
            last_time = time.time()
            
            while not stop_event.is_set():
                cycle_start = time.time()
                try:
                    data = client.db_read(180, 0, 12)
                    speed = struct.unpack('>h', data[6:8])[0]
                    current = struct.unpack('>h', data[8:10])[0]
                    torque = struct.unpack('>h', data[10:12])[0]
                    
                    # Record data point
                    now = time.time()
                    dt_list.append(now - last_time)
                    last_time = now
                    
                    # QC Spreader has no order/feedback distinction, map both to speed
                    orders.append(speed)
                    feedbacks.append(speed)
                    loads.append(False)
                    weights.append(1.0)
                    positions.append(0.0)
                    db180_list.append((speed, current, torque))
                    
                    # Stop Condition: Speed returns near 0
                    if abs(speed) < QC_SPEED_THRESHOLD:
                        sync_print(f"[STOP] [{crane_id}] QC Spreader Stopped. Analyzing {len(orders)} points...")
                        break
                        
                except Exception as ex_read:
                    sync_print(f"[!] [{crane_id}] QC Active read error: {ex_read}")
                    break
                
                # Maintain active poll rate
                elapsed = time.time() - cycle_start
                sleep_time = max(0, ACTIVE_POLL_RATE - elapsed)
                time.sleep(sleep_time)
                
            # Event finished, calculate and log KPIs
            if orders:
                kpis = calculate_kpis_qc(orders, feedbacks, loads, weights, positions, dt_list, db180_list, crane_id=crane_id)
                if kpis is None:
                    sync_print(f"[{crane_id}] DB180 데이터 없음 — 이벤트 폐기.")
                elif kpis['duration'] <= 1.5:
                    sync_print(f"[{crane_id}] QC Event too short ({kpis['duration']}s), ignored.")
                else:
                    log_event(crane_id, kpis)
                    save_raw_event(crane_id, orders, feedbacks, loads, weights, positions, dt_list, db180_list)
                    
        except Exception as e:
            sync_print(f"[!] [{crane_id}] QC Connection error: {e}. Retrying in 5 seconds...")
            try:
                client.disconnect()
            except:
                pass
            time.sleep(5)

def monitor_crane(crane_config):
    crane_id = crane_config['id']
    ip = crane_config['ip']
    rack = crane_config['rack']
    slot = crane_config['slot']
    
    if crane_config.get('type') == 'QC':
        monitor_qc_spreader(crane_config)
        return
        
    client = snap7.client.Client()
    prev_slack = False
    
    while not stop_event.is_set():
        try:
            if not client.get_connected():
                sync_print(f"[{datetime.now().strftime('%H:%M:%S')}] [{crane_id}] Connecting to PLC {ip}...")
                client.connect(ip, rack, slot)
                time.sleep(1)
                continue

            # Check Faults (Idle Polling)
            fault_data = client.db_read(59, 126, 1)
            current_slack = get_bool(fault_data, 0, 0)
            if current_slack and not prev_slack:
                pos_data = client.db_read(57, 200, 2)
                log_fault_event(crane_id, "Cable_Reel_Slack", get_int(pos_data, 0))
            prev_slack = current_slack

            # Check IDLE state (Poll slowly)
            order_data = client.db_read(57, 8, 2)
            current_order = get_int(order_data, 0)
            
            if abs(current_order) < SPEED_THRESHOLD:
                # Crane is idle
                time.sleep(IDLE_POLL_RATE)
                continue
            # Movement Detected -> Switch to Active Logging
            sync_print(f"\n[MOVE] [{crane_id}] Movement! Order: {current_order}. Recording...")
            orders, feedbacks, loads, weights, positions, dt_list, db170_list = [], [], [], [], [], [], []
            last_time = time.time()
            
            while not stop_event.is_set():
                cycle_start = time.time()
                try:
                    order_data = client.db_read(57, 8, 2)
                    current_order = get_int(order_data, 0)
                    
                    fb_data = client.db_read(57, 10, 2)
                    current_fb = get_int(fb_data, 0)
                    
                    tl_data = client.db_read(58, 185, 1)
                    is_locked = get_bool(tl_data, 0, 1)
                    
                    wt_data = client.db_read(57, 48, 2)
                    current_wt = get_int(wt_data, 0)
                    
                    pos_data = client.db_read(57, 200, 2)
                    current_pos = get_int(pos_data, 0)
                    
                    # Try DB170 (Cable Reel Drive data) on ALL cranes.
                    # If the PLC has not been mapped yet, the read will fail
                    # and db170_vals stays None → 이벤트가 폐기됩니다.
                    db170_vals = None
                    try:
                        db170_data = client.db_read(170, 0, 6)
                        db170_vals = (get_int(db170_data, 0), get_int(db170_data, 2), get_int(db170_data, 4))
                    except Exception:
                        db170_vals = None
                            
                    # Check Faults (Active Polling)
                    fault_data = client.db_read(59, 126, 1)
                    current_slack = get_bool(fault_data, 0, 0)
                    if current_slack and not prev_slack:
                        log_fault_event(crane_id, "Cable_Reel_Slack", current_pos)
                    prev_slack = current_slack
                    
                    # Record data point
                    now = time.time()
                    dt_list.append(now - last_time)
                    last_time = now
                    
                    orders.append(current_order)
                    feedbacks.append(current_fb)
                    loads.append(is_locked)
                    weights.append(current_wt)
                    positions.append(current_pos)
                    db170_list.append(db170_vals)
                    
                    # Stop Condition: Order speed returns near 0
                    if abs(current_order) < SPEED_THRESHOLD:
                        sync_print(f"[STOP] [{crane_id}] Stopped. Analyzing {len(orders)} points...")
                        break
                        
                except Exception as ex_read:
                    sync_print(f"[!] [{crane_id}] Read error: {ex_read}")
                    break
                
                # Maintain active poll rate
                elapsed = time.time() - cycle_start
                sleep_time = max(0, ACTIVE_POLL_RATE - elapsed)
                time.sleep(sleep_time)

            # Event finished, calculate and log KPIs
            if orders:
                kpis = calculate_kpis(orders, feedbacks, loads, weights, positions, dt_list, db170_list)
                if kpis is None:
                    sync_print(f"[{crane_id}] DB170 데이터 없음 — 이벤트 폐기.")
                elif kpis['duration'] <= 3.0:
                    sync_print(f"[{crane_id}] Event too short ({kpis['duration']}s), ignored.")
                else:
                    log_event(crane_id, kpis)
                    # Save raw PLC data for every valid event (gzip compressed)
                    save_raw_event(crane_id, orders, feedbacks, loads, weights, positions, dt_list, db170_list)
                    
        except Exception as e:
            sync_print(f"[!] [{crane_id}] Connection error: {e}. Retrying in 5 seconds...")
            try:
                client.disconnect()
            except:
                pass
            time.sleep(5)

def initialize_influx_kpis():
    """
    Ensure all cranes (especially newly added QC cranes 101~112) have at least one 
    heartbeat initialization record in InfluxDB, so that Grafana panels and variables 
    can render all crane tiles statically without waiting for their first physical movement.
    """
    sync_print("Initializing InfluxDB heartbeat records for all configured cranes...")
    init_kpis = {
        'algo_version': '3.1.1',
        'duration': 0.0,
        'peak_order': 0.0,
        'peak_fb': 0.0,
        'max_error': 0.0,
        'rms_error': 0.0,
        'reducer_damage': 0.0,
        'avg_weight': 1.0,
        'shock_penalty': 1.0,
        'peak_shock': 0.0,
        'curr_penalty': 1.0,
        'track_penalty': 1.0,
        'load_factor': 1.0,
        'start_pos': 0.0,
        'end_pos': 0.0,
        'avg_pos': 0.0,
        'peak_shock_pos': 0.0,
        'is_loaded': False
    }
    for crane in CRANES:
        cid = crane['id']
        try:
            log_event(cid, init_kpis)
        except Exception as e:
            sync_print(f"[!] Initialization failed for crane {cid}: {e}")

# --- Daily 08:00 KST Stress Alert Mailer (SMTP Direct to HPNT Exchange) ---
ALERT_SMTP_SERVER = "mail.hpnt.co.kr"
ALERT_SMTP_PORT = 25
ALERT_SENDER = "CranePdM_Alert <baewoong.kim@hpnt.co.kr>"
ALERT_RECIPIENT = "baewoong.kim@hpnt.co.kr"
ALERT_GRAFANA_URL = "http://10.200.19.104:3000"
ARMGC_ALERT_THRESHOLD = 50.0
QC_ALERT_THRESHOLD = 6.0
PEAK_SHOCK_COUNT_THRESHOLD = 15.0  # Peak Shock level counted as a high-impact event
ALERT_STATE_FILE = "daily_alert_last_checked.txt"
ALERT_LOG_FILE = "outlook_alert_history.log"

def _alert_log(msg):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] [ALERT] {msg}"
    sync_print(line)
    try:
        with open(ALERT_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def run_daily_stress_alert_check(target_date_str=None, force_send=False):
    from datetime import timezone
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    KST = timezone(timedelta(hours=9))
    now_kst = datetime.now(KST)
    if target_date_str:
        target_date = datetime.strptime(target_date_str, "%Y-%m-%d").replace(tzinfo=KST)
    else:
        yesterday = (now_kst - timedelta(days=1)).date()
        target_date = datetime(yesterday.year, yesterday.month, yesterday.day, 0, 0, 0, tzinfo=KST)

    start_utc = target_date.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    stop_utc = (target_date + timedelta(days=1)).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date_label = target_date.strftime("%Y-%m-%d")

    q_api = influx_client.query_api()

    # 1. ARMGC GCR Query (/^2.*/ strict isolation)
    q_armgc = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start_utc}, stop: {stop_utc})
      |> filter(fn: (r) => r["_measurement"] == "crane_movement")
      |> filter(fn: (r) => r["crane_id"] =~ /^2.*/)
      |> filter(fn: (r) => r["_field"] == "shock_penalty" or r["_field"] == "curr_penalty" or r["_field"] == "track_penalty" or r["_field"] == "peak_shock" or r["_field"] == "duration_s")
      |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
    '''
    armgc_by_crane = {}
    for t in q_api.query(q_armgc):
        for r in t.records:
            v = r.values
            if float(v.get("duration_s") or 0) <= 0:
                continue
            cid = str(v.get("crane_id"))
            armgc_by_crane.setdefault(cid, []).append(v)

    armgc_alerts, armgc_near = [], []
    peak_counts = []  # (crane_id, count of events with peak_shock >= threshold, total events, max peak)
    for cid, rows in armgc_by_crane.items():
        stresses = [float(x.get("shock_penalty") or 1.0) * float(x.get("curr_penalty") or 1.0) * float(x.get("track_penalty") or 1.0) for x in rows]
        peaks = [float(x.get("peak_shock") or 0.0) for x in rows]
        avg_s = sum(stresses) / len(stresses)
        item = {"crane_id": cid, "events": len(rows), "avg_stress": avg_s, "max_stress": max(stresses)}
        if avg_s >= ARMGC_ALERT_THRESHOLD:
            armgc_alerts.append(item)
        elif avg_s >= ARMGC_ALERT_THRESHOLD * 0.90:
            armgc_near.append(item)
        peak_counts.append((cid, sum(1 for p in peaks if p >= PEAK_SHOCK_COUNT_THRESHOLD), len(rows), max(peaks)))
    armgc_alerts.sort(key=lambda x: x["avg_stress"], reverse=True)
    armgc_near.sort(key=lambda x: x["avg_stress"], reverse=True)
    # Crane with the most high-peak-shock events (ties -> higher max peak)
    top_peak = None
    if peak_counts:
        best = max(peak_counts, key=lambda x: (x[1], x[3]))
        if best[1] > 0:
            top_peak = {"crane_id": best[0], "count": best[1], "events": best[2], "max_peak": best[3]}

    # 2. QC SCR Query (crane_type == "QC", component == "SpreaderCable", algo_version == "3.1.1")
    q_qc = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: {start_utc}, stop: {stop_utc})
      |> filter(fn: (r) => r["_measurement"] == "crane_movement")
      |> filter(fn: (r) => r["crane_type"] == "QC" and r["component"] == "SpreaderCable" and r["algo_version"] == "3.1.1")
      |> filter(fn: (r) => r["_field"] == "shock_penalty" or r["_field"] == "curr_penalty" or r["_field"] == "load_factor" or r["_field"] == "duration_s")
      |> pivot(rowKey:["_time", "crane_id"], columnKey: ["_field"], valueColumn: "_value")
    '''
    qc_by_crane = {}
    for t in q_api.query(q_qc):
        for r in t.records:
            v = r.values
            if float(v.get("duration_s") or 0) <= 0:
                continue
            cid = str(v.get("crane_id"))
            qc_by_crane.setdefault(cid, []).append(v)

    qc_alerts, qc_near = [], []
    for cid, rows in qc_by_crane.items():
        stresses = [float(x.get("shock_penalty") or 1.0) * float(x.get("curr_penalty") or 1.0) * float(x.get("load_factor") or 1.0) for x in rows]
        avg_s = sum(stresses) / len(stresses)
        item = {"crane_id": cid, "events": len(rows), "avg_stress": avg_s, "max_stress": max(stresses)}
        if avg_s >= QC_ALERT_THRESHOLD:
            qc_alerts.append(item)
        elif avg_s >= QC_ALERT_THRESHOLD * 0.90:
            qc_near.append(item)
    qc_alerts.sort(key=lambda x: x["avg_stress"], reverse=True)
    qc_near.sort(key=lambda x: x["avg_stress"], reverse=True)

    _alert_log(f"Checked {date_label}: ARMGC(>={ARMGC_ALERT_THRESHOLD})={len(armgc_alerts)}, QC(>={QC_ALERT_THRESHOLD})={len(qc_alerts)}, TopPeakShock={top_peak}")
    if not armgc_alerts and not qc_alerts and not force_send:
        _alert_log(f"No cranes exceeded thresholds on {date_label}. Skipping email.")
        return

    armgc_names = ", ".join([f"{x['crane_id']}호" for x in armgc_alerts]) if armgc_alerts else "없음"
    qc_names = ", ".join([f"{x['crane_id']}호" for x in qc_alerts]) if qc_alerts else "없음"
    subject = f"[주장비 감속기 Stress 이상 감지 알림] 전일({date_label}) 일평균 기준 초과 호기 - ARMGC {len(armgc_alerts)}대({armgc_names}) / QC {len(qc_alerts)}대({qc_names})"

    armgc_dash_path = "/d/total_control_tower_v1/cranepdm-v2-6-reducer-damage-diagnostics?orgId=1"
    qc_dash_path = "/d/qc_spreader_pdm/274bdbc?orgId=1"
    armgc_url_lan = f"{ALERT_GRAFANA_URL}{armgc_dash_path}"
    qc_url_lan = f"{ALERT_GRAFANA_URL}{qc_dash_path}"
    armgc_url_local = f"http://localhost:3000{armgc_dash_path}"
    qc_url_local = f"http://localhost:3000{qc_dash_path}"

    td = "padding:10px; border:1px solid #d0d7de; text-align:center;"
    th = "padding:10px; border:1px solid #d0d7de;"
    stress_td = "padding:10px; border:1px solid #d0d7de; text-align:center; background-color:#ffebe9; color:#cf222e; font-weight:bold; font-size:15px;"

    def make_rows(items, label, url_base):
        return "".join([f"""
        <tr>
            <td style="{td} font-weight:bold; font-size:14px;">
                <a href="{url_base}&var-Crane_ID={x['crane_id']}" target="_blank" rel="noopener noreferrer" style="color:#0969da; text-decoration:underline;">{label} {x['crane_id']}호</a>
            </td>
            <td style="{stress_td}">{x['avg_stress']:.2f}</td>
            <td style="{td}">{x['max_stress']:.1f}</td>
            <td style="{td}">{x['events']:,}회</td>
        </tr>""" for x in items])

    if armgc_alerts:
        armgc_rows = make_rows(armgc_alerts, "ARMGC", armgc_url_lan)
    else:
        armgc_rows = f'<tr><td colspan="4" style="padding:14px; border:1px solid #d0d7de; text-align:center; color:#1a7f37; background-color:#dafbe1;">전일 기준치({ARMGC_ALERT_THRESHOLD:.1f}) 초과 ARMGC 호기 없음 (정상)</td></tr>'
    if qc_alerts:
        qc_rows = make_rows(qc_alerts, "QC", qc_url_lan)
    else:
        qc_rows = f'<tr><td colspan="4" style="padding:14px; border:1px solid #d0d7de; text-align:center; color:#1a7f37; background-color:#dafbe1;">전일 기준치({QC_ALERT_THRESHOLD:.1f}) 초과 QC 호기 없음 (정상)</td></tr>'

    if top_peak:
        top_peak_html = f"""
        <div style="margin-top:12px; padding:12px 16px; background-color:#ddf4ff; border-left:4px solid #0969da; font-size:13px;">
            <b>최고 충격 최다 발생 호기 (ARMGC):</b>
            <a href="{armgc_url_lan}&var-Crane_ID={top_peak['crane_id']}" target="_blank" rel="noopener noreferrer" style="color:#0969da; font-weight:bold; text-decoration:underline;">ARMGC {top_peak['crane_id']}호</a>
            &nbsp;-&nbsp; 최고 충격(Peak Shock ≥ {PEAK_SHOCK_COUNT_THRESHOLD:.0f}) <b>{top_peak['count']:,}회</b> / 전체 주행 {top_peak['events']:,}회, 최대 {top_peak['max_peak']:.1f}
        </div>"""
    else:
        top_peak_html = f'<div style="margin-top:12px; padding:12px 16px; background-color:#f6f8fa; border-left:4px solid #8c959f; font-size:13px;"><b>최고 충격 최다 발생 호기 (ARMGC):</b> 전일 Peak Shock ≥ {PEAK_SHOCK_COUNT_THRESHOLD:.0f} 발생 호기 없음</div>'

    near_html = ""
    if armgc_near or qc_near:
        parts = []
        if armgc_near:
            parts.append("ARMGC 주의 관찰(45.0~49.9): " + ", ".join([f"<b>{x['crane_id']}호</b>({x['avg_stress']:.2f})" for x in armgc_near]))
        if qc_near:
            parts.append("QC 주의 관찰(5.4~5.99): " + ", ".join([f"<b>{x['crane_id']}호</b>({x['avg_stress']:.2f})" for x in qc_near]))
        near_html = f'<div style="margin-top:12px; padding:10px 14px; background-color:#fff8c5; border-left:4px solid #d4a72c; font-size:13px; color:#4d2d00;"><b>임계치 근접(주의 관찰) 호기 안내:</b> {" &nbsp;|&nbsp; ".join(parts)}</div>'

    header_row = f"""
        <tr style="background-color:#f6f8fa; color:#24292f;">
            <th style="{th} width:130px;">호기</th>
            <th style="{th} width:130px;">전일 평균<br>Stress</th>
            <th style="{th} width:130px;">최고<br>Stress</th>
            <th style="{th} width:130px;">운전<br>횟수</th>
        </tr>"""

    html_body = f"""
    <html>
    <body style="font-family:'Malgun Gothic', 'Apple SD Gothic Neo', sans-serif; color:#24292f; line-height:1.5; margin:0; padding:16px;">
        <div style="max-width:760px; border:1px solid #d0d7de; border-radius:8px; overflow:hidden;">
            <div style="background-color:#1f2328; color:#ffffff; padding:16px 20px;">
                <h2 style="margin:0; font-size:18px;">주장비 감속기 Stress 이상 감지 알림</h2>
                <p style="margin:6px 0 0 0; font-size:13px; color:#d0d7de;">
                    집계 대상일: <b>{date_label} (00:00 ~ 24:00 KST)</b> &nbsp;|&nbsp;
                    알람 기준: <b>ARMGC GCR 일평균 ≥ {ARMGC_ALERT_THRESHOLD:.1f}</b> / <b>QC SCR 일평균 ≥ {QC_ALERT_THRESHOLD:.1f}</b>
                </p>
            </div>
            <div style="padding:20px;">
                <h3 style="margin:0 0 10px 0; font-size:15px; color:#cf222e;">1. ARMGC GCR (야드 크레인 케이블 릴 감속기) - 기준({ARMGC_ALERT_THRESHOLD:.1f}) 초과: {len(armgc_alerts)}대</h3>
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead>{header_row}</thead>
                    <tbody>{armgc_rows}</tbody>
                </table>
                {top_peak_html}
                <h3 style="margin:24px 0 10px 0; font-size:15px; color:#0969da;">2. QC SCR (안벽 크레인 스프레더 케이블 감속기) - 기준({QC_ALERT_THRESHOLD:.1f}) 초과: {len(qc_alerts)}대</h3>
                <table style="width:100%; border-collapse:collapse; font-size:13px;">
                    <thead>{header_row}</thead>
                    <tbody>{qc_rows}</tbody>
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

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = ALERT_SENDER
    msg["To"] = ALERT_RECIPIENT
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    with smtplib.SMTP(ALERT_SMTP_SERVER, ALERT_SMTP_PORT, timeout=15) as server:
        server.ehlo()
        server.sendmail(ALERT_RECIPIENT, [ALERT_RECIPIENT], msg.as_string())
    _alert_log(f"SUCCESS: Sent daily alert email via {ALERT_SMTP_SERVER}:{ALERT_SMTP_PORT} to {ALERT_RECIPIENT}")

def daily_stress_alert_worker():
    """
    Background scheduler thread inside crane_edge_logger:
    Checks every 30s and triggers yesterday's daily Stress Index evaluation once per day at/after 08:00 KST.
    UsesALERT_STATE_FILE to prevent duplicate sends across restarts on the same day.
    """
    from datetime import timezone
    KST = timezone(timedelta(hours=9))
    _alert_log("Daily 08:00 KST Stress Alert Scheduler thread started (SMTP mode: mail.hpnt.co.kr:25).")
    while not stop_event.is_set():
        try:
            now_kst = datetime.now(KST)
            today_str = now_kst.strftime("%Y-%m-%d")
            last_checked = ""
            if os.path.exists(ALERT_STATE_FILE):
                try:
                    with open(ALERT_STATE_FILE, "r", encoding="utf-8") as f:
                        last_checked = f.read().strip()
                except Exception:
                    pass
            if now_kst.hour >= 8 and last_checked != today_str:
                with open(ALERT_STATE_FILE, "w", encoding="utf-8") as f:
                    f.write(today_str)
                run_daily_stress_alert_check()
        except Exception as e:
            _alert_log(f"Error in daily_stress_alert_worker: {e}")
        stop_event.wait(30)

def main():
    init_csv()
    initialize_influx_kpis()
    sync_print(f"Edge Logger v{APP_VERSION} Started. Monitoring {len(CRANES)} cranes...")
    
    # Start cleanup thread
    threading.Thread(target=cleanup_old_raw_data, daemon=True).start()
    threading.Thread(target=daily_stress_alert_worker, daemon=True).start()
    
    # Start crane monitoring threads
    for crane in CRANES:
        threading.Thread(target=monitor_crane, args=(crane,), daemon=True).start()
        
    # Start Tray Icon (This is BLOCKING)
    icon = setup_tray()
    icon.run()

if __name__ == "__main__":
    main()
