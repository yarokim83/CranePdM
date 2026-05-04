from influxdb_client import InfluxDBClient
from datetime import datetime
import os

INFLUX_URL = "http://localhost:8086"
INFLUX_TOKEN = "my-super-secret-auth-token"
INFLUX_ORG = "myorg"
INFLUX_BUCKET = "cranepdm_kpis"
CSV_FILE = 'crane_kpi_log.csv'

def reset_all():
    print("🧹 Starting full data reset...")
    
    # 1. Clear InfluxDB
    try:
        client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
        delete_api = client.delete_api()
        start = "1970-01-01T00:00:00Z"
        stop = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ')
        delete_api.delete(start, stop, "", bucket=INFLUX_BUCKET, org=INFLUX_ORG)
        print("✅ InfluxDB bucket cleared.")
    except Exception as e:
        print(f"⚠️ InfluxDB reset failed: {e}")

    # 2. Delete CSV
    if os.path.exists(CSV_FILE):
        try:
            os.remove(CSV_FILE)
            print(f"✅ CSV file '{CSV_FILE}' deleted.")
        except Exception as e:
            print(f"⚠️ CSV deletion failed: {e}")
    else:
        print("ℹ️ CSV file already gone.")

    print("✨ Reset complete.")

if __name__ == "__main__":
    reset_all()
