"""Tests for the Candidate 3 well-junction avalanche model (issue #208).

Limiting cases of the abrupt-junction formula, monotonicity in doping, the
verdict logic at its edges, both junctions across the stated ranges, the
transcribed junction stresses against the committed bench records, and
note/script agreement. unittest; also runs under pytest. No simulator.
"""
import importlib.util
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NOTE = ROOT / "docs" / "breakdown-c3-junction-model.md"
RECORD_DIR = ROOT / "sim" / "program-bias-scheme" / "records"


def _load():
    spec = importlib.util.spec_from_file_location("bd_c3_junction", ROOT / "scripts" / "breakdown_c3_junction_model.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bd_c3_junction"] = mod
    spec.loader.exec_module(mod)
    return mod


M = _load()


def record_pair(record_id: str, bench: str) -> tuple:
    """(cj, bj) of the 1x level summary row of `bench` in a program-bias-scheme record."""
    lines = (RECORD_DIR / f"{record_id}.md").read_text().splitlines()
    start = next(i for i, ln in enumerate(lines) if re.match(r"^\s+- ", ln) and f"`{bench}`" in ln)
    for ln in lines[start:]:
        if re.match(r"^\s+\| 1x \| ", ln):
            cells = [c.strip().strip("*") for c in ln.strip().strip("|").split("|")]
            # Level | VPP | corners ok | programmed | wc | wb | bc | cj | bj | gb | pairs over
            return float(cells[7]), float(cells[8])
    raise AssertionError(f"no 1x row for {bench} in {record_id}")


class AbruptJunction(unittest.TestCase):
    def test_known_limit_1e16(self):
        # Sze: V_B = 60 (Eg/1.1)^1.5 at N = 1e16; Eg = 1.12 eV gives 61.64 V.
        self.assertAlmostEqual(M.abrupt_bv(1e16), 60 * (1.12 / 1.1) ** 1.5, places=9)
        self.assertAlmostEqual(M.abrupt_bv(1e16), 61.64, places=2)

    def test_power_law_exponent(self):
        self.assertAlmostEqual(M.abrupt_bv(1e17) / M.abrupt_bv(1e16), 10 ** -0.75, places=9)

    def test_monotonic_decreasing_in_doping(self):
        ns = [1e15 * 1.5 ** k for k in range(40)]
        v = [M.abrupt_bv(n) for n in ns]
        self.assertTrue(all(a > b for a, b in zip(v, v[1:])))

    def test_inverse_round_trip(self):
        for bv in (5.0, 10.5, 14.0, 60.0):
            self.assertAlmostEqual(M.abrupt_bv(M.equivalent_doping(bv)), bv, places=9)

    def test_pdk_bv_implies_plausible_well_doping(self):
        n = M.equivalent_doping(M.BV_PN)
        self.assertTrue(8e16 < n < 1.4e17, n)

    def test_rejects_nonpositive_doping(self):
        with self.assertRaises(ValueError):
            M.abrupt_bv(0.0)

    def test_temperature_scale(self):
        self.assertEqual(M.temp_scale(27.0, 0.001), 1.0)
        self.assertLess(M.temp_scale(-40.0, 0.001), 1.0)
        self.assertGreater(M.temp_scale(125.0, 0.001), 1.0)


class RangesAndVerdict(unittest.TestCase):
    def test_doping_extremes_ordering_both_junctions(self):
        for n_rng in (M.N_NW, M.N_SUB):
            lo = M.bv_profile(n_rng[1], M.CURV[0], M.T_COLD, M.ALPHA[1])
            hi = M.bv_profile(n_rng[0], M.CURV[1], M.T_HOT, M.ALPHA[1])
            self.assertLess(lo, hi)
            self.assertLess(lo, M.abrupt_bv(n_rng[1]))
            self.assertGreater(hi, M.abrupt_bv(n_rng[0]))

    def test_well_substrate_stays_above_p_n_well(self):
        # Substrate side is lighter, so that junction is the higher-voltage one over the whole range.
        self.assertGreater(M.bv_profile(M.N_SUB[1], 1.0, 27.0, 0.001), M.bv_profile(M.N_NW[0], 1.0, 27.0, 0.001))

    def test_anchored_range_brackets_nominal(self):
        for bv in (M.BV_PN, M.BV_NWPS):
            lo, nom, hi = M.bv_anchored_range(bv)
            self.assertLess(lo, nom)
            self.assertLess(nom, hi)

    def test_verdict_edges(self):
        self.assertEqual(M.verdict(5.0, 5.0, 9.0), "IN-RATING")
        self.assertEqual(M.verdict(5.01, 5.0, 9.0), "UNDETERMINED")
        self.assertEqual(M.verdict(9.0, 5.0, 9.0), "UNDETERMINED")
        self.assertEqual(M.verdict(9.01, 5.0, 9.0), "NOT IN-RATING")

    def test_critical_doping_is_boundary(self):
        for stress in (6.34, 8.13, 11.95):
            n = M.critical_doping(stress)
            self.assertAlmostEqual(M.bv_profile(n, 1.0, M.T_COLD, M.ALPHA[1]), stress, places=6)

    def test_critical_doping_decreases_with_stress(self):
        self.assertGreater(M.critical_doping(6.0), M.critical_doping(12.0))

    def test_both_junction_types_covered_in_stress_table(self):
        for key, st in M.STRESS.items():
            self.assertIn("cj", st)
            self.assertIn("bj", st)
            self.assertGreaterEqual(M.well_substrate_v(*key), 0.0)

    def test_stress_rises_with_vbd_for_every_arrangement(self):
        for s in M.SCHEMES:
            self.assertLess(M.STRESS[(s, "floor")]["cj"], M.STRESS[(s, "assumed")]["cj"])
            self.assertLess(M.STRESS[(s, "assumed")]["cj"], M.STRESS[(s, "typ")]["cj"])


class StressMatchesRecords(unittest.TestCase):
    def test_every_stress_value_traces_to_a_record(self):
        for scheme, (prefix, recs) in M.RECORDS.items():
            for case, rid in recs.items():
                pairs = [record_pair(rid, f"{prefix}_{v}") for v in ("b1m", "b1l")]
                got = M.STRESS[(scheme, case)]
                self.assertAlmostEqual(got["cj"], max(p[0] for p in pairs), places=2, msg=(scheme, case))
                self.assertAlmostEqual(got["bj"], max(p[1] for p in pairs), places=2, msg=(scheme, case))


class NoteAgreement(unittest.TestCase):
    def test_note_exists(self):
        self.assertTrue(NOTE.exists())

    def test_generated_tables_match_script(self):
        self.assertEqual(M.check_note(NOTE), [])

    def test_check_flags_a_tampered_table(self):
        import tempfile
        text = NOTE.read_text().replace("| 11.07 |", "| 11.08 |", 1)
        self.assertNotEqual(text, NOTE.read_text())
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "n.md"
            p.write_text(text)
            self.assertIn("stress", M.check_note(p))


if __name__ == "__main__":
    unittest.main()
