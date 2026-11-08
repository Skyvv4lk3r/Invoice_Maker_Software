"""Run with the project's Python interpreter; no activated shell is required."""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMMANDS = [
    [sys.executable, "-m", "ruff", "check", "."],
    [sys.executable, "-m", "ruff", "format", "--check", "."],
    [
        str(
            Path(sys.executable).parent
            / ("lint-imports.exe" if sys.platform == "win32" else "lint-imports")
        )
    ],
    [sys.executable, "-m", "pytest", "tests/unit", "tests/integration", "tests/architecture"],
]

if __name__ == "__main__":
    for command in COMMANDS:
        print("Running:", " ".join(command), flush=True)
        subprocess.run(command, cwd=ROOT, check=True)
