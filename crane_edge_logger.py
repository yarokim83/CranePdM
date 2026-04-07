import snap7
from snap7.util import get_int, get_bool
import time
import math
import csv
import os
from datetime import datetime
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS
import threading
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
    {"id": "272", "ip": "10.200.72.46", "rack": 0, "slot": 2}
]

# Logging Configuration
CSV_FILE = 'crane_kpi_log.csv'
IDLE_POLL_RATE = 0.5    # Seconds between checks when idle
ACTIVE_POLL_RATE = 0.1  # Seconds between checks when moving (10Hz)
SPEED_THRESHOLD = 50    # Minimum speed to trigger 'movement' event

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
            exe_path = os.path.realpath(sys.executable if getattr(sys, 'frozen', False) else sys.argv[0])
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
    
    icon = pystray.Icon(APP_NAME, image, "Crane PdM Logger", menu)
    return icon

def calculate_kpis(orders, feedbacks, loads, weights, positions, dt_list, db170_list=None):
    """
    V2.0 Physical Model — Cable Reel Drive Data (Torque, Speed, Current) only.
    If db170_list is unavailable (DB not mapped), event is skipped.
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
    sum_shock, sum_curr, sum_track = 0, 0, 0
    peak_shock = 1.0
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

        # Dynamic Shock Penalty (Cap at 10.0 for damage calc, but uncap for peak_shock logging)
        # V2.3: Sensitivity set to 0.06 to balance precision and uncap for Peak Shock trend
        torque_deriv = (v2_torque - prev_v2_torque) / dt
        raw_shock = 1.0 + 0.06 * abs(torque_deriv)
        shock_penalty = min(MAX_INDIVIDUAL_PENALTY, raw_shock)

        # Control Anomaly Penalty A — Current vs Torque ratio (Cap at 10.0)
        # Ratio > 0.2 indicates high mechanical resistance relative to torque
        # Added threshold: Ignore AC magnetizing current false-positives when under no-load
        if abs(v2_torque) > 10.0:
            curr_ratio = abs(v2_current) / (abs(v2_torque) + 0.1)
            curr_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + 5.0 * max(0, curr_ratio - CURR_THRESHOLD))
        else:
            curr_penalty = 1.0

        # Control Anomaly Penalty B — Speed tracking error (Cap at 10.0)
        # V2.1: Use higher TRACK_GATE(500) and TRACK_SCALE(5.0) to stabilize noise
        if abs(order) > TRACK_GATE:
            tracking_error_ratio = abs_err / (abs(order) + TRACK_EPSILON)
            tracking_penalty = min(MAX_INDIVIDUAL_PENALTY, 1.0 + TRACK_SCALE * max(0, tracking_error_ratio - 0.05))
        else:
            tracking_penalty = 1.0

        total_penalty = min(MAX_TOTAL_PENALTY, shock_penalty * curr_penalty * tracking_penalty)
        instant_damage = base_fatigue * total_penalty * 0.001
        total_reducer_damage += instant_damage
        
        sum_shock += shock_penalty
        sum_curr += curr_penalty
        sum_track += tracking_penalty
        # V2.3: Record the TRUE unbounded shock severity for maintenance insight
        peak_shock = max(peak_shock, raw_shock)

    rms_error = math.sqrt(sum_sq_err / len(orders))
    event_duration = sum(dt_list)
    avg_shock = sum_shock / (len(orders)-1)
    avg_curr = sum_curr / (len(orders)-1)
    avg_track = sum_track / (len(orders)-1)

    return {
        'algo_version': '2.3',
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
        'curr_penalty': round(avg_curr, 3),
        'track_penalty': round(avg_track, 3),
        'start_pos': positions[0],
        'end_pos': positions[-1],
        'avg_pos': round(avg_pos, 1)
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
            kpis['avg_pos']
        ])
        
    try:
        point = (
            Point("crane_movement")
            .tag("crane_id", crane_id)
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
            .field("start_pos", float(kpis['start_pos']))
            .field("end_pos", float(kpis['end_pos']))
            .field("avg_pos", float(kpis['avg_pos']))
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

def monitor_crane(crane_config):
    crane_id = crane_config['id']
    ip = crane_config['ip']
    rack = crane_config['rack']
    slot = crane_config['slot']
    
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
                    # 10000 갭 등 치명적 속도오차 발생 시에만 Raw 데이터를 파일로 덤프
                    if kpis['max_error'] > 9500:
                        dump_raw_anomaly(crane_id, kpis, orders, feedbacks, positions, dt_list, db170_list)
                    
        except Exception as e:
            sync_print(f"[!] [{crane_id}] Connection error: {e}. Retrying in 5 seconds...")
            try:
                client.disconnect()
            except:
                pass
            time.sleep(5)

def main():
    init_csv()
    sync_print(f"Edge Logger Started. Monitoring {len(CRANES)} cranes...")
    
    # Start threads in background
    for crane in CRANES:
        threading.Thread(target=monitor_crane, args=(crane,), daemon=True).start()
        
    # Start Tray Icon (This is BLOCKING)
    icon = setup_tray()
    icon.run()

if __name__ == "__main__":
    main()
