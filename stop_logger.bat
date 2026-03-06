@echo off
chcp 65001 >nul
echo ============================================
echo   CranePdM Edge Logger 백그라운드 프로세스 종료
echo ============================================
echo.

powershell -Command "Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'crane_edge_logger.py' -and $_.Name -match 'pythonw.exe' } | Invoke-CimMethod -MethodName Terminate"

echo.
echo ============================================
echo   종료 대상 프로세스가 있으면 종료되었습니다.
echo ============================================
pause
