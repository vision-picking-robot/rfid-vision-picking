@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title RFID bridge - tag UID to robot PC

rem 1) Python environment (first run only)
if exist ".venv-win\Scripts\python.exe" goto :deps
echo [준비] Python 가상환경 생성 (.venv-win)
where py >nul 2>nul && (py -3 -m venv .venv-win) || (python -m venv .venv-win)
if errorlevel 1 (
  echo Python 3.10 이상을 설치하고 "Add python.exe to PATH"를 체크한 뒤 다시 실행하세요.
  pause & exit /b 1
)
:deps
.venv-win\Scripts\python.exe -c "import httpx" >nul 2>nul
if not errorlevel 1 goto :api
echo [준비] httpx 설치
.venv-win\Scripts\python.exe -m pip install -r windows_rfid_bridge\requirements.txt
if errorlevel 1 ( echo 설치 실패 - 인터넷 연결을 확인하세요. & pause & exit /b 1 )

rem 2) Robot PC address (asked once, saved to api_url.txt)
:api
set "API_FILE=%~dp0api_url.txt"
set "API_URL="
if exist "%API_FILE%" set /p API_URL=<"%API_FILE%"
if not defined API_URL goto :ask
if /i "%API_URL:~0,4%"=="http" goto :run
:ask
set "API_URL=http://192.168.204.52:8000"
set /p "API_URL=로봇 PC 주소 입력 (Enter = %API_URL%): "
>"%API_FILE%" echo %API_URL%

rem 3) Tag UID -> robot PC
:run
echo 로봇 PC: %API_URL%   (변경: windows_rfid_bridge\api_url.txt 삭제 후 다시 실행)
.venv-win\Scripts\python.exe windows_rfid_bridge\bridge.py --api %API_URL% %*
pause
