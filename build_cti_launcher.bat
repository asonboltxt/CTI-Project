@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo Create the project environment first by running launch_cti.bat.
    pause
    exit /b 1
)

echo Installing the launcher build tool...
".venv\Scripts\python.exe" -m pip install pyinstaller
if errorlevel 1 (
    echo Failed to install PyInstaller.
    pause
    exit /b 1
)

echo Building CTI_Launcher.exe...
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --console --name CTI_Launcher --distpath . --workpath build\cti_launcher --specpath build cti_launcher.py
if errorlevel 1 (
    echo Launcher build failed.
    pause
    exit /b 1
)

echo Created CTI_Launcher.exe in this folder.
pause