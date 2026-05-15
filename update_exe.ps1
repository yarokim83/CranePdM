Write-Host "Killing existing crane_edge_logger.exe..."
Get-CimInstance Win32_Process -Filter "Name='crane_edge_logger.exe'" | Invoke-CimMethod -MethodName Terminate | Out-Null
Start-Sleep -Seconds 2

Write-Host "Updating executable..."
Move-Item -Path dist\crane_edge_logger.exe -Destination deploy_package\crane_edge_logger.exe -Force

Write-Host "Starting new executable..."
Start-Process -FilePath deploy_package\crane_edge_logger.exe -WindowStyle Hidden
Write-Host "Done."
