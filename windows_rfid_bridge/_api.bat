@echo off
rem Reads the robot PC URL from api_url.txt, asking once if it is missing or invalid.
set "API_FILE=%~dp0api_url.txt"
set "API_URL="
if exist "%API_FILE%" set /p API_URL=<"%API_FILE%"
if not defined API_URL goto :ask
if /i "%API_URL:~0,4%"=="http" goto :have
:ask
set "API_URL=http://192.168.204.52:8000"
set /p "API_URL=로봇 PC 주소 입력 (Enter = %API_URL%): "
>"%API_FILE%" echo %API_URL%
:have
echo 로봇 PC: %API_URL%   (변경: windows_rfid_bridge\api_url.txt 수정 또는 삭제)
