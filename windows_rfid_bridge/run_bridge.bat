@echo off
chcp 65001 >nul
cd /d "%~dp0.."
title RFID 태그 관제 - 준비

rem 1) Python environment (first run only)
if exist ".venv-win\Scripts\pythonw.exe" goto :deps
echo [준비] Python 가상환경 생성 (.venv-win)
where py >nul 2>nul && (py -3 -m venv .venv-win) || (python -m venv .venv-win)
if errorlevel 1 (
  echo Python 3.10 이상을 설치하고 "Add python.exe to PATH"를 체크한 뒤 다시 실행하세요.
  pause & exit /b 1
)
:deps
.venv-win\Scripts\python.exe -c "import httpx, tkinter, PIL" >nul 2>nul
if not errorlevel 1 goto :run
echo [준비] httpx, pillow 설치
.venv-win\Scripts\python.exe -m pip install -r windows_rfid_bridge\requirements.txt
if errorlevel 1 ( echo 설치 실패 - 인터넷 연결을 확인하세요. & pause & exit /b 1 )
.venv-win\Scripts\python.exe -c "import tkinter" >nul 2>nul
if errorlevel 1 ( echo Python 설치 시 "tcl/tk and IDLE" 항목을 체크해 다시 설치하세요. & pause & exit /b 1 )

rem 2) RFID 태그 관제 프로그램 (콘솔 창 없이 실행; 로봇 PC 주소는 프로그램 아래쪽에서 변경)
:run
start "" ".venv-win\Scripts\pythonw.exe" windows_rfid_bridge\control_panel.py %*
