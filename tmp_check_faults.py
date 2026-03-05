from influxdb_client import InfluxDBClient

def check_faults():
    url = "http://localhost:8086"
    token = "my-super-secret-auth-token"
    org = "myorg"
    bucket = "cranepdm_kpis"

    client = InfluxDBClient(url=url, token=token, org=org)
    query_api = client.query_api()

    # Query for any crane_faults in the last 24 hours
    query = f"""
        from(bucket: "{bucket}")
        |> range(start: -24h)
        |> filter(fn: (r) => r["_measurement"] == "crane_faults")
    """

    try:
        tables = query_api.query(query)
        count = 0
        for table in tables:
            for record in table.records:
                count += 1
                if count <= 5: # Print up to 5 examples
                    print(f"Time: {record.get_time()}, Crane: {record['crane_id']}, Fault: {record['fault_name']}, Position: {record.get_value()}")
        
        print(f"\nTotal fault events found in the last 24h: {count}")
    
    except Exception as e:
        print(f"Query Error: {e}")

if __name__ == "__main__":
    check_faults()
