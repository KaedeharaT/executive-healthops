<# Reuse the existing Demo database; ordinary startup never seeds or migrates it. #>
[CmdletBinding()]
param(
    [switch]$Rebuild,
    [switch]$NoBrowser,
    [string]$Instance = "portfolio",
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [string]$DatabasePath = ""
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
if ($Rebuild) {
    throw "Launcher does not rebuild databases. Use the separate build_portfolio_demo.py maintenance command explicitly."
}
if (-not $DatabasePath) { $DatabasePath = Join-Path $ProjectRoot "data\portfolio_demo.db" }
if (-not (Test-Path -LiteralPath $DatabasePath -PathType Leaf)) {
    throw "Demo database not found: $DatabasePath. Restore or prepare it explicitly before starting."
}
$DatabasePath = (Resolve-Path -LiteralPath $DatabasePath).Path
$env:DATABASE_URL = "sqlite:///" + ($DatabasePath -replace "\\", "/")
$env:PORTFOLIO_DEMO = "true"
$env:AGENT_SUPERVISOR_ENABLED = "true"
& (Join-Path $PSScriptRoot "invoke_healthops_launcher.ps1") -Profile portfolio `
    -Instance $Instance -ApiPort $ApiPort -UiPort $UiPort -NoBrowser:$NoBrowser
