$taskName = "CranePdM_Logger_Watchdog"

# Unregister if it somehow exists
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

# Create Action
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\Users\huser\.gemini\CranePdM\logger_watchdog.ps1"'

# Create Triggers
$trigger1 = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) -RepetitionInterval (New-TimeSpan -Minutes 30)
$trigger2 = New-ScheduledTaskTrigger -AtLogOn

# Create Settings
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable:$false

# Register Task (Run as current user to bypass Admin requirement)
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger1,$trigger2 -Settings $settings -Force
Write-Host "Task successfully registered under current user."
