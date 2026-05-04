import json
import urllib.request
import urllib.error
import base64

url = 'http://127.0.0.1:3000/api/dashboards/db'
username = 'admin'
password = 'password' # Let's try standard passwords

with open(r'c:\Users\huser\.gemini\CranePdM\grafana_v2_detail_dashboard.json', 'r', encoding='utf-8') as f:
    dashboard = json.load(f)

payload = {
    "dashboard": dashboard,
    "overwrite": True
}
data = json.dumps(payload).encode('utf-8')

req = urllib.request.Request(url, data=data)
req.add_header('Content-Type', 'application/json')
base64string = base64.b64encode(f"{username}:{password}".encode('ascii')).decode('ascii')
req.add_header("Authorization", "Basic %s" % base64string)

try:
    with urllib.request.urlopen(req) as response:
        print("Status Code:", response.status)
        print("Response:", response.read().decode('utf-8'))
except urllib.error.HTTPError as e:
    print("HTTP Error:", e.code, e.reason)
    # try admin:admin
    try:
        req.add_header("Authorization", "Basic %s" % base64.b64encode(b"admin:admin").decode('ascii'))
        with urllib.request.urlopen(req) as response:
            print("Status Code:", response.status)
            print("Response:", response.read().decode('utf-8'))
    except Exception as e2:
        print("Failed with admin:admin too", e2)
except Exception as e:
    print("Error:", e)
