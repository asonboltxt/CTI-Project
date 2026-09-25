"""
CTI Launcher
============

Standalone bootstrapper for the CTI application. Reproduces the logic of the
original CTI launcher batch file:

  1. Locate a usable Python interpreter (.venv -> py -3 -> python -> winget install).
  2. Create the .venv virtual environment if it does not exist.
  3. Install/update dependencies from requirements.txt.
  4. Start app.py in its own console window.
  5. Wait briefly, then open http://127.0.0.1:5000 in the default browser.

Build into a single executable with:

    pip install pyinstaller
    pyinstaller --onefile --console --name CTI_Launcher --icon=cti.ico launcher.py

The resulting CTI_Launcher.exe must sit in the same folder as app.py and
requirements.txt (the same place the .bat file lived).
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #

APP_ENTRY = "app.py"
REQUIREMENTS = "requirements.txt"
VENV_DIR = ".venv"
APP_URL = "http://127.0.0.1:5000"
STARTUP_DELAY_SECONDS = 3
WINGET_PACKAGE_ID = "Python.Python.3.12"
PYTHON_DOWNLOAD_URL = "https://www.python.org/downloads/windows/"

# Windows flag: launch the child process in a brand-new console window,
# mirroring `start "CTI Engine" cmd /k ...` from the batch file.
CREATE_NEW_CONSOLE = 0x00000010


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def app_root() -> str:
    """Folder containing the launcher (works both frozen and as a .py script)."""
    if getattr(sys, "frozen", False):
        # PyInstaller one-file: sys.executable is the .exe the user double-clicked.
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def log(message: str) -> None:
    print(message, flush=True)


def fail(message: str, code: int = 1) -> "NoReturn":  # type: ignore[valid-type]
    """Print an error, keep the window open, and exit."""
    log("")
    log(f"ERROR: {message}")
    log("")
    try:
        input("Press Enter to close this window...")
    except EOFError:
        pass
    sys.exit(code)


def venv_python(root: str) -> str:
    """Path to the interpreter inside the project virtual environment."""
    if os.name == "nt":
        return os.path.join(root, VENV_DIR, "Scripts", "python.exe")
    return os.path.join(root, VENV_DIR, "bin", "python")


def run(command: list[str], cwd: str) -> int:
    """Run a command, streaming its output to this console."""
    try:
        return subprocess.call(command, cwd=cwd)
    except FileNotFoundError:
        return 1
    except OSError:
        return 1


# --------------------------------------------------------------------------- #
# Step 1 - find a Python interpreter capable of creating the venv
# --------------------------------------------------------------------------- #

def find_system_python() -> list[str] | None:
    """Return the command used to invoke a system Python, or None."""
    # Prefer the Windows launcher pinned to Python 3.
    launcher = shutil.which("py")
    if launcher:
        return [launcher, "-3"]

    interpreter = shutil.which("python")
    if interpreter:
        return [interpreter]

    # Common per-user winget/Store install locations (PATH may not be refreshed yet).
    local_appdata = os.environ.get("LocalAppData", "")
    if local_appdata:
        for version in ("Python313", "Python312", "Python311"):
            candidate = os.path.join(
                local_appdata, "Programs", "Python", version, "python.exe"
            )
            if os.path.exists(candidate):
                return [candidate]

    return None


def install_python_with_winget() -> bool:
    """Attempt an unattended, user-scope Python install via winget."""
    winget = shutil.which("winget")
    if not winget:
        log("Python was not found, and Windows Package Manager is unavailable.")
        log(f"Install Python 3.12 or newer from {PYTHON_DOWNLOAD_URL}")
        log("Then run this launcher again.")
        return False

    log("Python was not found. Installing Python 3.12...")
    exit_code = subprocess.call(
        [
            winget,
            "install",
            "--id",
            WINGET_PACKAGE_ID,
            "--exact",
            "--scope",
            "user",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ]
    )
    if exit_code != 0:
        log("Python installation failed.")
        return False

    return True


def resolve_python(root: str) -> list[str]:
    """Return the command for a Python that can build the virtual environment."""
    command = find_system_python()
    if command:
        return command

    if not install_python_with_winget():
        fail("Unable to install Python automatically.")

    # Re-probe after the install; winget writes to a per-user location.
    command = find_system_python()
    if command:
        return command

    fail(
        "Python was installed but is not available yet.\n"
        "Close and reopen this launcher so Windows can refresh the PATH."
    )


# --------------------------------------------------------------------------- #
# Step 2 - create the virtual environment
# --------------------------------------------------------------------------- #

def ensure_virtualenv(root: str) -> str:
    python_in_venv = venv_python(root)
    if os.path.exists(python_in_venv):
        return python_in_venv

    base_python = resolve_python(root)

    log("Creating the CTI Python environment...")
    if run(base_python + ["-m", "venv", VENV_DIR], cwd=root) != 0:
        fail("Failed to create the Python environment.")

    if not os.path.exists(python_in_venv):
        fail("Failed to locate the CTI Python environment.")

    return python_in_venv


# --------------------------------------------------------------------------- #
# Step 3 - install dependencies
# --------------------------------------------------------------------------- #

def install_dependencies(root: str, python_in_venv: str) -> None:
    requirements_path = os.path.join(root, REQUIREMENTS)
    if not os.path.exists(requirements_path):
        fail(f"{REQUIREMENTS} was not found next to this launcher.\nLooked in: {root}")

    log("Installing or updating CTI dependencies...")
    exit_code = run(
        [python_in_venv, "-m", "pip", "install", "-r", requirements_path],
        cwd=root,
    )
    if exit_code != 0:
        fail(
            "Dependency installation failed.\n"
            "Check your network connection or proxy settings and try again."
        )


# --------------------------------------------------------------------------- #
# Step 4 - start the application
# --------------------------------------------------------------------------- #

def start_application(root: str, python_in_venv: str) -> subprocess.Popen:
    app_path = os.path.join(root, APP_ENTRY)
    if not os.path.exists(app_path):
        fail(f"{APP_ENTRY} was not found next to this launcher.\nLooked in: {root}")

    log("Starting the CTI application...")

    kwargs: dict = {"cwd": root}
    if os.name == "nt":
        # Give the Flask server its own window so its log output stays visible
        # and closing the launcher does not kill it mid-request.
        kwargs["creationflags"] = CREATE_NEW_CONSOLE

    try:
        return subprocess.Popen([python_in_venv, app_path], **kwargs)
    except OSError as error:
        fail(f"Failed to start {APP_ENTRY}: {error}")


# --------------------------------------------------------------------------- #
# Step 5 - open the browser
# --------------------------------------------------------------------------- #

def open_browser(process: subprocess.Popen) -> None:
    for _ in range(STARTUP_DELAY_SECONDS):
        time.sleep(1)
        if process.poll() is not None:
            fail(
                "The CTI application stopped before it finished starting.\n"
                "Review the CTI Engine window for the underlying error."
            )

    log(f"Opening {APP_URL} ...")
    webbrowser.open(APP_URL)


# --------------------------------------------------------------------------- #
# Entry point
# --------------------------------------------------------------------------- #

def main() -> int:
    root = app_root()
    os.chdir(root)

    log("=" * 58)
    log("  CTI Launcher")
    log("=" * 58)
    log(f"Working folder: {root}")
    log("")

    python_in_venv = ensure_virtualenv(root)
    install_dependencies(root, python_in_venv)
    process = start_application(root, python_in_venv)
    open_browser(process)

    log("")
    log("CTI is running. Leave the 'CTI Engine' window open while you work.")
    log("Close that window to stop the application.")
    log("")
    try:
        input("Press Enter to close this launcher window...")
    except EOFError:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
