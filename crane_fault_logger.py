import snap7
from snap7.util import get_bool
import time
import csv
import os
from datetime import datetime
import threading
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

# PLC Configurations
CRANES = [
    {"id": "ARMGC_211", "ip": "10.200.71.11", "rack": 0, "slot": 2},
    {"id": "ARMGC_212", "ip": "10.200.71.12", "rack": 0, "slot": 2},
    {"id": "ARMGC_213", "ip": "10.200.71.13", "rack": 0, "slot": 2},
    {"id": "ARMGC_214", "ip": "10.200.72.14", "rack": 0, "slot": 2},
    {"id": "ARMGC_215", "ip": "10.200.72.15", "rack": 0, "slot": 2},
    {"id": "ARMGC_216", "ip": "10.200.72.16", "rack": 0, "slot": 2}
]

# Fault Definitions
FAULTS = {
    "Spreader_Land_Fault_XT": {"db": 59, "byte": 202, "bit": 3},
    "Spreader_Land_Fault_YT": {"db": 59, "byte": 202, "bit": 4},
    "Spreader_Land_Fault_YD": {"db": 59, "byte": 202, "bit": 5},
    "SPSS_Trolley_Dir_Not_Clear": {"db": 59, "byte": 212, "bit": 6}
}
RESET_MARKER = {"byte": 103, "bit": 2}

POLL_RATE = 3.0  # Optimized: Check faults every 3 seconds to minimize network load

# InfluxDB Configuration
INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"
CSV_FILE = 'crane_fault_log.csv'

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

print_lock = threading.Lock()
def sync_print(msg):
    with print_lock:
        print(msg)

def init_csv():
    if not os.path.exists(CSV_FILE):
        with open(CSV_FILE, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow([
                'timestamp', 'crane_id', 'fault_name', 'event_type', 
                'downtime_s', 'was_reset_pressed'
            ])

def log_fault_event(crane_id, fault_name, event_type, downtime=0.0, reset_status="N/A"):
    ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # Write CSV
    with open(CSV_FILE, 'a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([ts, crane_id, fault_name, event_type, round(downtime, 1), reset_status])
        
    # Write InfluxDB
    try:
        point = (
            Point("crane_faults")
            .tag("crane_id", crane_id)
            .tag("fault_name", fault_name)
            .tag("event_type", event_type)  # "Occurrence" or "Resolved"
            .field("downtime_s", float(round(downtime, 2)))
            .field("count", 1 if event_type == "Occurrence" else 0)
        )
        write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)
        influx_status = "OK"
    except Exception as e:
        influx_status = f"Err: {e}"

    if event_type == "Occurrence":
        sync_print(f"[{ts}] 🚨 [{crane_id}] FAULT OCCURRED: {fault_name} | DB:OK")
    else:
        sync_print(f"[{ts}] ✅ [{crane_id}] FAULT RESOLVED: {fault_name} | Downtime: {round(downtime,1)}s | DB:{influx_status}")

def monitor_faults(crane):
    crane_id = crane['id']
    ip = crane['ip']
    rack = crane['rack']
    slot = crane['slot']
    
    client = snap7.client.Client()
    
    # Track the active occurrence time for each fault
    # Example: {"Spreader_Land_Fault_XT": 1690000000.0, ...}
    active_faults = {}
    
    while True:
        try:
            if not client.get_connected():
                sync_print(f"[{datetime.now().strftime('%H:%M:%S')}] [{crane_id}] Connecting Fault Logger to {ip}...")
                client.connect(ip, rack, slot)
                time.sleep(1)
                continue
                
            # Note: We read an 11-byte block from 202 to 212 to cover all faults efficiently
            # DB59.DBB202 is at index 0, DB59.DBB212 is at index 10
            fault_data = client.db_read(59, 202, 11)
            
            # Read Reset Marker M103
            try:
                mk_data = client.read_area(snap7.types.Areas.MK, 0, 103, 1)
                reset_pressed = get_bool(mk_data, 0, 2)
            except Exception:
                reset_pressed = False
            
            now = time.time()
            reset_status = "Pressed" if reset_pressed else "Not Pressed"
            
            for f_name, db_info in FAULTS.items():
                offset = db_info['byte'] - 202 # Calculate index in the byte array
                is_active = get_bool(fault_data, offset, db_info['bit'])
                
                # Fault just appeared (0 -> 1)
                if is_active and f_name not in active_faults:
                    active_faults[f_name] = now
                    log_fault_event(crane_id, f_name, "Occurrence", 0, reset_status)
                    
                # Fault just cleared (1 -> 0)
                elif not is_active and f_name in active_faults:
                    start_time = active_faults.pop(f_name)
                    downtime = now - start_time
                    log_fault_event(crane_id, f_name, "Resolved", downtime, reset_status)
                    
            # 3초 대기 (네트워크 부하 최소화)
            time.sleep(POLL_RATE)
            
        except Exception as e:
            sync_print(f"⚠️ [{crane_id}] Fault logger connection error: {e}. Retrying in 10s...")
            try:
                client.disconnect()
            except:
                pass
            time.sleep(10)

def main():
    init_csv()
    sync_print(f"Fault Logger Started. Monitoring {len(FAULTS)} types of faults on {len(CRANES)} cranes...")
    
    threads = []
    for crane in CRANES:
        t = threading.Thread(target=monitor_faults, args=(crane,), daemon=True)
        t.start()
        threads.append(t)
        
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        sync_print("\nFault Logger stopped.")

if __name__ == "__main__":
    main()
