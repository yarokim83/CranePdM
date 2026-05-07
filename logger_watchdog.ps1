$processName = "crane_edge_logger"
$exePath = "C:\Users\huser\.gemini\CranePdM\deploy_package\crane_edge_logger.exe"
$workingDir = "C:\Users\huser\.gemini\CranePdM\deploy_package"

# Check if the process is running
$process = Get-Process -Name $processName -ErrorAction SilentlyContinue

if (-not $process) {
    # If not running, start the process
    Write-Output "[$(Get-Date)] Process not found. Restarting $processName..." | Out-File -Append -FilePath "C:\Users\huser\.gemini\CranePdM\deploy_package\watchdog.log"
    Start-Process -FilePath $exePath -WorkingDirectory $workingDir -WindowStyle Hidden
} else {
    # It is running, do nothing
}
