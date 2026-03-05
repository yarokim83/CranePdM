import snap7
import time

CRANES = [
    {"id": "ARMGC_211", "ip": "10.200.71.11"},
    {"id": "ARMGC_212", "ip": "10.200.71.12"},
    {"id": "ARMGC_213", "ip": "10.200.71.13"},
    {"id": "ARMGC_221", "ip": "10.200.71.17"},
    {"id": "ARMGC_246", "ip": "10.200.72.34"},
    {"id": "ARMGC_254", "ip": "10.200.72.38"}
]

for crane in CRANES:
    client = snap7.client.Client()
    print(f"Testing connection to {crane['id']} ({crane['ip']})...", end=" ")
    try:
        client.connect(crane['ip'], 0, 2)
        if client.get_connected():
            print("SUCCESS")
            client.disconnect()
        else:
            print("FAILED (Not connected)")
    except Exception as e:
        print(f"ERROR: {e}")
