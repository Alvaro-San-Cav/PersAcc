# PersAcc — arranque en producción (single-process).
# Sirve el frontend compilado (frontend/dist) desde el propio backend FastAPI.
#
# Uso:
#   .\run.ps1              # arranca (compila el frontend si falta dist)
#   .\run.ps1 -Port 8001   # puerto alternativo
param(
    [int]$Port = 8001
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$py = Join-Path $root '.venv\Scripts\python.exe'
if (-not (Test-Path $py)) { $py = 'python' }

# Compilar el frontend si no existe el build
$dist = Join-Path $root 'frontend\dist'
if (-not (Test-Path $dist)) {
    Write-Host 'Compilando frontend...' -ForegroundColor Cyan
    Push-Location (Join-Path $root 'frontend')
    pnpm install
    pnpm build
    Pop-Location
}

Write-Host "PersAcc en http://localhost:$Port" -ForegroundColor Green
& $py -m uvicorn server:app --app-dir (Join-Path $root 'backend') --host 127.0.0.1 --port $Port
