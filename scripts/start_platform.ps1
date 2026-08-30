[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$ProjectRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$StreamlitApp = Join-Path $ProjectRoot "streamlit_app.py"
$SourceRoot = Join-Path $ProjectRoot "src"

function Write-Status([string]$State, [string]$Message) {
    $colour = switch ($State) { "OK" { "Green" } "WARN" { "Yellow" } "ERROR" { "Red" } default { "White" } }
    Write-Host "[$State] $Message" -ForegroundColor $colour
}

function Read-ProjectEnv {
    $envFile = Join-Path $ProjectRoot ".env"
    if (-not (Test-Path -LiteralPath $envFile)) {
        Write-Status "WARN" ".env not found; using current environment settings."
        return
    }
    foreach ($line in Get-Content -LiteralPath $envFile) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*?)\s*$') {
            $name, $value = $matches[1], $matches[2]
            if (-not (Test-Path "Env:$name")) { Set-Item -Path "Env:$name" -Value $value }
        }
    }
}

function Test-PlatformUrl([string]$Url) {
    try { return (Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 2).StatusCode -eq 200 }
    catch { return $false }
}

function Get-PortProcess([int]$Port) {
    $listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
    if (-not $listener) { return $null }
    return Get-CimInstance Win32_Process -Filter "ProcessId=$($listener.OwningProcess)"
}

function Is-ThisProjectProcess($Process) {
    if ($null -eq $Process -or [string]::IsNullOrWhiteSpace($Process.CommandLine)) { return $false }
    $command = $Process.CommandLine.ToLowerInvariant()
    return $command.Contains($ProjectRoot.ToLowerInvariant()) -and ($command.Contains("streamlit_app.py") -or $command.Contains("uvicorn") -or $command.Contains("executive_health_ai.api"))
}

function Stop-ProjectService([int]$Port, [string]$Name) {
    $existing = Get-PortProcess $Port
    if (-not $existing) { return }
    if (-not (Is-ThisProjectProcess $existing)) {
        throw "[ERROR] Port $Port is occupied by another program. PID=$($existing.ProcessId) CommandLine=$($existing.CommandLine)"
    }
    Write-Status "OK" "Restarting previous project $Name :$Port"
    Stop-Process -Id $existing.ProcessId -ErrorAction Stop
    for ($i = 0; $i -lt 10; $i++) {
        if (-not (Get-PortProcess $Port)) { return }
        Start-Sleep -Milliseconds 500
    }
    throw "[ERROR] Could not stop previous project $Name :$Port."
}

function Wait-ForUrl([string]$Url, [string]$Name) {
    for ($i = 0; $i -lt 45; $i++) {
        if (Test-PlatformUrl $Url) { return $true }
        Start-Sleep -Seconds 1
    }
    Write-Status "ERROR" "$Name did not become ready within 45 seconds."
    return $false
}

function Start-LocalService([int]$Port, [string]$Url, [string]$Name, [string[]]$Arguments) {
    if (Get-PortProcess $Port) { throw "[ERROR] Port $Port is still occupied; startup stopped to prevent port drift." }
    Start-Process -FilePath $Python -ArgumentList $Arguments -WorkingDirectory $ProjectRoot -WindowStyle Hidden | Out-Null
    if (-not (Wait-ForUrl $Url $Name)) { throw "$Name failed to start." }
    Write-Status "OK" "$Name      $Url"
}

try {
    Write-Host "========================================"
    Write-Host "      AI Health Management Platform"
    Write-Host "========================================"
    if (-not (Test-Path -LiteralPath $ProjectRoot)) { throw "Project directory not found: $ProjectRoot" }
    Set-Location -LiteralPath $ProjectRoot
    Write-Status "OK" "Project directory"
    if (-not (Test-Path -LiteralPath $Python)) { throw "Project Python virtual environment not found: $Python" }
    Write-Status "OK" "Python virtual environment"

    Read-ProjectEnv
    # Restart only listeners whose command line proves they belong to this project.
    Stop-ProjectService 8501 "Streamlit"
    Stop-ProjectService 8000 "FastAPI"

    $ollamaReady = Test-PlatformUrl "http://127.0.0.1:11434/api/tags"
    if (-not $ollamaReady) {
        $ollama = Get-Command ollama -ErrorAction SilentlyContinue
        if ($ollama) {
            Start-Process -FilePath $ollama.Source -ArgumentList "serve" -WindowStyle Hidden | Out-Null
            $ollamaReady = Wait-ForUrl "http://127.0.0.1:11434/api/tags" "Ollama"
        }
    }
    if ($ollamaReady) { Write-Status "OK" "Ollama" } else { Write-Status "WARN" "Ollama unavailable; rule-based parsing remains available." }

    $local_llmReady = $false
    $configuredModel = $env:LOCAL_LLM_MODEL
    if ($ollamaReady -and -not [string]::IsNullOrWhiteSpace($configuredModel)) {
        try {
            $tags = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
            $local_llmReady = $null -ne @($tags.models | Where-Object { $_.name -eq $configuredModel })[0]
        } catch { $local_llmReady = $false }
    }
    if ($local_llmReady) { Write-Status "OK" "local LLM ready" } else { Write-Status "WARN" "local LLM not configured or unavailable; rule-based parsing remains available." }

    & $Python -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { throw "Database upgrade failed." }
    Write-Status "OK" "Database"

    Start-LocalService 8000 "http://127.0.0.1:8000/docs" "FastAPI" @("-m", "uvicorn", "executive_health_ai.api:app", "--app-dir", $SourceRoot, "--host", "127.0.0.1", "--port", "8000")
    Start-LocalService 8501 "http://127.0.0.1:8501" "Streamlit" @("-m", "streamlit", "run", $StreamlitApp, "--server.headless", "true", "--server.address", "127.0.0.1", "--server.port", "8501")

    Write-Host "Opening latest local platform..."
    Start-Process "http://127.0.0.1:8501"
}
catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    Write-Host "Platform did not start. Resolve the error above and try again." -ForegroundColor Red
    exit 1
}
