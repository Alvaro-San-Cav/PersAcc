@echo off
echo ===================================================
echo    Building PersAcc Installer
echo ===================================================
echo.

cd /d "%~dp0.."

REM Set Python paths
set PYTHON_EXE=C:\Proyectos\FIN\.venv\Scripts\python.exe
set PYTHON_BASE=C:\Users\Usuario\AppData\Local\Programs\Python\Python313

if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python not found
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
"%PYTHON_EXE%" -m PyInstaller --onefile --noconsole --clean --name "PersAcc_Installer" --icon="%CD%\assets\logo.ico" --add-data "%CD%\assets;assets" --add-data "%CD%\src;src" --add-data "%CD%\scripts;scripts" --add-data "%CD%\locales;locales" --add-data "%CD%\app.py;." --add-data "%CD%\requirements.txt;." --add-data "%CD%\.streamlit;.streamlit" --add-binary "%PYTHON_BASE%\DLLs\tcl86t.dll;." --add-binary "%PYTHON_BASE%\DLLs\tk86t.dll;." --add-binary "%PYTHON_BASE%\DLLs\_tkinter.pyd;." --add-data "%PYTHON_BASE%\tcl\tcl8.6;tcl\tcl8.6" --add-data "%PYTHON_BASE%\tcl\tk8.6;tcl\tk8.6" --hidden-import "tkinter" --collect-all "tkinter" --distpath "%CD%\installer\dist" --workpath "%CD%\installer\build" --specpath "%CD%\installer" "%CD%\installer\install_wizard.py"

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
copy /Y "installer\TRUSTED_SOFTWARE.txt" "installer\dist\release\"

powershell Compress-Archive -Path "installer\dist\release\*" -DestinationPath "installer\dist\PersAcc_Setup_v3.0.zip" -Force

echo.
echo ===================================================
echo    SUCCESS!
echo    Run: installer\dist\release\PersAcc_Installer.exe
echo ===================================================
pause
