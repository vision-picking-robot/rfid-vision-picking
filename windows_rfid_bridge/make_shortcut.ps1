# Creates the "RFID 태그 관제" shortcut (opens the control panel without a console window).
param([string]$Desktop = [Environment]::GetFolderPath('Desktop'))
$root = Split-Path -Parent $PSScriptRoot
$pythonw = Join-Path $root '.venv-win\Scripts\pythonw.exe'
if (-not (Test-Path $pythonw)) {
    Write-Host '먼저 windows_rfid_bridge\run_bridge.bat 을 한 번 실행하세요.'
    exit 1
}
$link = Join-Path $Desktop 'RFID 태그 관제.lnk'
$s = (New-Object -ComObject WScript.Shell).CreateShortcut($link)
$s.TargetPath = $pythonw
$s.Arguments = '"' + (Join-Path $root 'windows_rfid_bridge\control_panel.py') + '"'
$s.WorkingDirectory = $root
$s.IconLocation = Join-Path $root 'windows_rfid_bridge\assets\app.ico'
$s.Description = 'E0509 RFID 태그 관제'
$s.Save()
Write-Host "바로가기를 만들었습니다: $link"
