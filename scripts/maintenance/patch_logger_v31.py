with open("crane_edge_logger.py", "r", encoding="utf-8") as f:
    code = f.read()

# 1. Update QC 112 config and version comment
old_cfg = '''    {"id": "111", "ip": "10.200.73.21", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "112", "ip": "10.200.73.22", "rack": 0, "slot": 2, "type": "QC"}
]

# Logging Configuration
CSV_FILE = 'crane_kpi_log.csv'
RAW_DATA_DIR = 'raw_plc_data'  # Raw PLC samples saved here (gzip compressed)
RAW_RETENTION_DAYS = 90        # Auto-move raw files older than this to backups
IDLE_POLL_RATE = 0.5    # Seconds between checks when idle
ACTIVE_POLL_RATE = 0.1  # Version 3.0.0 - QC SCR Dedicated Hoist & Manual Operation Algorithm V3.0'''

new_cfg = '''    {"id": "111", "ip": "10.200.73.21", "rack": 0, "slot": 2, "type": "QC"},
    {"id": "112", "ip": "10.200.73.22", "rack": 0, "slot": 2, "type": "QC", "drive": "SINAMICS"}
]

# Logging Configuration
CSV_FILE = 'crane_kpi_log.csv'
RAW_DATA_DIR = 'raw_plc_data'  # Raw PLC samples saved here (gzip compressed)
RAW_RETENTION_DAYS = 90        # Auto-move raw files older than this to backups
IDLE_POLL_RATE = 0.5    # Seconds between checks when idle
ACTIVE_POLL_RATE = 0.1  # Version 3.1.0 - QC 112 SINAMICS Drive Scale Normalization (Raw preserved, KPI normalized)'''

assert old_cfg in code, "old_cfg not found"
code = code.replace(old_cfg, new_cfg, 1)

# 2. Update calculate_kpis_qc
old_calc = '''def calculate_kpis_qc(orders, feedbacks, loads, weights, positions, dt_list, db180_list):
    """
    QC SCR V3.0 Dedicated KPI calculation function.
    Tailored for Hoist (Vertical Lifting) mechanism & Manual Driver Operation.
    Replaces track_penalty with load_factor, and tunes current/shock penalties for Hoist drive.
    """
    if not orders or not dt_list or not db180_list:
        return None
        
    event_duration = sum(dt_list)
    if event_duration <= 0:
        return None

    valid_db180 = [v for v in db180_list if v is not None]
    if not valid_db180:
        return None

    speeds = [v[0] for v in valid_db180]
    currents = [v[1] for v in valid_db180]
    torques = [v[2] for v in valid_db180]
    
    peak_speed = max([abs(s) for s in speeds]) if speeds else 0.0
    avg_weight = sum(weights) / len(weights) if weights else 1.0
    is_loaded = any(loads) if loads else False

    # 1. Manual Operation Shock Penalty:
    # Captures manual joystick dynamic spikes in torque d(Torque)/dt & speed acceleration d(Speed)/dt
    dt_arr = np.array(dt_list[:len(valid_db180)])
    dt_arr = np.where(dt_arr <= 0, 0.1, dt_arr)
    
    torque_arr = np.array(torques, dtype=float)
    speed_arr = np.array(speeds, dtype=float)
    
    d_torque = np.abs(np.diff(torque_arr, prepend=torque_arr[0])) / dt_arr
    d_speed = np.abs(np.diff(speed_arr, prepend=speed_arr[0])) / dt_arr
    
    raw_shock_list = 1.0 + 0.02 * d_torque + 0.02 * d_speed
    shock_penalty = float(np.percentile(raw_shock_list, 95))
    peak_shock = float(np.max(raw_shock_list))

    # 2. Hoist Drive Current Penalty:
    # Offset base idling/holding current (~30 Amps) and evaluate over-current ratio
    curr_ratios = []
    for c, t in zip(currents, torques):
        adj_curr = max(0.0, abs(c) - 30.0)
        t_abs = abs(t) + 1.0
        curr_ratios.append(adj_curr / t_abs)
        
    avg_curr_ratio = sum(curr_ratios) / len(curr_ratios) if curr_ratios else 0.0
    curr_penalty = min(5.0, max(1.0, 1.0 + 0.15 * avg_curr_ratio))

    # 3. Hoist Load Factor (Replaces track_penalty):
    # Weight load factor: 1.0 base, increases slightly if load/weight is heavy
    w_effective = avg_weight if is_loaded else 1.0
    load_factor = min(3.0, max(1.0, 1.0 + 0.02 * max(0.0, w_effective - 10.0)))

    return {
        'algo_version': '3.0.0',
        'duration': round(event_duration, 2),
        'peak_order': peak_speed,
        'peak_fb': peak_speed,'''

