#!/usr/bin/env python3
"""Launcher: run scripts/clip_for_hecras.py (modular entry point)."""
import runpy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Run the script in scripts/ as __main__
script = ROOT / "scripts" / "clip_for_hecras.py"
runpy.run_path(str(script), run_name="__main__")
