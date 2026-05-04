from influxdb_client import InfluxDBClient

url = "http://localhost:8086"
token = "my-super-secret-auth-token"
org = "myorg"
client = InfluxDBClient(url=url, token=token, org=org)
buckets_api = client.buckets_api()

buckets = buckets_api.find_buckets().buckets
for b in buckets:
    print(f"Name: {b.name}, ID: {b.id}")
