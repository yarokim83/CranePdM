import snap7
import struct
import time
from datetime import datetime

# QC 109 specific deep diagnostic
ip_109 = "10.200.73.19"
db_number = 180

print("=== DEEP DIAGNOSTIC: QC 109 PLC DB180 RAW DUMP ===")
print(f"Target: {ip_109}, DB: {db_number}")
print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")

client = snap7.client.Client()
try:
    client.connect(ip_109, 0, 2)
    print(f"Connection Status: {'CONNECTED' if client.get_connected() else 'FAILED'}")
    
    # Read full DB180 (first 50 bytes)
    data = client.db_read(db_number, 0, 50)
    print(f"\n--- DB180 Raw Bytes (0-49) ---")
    for i in range(0, len(data), 2):
        word_val = struct.unpack('>h', data[i:i+2])[0]
        uword_val = struct.unpack('>H', data[i:i+2])[0]
        print(f"  DBW{i:3d}: Signed={word_val:8d}  Unsigned={uword_val:8d}  Hex=0x{data[i]:02X}{data[i+1]:02X}")
    
    # Standard mapping: DBW6=Speed, DBW8=Current, DBW10=Torque
    speed_w6 = struct.unpack('>h', data[6:8])[0]
    current_w8 = struct.unpack('>h', data[8:10])[0]
    torque_w10 = struct.unpack('>h', data[10:12])[0]
    print(f"\n--- Standard Mapping (DBW6/8/10) ---")
    print(f"  Speed (DBW6):   {speed_w6}")
    print(f"  Current (DBW8): {current_w8}")
    print(f"  Torque (DBW10): {torque_w10}")
    
    # Check ALL word addresses for possible speed signal
    print(f"\n--- Searching for NON-ZERO values (possible speed elsewhere) ---")
    for i in range(0, len(data), 2):
        val = struct.unpack('>h', data[i:i+2])[0]
        if val != 0:
            print(f"  DBW{i}: {val}")

    # Continuous poll 5 times with 1 sec interval to detect changes
    print(f"\n--- Continuous Polling (5 reads, 1s interval) ---")
    for sample in range(5):
        time.sleep(1)
        data = client.db_read(db_number, 0, 50)
        speed = struct.unpack('>h', data[6:8])[0]
        current = struct.unpack('>h', data[8:10])[0]
        torque = struct.unpack('>h', data[10:12])[0]
        
        # Also check other candidate addresses
        w0 = struct.unpack('>h', data[0:2])[0]
        w2 = struct.unpack('>h', data[2:4])[0]
        w4 = struct.unpack('>h', data[4:6])[0]
        w12 = struct.unpack('>h', data[12:14])[0]
        w14 = struct.unpack('>h', data[14:16])[0]
        w16 = struct.unpack('>h', data[16:18])[0]
        w18 = struct.unpack('>h', data[18:20])[0]
        w20 = struct.unpack('>h', data[20:22])[0]
        
        ts = datetime.now().strftime('%H:%M:%S')
        print(f"  [{ts}] W0={w0:6} W2={w2:6} W4={w4:6} SPD(W6)={speed:6} CUR(W8)={current:6} TRQ(W10)={torque:6} W12={w12:6} W14={w14:6} W16={w16:6} W18={w18:6} W20={w20:6}")

except Exception as e:
    print(f"ERROR: {e}")
finally:
    try:
        client.disconnect()
    except:
        pass

# Compare with a known working crane (e.g., 110 which was active)
print("\n\n=== COMPARISON: QC 110 (Known Active) ===")
client2 = snap7.client.Client()
try:
    client2.connect("10.200.73.20", 0, 2)
    data2 = client2.db_read(180, 0, 50)
    print(f"--- DB180 Raw Bytes (0-49) ---")
    for i in range(0, len(data2), 2):
        word_val = struct.unpack('>h', data2[i:i+2])[0]
        print(f"  DBW{i:3d}: Signed={word_val:8d}")
    speed = struct.unpack('>h', data2[6:8])[0]
    current = struct.unpack('>h', data2[8:10])[0]
    torque = struct.unpack('>h', data2[10:12])[0]
    print(f"\n  Speed (DBW6):   {speed}")
    print(f"  Current (DBW8): {current}")
    print(f"  Torque (DBW10): {torque}")
except Exception as e:
    print(f"ERROR: {e}")
finally:
    try:
        client2.disconnect()
    except:
        pass
