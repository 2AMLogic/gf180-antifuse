#!/usr/bin/env python3
"""Regenerate the cell_candidate3_A2x_G2x signed PMOS bitcell."""
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from candidate3_points import main

if __name__ == "__main__":
    main(str(HERE), "A2x_G2x")
