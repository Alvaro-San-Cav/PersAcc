# PersAcc — arranque en DESARROLLO (backend + frontend con hot-reload).
# Lanza uvicorn (:8001, --reload) y Vite (:5174, HMR) en paralelo.
#
# Uso:
#   .\dev.ps1                       # arranca ambos
#   .\dev.ps1 -ApiPort 8001 -WebPort 5174
#
# Ctrl+C corta ambos.
param(
    [int]$ApiPort = 8001,
    [int]$WebPort = 5174
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$backend = Start-Process -PassThru -NoNewWindow $py `
    -ArgumentList '-m', 'uvicorn', 'server:app', '--app-dir', (Join-Path $root 'backend'),
        '--host', '127.0.0.1', '--port', $ApiPort, '--reload'

$frontend = Start-Process -PassThru -NoNewWindow 'pnpm' `
    -WorkingDirectory (Join-Path $root 'frontend') `
    -ArgumentList 'dev', '--port', $WebPort

Write-Host "Backend  http://127.0.0.1:$ApiPort" -ForegroundColor Green
Write-Host "Frontend http://localhost:$WebPort"  -ForegroundColor Green
Write-Host 'Ctrl+C para parar ambos.' -ForegroundColor Yellow

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id, $frontend.Id -Force -ErrorAction SilentlyContinue
}
