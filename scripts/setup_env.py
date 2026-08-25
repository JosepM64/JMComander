#!/usr/bin/env python3
import os
import platform
import subprocess
import sys


def run(cmd, shell=False):
    print("+" + (" ".join(cmd) if isinstance(cmd, list) else cmd))
    subprocess.check_call(cmd, shell=shell)


def main():
    venv_dir = os.path.join(os.getcwd(), "venv")

    if not os.path.isdir(venv_dir):
        pyexe = sys.executable
        print("Creant entorn virtual en:", venv_dir)
        run([pyexe, "-m", "venv", "venv"])

    if platform.system() == "Windows":
        py = os.path.join(venv_dir, "Scripts", "python.exe")
        pip = os.path.join(venv_dir, "Scripts", "pip.exe")
    else:
        py = os.path.join(venv_dir, "bin", "python")
        pip = os.path.join(venv_dir, "bin", "pip")

    run([py, "-m", "pip", "install", "--upgrade", "pip"])
    run([pip, "install", "-r", "requirements.txt"])
    print("Entorn preparat. Per executar, activa'l i executa 'python -m src.app'")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as e:
        print("Error during setup_env:", e)
        sys.exit(1)
