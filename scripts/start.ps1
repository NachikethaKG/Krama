# Start the whole Krama stack on this laptop, in real mode (the UI talks to the real API).
#
#   start-krama.bat              (from the repo root, in any terminal or by double-click)
#   start-krama.bat -NoBrowser   (don't open the browser)
#
# 1. Docker Desktop (started if it isn't running) with Postgres, Redis and Gitea
# 2. Database migrations
# 3. API on http://localhost:8000 in its own window
# 4. Web app on http://localhost:3000 in its own window (NEXT_PUBLIC_API_MODE=http)
# 5. Waits until both answer, then opens http://localhost:3000/login
#
# Stop everything with stop-krama.bat. Sign in as demo@krama.dev with KRAMA_DEMO_PASSWORD from .env.
param([switch]$NoBrowser)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "data\.krama-pids"
Set-Location $root

function Step($text) { Write-Host "`n==> $text" -ForegroundColor Cyan }
function Fail($text) { Write-Host "`nERROR: $text" -ForegroundColor Red; exit 1 }

function Test-Listening($port) {
    return [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
}

function Wait-Http($url, $seconds) {
    $deadline = (Get-Date).AddSeconds($seconds)
    while ((Get-Date) -lt $deadline) {
        try {
            $r = Invoke-WebRequest -UseBasicParsing -Uri $url -TimeoutSec 10
            if ($r.StatusCode -lt 500) { return $true }
        } catch { }
        Start-Sleep -Seconds 2
    }
    return $false
}

if (-not (Test-Path ".env")) { Fail "No .env in $root. Copy .env.example to .env and fill it in first." }
foreach ($tool in "docker", "uv", "pnpm") {
    if (-not (Get-Command $tool -ErrorAction SilentlyContinue)) { Fail "'$tool' is not installed or not on PATH." }
}

# 1. Docker
Step "Docker"
docker info *> $null
if ($LASTEXITCODE -ne 0) {
    $desktop = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $desktop)) { Fail "Docker isn't running. Start Docker Desktop, then run start-krama.bat again." }
    Write-Host "Starting Docker Desktop (this can take a minute)..."
    Start-Process $desktop
    $deadline = (Get-Date).AddSeconds(180)
    do {
        Start-Sleep -Seconds 3
        docker info *> $null
    } while ($LASTEXITCODE -ne 0 -and (Get-Date) -lt $deadline)
    if ($LASTEXITCODE -ne 0) { Fail "Docker didn't start within 3 minutes." }
}
Write-Host "Starting Postgres, Redis and Gitea..."
docker compose --env-file .env -f infra/docker-compose.yml up -d --wait
if ($LASTEXITCODE -ne 0) { Fail "docker compose up failed (see above)." }

# 2. Migrations
Step "Database migrations"
Push-Location backend
uv run alembic upgrade head
$code = $LASTEXITCODE
Pop-Location
if ($code -ne 0) { Fail "alembic upgrade failed (see above)." }

# 3 + 4. Servers, each in its own window so their logs stay readable
$pids = @()
Step "API on http://localhost:8000"
if (Test-Listening 8000) {
    Write-Host "Something already listens on :8000; leaving it running (run stop-krama.bat first for a fresh start)."
} else {
    $api = "`$host.UI.RawUI.WindowTitle = 'Krama API :8000'; Set-Location '$root\backend'; " +
        "uv run uvicorn app.main:app --loop app.dev_loop:factory --host 127.0.0.1 --port 8000"
    $pids += (Start-Process powershell -ArgumentList "-NoExit", "-Command", $api -PassThru).Id
}

Step "Web app on http://localhost:3000"
if (Test-Listening 3000) {
    Write-Host "Something already listens on :3000; leaving it running (run stop-krama.bat first for a fresh start)."
} else {
    $web = "`$host.UI.RawUI.WindowTitle = 'Krama web :3000'; " +
        "`$env:NEXT_PUBLIC_API_MODE = 'http'; `$env:NEXT_PUBLIC_API_URL = 'http://localhost:8000/api/v1'; " +
        "Set-Location '$root\frontend'; pnpm dev --port 3000"
    $pids += (Start-Process powershell -ArgumentList "-NoExit", "-Command", $web -PassThru).Id
}
if ($pids.Count -gt 0) {
    New-Item -ItemType Directory -Force (Split-Path $pidFile) | Out-Null
    Add-Content -Path $pidFile -Value $pids -Encoding ascii
}

# 5. Wait until both answer
Step "Waiting for the servers"
if (-not (Wait-Http "http://127.0.0.1:8000/api/v1/health" 120)) { Fail "The API didn't answer in 2 minutes: check the 'Krama API' window." }
Write-Host "API is up."
if (-not (Wait-Http "http://127.0.0.1:3000/login" 240)) { Fail "The web app didn't answer in 4 minutes: check the 'Krama web' window." }
Write-Host "Web app is up."

Write-Host ""
Write-Host "Krama is running." -ForegroundColor Green
Write-Host "  Web app : http://localhost:3000   (sign in: demo@krama.dev / KRAMA_DEMO_PASSWORD from .env)"
Write-Host "  API     : http://localhost:8000/api/v1/health"
Write-Host "  Gitea   : http://localhost:3001"
Write-Host "  Stop    : stop-krama.bat"
if (-not $NoBrowser) { Start-Process "http://localhost:3000/login" }
