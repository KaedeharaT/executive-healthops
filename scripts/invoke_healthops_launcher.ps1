<# Shared foreground lifecycle. Keep this window open while using HealthOps. #>
[CmdletBinding()]
param(
    [ValidateSet("platform", "portfolio")][string]$Profile = "platform",
    [switch]$NoBrowser,
    [string]$Instance = "platform",
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$manager = Join-Path $PSScriptRoot "service_processes.py"
if (-not (Test-Path -LiteralPath $Python)) { throw "Project Python not found: $Python" }
$token = [guid]::NewGuid().ToString("N")
$serviceArgs = @("--instance", $Instance, "--profile", $Profile,
    "--api-port", "$ApiPort", "--ui-port", "$UiPort", "--launcher-pid", "$PID", "--token", $token)
if (-not $NoBrowser) { $serviceArgs += "--open-browser" }
Push-Location $ProjectRoot
try {
    $env:PYTHONPATH = Join-Path $ProjectRoot "src"
    Write-Host "Checking HealthOps leftovers and starting services..."
    Write-Host "Logs: .runtime/logs/$Instance/; PIDs: .runtime/processes/$Instance.json"
    # The hidden supervisor watches this shell and the controller independently.
    & $Python -u $manager launch @serviceArgs
    if ($LASTEXITCODE -ne 0) { throw "HealthOps launcher failed. See the error above and .runtime/logs/$Instance/." }
} finally {
    try {
        # Token-scoped cleanup cannot kill a replacement using this instance.
        & $Python $manager stop --instance $Instance --token $token
        if ($LASTEXITCODE -ne 0) { Write-Error "HealthOps cleanup failed; inspect .runtime/logs/$Instance/." }
    } finally {
        Pop-Location
    }
}
