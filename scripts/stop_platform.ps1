[CmdletBinding()]
param([string]$Instance = "platform", [switch]$All)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$manager = Join-Path $PSScriptRoot "service_processes.py"
$instances = @($Instance)
if ($All) {
    $instances = @(Get-ChildItem -LiteralPath (Join-Path $ProjectRoot ".runtime\processes") -Filter "*.json" -ErrorAction SilentlyContinue | ForEach-Object { $_.BaseName })
}
foreach ($name in $instances) {
    & $Python $manager stop --instance $name
    if ($LASTEXITCODE -ne 0) { throw "Could not stop $name. See .runtime/logs/$name/." }
}
