@echo off
:: Check Administrator Privileges
NET SESSION >nul 2>&1
if %errorLevel% == 0 (
    goto :RunPowerShell
) else (
    echo [Info] Requesting Administrator Privileges...
    powershell -Command "Start-Process '%~dpnx0' -Verb RunAs"
    exit /b
)

:RunPowerShell
echo [Info] Registering CranePdM Logger Watchdog task into Windows Task Scheduler...

powershell -ExecutionPolicy Bypass -Command "$taskName='CranePdM_Logger_Watchdog'; $scriptPath='C:\Users\huser\.gemini\CranePdM\logger_watchdog.ps1'; Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue; $action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-ExecutionPolicy Bypass -WindowStyle Hidden -File ' + [char]34 + $scriptPath + [char]34); $trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 5); $trigger2 = New-ScheduledTaskTrigger -AtStartup; $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false; $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger1,$trigger2 -Settings $settings -Principal $principal -Force"

echo.
echo ========================================================
echo [SUCCESS] Watchdog Task Scheduler Registration Completed!
echo - Auto-starts on System Bootup / Server Restart.
echo - Auto-recovers Logger within 5 minutes if process drops.
echo ========================================================
echo.
pause
