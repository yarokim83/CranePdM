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
    {"id": "ARMGC_246", "ip": "10.200.72.34", "rack": 0, "slot": 2},
    {"id": "ARMGC_212", "ip": "10.200.71.12", "rack": 0, "slot": 2} # Added ARMGC 212
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
                'max_error', 'rms_error', 'mean_stress', 'reducer_damage', 'avg_weight', 'is_loaded'
            ])
            
# Thread-safe lock for printing
print_lock = threading.Lock()

def sync_print(msg):
    with print_lock:
        print(msg)

def calculate_kpis(orders, feedbacks, loads, weights, dt_list):
    if not orders or len(orders) < 2:
        return None

    # Identify dominant load state for this event
    is_loaded = sum(loads) > len(loads) // 2
    avg_weight = sum(weights) / len(weights) if weights else 0

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
        'is_loaded': is_loaded
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
            1 if kpis['is_loaded'] else 0
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
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        influx_status = "InfluxDB OK"
    except Exception as e:
        influx_status = f"InfluxDB Error: {e}"

    sync_print(f"[{ts}] [{crane_id}] Logged | Dur: {kpis['duration']}s | RDI(Damage): {kpis['reducer_damage']} | Stress: {kpis['mean_stress']} | Load: {'Yes' if kpis['is_loaded'] else 'No'} | {influx_status}")

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
            orders, feedbacks, loads, weights, dt_list = [], [], [], [], []
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
                    
                    # Record data point
                    now = time.time()
                    dt_list.append(now - last_time)
                    last_time = now
                    
                    orders.append(current_order)
                    feedbacks.append(current_fb)
                    loads.append(is_locked)
                    weights.append(current_wt)
                    
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
                kpis = calculate_kpis(orders, feedbacks, loads, weights, dt_list)
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
