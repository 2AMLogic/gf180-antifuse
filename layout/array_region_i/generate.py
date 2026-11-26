# /// script
# dependencies = ["klayout==0.30.13"]
# ///
"""Generate the Region I cell matrix."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "array_core"))
from regions import I
from route_matrix import main

if __name__ == "__main__":
    main(I)
