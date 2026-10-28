# Stop what start-krama.bat started: the API and web app windows, then the Docker services (their data is kept).
#
#   stop-krama.bat            (stop everything)
#   stop-krama.bat -KeepDocker (stop only the API and web app)
param([switch]$KeepDocker)

$root = Split-Path -Parent $PSScriptRoot
$pidFile = Join-Path $root "data\.krama-pids"
Set-Location $root

# The windows start-krama.bat opened (taskkill /T also ends uvicorn / next under them)
if (Test-Path $pidFile) {
    foreach ($id in Get-Content $pidFile) {
        if ($id) { taskkill /T /F /PID $id *> $null }
    }
    Remove-Item $pidFile
}
# Anything still listening on the app ports (e.g. started by hand)
foreach ($port in 8000, 3000) {
    foreach ($c in Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) {
        taskkill /T /F /PID $c.OwningProcess *> $null
    }
    $still = [bool](Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)
    Write-Host ("Port {0}: {1}" -f $port, $(if ($still) { "STILL IN USE" } else { "stopped" }))
}

if (-not $KeepDocker) {
    docker info *> $null
    if ($LASTEXITCODE -eq 0) {
        docker compose --env-file .env -f infra/docker-compose.yml stop
        Write-Host "Docker services stopped (data kept)."
    } else {
        Write-Host "Docker isn't running; nothing to stop there."
    }
}
Write-Host "Krama is stopped." -ForegroundColor Green
