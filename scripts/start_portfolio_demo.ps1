<#
Start the isolated Executive HealthOps portfolio demo on Windows.
It creates/uses only data\portfolio_demo.db and never changes the normal
development database.  Stop the two spawned Python processes from Task Manager
or close their PowerShell hosts when you finish.
#>
[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

$databasePath = Join-Path $projectRoot "data\portfolio_demo.db"
if ($Rebuild -or -not (Test-Path -LiteralPath $databasePath)) {
    & $python (Join-Path $projectRoot "scripts\build_portfolio_demo.py") --rebuild
    if ($LASTEXITCODE -ne 0) { throw "作品集演示数据库创建失败。" }
}

$databaseUrl = "sqlite:///" + ($databasePath -replace "\\", "/")
$env:DATABASE_URL = $databaseUrl
$env:PORTFOLIO_DEMO = "true"
$env:PYTHONPATH = (Join-Path $projectRoot "src")

function Test-LocalPort([int]$Port) {
    return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
}

Push-Location $projectRoot
try {
    if (Test-LocalPort 8000) { throw "端口 8000 已被占用。请先停止已有 API，避免误连接到非作品集数据库。" }
    if (Test-LocalPort 8501) { throw "端口 8501 已被占用。请先停止已有 Streamlit，避免误连接到非作品集数据库。" }
    Start-Process -FilePath $python -ArgumentList "-m uvicorn executive_health_ai.api:app --app-dir src --host 127.0.0.1 --port 8000" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
    Start-Process -FilePath $python -ArgumentList "-m streamlit run streamlit_app.py --server.address 127.0.0.1 --server.port 8501" -WorkingDirectory $projectRoot -WindowStyle Hidden | Out-Null
    if (-not $NoBrowser) {
        Start-Sleep -Seconds 2
        Start-Process "http://127.0.0.1:8501"
    }
    Write-Host "Portfolio Demo is using data/portfolio_demo.db"
    Write-Host "Streamlit: http://127.0.0.1:8501"
    Write-Host "FastAPI:   http://127.0.0.1:8000/docs"
} finally {
    Pop-Location
}