new_calc = '''# QC 112 (Siemens SINAMICS Drive) -> Masterdrive (QC 101~111) Normalization Scale Factors
# Raw PLC DB180 files (raw_plc_data) preserve unscaled PLC values; normalization is applied only in calculate_kpis_qc().
QC_SINAMICS_CRANES = {"112"}
SINAMICS_SPEED_SCALE = 0.667    # SINAMICS speed range (~1350-1600) -> Masterdrive (~850-1000)
SINAMICS_CURR_SCALE = 1.65      # SINAMICS current range (idle ~20, max ~28) -> Masterdrive (idle ~30, max ~46)
SINAMICS_TORQUE_SCALE = 3.50    # SINAMICS torque range (idle ~27, max ~40) -> Masterdrive (idle ~90, max ~140)
SINAMICS_SHOCK_DAMPING = 0.43   # SINAMICS ramp d(Speed)/dt & d(Torque)/dt damping to match Masterdrive baseline (~5.0)

def calculate_kpis_qc(orders, feedbacks, loads, weights, positions, dt_list, db180_list, crane_id=None):
    """
    QC SCR V3.1 Dedicated KPI calculation function.
    Tailored for Hoist (Vertical Lifting) mechanism & Manual Driver Operation.
    Includes scale normalization for QC 112 (Siemens SINAMICS drive) while keeping raw PLC logs unscaled.
    """
    if not orders or not dt_list or not db180_list:
        return None
        
    event_duration = sum(dt_list)
    if event_duration <= 0:
        return None

    valid_db180 = [v for v in db180_list if v is not None]
    if not valid_db180:
        return None

    is_sinamics = (str(crane_id) in QC_SINAMICS_CRANES)
    if is_sinamics:
        speeds = [v[0] * SINAMICS_SPEED_SCALE for v in valid_db180]
        currents = [v[1] * SINAMICS_CURR_SCALE for v in valid_db180]
        torques = [v[2] * SINAMICS_TORQUE_SCALE for v in valid_db180]
        shock_coeff = 0.02 * SINAMICS_SHOCK_DAMPING
    else:
        speeds = [float(v[0]) for v in valid_db180]
        currents = [float(v[1]) for v in valid_db180]
        torques = [float(v[2]) for v in valid_db180]
        shock_coeff = 0.02
    
    peak_speed = round(max([abs(s) for s in speeds]), 1) if speeds else 0.0
    avg_weight = sum(weights) / len(weights) if weights else 1.0
    is_loaded = any(loads) if loads else False

    # 1. Manual Operation Shock Penalty:
    # Captures manual joystick dynamic spikes in torque d(Torque)/dt & speed acceleration d(Speed)/dt
    dt_arr = np.array(dt_list[:len(valid_db180)])
    dt_arr = np.where(dt_arr <= 0, 0.1, dt_arr)
    
    torque_arr = np.array(torques, dtype=float)
    speed_arr = np.array(speeds, dtype=float)
    
    d_torque = np.abs(np.diff(torque_arr, prepend=torque_arr[0])) / dt_arr
    d_speed = np.abs(np.diff(speed_arr, prepend=speed_arr[0])) / dt_arr
    
    raw_shock_list = 1.0 + shock_coeff * d_torque + shock_coeff * d_speed
    shock_penalty = float(np.percentile(raw_shock_list, 95))
    peak_shock = float(np.max(raw_shock_list))

    # 2. Hoist Drive Current Penalty:
    # Offset base idling/holding current (~30 Amps) and evaluate over-current ratio
    curr_ratios = []
    for c, t in zip(currents, torques):
        adj_curr = max(0.0, abs(c) - 30.0)
        t_abs = abs(t) + 1.0
        curr_ratios.append(adj_curr / t_abs)
        
    avg_curr_ratio = sum(curr_ratios) / len(curr_ratios) if curr_ratios else 0.0
    curr_penalty = min(5.0, max(1.0, 1.0 + 0.15 * avg_curr_ratio))

    # 3. Hoist Load Factor (Replaces track_penalty):
    # Weight load factor: 1.0 base, increases slightly if load/weight is heavy
    w_effective = avg_weight if is_loaded else 1.0
    load_factor = min(3.0, max(1.0, 1.0 + 0.02 * max(0.0, w_effective - 10.0)))

    return {
        'algo_version': '3.1.0',
        'duration': round(event_duration, 2),
        'peak_order': peak_speed,
        'peak_fb': peak_speed,'''

assert old_calc in code, "old_calc not found"
code = code.replace(old_calc, new_calc, 1)

# 3. Pass crane_id into calculate_kpis_qc in monitor_qc_spreader
old_call = "kpis = calculate_kpis_qc(orders, feedbacks, loads, weights, positions, dt_list, db180_list)"
new_call = "kpis = calculate_kpis_qc(orders, feedbacks, loads, weights, positions, dt_list, db180_list, crane_id=crane_id)"
assert old_call in code, "old_call not found"
code = code.replace(old_call, new_call, 1)

# 4. Update version strings from 3.0.0 to 3.1.0 in calculate_kpis and initialize_influx_kpis
code = code.replace("'algo_version': '3.0.0'", "'algo_version': '3.1.0'")

with open("crane_edge_logger.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Successfully updated crane_edge_logger.py to v3.1.0!")
