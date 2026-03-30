import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('C:/Users/huser/.gemini/CranePdM/crane_kpi_log.csv', on_bad_lines='skip')

# Ensure timestamp is datetime and coerce errors
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])

print(f"Total Log entries: {len(df)}")
print(f"Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

# 1. Group by crane_id
summary = df.groupby('crane_id').agg({
    'timestamp': 'count',
    'peak_shock': ['max', 'mean'],
    'reducer_damage': 'sum',
    'avg_weight': 'mean',
    'algo_version': lambda x: x.iloc[-1]
}).reset_index()

summary.columns = ['crane_id', 'event_count', 'max_peak_shock', 'avg_peak_shock', 'total_damage_index', 'avg_weight', 'current_version']

print("\n--- Summary by Crane ---")
print(summary.sort_values('event_count', ascending=False).to_string(index=False))

# 2. Version comparison (2.2 vs 2.3)
v_comp = df.groupby('algo_version').agg({
    'reducer_damage': 'mean',
    'peak_shock': 'mean'
})
print("\n--- Version Comparison (Average Stress/Shock) ---")
print(v_comp)

# 3. Check for Crane 264
c264 = df[df['crane_id'] == 264]
print(f"\nCrane 264 Entries: {len(c264)}")
if len(c264) > 0:
    print(c264.tail())

# 4. Top 5 High Stress Events
print("\n--- Top 5 Highest Shock Events ---")
print(df.sort_values('peak_shock', ascending=False)[['timestamp', 'crane_id', 'peak_shock', 'reducer_damage']].head())
