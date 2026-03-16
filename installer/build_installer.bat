@echo off
echo ===================================================
echo    Building PersAcc Installer
echo ===================================================
echo.

cd /d "%~dp0.."

REM Set Python paths
set PYTHON_EXE=C:\Proyectos\FIN\.venv\Scripts\python.exe

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found
    pause
    exit /b 1
)

set PYBASE_FILE=%TEMP%\persacc_python_base.txt
if exist "%PYBASE_FILE%" del /q "%PYBASE_FILE%"
"%PYTHON_EXE%" -c "import sys; print(sys.base_prefix)" > "%PYBASE_FILE%"
set /p PYTHON_BASE=<"%PYBASE_FILE%"
if exist "%PYBASE_FILE%" del /q "%PYBASE_FILE%"
if not exist "%PYTHON_BASE%" (
    echo [ERROR] Python base path not found: %PYTHON_BASE%
    pause
    exit /b 1
)

set TCL_DLL=
for %%F in ("%PYTHON_BASE%\DLLs\tcl*.dll") do if not defined TCL_DLL set TCL_DLL=%%~fF
set TK_DLL=
for %%F in ("%PYTHON_BASE%\DLLs\tk*.dll") do if not defined TK_DLL set TK_DLL=%%~fF
set TKINTER_PYD=
for %%F in ("%PYTHON_BASE%\DLLs\_tkinter*.pyd") do if not defined TKINTER_PYD set TKINTER_PYD=%%~fF

set TCL_DIR=
for /d %%D in ("%PYTHON_BASE%\tcl\tcl*") do if not defined TCL_DIR set TCL_DIR=%%~fD
set TK_DIR=
for /d %%D in ("%PYTHON_BASE%\tcl\tk*") do if not defined TK_DIR set TK_DIR=%%~fD

if not exist "%TCL_DLL%" (
    echo [ERROR] Tcl DLL not found
    pause
    exit /b 1
)
if not exist "%TK_DLL%" (
    echo [ERROR] Tk DLL not found
    pause
    exit /b 1
)
if not exist "%TKINTER_PYD%" (
    echo [ERROR] _tkinter.pyd not found
    pause
    exit /b 1
)
if not exist "%TCL_DIR%" (
    echo [ERROR] Tcl runtime dir not found
    pause
    exit /b 1
)
if not exist "%TK_DIR%" (
    echo [ERROR] Tk runtime dir not found
    pause
    exit /b 1
)

echo [1/4] Cleaning previous builds...
if exist "installer\dist" rmdir /s /q "installer\dist"
if exist "installer\build" rmdir /s /q "installer\build"
if exist "installer\*.spec" del /q "installer\*.spec"

echo [2/4] Installing PyInstaller...
"%PYTHON_EXE%" -m pip install --quiet pyinstaller

echo [3/4] Building executable...
"%PYTHON_EXE%" -m PyInstaller --onefile --noconsole --clean --name "PersAcc_Installer" --icon="%CD%\assets\logo.ico" --add-data "%CD%\assets;assets" --add-data "%CD%\src;src" --add-data "%CD%\scripts;scripts" --add-data "%CD%\locales;locales" --add-data "%CD%\app.py;." --add-data "%CD%\requirements.txt;." --add-data "%CD%\.streamlit;.streamlit" --add-binary "%TCL_DLL%;." --add-binary "%TK_DLL%;." --add-binary "%TKINTER_PYD%;." --add-data "%TCL_DIR%;tcl\tcl8.6" --add-data "%TK_DIR%;tcl\tk8.6" --hidden-import "tkinter" --collect-all "tkinter" --distpath "%CD%\installer\dist" --workpath "%CD%\installer\build" --specpath "%CD%\installer" "%CD%\installer\install_wizard.py"

if not exist "installer\dist\PersAcc_Installer.exe" (
    echo [ERROR] Build failed!
    pause
    exit /b 1
)

echo.
echo [4/4] Packaging release...
if exist "installer\dist\release" rmdir /s /q "installer\dist\release"
mkdir "installer\dist\release"

copy /Y "installer\dist\PersAcc_Installer.exe" "installer\dist\release\"
copy /Y "installer\README_INSTALLER.md" "installer\dist\release\README.md"
copy /Y "installer\TRUSTED_SOFTWARE_WARNING.txt" "installer\dist\release\"

powershell Compress-Archive -Path "installer\dist\release\*" -DestinationPath "installer\dist\PersAcc_Setup_v3.0.zip" -Force

echo.
echo ===================================================
echo    SUCCESS!
echo    Run: installer\dist\release\PersAcc_Installer.exe
echo ===================================================
pause
