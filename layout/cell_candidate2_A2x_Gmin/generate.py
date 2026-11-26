#!/usr/bin/env python3
"""Build the C2 A2x_Gmin cell with 8 µm per LDNMOS finger and a 1 µm capacitor."""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from candidate2_points import main

if __name__ == "__main__":
    main(str(HERE), "A2x_Gmin")
