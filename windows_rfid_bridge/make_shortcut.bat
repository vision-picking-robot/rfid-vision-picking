@echo off
chcp 65001 >nul
rem 바탕화면에 "RFID 태그 관제" 바로가기를 만든다 (콘솔 창 없이 프로그램이 바로 열린다).
rem 먼저 run_bridge.bat을 한 번 실행해 .venv-win이 만들어져 있어야 한다.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0make_shortcut.ps1"
pause
