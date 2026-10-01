@echo off
setlocal
where pwsh.exe >nul 2>nul
if errorlevel 1 (
    powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_portfolio_demo.ps1" %*
) else (
    pwsh.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\start_portfolio_demo.ps1" %*
)
if errorlevel 1 (
    pause
    exit /b 1
)
