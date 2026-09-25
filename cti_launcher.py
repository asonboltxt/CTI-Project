from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import webbrowser
from pathlib import Path


APP_URL = "http://127.0.0.1:5000"


def project_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent


def fail(message: str) -> int:
    print(message)
    input("Press Enter to close...")
    return 1


def find_python(root: Path) -> tuple[str, list[str]] | None:
    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if venv_python.exists():
        return str(venv_python), []

    py_launcher = shutil.which("py")
    if py_launcher:
        return py_launcher, ["-3"]

    python = shutil.which("python")
    if python:
        return python, []

    winget = shutil.which("winget")
    if not winget:
        return None

    print("Python was not found. Installing Python 3.12...")
    result = subprocess.run(
        [
            winget,
            "install",
            "--id",
            "Python.Python.3.12",
            "--exact",
            "--scope",
            "user",
            "--accept-source-agreements",
            "--accept-package-agreements",
        ],
        cwd=root,
    )
    if result.returncode:
        return None

    installed = Path(os.environ.get("LocalAppData", "")) / "Programs" / "Python" / "Python312" / "python.exe"
    if installed.exists():
        return str(installed), []
    return find_python(root)


def run(python: str, args: list[str], root: Path) -> bool:
    result = subprocess.run([python, *args], cwd=root)
    return result.returncode == 0


def main() -> int:
    root = project_dir()
    requirements = root / "requirements.txt"
    app = root / "app.py"
    if not requirements.exists() or not app.exists():
        return fail(f"CTI files were not found beside this launcher: {root}")

    python_info = find_python(root)
    if python_info is None:
        return fail(
            "Python was not found, and Windows Package Manager is unavailable.\n"
            "Install Python 3.12 or newer, then run CTI_Launcher.exe again."
        )
    python, python_args = python_info

    venv_python = root / ".venv" / "Scripts" / "python.exe"
    if not venv_python.exists():
        print("Creating the CTI Python environment...")
        if not run(python, [*python_args, "-m", "venv", ".venv"], root):
            return fail("Failed to create the Python environment.")

    print("Installing or updating CTI dependencies...")
    if not run(str(venv_python), ["-m", "pip", "install", "-r", str(requirements)], root):
        return fail("Dependency installation failed. Check your network connection and try again.")

    print("Starting the CTI application...")
    creation_flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(
        [str(venv_python), str(app)],
        cwd=root,
        creationflags=creation_flags,
    )
    time.sleep(3)
    webbrowser.open(APP_URL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())