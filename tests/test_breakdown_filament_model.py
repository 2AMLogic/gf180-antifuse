"""Tests for the post-breakdown filament model (issue #209). unittest; no simulator."""
import importlib.util
import math
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("bfm", ROOT / "scripts" / "breakdown_filament_model.py")
M = importlib.util.module_from_spec(_spec)
sys.modules["bfm"] = M
_spec.loader.exec_module(M)
NOTE = ROOT / "docs" / "breakdown-filament-model.md"
SPICE = (ROOT / "design" / "breakdown" / "breakdown_params.spice").read_text()


def spice_param(name):
    return float(re.search(rf"^\.param {name}\s*=\s*([0-9.eE+-]+)", SPICE, re.M).group(1))


class Inputs(unittest.TestCase):
    def test_constants_match_param_file(self):
        self.assertEqual(M.RF_MED_ASSUMED, spice_param("bd_rf_med"))
        self.assertEqual(M.RF_SIG_ASSUMED, spice_param("bd_rf_sig"))
        self.assertEqual(M.Z_WC, spice_param("bd_zrf_wc"))
        self.assertEqual(M.TOX["thin"], spice_param("c1_bd_tox"))
        self.assertEqual(M.TOX["thick"], spice_param("c2_bd_tox"))
        self.assertAlmostEqual(M.RF_WC_ASSUMED, 81.7e3, delta=100)

    def test_baseline_values_in_sim_readme(self):
        readme = (ROOT / "sim" / "cell-breakdown-model" / "README.md").read_text()
        self.assertIn("8.35 µA at `ss_125c_bl0p90v`", readme)
        self.assertIn("10.98 µA at `ss_125c_bl0p90v`", readme)


class Model(unittest.TestCase):
    def test_note_and_script_agree(self):
        have = M.extract(NOTE.read_text())
        gen = M.render()
        self.assertEqual(set(have), set(gen))
        for k in gen:
            self.assertEqual(have[k], gen[k], k)
        self.assertEqual(M.main(["--check", str(NOTE)]), 0)

    def test_reproduces_baseline_at_matching_compliance(self):
        # no compliance spread, intrinsic sigma only: +3 sigma at I_c = 100 uA is 81.7 kOhm
        for c in ("C1", "C2"):
            ox = M.CAND[c]["oxide"]
            ic = M.i_c_equal_baseline(oxide=ox, sig_ic=0.0)
            rf = M.r_quantile(ic, ox, M.Z_WC, sig_ic=0.0)
            self.assertAlmostEqual(rf, M.RF_WC_ASSUMED, delta=1)
            self.assertAlmostEqual(M.i_read(rf, c), M.CAND[c]["i_prog_min"], delta=1e-12)

    def test_thin_median_anchor(self):
        self.assertAlmostEqual(M.r_med(M.I_ANCHOR, "thin"), M.RF_MED_ASSUMED)

    def test_monotone_in_compliance(self):
        for c in ("C1", "C2"):
            cur = [M.i_prog_min(i, c) for i in M.I_C_GRID]
            self.assertEqual(cur, sorted(cur))

    def test_compliance_extremes(self):
        for c in ("C1", "C2"):
            self.assertLess(M.i_prog_min(1e-9, c), 1e-8)           # weak filament: current -> 0
            ceiling = M.V_RAIL_LOW / M.r_acc(c)                      # strong: access-limited
            self.assertLess(M.i_prog_min(1.0, c), ceiling)
            self.assertGreater(M.i_prog_min(1.0, c), 0.8 * ceiling)

    def test_plus_3_sigma_is_worst_quantile(self):
        for ox in ("thin", "thick"):
            for ic in M.I_C_GRID:
                lo, med, hi = (M.r_quantile(ic, ox, z) for z in (-3, 0, 3))
                self.assertLess(lo, med)
                self.assertLess(med, hi)
                self.assertAlmostEqual(math.sqrt(lo * hi), med, delta=med * 1e-12)

    def test_nonlinear_limits(self):
        for c in ("C1", "C2"):
            rf = M.r_quantile(100e-6, M.CAND[c]["oxide"], M.Z_WC)
            base = M.i_read(rf, c, 1.0)
            self.assertAlmostEqual(M.i_read(rf, c, 1.0 + 1e-9), base, delta=base * 1e-6)
            self.assertLess(M.i_read(rf, c, 2.0), M.i_read(rf, c, 1.5))
            self.assertLess(M.i_read(rf, c, 1.5), base)
        # C2: filament sees ~ the whole rail, so ratio ~ (V_rail/V_f)^(p-1)
        rf = M.r_quantile(100e-6, "thick", M.Z_WC)
        r = M.i_read(rf, "C2", 2.0) / M.i_read(rf, "C2", 1.0)
        self.assertAlmostEqual(r, M.V_RAIL_LOW / M.v_f("thick"), delta=0.01)

    def test_candidate3_access_limited(self):
        r_eff = M.V_RAIL_LOW / M.C3_I_PROG_MIN
        self.assertGreater(r_eff, 100 * M.RF_WC_ASSUMED)
        self.assertAlmostEqual(M.C3_I_PROG_MIN / M.C3_I_SNEAK_MAX, 39, delta=0.5)


if __name__ == "__main__":
    unittest.main()
