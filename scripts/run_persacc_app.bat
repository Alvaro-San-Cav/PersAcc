@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0.."
set "ROOT=%CD%"

set "PY=%ROOT%\.venv\Scripts\python.exe"
if not exist "%PY%" set "PY=python"

set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME%" set "CHROME=chrome.exe"

rem Compilar el frontend si falta el build
if not exist "%ROOT%\frontend\dist\index.html" (
    pushd "%ROOT%\frontend"
    call pnpm install
    call pnpm build
    popd
)

rem Arrancar el backend (sirve frontend/dist) en segundo plano
start "PersAccBackend" /B "%PY%" -m uvicorn server:app --app-dir "%ROOT%\backend" --host 127.0.0.1 --port 8001

rem Esperar a que el backend acepte conexiones (max ~30s)
set /a tries=0
:waitloop
timeout /t 1 /nobreak >nul
powershell -NoProfile -Command "try{(New-Object Net.Sockets.TcpClient).Connect('127.0.0.1',8001);exit 0}catch{exit 1}" >nul 2>&1
if not errorlevel 1 goto ready
set /a tries+=1
if %tries% lss 30 goto waitloop
:ready

rem Abrir Chrome en modo app y esperar a que se cierre
start /WAIT "" "%CHROME%" --app=http://localhost:8001 --start-maximized --user-data-dir="%TEMP%\PersAccChromeProfile" --no-first-run --disable-popup-blocking --disable-features=Translate,TranslateUI

rem Al cerrar Chrome, terminar el backend
wmic process where "name='python.exe' and commandline like '%%server:app%%'" call terminate >nul 2>&1
exit
