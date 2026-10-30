import time
import subprocess
import os

process_name = "crane_edge_logger.exe"
exe_path = r"C:\Users\huser\.gemini\CranePdM\deploy_package\crane_edge_logger.exe"
working_dir = r"C:\Users\huser\.gemini\CranePdM\deploy_package"

print("=== STARTING CONTINUOUS IN-MEMORY WATCHDOG SERVICE ===")

while True:
    try:
        # Check running processes
        output = subprocess.check_output('tasklist /FI "IMAGENAME eq crane_edge_logger.exe"', shell=True).decode('utf-8', errors='ignore')
        if "crane_edge_logger.exe" not in output:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] WARNING: {process_name} is NOT running! Restarting immediately...")
            subprocess.Popen([exe_path], cwd=working_dir, creationflags=subprocess.CREATE_NO_WINDOW)
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] SUCCESS: {process_name} restarted.")
    except Exception as e:
        print(f"Watchdog check error: {e}")
        
    time.sleep(10)
