"""
Build CTI_Launcher.exe
======================

Run this ONCE on a Windows machine that already has Python installed:

    python build_launcher.py

It will:
  1. Install PyInstaller into an isolated build environment (.buildenv).
  2. Compile launcher.py into a single-file CTI_Launcher.exe.
  3. Copy CTI_Launcher.exe next to app.py so it is ready to double-click.
  4. Clean up the build scratch folders.

After this, CTI_Launcher.exe is the ONLY file users need to double-click.
They do not need Python installed -- the launcher installs it for them.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BUILD_ENV = os.path.join(ROOT, ".buildenv")
SOURCE = os.path.join(ROOT, "launcher.py")
EXE_NAME = "CTI_Launcher"
ICON = os.path.join(ROOT, "cti.ico")  # optional


def build_python() -> str:
    if os.name == "nt":
        return os.path.join(BUILD_ENV, "Scripts", "python.exe")
    return os.path.join(BUILD_ENV, "bin", "python")


def step(message: str) -> None:
    print(f"\n==> {message}", flush=True)


def check(exit_code: int, message: str) -> None:
    if exit_code != 0:
        print(f"\nERROR: {message}")
        input("Press Enter to close...")
        sys.exit(1)


def main() -> int:
    if not os.path.exists(SOURCE):
        print("ERROR: launcher.py was not found next to build_launcher.py.")
        input("Press Enter to close...")
        return 1

    step("Creating the build environment...")
    if not os.path.exists(build_python()):
        check(
            subprocess.call([sys.executable, "-m", "venv", BUILD_ENV]),
            "Could not create the build environment.",
        )

    step("Installing PyInstaller...")
    check(
        subprocess.call(
            [build_python(), "-m", "pip", "install", "--upgrade", "pip", "pyinstaller"]
        ),
        "Could not install PyInstaller. Check your network or proxy settings.",
    )

    step(f"Compiling {EXE_NAME}.exe ...")
    command = [
        build_python(),
        "-m",
        "PyInstaller",
        "--onefile",
        "--console",
        "--clean",
        "--noconfirm",
        "--name",
        EXE_NAME,
        "--distpath",
        os.path.join(ROOT, "dist"),
        "--workpath",
        os.path.join(ROOT, "build"),
        "--specpath",
        os.path.join(ROOT, "build"),
    ]
    if os.path.exists(ICON):
        command += ["--icon", ICON]
    command.append(SOURCE)

    check(subprocess.call(command, cwd=ROOT), "PyInstaller failed to build the launcher.")

    produced = os.path.join(ROOT, "dist", f"{EXE_NAME}.exe")
    if not os.path.exists(produced):
        print("ERROR: The build finished but the executable was not produced.")
        input("Press Enter to close...")
        return 1

    step("Placing the launcher next to app.py ...")
    final = os.path.join(ROOT, f"{EXE_NAME}.exe")
    shutil.copy2(produced, final)

    step("Cleaning up build files...")
    for folder in ("build", "dist"):
        shutil.rmtree(os.path.join(ROOT, folder), ignore_errors=True)

    print("\n" + "=" * 58)
    print("  Done.")
    print(f"  Double-click: {final}")
    print("=" * 58 + "\n")
    input("Press Enter to close...")
    return 0


if __name__ == "__main__":
    sys.exit(main())
