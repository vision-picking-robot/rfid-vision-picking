@echo off
chcp 65001 >nul
cd /d "%~dp0.."
call "%~dp0_api.bat"
echo 키보드 입력 모드: 드라이버/PC-SC 없이, 이 창에 입력되는 UID를 로봇 PC로 보냅니다.
.venv-win\Scripts\python.exe windows_rfid_bridge\bridge.py --api %API_URL% --keyboard %*
pause
