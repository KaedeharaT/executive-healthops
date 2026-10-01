[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [string]$Instance = "platform",
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $ProjectRoot ".env"
if (Test-Path -LiteralPath $envFile) {
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $name, $value = $matches[1], $matches[2]
            if (-not (Test-Path "Env:$name")) { Set-Item -Path "Env:$name" -Value $value }
        }
    }
}
# Startup manages processes only. Schema/data maintenance is an explicit task.
& (Join-Path $PSScriptRoot "invoke_healthops_launcher.ps1") @PSBoundParameters -Profile platform
