import snap7
from snap7.util import get_int

ip = "10.200.71.43"
rack = 0
slot = 2

client = snap7.client.Client()
print(f"Connecting to Crane 264 at {ip}...")
try:
    client.connect(ip, rack, slot)
    print("Connected successfully.")
    
    # Try reading DB57 (sanity check)
    try:
        db57 = client.db_read(57, 8, 2)
        print(f"DB57 read success: {get_int(db57, 0)}")
    except Exception as e:
        print(f"Failed to read DB57: {e}")

    # Try reading DB170
    try:
        db170 = client.db_read(170, 0, 6)
        print("DB170 read success!")
        print(f"Speed: {get_int(db170, 0)}")
        print(f"Current: {get_int(db170, 2)}")
        print(f"Torque: {get_int(db170, 4)}")
    except Exception as e:
        print(f"Failed to read DB170! Error type: {type(e).__name__}, Message: {e}")

    client.disconnect()
except Exception as e:
    print(f"Connection failed: {e}")
