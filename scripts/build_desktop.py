"""Build on Windows; package resources used by Qt, Alembic and document renderers."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

if __name__ == "__main__":
    subprocess.run(
        [
            sys.executable,
            "-m",
            "PyInstaller",
            "--noconfirm",
            "--clean",
            "--onedir",
            "--windowed",
            "--name",
            "InvoiceGenerator",
            "--collect-all",
            "invoice_generator",
            "--collect-all",
            "alembic",
            "--collect-data",
            "reportlab",
            str(ROOT / "scripts" / "desktop_entry.py"),
        ],
        cwd=ROOT,
        check=True,
    )
