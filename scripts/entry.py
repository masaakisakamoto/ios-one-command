#!/usr/bin/env python3
"""Keep invocation independent of the current working directory."""
import sys
from pathlib import Path

if sys.version_info < (3, 9):
    sys.exit("Python 3.9+ is required. / Python 3.9以降が必要です。")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ios_one.cli import main

if __name__ == "__main__":
    sys.exit(main())
