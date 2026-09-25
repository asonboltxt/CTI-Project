"""
Start CTI (no-build fallback)
=============================

Double-click this file to start CTI on any machine that already has Python
installed. Use this if you cannot build CTI_Launcher.exe.

.pyw files open with pythonw.exe, so no console window appears. All status
messages are shown in small dialog boxes instead.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import time
import tkinter as tk
import webbrowser
from tkinter import messagebox

APP_ENTRY = "app.py"
REQUIREMENTS = "requirements.txt"
VENV_DIR = ".venv"
APP_URL = "http://127.0.0.1:5000"
CREATE_NO_WINDOW = 0x08000000

ROOT = os.path.dirname(os.path.abspath(__file__))


class Splash:
    """Tiny always-on-top status window shown while CTI starts."""

    def __init__(self) -> None:
        self.window = tk.Tk()
        self.window.title("CTI")
        self.window.geometry("380x110")
        self.window.resizable(False, False)
        self.window.attributes("-topmost", True)
        tk.Label(
            self.window, text="CTI", font=("Segoe UI", 14, "bold")
        ).pack(pady=(16, 2))
        self.status = tk.Label(
            self.window, text="Starting...", font=("Segoe UI", 9), fg="#444444"
        )
        self.status.pack()

    def set(self, text: str) -> None:
        self.status.config(text=text)
        self.window.update_idletasks()
        self.window.update()

    def close(self) -> None:
        try:
            self.window.destroy()
        except tk.TclError:
            pass


def fail(splash: Splash, message: str) -> None:
    splash.close()
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    messagebox.showerror("CTI could not start", message)
    root.destroy()
    sys.exit(1)


def venv_python() -> str:
    if os.name == "nt":
        return os.path.join(ROOT, VENV_DIR, "Scripts", "pythonw.exe")
    return os.path.join(ROOT, VENV_DIR, "bin", "python")


def venv_python_console() -> str:
    if os.name == "nt":
        return os.path.join(ROOT, VENV_DIR, "Scripts", "python.exe")
    return os.path.join(ROOT, VENV_DIR, "bin", "python")


def quiet_run(command: list[str]) -> int:
    kwargs: dict = {"cwd": ROOT}
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
    try:
        return subprocess.call(command, **kwargs)
    except OSError:
        return 1


def main() -> None:
    os.chdir(ROOT)
    splash = Splash()

    if not os.path.exists(os.path.join(ROOT, APP_ENTRY)):
        fail(splash, f"{APP_ENTRY} was not found in:\n{ROOT}")

    # 1. Virtual environment
    if not os.path.exists(venv_python_console()):
        splash.set("Creating the Python environment...")
        base = shutil.which("py") or shutil.which("python") or sys.executable
        args = [base, "-3"] if os.path.basename(base).lower().startswith("py.") else [base]
        if quiet_run(args + ["-m", "venv", VENV_DIR]) != 0:
            fail(
                splash,
                "Failed to create the Python environment.\n\n"
                "Install Python 3.12 or newer from python.org and try again.",
            )

    # 2. Dependencies
    if os.path.exists(os.path.join(ROOT, REQUIREMENTS)):
        splash.set("Installing dependencies (this may take a minute)...")
        if quiet_run(
            [venv_python_console(), "-m", "pip", "install", "-r", REQUIREMENTS]
        ) != 0:
            fail(
                splash,
                "Dependency installation failed.\n\n"
                "Check your network connection or proxy settings and try again.",
            )

    # 3. Start the server, hidden
    splash.set("Starting the CTI application...")
    kwargs: dict = {"cwd": ROOT}
    if os.name == "nt":
        kwargs["creationflags"] = CREATE_NO_WINDOW
    try:
        process = subprocess.Popen([venv_python(), APP_ENTRY], **kwargs)
    except OSError as error:
        fail(splash, f"Failed to start {APP_ENTRY}:\n{error}")

    # 4. Wait, verify it survived, open the browser
    for _ in range(3):
        time.sleep(1)
        splash.set("Starting the CTI application...")
        if process.poll() is not None:
            fail(
                splash,
                "The CTI application stopped while starting.\n\n"
                "Run CTI_Launcher.exe instead to see the detailed error message.",
            )

    splash.set("Opening your browser...")
    webbrowser.open(APP_URL)
    time.sleep(1)
    splash.close()


if __name__ == "__main__":
    main()
