"""Make scripts/ importable from the tests (the scripts are not a package)."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "scripts"), str(ROOT / "scripts" / "planka")]
