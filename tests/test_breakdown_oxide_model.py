"""Tests for the gate-oxide breakdown model (issue #205). unittest; stdlib only.

Limiting cases and monotonicity of the closed-form model, the parameter table's
provenance rule, and agreement between the note and the generator script.
"""
import importlib.util
import math
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _load():
    spec = importlib.util.spec_from_file_location("breakdown_oxide_model", ROOT / "scripts" / "breakdown_oxide_model.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["breakdown_oxide_model"] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load()


class Limits(unittest.TestCase):
    def test_reference_point_is_e0(self):
        for n in M.CANDS:
            m = M.model(n)
            self.assertAlmostEqual(m.vbd(M.TREF), m.tox * M.E0, places=9)

    def test_monotone_in_pulse_width_and_quantile_and_area(self):
        for n in M.CANDS:
            for b in ("perc", "ext"):
                m = M.model(n, b)
                v = [m.vbd(t) for t, _ in M.PULSES]
                self.assertEqual(v, sorted(v, reverse=True))
                q = [m.vbd(1e-6, x) for x in (1e-3, 0.1, 0.5, 0.9, 0.999)]
                self.assertEqual(q, sorted(q))
                a = [m.vbd(1e-6, 0.5, M.A0 * x) for x in (1, 10, 100)]
                self.assertEqual(a, sorted(a, reverse=True))

    def test_decade_slope_is_tox_over_gamma_dec(self):
        for n in M.CANDS:
            m = M.model(n)
            self.assertAlmostEqual(m.vbd(1e-6) - m.vbd(1e-5), m.tox * MV / M.dec(m.gamma), places=9)

    def test_spread_vanishes_as_beta_grows(self):
        m = M.model(1)
        wide = M.Model(tox=m.tox, beta=1.0).sigma_v()
        tight = M.Model(tox=m.tox, beta=1e4).sigma_v()
        self.assertLess(tight, wide * 1e-3)

    def test_spread_formula(self):
        m = M.model(2, "ext")
        want = m.tox / (m.beta * m.gamma) * math.log(-math.log(1 - 0.999) / -math.log(1 - 0.001))
        self.assertAlmostEqual(m.sigma_v(), want, places=9)

    def test_ramp_equals_pulse_of_t_eff(self):
        m = M.model(1)
        for r in (1e-2, 1.0, 1e2):
            self.assertAlmostEqual(m.vbd_ramp(r), m.vbd(m.tox / (m.gamma * r)), places=12)

    def test_ramp_matches_numeric_miner_sum(self):
        m = M.model(1)
        r, q = 1.0, 0.5
        v = m.vbd_ramp(r, q)
        # integrate dt / T50 along the ramp up to v; (A/A0) * ln2 * sum^beta must equal -ln(1-q)
        n, tot = 200000, 0.0
        vmax = v
        for i in range(n):
            vi = (i + 0.5) / n * vmax
            tot += (vmax / n / r) / m.t50(vi / m.tox)
        self.assertAlmostEqual(M.LN2 * tot ** m.beta, -math.log(1 - q), delta=2e-3)

    def test_one_over_e_law_is_higher_at_long_times_and_equal_at_tref(self):
        for n in M.CANDS:
            a, b = M.model(n), M.model(n, law="1/E")
            self.assertAlmostEqual(a.vbd(M.TREF), b.vbd(M.TREF), places=9)
            self.assertGreater(b.vbd(M.TEN_YEARS), a.vbd(M.TEN_YEARS))

    def test_edge_pulse_range_100ns_to_dc(self):
        for n in M.CANDS:
            m = M.model(n)
            v = [m.vbd(1e-7), m.vbd(M.TEN_YEARS)]
            self.assertTrue(all(math.isfinite(x) and x > 0 for x in v))

    def test_tox_range_from_cox(self):
        lo, typ, hi = (M.EPS_R * M.EPS0 / (c * 1e-3) for c in M.COX["thin 3.3 V"][::-1])
        self.assertLess(lo, typ)
        self.assertLess(typ, hi)
        self.assertAlmostEqual(typ * 1e9, 7.85, delta=0.05)  # sources note: about 7.9 nm


MV = 1e8


class Provenance(unittest.TestCase):
    def test_params_file_is_not_modified_by_script(self):
        text = M.PARAMS_FILE.read_text()
        for name in ("bd_ebd", "bd_gam", "bd_beta"):
            self.assertRegex(text, rf"@param {name} .*provenance=assumed")

    def test_every_parameter_row_has_a_source_and_uncertainty(self):
        for line in M.blk_params().splitlines()[2:]:
            cells = [c.strip() for c in line.strip("|").split("|")]
            self.assertEqual(len(cells), 6)
            self.assertTrue(all(cells), line)
            src = cells[4]
            self.assertTrue("`assumed`" in src or "PDK" in src or "definition" in src or "committed" in src or "textbook" in src, line)


class NoteAgreement(unittest.TestCase):
    def test_note_blocks_match_script(self):
        self.assertEqual(M.check(), [])

    def test_all_blocks_present(self):
        text = M.NOTE.read_text()
        for k in M.BLOCKS:
            self.assertEqual(len(M.block_re(k).findall(text)), 1, k)


if __name__ == "__main__":
    unittest.main()
