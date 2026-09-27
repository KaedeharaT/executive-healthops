<# Start prepared OLD/NEW snapshots without console windows or database reseeding. #>
[CmdletBinding()]
param(
    [string]$Instance = "visual-qa",
    [string]$Manifest = "",
    [string]$CaptureScript = "",
    [string[]]$CaptureArguments = @()
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$manager = Join-Path $PSScriptRoot "service_processes.py"
if (-not $Manifest) { $Manifest = Join-Path $ProjectRoot ".runtime\neumorphism-v2\manifest.json" }
$started = $false
Push-Location $ProjectRoot
try {
    & $Python $manager start --instance $Instance --profile qa --manifest $Manifest
    if ($LASTEXITCODE -ne 0) { throw "QA servers failed. See .runtime/logs/$Instance/." }
    $started = $true
    if ($CaptureScript) {
        & $Python $CaptureScript @CaptureArguments
        if ($LASTEXITCODE -ne 0) { throw "QA capture failed." }
    } else {
        Write-Host "QA servers ready. Stop: .\scripts\stop_platform.ps1 -Instance $Instance"
    }
} finally {
    if ($started -and $CaptureScript) {
        & $Python $manager stop --instance $Instance
        if ($LASTEXITCODE -ne 0) { Write-Error "QA process cleanup failed." }
    }
    Pop-Location
}
