"""Rules and deck generation of sim/hv-pad-protection (issue #210). unittest; also runs under pytest. No simulator."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))
sys.path.insert(0, str(SIM / "hv-pad-protection"))

import verdicts as V  # noqa: E402
from harness.modload import load_module  # noqa: E402


def _runner():
    return load_module(SIM / "hv-pad-protection" / "run_experiment.py", "hv_pad_run")


GOOD = {"vox_max": 15.1, "ifil_max": 1.2e-3}


class RuleTests(unittest.TestCase):
    def test_programs_at_105_percent_and_passes(self):
        self.assertEqual(V.check_corner("cx", 15.96, 15.2, 2, GOOD), [])

    def test_below_vbd_must_not_program(self):
        codes = V.check_corner("cx", 14.44, 15.2, 2, {"vox_max": 14.4, "ifil_max": 1.4e-8})
        self.assertEqual(codes, [])
        self.assertIn("function:program-state", V.check_corner("cx", 14.44, 15.2, 2, GOOD))

    def test_clamped_plate_is_a_function_failure(self):
        codes = V.check_corner("jn", 15.96, 15.2, 2, {"vox_max": 12.0, "ifil_max": 1e-8, "ijn_max": 5e-4, "ijn_hold": 4e-4})
        self.assertIn("function:cell-voltage-short", codes)
        self.assertIn("function:program-state", codes)
        self.assertIn("rating:junction-conducts", codes)

    def test_standard_pad_rail_injection_and_pad_rating(self):
        vals = {"vox_max": 6.5, "ifil_max": 6e-9, "vpad_max": 6.5, "idvdd_hold": 0.1}
        codes = V.check_corner("astd", 15.96, 15.2, 2, vals)
        self.assertLessEqual({"rating:pad-over-5.5V", "rating:rail-injection", "function:cell-voltage-short"}, set(codes))

    def test_standard_pad_negative_drive_injects_into_dvss(self):
        vals = {"vox_max": 1.0, "ifil_max": 1e-9, "vpad_max": 1.0, "idvdd_hold": 0.0, "idvss_hold": 4e-3}
        self.assertIn("rating:rail-injection", V.check_corner("astd", -8.69, 7.9, 3, vals))

    def test_standard_pad_start_up_charging_is_not_injection(self):
        vals = {"vox_max": 4.0, "ifil_max": 4e-9, "vpad_max": 4.0, "idvdd_hold": 0.0, "idvss_hold": 0.0, "idvdd_max": 1.4e-3}
        self.assertEqual(V.check_corner("astd", 4.0, 8.0, 1, vals), [])

    def test_ballast_area_flag_only_with_ballast(self):
        vals = {**GOOD, "vr_max": 6.9}
        self.assertIn("rating:ballast-over-6V-area(open)", V.check_corner("c1", 16.72, 15.2, 2, vals))
        self.assertIn("rating:ballast-over-6V-area(open)", V.check_corner("nb", 16.72, 15.2, 2, vals, ballast=True))
        self.assertEqual(V.check_corner("cx", 16.72, 15.2, 2, vals), [])

    def test_neighbour_limit_is_the_candidate_cap_rating(self):
        for cand, limit in [(1, 3.3), (2, 6.0), (3, 3.3)]:
            with self.subTest(cand=cand, limit=limit):
                ok = {**GOOD, "voxj_max": limit - 0.1, "ifilj_max": 1e-9}
                bad = {**GOOD, "voxj_max": limit + 0.1, "ifilj_max": 1e-9}
                lv = 16.72 if cand == 2 else 8.8
                vbd = 15.2 if cand == 2 else (8.0 if cand == 1 else 7.9)
                self.assertEqual(V.check_corner("nb", lv, vbd, cand, ok), [])
                self.assertIn("rating:neighbour-over-cap-rating", V.check_corner("nb", lv, vbd, cand, bad))

    def test_negative_level_uses_magnitude(self):
        self.assertEqual(V.check_corner("cx", -8.69, 7.9, 3, {"vox_max": 8.6, "ifil_max": 5e-4}), [])

    def test_junction_edge_current_is_not_conduction(self):
        vals = {**GOOD, "ijn_max": 1.7e-6, "ijn_hold": 2e-11}
        self.assertEqual(V.check_corner("jn", 15.96, 15.2, 2, vals), [])

    def test_missing_measurement_is_never_a_pass(self):
        self.assertEqual(V.check_corner("cx", 8.4, 8.0, 1, {"vox_max": None, "ifil_max": 1e-3}), ["no-measurement"])

    def test_summarise_counts_per_level(self):
        s = V.summarise([(8.4, "a", ["x"]), (8.4, "b", []), (4.0, "c", [])])
        self.assertEqual(s["corners"], {8.4: 2, 4.0: 1})
        self.assertEqual(s["per_level"][8.4], {"x": 1})


class RunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.r = _runner()

    def test_levels_and_vbd_follow_the_assumed_params(self):
        r = self.r
        p = r.read_params()
        self.assertAlmostEqual(r.vbd_of(1, p), 8.0)
        self.assertAlmostEqual(r.vbd_of(2, p), 15.2)
        self.assertAlmostEqual(r.vbd_of(3, p), 7.9)
        cands = {c.n: c for c in r.CHAR.CANDIDATES}
        lv3 = r.levels(cands[3], 7.9)
        self.assertTrue(all(x < 0 for x in lv3))
        self.assertEqual(lv3[-1], -r.V_PAD_MAX)
        self.assertEqual(r.levels(cands[2], 15.2)[-1], r.V_PAD_MAX)

    def test_every_bench_deck_builds_and_names_each_measured_node(self):
        pdk = self.r.P.resolve_pdk()
        for n in (1, 2, 3):
            cand, pdk, defaults, vbd = self.r.setup(n)
            for name, bd in self.r.bench_defs(n).items():
                text, meas = self.r.body(name, bd, cand, pdk, defaults, vbd)
                with self.subTest(cand=n, bench=name):
                    self.assertIn("VAMP AMP 0 DC 0", text)
                    for m in meas:
                        node = m["spice"].split("v(")[1].split(")")[0]
                        with self.subTest(cand=n, bench=name, node=node):
                            cards = [ln.strip() for ln in text.upper().splitlines()
                                     if ln.strip().startswith("B") and f" {node.upper()} 0 V" in ln]
                            self.assertEqual(len(cards), 1, (n, name, node))
                    self.assertEqual(("XPD PAD PL 0 hv_pad_ballast" in text), (bd["path"] == "ballast"))
        self.assertIsNotNone(pdk)


if __name__ == "__main__":
    unittest.main()
