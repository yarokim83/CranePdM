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
    {"id": "264", "ip": "10.200.71.43", "rack": 0, "slot": 2},
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
                'timestamp', 'crane_id', 'event_duration_s', 'peak_order', 'peak_feedback', 
                'max_error', 'rms_error', 'mean_stress', 'reducer_damage', 'avg_weight', 'is_loaded',
                'start_pos', 'end_pos', 'avg_pos'
            ])
            
# Thread-safe lock for printing
print_lock = threading.Lock()

def sync_print(msg):
    with print_lock:
        print(msg)

def calculate_kpis(orders, feedbacks, loads, weights, positions, dt_list):
    if not orders or len(orders) < 2:
        return None

    # Identify dominant load state for this event
    is_loaded = sum(loads) > len(loads) // 2
    avg_weight = sum(weights) / len(weights) if weights else 0
    avg_pos = sum(positions) / len(positions) if positions else 0

    max_err = 0
    sum_sq_err = 0
    total_stress = 0
    total_reducer_damage = 0
    peak_order = max(map(abs, orders))
    peak_fb = max(map(abs, feedbacks))
    
    prev_fb = feedbacks[0]
    prev_accel = 0

    for i in range(1, len(orders)):
        dt = dt_list[i] if dt_list[i] > 0 else 0.1
        order = orders[i]
        fb = feedbacks[i]
        weight = weights[i]
        
        # 1. Error terms
        error = order - fb
        abs_err = abs(error)
        sum_sq_err += error ** 2
        if abs_err > max_err:
            max_err = abs_err
            
        # 2. Kinematics (Acceleration & Jerk)
        accel = (fb - prev_fb) / dt
        jerk = (accel - prev_accel) / dt
        
        # 3. Cable Reel Stress (Legacy)
        stress = (abs_err * 0.6) + (abs(fb - prev_fb) * 1.5)
        total_stress += stress
        
        # 4. Reducer Damage Index (Kinematic Torque & Backlash Fatigue)
        # Base Mass = 1.0. Payload (up to ~50t) adds proportionally.
        effective_mass = 1.0 + (max(0, weight) / 50.0)
        
        # Torque impact correlates to Mass * Acceleration
        torque_impact = abs(accel) * effective_mass
        backlash_shock = abs(jerk) * effective_mass
        
        # Cumulative Fatigue (Miner's Rule approximation)
        # We square the torque impact to exponentially penalize sharp spikes
        instant_damage = ((torque_impact ** 2) * 0.0001) + (backlash_shock * 0.005)
        total_reducer_damage += instant_damage
        
        prev_fb = fb
        prev_accel = accel
        
    rms_error = math.sqrt(sum_sq_err / len(orders))
    mean_stress = total_stress / len(orders)
    event_duration = sum(dt_list)

    return {
        'duration': round(event_duration, 2),
        'peak_order': peak_order,
        'peak_fb': peak_fb,
        'max_error': max_err,
        'rms_error': round(rms_error, 2),
        'mean_stress': round(mean_stress, 2),
        'reducer_damage': round(total_reducer_damage, 2),
        'avg_weight': round(avg_weight, 1),
        'is_loaded': is_loaded,
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
            kpis['duration'], 
            kpis['peak_order'], 
            kpis['peak_fb'], 
            kpis['max_error'], 
            kpis['rms_error'], 
            kpis['mean_stress'], 
            kpis['reducer_damage'],
            kpis['avg_weight'], 
            1 if kpis['is_loaded'] else 0,
            kpis['start_pos'],
            kpis['end_pos'],
            kpis['avg_pos']
        ])
        
    # Write to InfluxDB
    try:
        point = (
            Point("crane_movement")
            .tag("crane_id", crane_id)
            .tag("is_loaded", "Loaded" if kpis['is_loaded'] else "Empty")
            .field("duration_s", float(kpis['duration']))
            .field("peak_order", float(kpis['peak_order']))
            .field("peak_feedback", float(kpis['peak_fb']))
            .field("max_error", float(kpis['max_error']))
            .field("rms_error", float(kpis['rms_error']))
            .field("mean_stress", float(kpis['mean_stress']))
            .field("reducer_damage", float(kpis['reducer_damage']))
            .field("avg_weight", float(kpis['avg_weight']))
            .field("start_pos", float(kpis['start_pos']))
            .field("end_pos", float(kpis['end_pos']))
            .field("avg_pos", float(kpis['avg_pos']))
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        influx_status = "InfluxDB OK"
    except Exception as e:
        influx_status = f"InfluxDB Error: {e}"

    sync_print(f"[{ts}] [{crane_id}] Logged | Dur: {kpis['duration']}s | Pos: {kpis['start_pos']}->{kpis['end_pos']} | Stress: {kpis['mean_stress']} | {influx_status}")

def monitor_crane(crane_config):
    crane_id = crane_config['id']
    ip = crane_config['ip']
    rack = crane_config['rack']
    slot = crane_config['slot']
    
    client = snap7.client.Client()
    
    while True:
        try:
            if not client.get_connected():
                sync_print(f"[{datetime.now().strftime('%H:%M:%S')}] [{crane_id}] Connecting to PLC {ip}...")
                client.connect(ip, rack, slot)
                time.sleep(1)
                continue

            # Check IDLE state (Poll slowly)
            order_data = client.db_read(57, 8, 2)
            current_order = get_int(order_data, 0)
            
            if abs(current_order) < SPEED_THRESHOLD:
                # Crane is idle
                time.sleep(IDLE_POLL_RATE)
                continue
                
            # Movement Detected -> Switch to Active Logging
            sync_print(f"\n🚀 [{crane_id}] Movement! Order: {current_order}. Recording...")
            orders, feedbacks, loads, weights, positions, dt_list = [], [], [], [], [], []
            last_time = time.time()
            
            while True:
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
                    
                    # Record data point
                    now = time.time()
                    dt_list.append(now - last_time)
                    last_time = now
                    
                    orders.append(current_order)
                    feedbacks.append(current_fb)
                    loads.append(is_locked)
                    weights.append(current_wt)
                    positions.append(current_pos)
                    
                    # Stop Condition: Order speed returns near 0
                    if abs(current_order) < SPEED_THRESHOLD:
                        sync_print(f"🛑 [{crane_id}] Stopped. Analyzing {len(orders)} points...")
                        break
                        
                except Exception as ex_read:
                    sync_print(f"⚠️ [{crane_id}] Read error: {ex_read}")
                    break
                
                # Maintain active poll rate
                elapsed = time.time() - cycle_start
                sleep_time = max(0, ACTIVE_POLL_RATE - elapsed)
                time.sleep(sleep_time)

            # Event finished, calculate and log KPIs
            if orders:
                kpis = calculate_kpis(orders, feedbacks, loads, weights, positions, dt_list)
                if kpis and kpis['duration'] > 1.0: # Ignore very short blips
                    log_event(crane_id, kpis)
                else:
                    sync_print(f"[{crane_id}] Event too short, ignored.")
                    
        except Exception as e:
            sync_print(f"⚠️ [{crane_id}] Connection error: {e}. Retrying in 5 seconds...")
            try:
                client.disconnect()
            except:
                pass
            time.sleep(5)

def main():
    init_csv()
    sync_print(f"Edge Logger Started. Monitoring {len(CRANES)} cranes...")
    
    threads = []
    for crane in CRANES:
        t = threading.Thread(target=monitor_crane, args=(crane,), daemon=True)
        t.start()
        threads.append(t)
        
    try:
        # Keep main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sync_print("\nLogger stopped by user.")

if __name__ == "__main__":
    main()
