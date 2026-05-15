@echo off
chcp 65001 >nul
echo ============================================
echo   CranePdM Edge Logger 시작
echo ============================================
echo.

cd /d C:\Users\huser\CranePdM

echo [1/2] Python 패키지 확인 중...
pip install -r requirements.txt --quiet 2>nul

echo [2/2] Edge Logger 실행 중...
echo.
python crane_edge_logger.py

echo.
echo ============================================
echo   프로그램이 종료되었습니다.
echo   오류 메시지를 확인한 후 아무 키나 누르세요.
echo ============================================
pause
