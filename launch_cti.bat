@echo off
setlocal
cd /d "%~dp0"
set "PYTHON_EXE="
set "PYTHON_ARGS="

if not exist ".venv\Scripts\python.exe" (
    where py >nul 2>nul
    if errorlevel 1 (
        where python >nul 2>nul
        if errorlevel 1 (
            where winget >nul 2>nul
            if errorlevel 1 (
                echo Python was not found, and Windows Package Manager is unavailable.
                echo Install Python 3.12 or newer from https://www.python.org/downloads/windows/
                echo Then run this file again.
                pause
                exit /b 1
            )
            echo Python was not found. Installing Python 3.12...
            winget install --id Python.Python.3.12 --exact --scope user --accept-source-agreements --accept-package-agreements
            if errorlevel 1 (
                echo Python installation failed.
                pause
                exit /b 1
            )
            if exist "%LocalAppData%\Programs\Python\Python312\python.exe" (
                set "PYTHON_EXE=%LocalAppData%\Programs\Python\Python312\python.exe"
            )
        )
    )
)

if exist ".venv\Scripts\python.exe" goto install_dependencies

if defined PYTHON_EXE goto create_environment

where py >nul 2>nul
if not errorlevel 1 (
    set "PYTHON_EXE=py"
    set "PYTHON_ARGS=-3"
) else (
    where python >nul 2>nul
    if not errorlevel 1 set "PYTHON_EXE=python"
)

if not defined PYTHON_EXE (
    echo Python was installed but is not available yet.
    echo Close and reopen this file so Windows can refresh the PATH.
    pause
    exit /b 1
)

:create_environment
if defined PYTHON_ARGS (
    echo Creating the CTI Python environment...
) else (
    echo Creating the CTI Python environment...
)
"%PYTHON_EXE%" %PYTHON_ARGS% -m venv .venv
if errorlevel 1 (
    echo Failed to create the Python environment.
    pause
    exit /b 1
)

:install_dependencies
if not exist ".venv\Scripts\python.exe" (
    echo Failed to locate the CTI Python environment.
    pause
    exit /b 1
)

echo Installing or updating CTI dependencies...
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 (
    echo Dependency installation failed. Check your network connection and try again.
    pause
    exit /b 1
)

echo Starting the CTI application...
start "CTI Engine" cmd /k ""%~dp0.venv\Scripts\python.exe" "%~dp0app.py""

timeout /t 3 /nobreak >nul
start "" "http://127.0.0.1:5000"

endlocal
