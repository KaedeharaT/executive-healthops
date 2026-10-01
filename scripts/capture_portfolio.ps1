<#
Create real, local browser screenshots for the Executive HealthOps portfolio.

This is a development/portfolio helper.  It installs Playwright only into the
repository virtual environment; it does not change project dependencies,
application code, or demo data.
#>
[CmdletBinding()]
param([switch]$SkipInstall)

$ErrorActionPreference = "Stop"
if ($PSVersionTable.PSVersion.Major -lt 7) {
    throw "Run this portfolio helper from PowerShell 7: pwsh -File .\\scripts\\capture_portfolio.ps1"
}
$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPath = Join-Path $projectRoot ".venv"
$python = Join-Path $venvPath "Scripts\python.exe"

function Get-BootstrapPython {
    $candidates = @(
        @{ Command = "py"; Arguments = @("-3.11") },
        @{ Command = "python"; Arguments = @() }
    )
    foreach ($candidate in $candidates) {
        if (Get-Command $candidate.Command -ErrorAction SilentlyContinue) {
            return $candidate
        }
    }
    throw "Python 3.11 is required to create .venv. Install Python and retry."
}

if (-not (Test-Path -LiteralPath $python)) {
    Write-Host "Creating repository virtual environment..."
    $bootstrap = Get-BootstrapPython
    & $bootstrap.Command @($bootstrap.Arguments + @("-m", "venv", $venvPath))
    if ($LASTEXITCODE -ne 0) { throw "Failed to create .venv." }
}

if (-not $SkipInstall) {
Write-Host "Preparing project and local Playwright tooling..."
& $python -m pip install --upgrade pip
if ($LASTEXITCODE -ne 0) { throw "Failed to upgrade pip." }
& $python -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "Failed to install project development dependencies." }
& $python -m pip install playwright
if ($LASTEXITCODE -ne 0) { throw "Failed to install Playwright in .venv." }
& $python -m playwright install chromium
if ($LASTEXITCODE -ne 0) { throw "Failed to install Playwright Chromium." }
}

$started = $false
try {
Write-Host "Starting the existing Portfolio Demo for capture..."
$demoDatabase = Join-Path $projectRoot "data\portfolio_demo.db"
if (-not (Test-Path -LiteralPath $demoDatabase)) { throw "Prepare the Demo database explicitly before capture." }
$env:DATABASE_URL = "sqlite:///" + ($demoDatabase -replace "\\", "/")
$env:PORTFOLIO_DEMO = "true"
$env:AGENT_SUPERVISOR_ENABLED = "true"
# This automation owns its background group until capture exits.
& $python (Join-Path $PSScriptRoot "service_processes.py") start --profile portfolio --instance portfolio-capture --launcher-pid $PID
if ($LASTEXITCODE -ne 0) { throw "Portfolio Demo startup failed." }
$started = $true

$demoUrl = "http://127.0.0.1:8501"
$deadline = (Get-Date).AddSeconds(90)
do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing $demoUrl -TimeoutSec 5
        if ($response.StatusCode -eq 200) { break }
    } catch {
        Start-Sleep -Seconds 2
    }
} while ((Get-Date) -lt $deadline)

if (-not $response -or $response.StatusCode -ne 200) {
    throw "Portfolio Demo did not return HTTP 200 at $demoUrl within 90 seconds."
}

$imagesDir = Join-Path $projectRoot "docs\images"
New-Item -ItemType Directory -Force -Path $imagesDir | Out-Null
$summaryPath = Join-Path $env:TEMP "executive-healthops-portfolio-screenshot-summary.json"

Write-Host "Capturing real Streamlit Portfolio Demo pages..."
& $python (Join-Path $PSScriptRoot "capture_portfolio_screenshots.py") `
    --url $demoUrl `
    --output-dir $imagesDir `
    --summary-json $summaryPath
$captureExit = $LASTEXITCODE

if (Test-Path -LiteralPath $summaryPath) {
    $summary = Get-Content -LiteralPath $summaryPath -Raw | ConvertFrom-Json
    Write-Host ""
    Write-Host "Screenshot summary"
    Write-Host "Dashboard: $($summary.dashboard.status)"
    Write-Host "Member overview: $($summary.member_overview.status)"
    Write-Host "Doctor review: $($summary.doctor_review.status)"
    Write-Host "Timeline: $($summary.timeline.status)"
    Write-Host "Knowledge center: $($summary.knowledge_center.status)"
    Write-Host ""
    Write-Host "Generated PNG files:"
    foreach ($entry in $summary.PSObject.Properties) {
        if ($entry.Value.path) { Write-Host ([System.IO.Path]::GetFullPath($entry.Value.path)) }
    }
}

} finally {
    if ($started) { & (Join-Path $PSScriptRoot "stop_platform.ps1") -Instance portfolio-capture }
}
exit $captureExit
