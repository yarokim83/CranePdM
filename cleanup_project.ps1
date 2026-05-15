# 1. Merge raw_plc_data
Write-Host "Merging raw_plc_data..."
if (Test-Path "raw_plc_data") {
    # Ensure destination exists
    if (!(Test-Path "deploy_package\raw_plc_data")) {
        New-Item -ItemType Directory -Force -Path "deploy_package\raw_plc_data"
    }
    Move-Item -Path "raw_plc_data\*" -Destination "deploy_package\raw_plc_data\" -Force
    Remove-Item -Path "raw_plc_data" -Recurse -Force
    Write-Host "Merged and removed old raw_plc_data."
}

# 2. Backups
Write-Host "Organizing backups..."
New-Item -ItemType Directory -Force -Path "backups" | Out-Null
if (Test-Path "crane_kpi_log.csv") { Move-Item -Path "crane_kpi_log.csv" -Destination "backups\" -Force }
if (Test-Path "backup_influx_430_504.csv") { Move-Item -Path "backup_influx_430_504.csv" -Destination "backups\" -Force }
if (Test-Path "backup_20260428") { Move-Item -Path "backup_20260428" -Destination "backups\" -Force }
if (Test-Path "archived_data") { Move-Item -Path "archived_data" -Destination "backups\" -Force }

# 3. Scripts
Write-Host "Moving scripts..."
New-Item -ItemType Directory -Force -Path "scripts\maintenance" | Out-Null
New-Item -ItemType Directory -Force -Path "scripts\analysis" | Out-Null

# List of maintenance scripts
$maintScripts = @(
    "add_table_panel.py", "check_235.py", "check_235_7d.py", "check_shock_data.py",
    "check_v24_fields.py", "deploy_dashboards.py", "diagnose_influx.py", "fix_history.py",
    "fix_xychart.py", "fix_xychart2.py", "force_smooth_history.py", "precise_downscale.py",
    "push_dashboard.py", "test_query_again.py", "unify_v24_30mar_27apr.py",
    "update_dash_fallback.py", "update_dashboard_sources.py", "update_threshold.py",
    "update_threshold_24.py", "update_xychart.py", "verify_detail_query.py", "backup_db.py"
)

foreach ($script in $maintScripts) {
    if (Test-Path $script) { Move-Item -Path $script -Destination "scripts\maintenance\" -Force }
}

# List of analysis scripts
$analysisScripts = @(
    "analyze_235.py", "analyze_256.py", "compare_235.py", "track_235.py", "validate_v261.py"
)

foreach ($script in $analysisScripts) {
    if (Test-Path $script) { Move-Item -Path $script -Destination "scripts\analysis\" -Force }
}

Write-Host "Cleanup completed successfully!"
