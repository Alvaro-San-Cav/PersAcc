# PersAcc — mata TODO (zombies incluidos) y relanza backend + frontend limpio.
#
# Uso:
#   .\restart.ps1                          # mata puertos 8001/5174 y arranca dev
#   .\restart.ps1 -ApiPort 8001 -WebPort 5174
#   .\restart.ps1 -KillOnly                # solo mata, no arranca
#
# En dev NO hace falta "rebuild": Vite HMR + uvicorn --reload aplican los cambios
# en caliente. Este script existe para el otro problema: servers colgados de
# sesiones anteriores que bloquean los puertos.
param(
    [int]$ApiPort = 8001,
    [int]$WebPort = 5174,
    [switch]$KillOnly
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot

function Kill-Port([int]$port) {
    $pids = @()
    try {
        $pids = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop |
            Select-Object -ExpandProperty OwningProcess -Unique
    } catch { }
    foreach ($procId in $pids) {
        if ($procId -and $procId -ne 0) {
            $name = (Get-Process -Id $procId -ErrorAction SilentlyContinue).ProcessName
            Write-Host "  matando :$port -> PID $procId ($name)" -ForegroundColor DarkYellow
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host 'Matando servers en puertos objetivo...' -ForegroundColor Cyan
# Incluye 5175 (instancia preview) por si quedo viva.
foreach ($p in @($ApiPort, $WebPort, 5175)) { Kill-Port $p }
Start-Sleep -Milliseconds 400

if ($KillOnly) {
    Write-Host 'Listo (solo kill).' -ForegroundColor Green
    return
}

$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

$backend = Start-Process -PassThru -NoNewWindow $py `
    -ArgumentList '-m', 'uvicorn', 'server:app', '--app-dir', (Join-Path $root 'backend'),
        '--host', '127.0.0.1', '--port', $ApiPort, '--reload'

# pnpm es un shim .cmd (no .exe) -> Start-Process no lo lanza directo.
# Se ejecuta vía cmd.exe para que resuelva el shim.
$frontend = Start-Process -PassThru -NoNewWindow 'cmd.exe' `
    -WorkingDirectory (Join-Path $root 'frontend') `
    -ArgumentList '/c', 'pnpm', 'dev', '--port', $WebPort, '--strictPort'

Write-Host ''
Write-Host "Backend  http://127.0.0.1:$ApiPort" -ForegroundColor Green
Write-Host "Frontend http://localhost:$WebPort"  -ForegroundColor Green
Write-Host 'Ctrl+C para parar ambos.' -ForegroundColor Yellow

try {
    Wait-Process -Id $backend.Id, $frontend.Id
} finally {
    Stop-Process -Id $backend.Id, $frontend.Id -Force -ErrorAction SilentlyContinue
}
