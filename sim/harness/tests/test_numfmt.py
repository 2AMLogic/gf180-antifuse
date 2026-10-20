"""Targeted tests for sim/harness/numfmt.py.  Expected strings are copied from
committed records / generated netlists so the shared formatters stay
byte-identical to what the per-experiment copies rendered.  Run:

    python3 -m unittest discover -s sim/harness/tests
"""

import math
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(HERE.parent.parent))
from harness import numfmt as N  # noqa: E402


class SpiceNum(unittest.TestCase):
    def test_suffixes(self):
        for tok, want in (("0.30u", 0.30e-6), ("1e-6", 1e-6), ("5meg", 5e6), ("5MEG", 5e6),
                          ("5m", 5e-3), ("2k", 2e3), ("3g", 3e9), ("10f", 10e-15), ("7", 7.0),
                          ("1.5e3", 1.5e3), ("-0.3", -0.3), ("1E-9n", 1e-18)):
            self.assertAlmostEqual(N.spice_num(tok) / want, 1.0, msg=tok)

    def test_meg_is_not_milli(self):
        self.assertEqual(N.spice_num("1meg"), 1e6)
        self.assertEqual(N.spice_num("1m"), 1e-3)

    def test_rejects(self):
        for tok in ("", "abc", "1.2.3", "1x"):
            with self.assertRaises(ValueError, msg=tok):
                N.spice_num(tok)


class Format(unittest.TestCase):
    def test_fmt_matches_committed_netlist_text(self):
        self.assertEqual(N.fmt(1e-6), "1.000000e-06")

    def test_sci_defaults_match_records(self):
        self.assertEqual(N.sci(7.2887e-09), "7.2887e-09")
        self.assertEqual(N.sci(None), "n/a")
        self.assertEqual(N.sci(None, placeholder="N/A (corner not resolved -- see raw logs)"),
                         "N/A (corner not resolved -- see raw logs)")

    def test_sci_digits(self):
        self.assertEqual(N.sci(7.123e-10, digits=3), "7.123e-10")

    def test_sci_nan_is_opt_in(self):
        self.assertEqual(N.sci(math.nan), "nan")
        self.assertEqual(N.sci(math.nan, nan_placeholder=True), "n/a")


class CellDefaults(unittest.TestCase):
    def test_candidate1(self):
        d = N.cell_defaults(REPO / "design" / "netlists" / "cell_candidate1.spice")
        self.assertEqual(d, {"wcap": 1e-6, "lcap": 1e-6, "wacc": 0.30e-6, "lacc": 0.70e-6})


if __name__ == "__main__":
    unittest.main()
