<#
Start the isolated Executive HealthOps portfolio demo on Windows.
It creates/uses only data\portfolio_demo.db and never changes the normal
development database. Stop with scripts/stop_platform.ps1 -Instance portfolio.
#>
[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBrowser,
    [string]$Instance = "portfolio",
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $python = "python"
}

$manager = Join-Path $PSScriptRoot "service_processes.py"
$serviceArgs = @("--instance", $Instance, "--profile", "portfolio", "--api-port", "$ApiPort", "--ui-port", "$UiPort")
# Reject occupied ports BEFORE changing the disposable demo database.
& $python $manager preflight @serviceArgs
if ($LASTEXITCODE -ne 0) { throw "Release the occupied services before preparing the demo." }
Push-Location $projectRoot
try {
$databasePath = Join-Path $projectRoot "data\portfolio_demo.db"
if ($Rebuild) {
    & $python (Join-Path $projectRoot "scripts\build_portfolio_demo.py") --rebuild
    if ($LASTEXITCODE -ne 0) { throw "作品集演示数据库创建失败。" }
} else {
    # The demo database is disposable synthetic data. Keep its fixture contract
    # aligned with the application so an old local file cannot produce empty UI.
    & $python (Join-Path $projectRoot "scripts\build_portfolio_demo.py") --ensure-current
    if ($LASTEXITCODE -ne 0) { throw "作品集演示数据检查失败。" }
}

$databaseUrl = "sqlite:///" + ($databasePath -replace "\\", "/")
$env:DATABASE_URL = $databaseUrl
$env:PORTFOLIO_DEMO = "true"
$env:AGENT_SUPERVISOR_ENABLED = "true"
$env:PYTHONPATH = (Join-Path $projectRoot "src")

# Existing demo databases can outlive application code updates.  Always bring
# the isolated schema to head before either service is allowed to start.
& $python -m alembic upgrade head
if ($LASTEXITCODE -ne 0) {
    throw "Portfolio Demo 数据库结构升级失败。请先执行 alembic upgrade head。"
}
& $python (Join-Path $projectRoot "scripts\record_care_responsibility.py")
if ($LASTEXITCODE -ne 0) { throw "现有健康管理流程责任记录更新失败。" }

    & $python $manager start @serviceArgs
    if ($LASTEXITCODE -ne 0) { throw "Portfolio services failed. See .runtime/logs/$Instance/." }
    if (-not $NoBrowser) {
        Start-Process "http://127.0.0.1:$UiPort"
    }
    Write-Host "Portfolio Demo is using data/portfolio_demo.db"
    Write-Host "Streamlit: http://127.0.0.1:$UiPort"
    Write-Host "FastAPI:   http://127.0.0.1:$ApiPort/docs"
    Write-Host "Logs: .runtime/logs/$Instance/; PIDs: .runtime/processes/$Instance.json"
    Write-Host "Stop: .\scripts\stop_platform.ps1 -Instance $Instance"
} finally {
    Pop-Location
}
