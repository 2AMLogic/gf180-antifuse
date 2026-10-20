"""Offline tests for sim/integrated-transition (no simulator).

    python3 -m unittest discover -s sim/integrated-transition -p 'test_integrated.py'
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402
import limits as LIM  # noqa: E402
import make_bench as B  # noqa: E402


class Bench(unittest.TestCase):
    def test_testbench_is_current(self):
        for p, t in B.outputs().items():
            self.assertTrue(p.exists() and p.read_text() == t, f"stale {p.name}; run make_bench.py")

    def requests(self):
        for sl in B.SLICE_CELLS:
            for proc in B.PROCESS:
                for tier in B.TIER_POINTS:
                    yield sl, proc, tier, json.loads((B.TB_DIR / B.request_name(sl, proc, tier)).read_text())

    def test_point_lists_decode_back_to_their_definition(self):
        for sl, proc, tier, req in self.requests():
            pts = B.points(sl, proc, tier)
            self.assertEqual(len(req["corners"]["supply_v"]["vdd"]), len(pts))
            for i, pt in enumerate(pts):
                sv = {k: v[i] for k, v in req["corners"]["supply_v"].items()}
                d = A.decode(sl, sv)
                self.assertEqual((d["cell"], d["scen"], d["var"], d["scale"]), (pt["cell"], pt["scen"], pt["var"], pt["scale"]))

    def test_tier_a_covers_every_subcombination_and_the_full_pvt_grid(self):
        seen = {}
        for sl, proc, tier, req in self.requests():
            if tier != "A":
                continue
            self.assertEqual(req["corners"]["temperature_c"], list(B.TEMPS))
            self.assertEqual(sorted(set(round(v / B.VDD, 2) for v in req["corners"]["supply_v"]["vdd"])), list(B.SUPPLY_SCALES))
            for i in range(len(req["corners"]["supply_v"]["vdd"])):
                d = A.decode(sl, {k: v[i] for k, v in req["corners"]["supply_v"].items()})
                seen.setdefault(d["band"], set()).add((d["cap"], d["acc"]))
        for band in "I II III".split():
            self.assertEqual(len(seen[band]), 4, band)
        self.assertEqual(len(B.PROCESS), 5)

    def test_tier_b_is_the_declared_reduced_corner_set_and_keeps_opposite_subcombinations(self):
        corners = set()
        for sl, proc, tier, req in self.requests():
            if tier != "B":
                continue
            for t in req["corners"]["temperature_c"]:
                for v in set(round(x / B.VDD, 2) for x in req["corners"]["supply_v"]["vdd"]):
                    corners.add((proc, t, v))
            combos = {}
            for i in range(len(req["corners"]["supply_v"]["vdd"])):
                d = A.decode(sl, {k: v[i] for k, v in req["corners"]["supply_v"].items()})
                combos.setdefault(d["band"], set()).add((d["cap"], d["acc"]))
            for band, cs in combos.items():
                self.assertEqual(len(cs), 2, (sl, band))
                (c1, a1), (c2, a2) = sorted(cs)
                self.assertTrue(c1 != c2 and a1 != a2, "tier B cells must differ on both axes")
        self.assertEqual(len(corners), 7)

    def test_request_units_per_shard_stay_small(self):
        for sl, proc, tier, req in self.requests():
            n = len(req["corners"]["supply_v"]["vdd"]) * len(req["corners"]["temperature_c"])
            self.assertLessEqual(-(-n // req["remote"]["hosts"]), B.UNITS_PER_HOST)

    def test_every_probe_has_a_measurement(self):
        for sl in B.SLICE_CELLS:
            req = json.loads((B.TB_DIR / f"{sl}_ss.request.json").read_text())
            names = {m["name"] for m in req["measurements"]}
            man = json.loads((B.TB_DIR / f"probes_{sl}.json").read_text())
            self.assertTrue(set(man) <= names)
            self.assertEqual(len({m["name"] for m in req["measurements"]}), len(req["measurements"]))
            # ngspice allows at most 99 par() calls and the bench must not use any
            self.assertFalse(any("par(" in m["spice"] for m in req["measurements"]))

    def test_every_scenario_and_variant_is_run_somewhere(self):
        run = {pv for tier in B.TIER_POINTS.values() for pv in tier}
        self.assertEqual({s for s, _v in run}, set(B.SCENARIOS))
        self.assertEqual({v for _s, v in run}, set(B.VARIANTS))

    def test_no_hand_rolled_simulator_loop(self):
        for f in HERE.glob("*.py"):
            if f.name == "test_integrated.py":
                continue
            t = f.read_text()
            self.assertNotIn("ngspice -b", t.replace("`ngspice -b`", ""), f.name)


class Limits(unittest.TestCase):
    def test_only_stated_pairs_are_checked(self):
        self.assertEqual(LIM.limit_for("nfet_06v0", "gs", "cell", False)[0], 6.0)
        self.assertEqual(LIM.limit_for("nfet_10v0_asym", "gd", "colpg", False)[0], 10.0)
        self.assertIsNone(LIM.limit_for("nfet_06v0", "ds", "cell", False)[0])
        self.assertIsNone(LIM.limit_for("ppolyf_u_2k_6p0", "t12", "progleg", False)[0])

    def test_selected_capacitor_is_never_judged(self):
        self.assertIsNone(LIM.limit_for("cap_nmos_03v3", "t12", "cell", True)[0])
        self.assertEqual(LIM.limit_for("cap_nmos_03v3", "t12", "cell", False)[0], 3.3)


class Settle(unittest.TestCase):
    def meas(self, sense, rdata, band="i"):
        m = {}
        for i, (s, r) in enumerate(zip(sense, rdata)):
            m[f"sense_s{i}_{band}"], m[f"rdata_s{i}_{band}"] = s, r
        return m

    def test_stable_from_first_read_sample(self):
        n = len(B.SAMPLES)
        t_dec, t_set, ok = A.settle(self.meas([3.3] * n, [3.3] * n), "I", 3.3, 2.8, True)
        self.assertTrue(ok)
        self.assertAlmostEqual(t_dec, B.SAMPLES[0] - 2.8)

    def test_late_flip_sets_delay_and_early_samples_do_not_count(self):
        n = len(B.SAMPLES)
        rd = [0.0] * 4 + [3.3] * (n - 4)
        t_dec, t_set, ok = A.settle(self.meas([0.0] * 4 + [3.3] * (n - 4), rd), "I", 3.3, 2.8, True)
        self.assertTrue(ok)
        self.assertAlmostEqual(t_dec, B.SAMPLES[4] - 2.8)

    def test_wrong_final_decision_is_not_ok(self):
        n = len(B.SAMPLES)
        t_dec, _s, ok = A.settle(self.meas([0.0] * n, [0.0] * n), "I", 3.3, 2.8, True)
        self.assertFalse(ok)
        self.assertIsNone(t_dec)

    def test_samples_before_read_enable_are_ignored(self):
        n = len(B.SAMPLES)
        t_dec, _s, ok = A.settle(self.meas([3.3] * n, [3.3] * n), "I", 3.3, 3.0, True)
        self.assertGreater(B.SAMPLES[B.SAMPLES.index(next(t for t in B.SAMPLES if t > 3.0))], 3.0)
        self.assertGreater(t_dec, 0)


class Grade(unittest.TestCase):
    def corner(self, sl="slice_i_ii", idx=0, over=None):
        req = json.loads((B.TB_DIR / f"{sl}_typical.request.json").read_text())
        sv = {k: v[idx] for k, v in req["corners"]["supply_v"].items()}
        vals = {m["name"]: 0.0 for m in req["measurements"]}
        vals.update(over or {})
        return {"status": "pass", "process": "typical", "temperature_c": 27, "supply_v": sv,
                "measurements": [{"name": k, "value": v} for k, v in vals.items()]}

    def test_quiet_unprogrammed_point_passes_every_check(self):
        r = A.grade("slice_i_ii", self.corner())
        self.assertTrue(all(r["chk"].values()), r["chk"])

    def test_missing_measurement_is_ungradable_not_a_pass(self):
        c = self.corner()
        c["measurements"] = [m for m in c["measurements"] if m["name"] != "sense_max_arm_i"]
        with self.assertRaises(A.Ungradable):
            A.grade("slice_i_ii", c)

    def test_armed_sense_excursion_fails_its_check(self):
        r = A.grade("slice_i_ii", self.corner(over={"sense_max_arm_i": 1.0}))
        self.assertFalse(r["chk"]["armed_sense"])

    def test_leg_overlap_fails_exclusion(self):
        r = A.grade("slice_i_ii", self.corner(over={"both_max_i": 3.0}))
        self.assertFalse(r["chk"]["exclusion"])

    def test_floating_unselected_line_is_flagged(self):
        r = A.grade("slice_i_ii", self.corner(over={"ln_max_cg_12": 0.5}))
        self.assertFalse(r["chk"]["unselected_off"])
        self.assertEqual(r["off_line"], "cg_12")

    def test_active_low_word_line_is_judged_against_vddh(self):
        sl = "slice_ii_iii"
        req = json.loads((B.TB_DIR / f"{sl}_typical.request.json").read_text())
        c = self.corner(sl=sl, over={"ln_min_wl_1_iii": 0.0, "ln_max_wl_1_iii": 5.0, "ln_min_wl_2_iii": 5.0, "ln_max_wl_2_iii": 5.0})
        r = A.grade(sl, c)
        self.assertGreater(r["off_dev"], 4.0)   # row 1 low word line is far from its OFF level (VDDH = 5 V)


if __name__ == "__main__":
    unittest.main()
