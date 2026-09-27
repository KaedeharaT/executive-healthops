[CmdletBinding()]
param(
    [switch]$NoBrowser,
    [string]$Instance = "platform",
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501
)
$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$manager = Join-Path $PSScriptRoot "service_processes.py"
$serviceArgs = @("--instance", $Instance, "--profile", "platform", "--api-port", "$ApiPort", "--ui-port", "$UiPort")
if (-not (Test-Path -LiteralPath $Python)) { throw "Project Python virtual environment not found: $Python" }
Push-Location $ProjectRoot
try {
    $envFile = Join-Path $ProjectRoot ".env"
    if (Test-Path -LiteralPath $envFile) {
        foreach ($line in Get-Content -LiteralPath $envFile) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
                $name, $value = $matches[1], $matches[2]
                if (-not (Test-Path "Env:$name")) { Set-Item -Path "Env:$name" -Value $value }
            }
        }
    }
    # Restart only the recorded process tree, never an unowned port listener.
    & $Python $manager stop --instance $Instance
    if ($LASTEXITCODE -ne 0) { throw "Previous service group could not be stopped." }
    & $Python $manager preflight @serviceArgs
    if ($LASTEXITCODE -ne 0) { throw "Port occupied. Stop the previous launcher before retrying." }
    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database upgrade failed." }
    & $Python $manager start @serviceArgs
    if ($LASTEXITCODE -ne 0) { throw "Services failed. See .runtime/logs/$Instance/." }
    # local LLM remains optional; an existing Ollama is never owned or stopped.
    try {
        $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2
        $model = @($tags.models | Where-Object { $_.name -eq $env:LOCAL_LLM_MODEL })
        if ($model.Count -gt 0) { Write-Host "local LLM ready" }
        else { Write-Host "local LLM not configured; rule-based parsing remains available." }
    } catch { Write-Host "local LLM unavailable; rule-based parsing remains available." }
    Write-Host "Streamlit: http://127.0.0.1:$UiPort; FastAPI: http://127.0.0.1:$ApiPort/docs"
    Write-Host "Logs: .runtime/logs/$Instance/; PIDs: .runtime/processes/$Instance.json"
    Write-Host "Stop: .\scripts\stop_platform.ps1 -Instance $Instance"
    if (-not $NoBrowser) { Start-Process "http://127.0.0.1:$UiPort" }
} finally {
    Pop-Location
}
