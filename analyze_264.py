import pandas as pd
import numpy as np

# Load data
df = pd.read_csv('C:/Users/huser/.gemini/CranePdM/crane_kpi_log.csv', on_bad_lines='skip')
df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
df = df.dropna(subset=['timestamp'])

# Filter for crane 264 since March 30
df_264 = df[(df['crane_id'] == 264) & (df['timestamp'] >= '2026-03-30')].copy()

if df_264.empty:
    print("No data found for crane 264 since 2026-03-30.")
    # Check if ANY data exists for 264 to diagnose
    any_264 = df[df['crane_id'] == 264]
    print(f"Total historical records for 264 (all time): {len(any_264)}")
else:
    print(f"\n--- Crane 264 Analysis Summary (Since 2026-03-30) ---")
    print(f"Total events recorded: {len(df_264)}")
    print(f"Analysis Period: {df_264['timestamp'].min()} ~ {df_264['timestamp'].max()}")
    
    # 1. Stress Analysis
    print(f"\n[Stress (Reducer Damage)]")
    print(f"Average Stress: {df_264['reducer_damage'].mean():.2f}")
    print(f"Max Stress: {df_264['reducer_damage'].max():.2f}")
    
    # Thresholds: Normal < 200, Warning 200-1000, Danger >= 1000
    normal = len(df_264[df_264['reducer_damage'] < 200])
    warning = len(df_264[(df_264['reducer_damage'] >= 200) & (df_264['reducer_damage'] < 1000)])
    danger = len(df_264[df_264['reducer_damage'] >= 1000])
    
    print(f"Status Distribution:")
    print(f"  - Normal (< 200): {normal} ({normal/len(df_264)*100:.1f}%)")
    print(f"  - Warning (200~1000): {warning} ({warning/len(df_264)*100:.1f}%)")
    print(f"  - Danger (>= 1000): {danger} ({danger/len(df_264)*100:.1f}%)")
    
    # 2. Peak Shock Analysis
    print(f"\n[Peak Shock (G)]")
    print(f"Max Peak Shock: {df_264['peak_shock'].max():.2f} G")
    print(f"Avg Peak Shock: {df_264['peak_shock'].mean():.2f} G")
    
    # 3. Top 5 High-Stress Locations
    print(f"\n[Top 5 High-Stress Events & Positions]")
    top_events = df_264.sort_values('reducer_damage', ascending=False).head(5)
    print(top_events[['timestamp', 'reducer_damage', 'peak_shock', 'avg_pos']])
    
    # 4. Version Check (264 was the fixed crane)
    print(f"\n[Software Version]")
    print(df_264['algo_version'].value_counts())
