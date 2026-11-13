@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title RFID bridge (console) - tag UID to robot PC
rem 예전 콘솔 방식. 평소에는 run_bridge.bat (관제 프로그램)을 쓴다.

if not exist ".venv-win\Scripts\python.exe" (
  echo 먼저 windows_rfid_bridge\run_bridge.bat 을 한 번 실행해 환경을 준비하세요.
  pause & exit /b 1
)

set "API_FILE=%~dp0api_url.txt"
set "API_URL="
if exist "%API_FILE%" set /p API_URL=<"%API_FILE%"
if not defined API_URL goto :ask
if /i "%API_URL:~0,4%"=="http" goto :run
:ask
set "API_URL=http://192.168.204.52:8000"
set /p "API_URL=로봇 PC 주소 입력 (Enter = %API_URL%): "
>"%API_FILE%" echo %API_URL%

:run
echo 로봇 PC: %API_URL%   (변경: windows_rfid_bridge\api_url.txt 삭제 후 다시 실행)
.venv-win\Scripts\python.exe windows_rfid_bridge\bridge.py --api %API_URL% %*
pause
