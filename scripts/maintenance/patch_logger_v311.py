with open("crane_edge_logger.py", "r", encoding="utf-8") as f:
    code = f.read()

old_ver = "ACTIVE_POLL_RATE = 0.1  # Version 3.1.0 - QC 112 SINAMICS Drive Scale Normalization (Raw preserved, KPI normalized)"
new_ver = "ACTIVE_POLL_RATE = 0.1  # Version 3.1.1 - QC 112 SINAMICS Scale Normalization + Source Tag Isolation (live_qc_v31)"
assert old_ver in code, "old_ver not found"
code = code.replace(old_ver, new_ver, 1)

code = code.replace("'algo_version': '3.1.0'", "'algo_version': '3.1.1'")
old_src = 'source_tag = "live_qc_v30" if crane_type == "QC" else "live_v26"'
new_src = 'source_tag = "live_qc_v31" if crane_type == "QC" else "live_v26"'
assert old_src in code, "old_src not found"
code = code.replace(old_src, new_src, 1)

with open("crane_edge_logger.py", "w", encoding="utf-8") as f:
    f.write(code)

print("Updated crane_edge_logger.py to v3.1.1 with source='live_qc_v31'")
