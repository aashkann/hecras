#!/usr/bin/env python3
"""
Run all tests and report results.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.config import PROJECT_ROOT


def main() -> int:
    print("Running test suite...")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v"],
        cwd=PROJECT_ROOT,
    )
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
