import snap7
import struct

qc_cranes = [
    {"id": "101", "ip": "10.200.73.11"},
    {"id": "102", "ip": "10.200.73.12"},
    {"id": "103", "ip": "10.200.73.13"},
    {"id": "104", "ip": "10.200.73.14"},
    {"id": "105", "ip": "10.200.73.15"},
    {"id": "106", "ip": "10.200.73.16"},
    {"id": "107", "ip": "10.200.73.17"},
    {"id": "108", "ip": "10.200.73.18"},
    {"id": "109", "ip": "10.200.73.19"},
    {"id": "110", "ip": "10.200.73.20"},
    {"id": "111", "ip": "10.200.73.21"},
    {"id": "112", "ip": "10.200.73.22"}
]

print("=== STARTING DIAGNOSTIC SCAN OF ALL 12 QC PLCS (DB180) ===")
for qc in qc_cranes:
    cid = qc["id"]
    ip = qc["ip"]
    client = snap7.client.Client()
    try:
        client.connect(ip, 0, 2)
        if client.get_connected():
            data = client.db_read(180, 0, 12)
            speed = struct.unpack('>h', data[6:8])[0]
            current = struct.unpack('>h', data[8:10])[0]
            torque = struct.unpack('>h', data[10:12])[0]
            print(f"QC {cid} ({ip}) -> SUCCESS | Speed: {speed:5} | Current: {current:5} | Torque: {torque:5}")
        else:
            print(f"QC {cid} ({ip}) -> FAILED | Reason: Socket connection failed")
    except Exception as e:
        print(f"QC {cid} ({ip}) -> ERROR  | Reason: {e}")
    finally:
        client.disconnect()
print("=== SCAN FINISHED ===")
