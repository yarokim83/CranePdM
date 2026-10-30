import os
import time
import shutil
import subprocess

src = r"C:\Users\huser\.gemini\CranePdM\dist\crane_edge_logger.exe"
dst = r"C:\Users\huser\.gemini\CranePdM\deploy_package\crane_edge_logger.exe"
old_dst = r"C:\Users\huser\.gemini\CranePdM\deploy_package\crane_edge_logger.exe.old"

print("1. Checking running processes...")
res = subprocess.run(["tasklist", "/FI", "IMAGENAME eq crane_edge_logger.exe"], capture_output=True, text=True)
print(res.stdout)

print("2. Renaming existing crane_edge_logger.exe -> crane_edge_logger.exe.old (Windows allows renaming running EXEs!)...")
try:
    if os.path.exists(old_dst):
        try:
            os.remove(old_dst)
        except Exception:
            old_dst = old_dst + "." + str(int(time.time()))
    if os.path.exists(dst):
        os.rename(dst, old_dst)
        print(f"   Renamed running exe to {old_dst}")
except Exception as e:
    print(f"   Rename notice: {e}")

print(f"3. Copying {src} -> {dst}...")
shutil.copy2(src, dst)
print(f"   SUCCESS! Size={os.path.getsize(dst)} bytes, MTime={time.ctime(os.path.getmtime(dst))}")

print("4. Killing old crane_edge_logger.exe process...")
subprocess.run(["taskkill", "/F", "/T", "/IM", "crane_edge_logger.exe"], capture_output=True)
time.sleep(2)

print("5. Starting new v3.1.0 crane_edge_logger.exe...")
subprocess.Popen(
    [dst],
    cwd=r"C:\Users\huser\.gemini\CranePdM\deploy_package",
    creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
)
time.sleep(2)
res2 = subprocess.run(["tasklist", "/FI", "IMAGENAME eq crane_edge_logger.exe"], capture_output=True, text=True)
print("6. Running processes after restart:\n" + res2.stdout)
