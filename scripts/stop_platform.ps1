[CmdletBinding()]
param([string]$Instance = "platform", [switch]$All, [int]$ApiPort = 8000, [int]$UiPort = 8501)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$manager = Join-Path $PSScriptRoot "service_processes.py"
Write-Host "Stopping HealthOps..."
if ($All) {
    $records = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot ".runtime\processes") -Filter "*.json" -ErrorAction SilentlyContinue)
    foreach ($record in $records) {
        & $Python $manager stop --instance $record.BaseName
        if ($LASTEXITCODE -ne 0) { throw "Could not stop $($record.BaseName)." }
    }
}
if ($Instance -in @("platform", "portfolio") -or $All) {
    # Public profiles share ports; include positively identified legacy services.
    & $Python $manager cleanup --instance $Instance --api-port $ApiPort --ui-port $UiPort
} else {
    & $Python $manager stop --instance $Instance
}
if ($LASTEXITCODE -ne 0) { throw "HealthOps cleanup failed. No successful stop was reported." }
Write-Host "HealthOps stopped cleanly."
