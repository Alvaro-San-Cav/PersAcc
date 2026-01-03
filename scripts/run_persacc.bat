@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0.."

echo ===================================================
echo    Iniciando PersAcc...
echo ===================================================
echo.

echo [INFO] Directorio actual: %CD%
echo [INFO] Activando entorno virtual...

set VENV_PATH=C:\Proyectos\FIN\.venv

if not exist "%VENV_PATH%\Scripts\activate.bat" (
    echo [ERROR] No se encontro el entorno virtual en: %VENV_PATH%
    pause
    exit /b 1
)

call "%VENV_PATH%\Scripts\activate.bat"

echo [INFO] Entorno virtual activado.
echo [INFO] Iniciando servidor...
echo.

:: Ejecutar Streamlit en segundo plano (desde raíz del proyecto)
start /B streamlit run app.py --server.headless true

:: Esperar un momento para que Streamlit inicie
timeout /t 3 /nobreak >nul

echo [INFO] Abriendo aplicacion en Chrome...

:: Abrir Chrome en modo app maximizado y ESPERAR a que se cierre
start /WAIT "" "chrome.exe" --app=http://localhost:8501 --start-maximized --user-data-dir="%TEMP%\PersAccChromeProfile" --lang=es --disable-features=Translate,TranslateUI,OptimizationHints --no-first-run --disable-translate --disable-popup-blocking

:: Cuando Chrome se cierra, matar Streamlit
echo [INFO] Chrome cerrado. Terminando servidor...
taskkill /F /IM streamlit.exe >nul 2>&1
taskkill /F /FI "WINDOWTITLE eq streamlit*" >nul 2>&1

:: Matar proceso python que está corriendo app.py especificamente
wmic process where "name='python.exe' and commandline like '%%app.py%%'" call terminate >nul 2>&1

exit
