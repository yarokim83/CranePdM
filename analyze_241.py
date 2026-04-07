import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('C:/Users/huser/.gemini/CranePdM/crane_kpi_log.csv', on_bad_lines='skip')
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])

# Filter for crane 241
df_241 = df[df['crane_id'] == 241].copy()

if df_241.empty:
    print("No data found for crane 241.")
else:
    print(f"--- Crane 241 Detailed Analysis ---")
    print(f"Total events: {len(df_241)}")
    print(f"Analysis Period: {df_241['timestamp'].min()} ~ {df_241['timestamp'].max()}")
    
    # 1. Stress (Reducer Damage) Analysis
    print(f"\n[Stress (Reducer Damage)]")
    print(f"Average Stress: {df_241['reducer_damage'].mean():.2f}")
    print(f"Max Stress: {df_241['reducer_damage'].max():.2f}")
    print(f"Cumulative Stress Index: {df_241['reducer_damage'].sum():.2f}")
    
    # Threshold counts (Current thresholds: Normal < 200, Warning 200~1000, Danger >= 1000)
    normal = len(df_241[df_241['reducer_damage'] < 200])
    warning = len(df_241[(df_241['reducer_damage'] >= 200) & (df_241['reducer_damage'] < 1000)])
    danger = len(df_241[df_241['reducer_damage'] >= 1000])
    
    print(f"Status Distribution:")
    print(f"  - Normal (< 200): {normal} ({normal/len(df_241)*100:.1f}%)")
    print(f"  - Warning (200~1000): {warning} ({warning/len(df_241)*100:.1f}%)")
    print(f"  - Danger (>= 1000): {danger} ({danger/len(df_241)*100:.1f}%)")
    
    # 2. Peak Shock Analysis
    print(f"\n[Peak Shock (G)]")
    print(f"Average Peak Shock: {df_241['peak_shock'].mean():.2f} G")
    print(f"Max Peak Shock: {df_241['peak_shock'].max():.2f} G")
    
    # 3. Operations Analysis
    print(f"\n[Operations]")
    print(f"Average Weight: {df_241['avg_weight'].mean():.2f} tons")
    print(f"Loaded Events: {len(df_241[df_241['is_loaded'] == 1])}")
    print(f"MT Ratio (Loaded/Empty): {len(df_241[df_241['is_loaded'] == 1])/len(df_241):.2f}")
    
    # 4. Top 3 Worst Events
    print(f"\n[Top 3 Worst Stress Events]")
    worst = df_241.sort_values('reducer_damage', ascending=False).head(3)
    print(worst[['timestamp', 'reducer_damage', 'peak_shock', 'avg_weight']])
