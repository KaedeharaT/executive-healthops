@echo off
setlocal
where pwsh.exe >nul 2>nul
if errorlevel 1 (
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_platform.ps1"
) else (
    pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\stop_platform.ps1"
)
if errorlevel 1 (
    pause
    exit /b 1
)
echo HealthOps stopped.
echo Ports 8501 and 8000 released.
