# /// script
# dependencies = ["klayout==0.30.13", "klayout-tools==0.9.2"]
# ///
"""Verify the Region I cell matrix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "array_core"))
from regions import I
from check_matrix import main

if __name__ == "__main__":
    main(I)
