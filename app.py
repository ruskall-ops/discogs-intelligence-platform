"""Compatibility launcher for existing desktop shortcuts."""

from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from dip.app import main


if __name__ == "__main__":
    main()
