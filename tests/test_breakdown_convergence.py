"""Tests for the #74 convergence accounting in
sim/cell-breakdown-model/run_experiment.py (unittest; also runs under pytest).

No simulation is run: these check failure classification, attribution,
grid accounting (failed corners stay in the denominator), the corner-id
parsing the per-level tables rely on, and the threshold prediction.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402

RE = load_module(ROOT / "sim" / "cell-breakdown-model" / "run_experiment.py", "bd_run_experiment")

PARAMS, PERR = RE.CHECK.parse_params((RE.BD_DIR / "breakdown_params.spice").read_text())
CAND = {c.n: c for c in RE.CHAR.CANDIDATES}

TIMESTEP_LOG = (
    "No. of Data Rows : 1168\n"
    'doAnalyses: TRAN:  Timestep too small; time = 1.12011e-05, timestep = 1.25e-20: '
    'trouble with node "e.xb.xc.xc1.ec_moscap#branch"\n\ntran simulation(s) aborted\n')
MEAS_ERR = [{"severity": "error", "code": "measurement", "message": "measurement 'st' produced no value"}]


class ClassifyFailure(unittest.TestCase):
    def test_pass_needs_every_value(self):
        o = RE.classify_failure("pass", [], "ngspice-46 done\n", {"st": 1.0, "dmg": 2.0})
        self.assertEqual(o["kind"], "pass")
        o = RE.classify_failure("pass", [], "ngspice-46 done\n", {"st": 1.0, "dmg": None})
        self.assertEqual(o["kind"], "missing-measurement")
        self.assertEqual(o["missing"], ["dmg"])

    def test_timestep_records_time_node_and_location(self):
        o = RE.classify_failure("error", MEAS_ERR, TIMESTEP_LOG, {"st": None})
        self.assertEqual(o["kind"], "timestep")
        self.assertAlmostEqual(o["time"], 1.12011e-05)
        self.assertEqual(o["node"], "e.xb.xc.xc1.ec_moscap#branch")
        self.assertEqual(o["where"], "stock cell / testbench")

    def test_timestep_inside_element_is_attributed_to_it(self):
        log = TIMESTEP_LOG.replace("e.xb.xc.xc1.ec_moscap#branch", "xdut.xbd.dmg")
        self.assertEqual(RE.classify_failure("error", MEAS_ERR, log, {"st": None})["where"], "breakdown element")

    def test_timeout_wins_over_missing_measurements(self):
        diags = [{"severity": "error", "code": "timeout", "message": "ngspice did not complete within 300s"}] + MEAS_ERR
        self.assertEqual(RE.classify_failure("error", diags, None, {"st": None})["kind"], "timeout")

    def test_error_without_log_or_missing_value(self):
        self.assertEqual(RE.classify_failure("error", [], None, {"st": 0.0})["kind"], "error")


class GridAccounting(unittest.TestCase):
    def test_failures_stay_in_denominator(self):
        t = RE.tally(["pass", "pass", "timeout", "timestep", "missing-measurement", "error"])
        self.assertEqual(t["attempted"], 6)
        self.assertEqual(t["pass"], 2)
        self.assertEqual(sum(t[k] for k in ("pass", "timeout", "timestep", "missing-measurement", "error")), 6)

    def test_attribution(self):
        self.assertEqual(RE.attribute_corner({"st": False, "b0": False, "b1m": False}), "stock-cell")
        self.assertEqual(RE.attribute_corner({"st": True, "b0": False, "b1m": True}), "wrapper (element disabled)")
        self.assertEqual(RE.attribute_corner({"st": True, "b0": True, "b1m": True, "b1l": False}),
                         "breakdown-element (enabled)")
        self.assertEqual(RE.attribute_corner({"st": True, "b0": True, "b1m": True, "b1l": True}), "converged")
        self.assertEqual(RE.attribute_corner({"b1m": False}), "enabled deck (stock deck not run)")


class CornerIds(unittest.TestCase):
    def test_levels_parse_back(self):
        self.assertEqual(RE.corner_level("moscap_ss_-40c_pla-8p69v"), -8.69)
        self.assertEqual(RE.corner_level("moscap_ff_125c_vpp16p72v"), 16.72)
        self.assertEqual(RE.corner_level("moscap_typical_27c_pl3p30v"), 3.3)
        self.assertEqual(RE.corner_temp("moscap_ss_-40c_pla-8p69v"), -40)

    def test_corner_key_for_single_instance_benches(self):
        c = {"process": "moscap_ss", "temperature_c": -40.0, "supply_v": {"vamp": 8.69}}
        self.assertEqual(RE.corner_key("prog_b1m", c, CAND[3], PARAMS), "moscap_ss_-40c_vpp8p69v")
        c["supply_v"] = {"vamp": -8.69}
        self.assertEqual(RE.corner_key("trig1_st", c, CAND[3], PARAMS), "moscap_ss_-40c_pl-8p69v")

    def test_level_labels_cover_every_level(self):
        for n, cand in CAND.items():
            for stim in RE.CONV_STIMULI:
                labels = [RE.level_label(cand, PARAMS, stim, v) for v in RE.conv_levels(cand, PARAMS, stim)]
                self.assertEqual(labels, ["rated", "0.9x", "0.95x", "1x", "1.1x"], (n, stim))

    def test_prog_levels_positive_trig1_signed(self):
        self.assertTrue(all(v > 0 for v in RE.conv_levels(CAND[3], PARAMS, "prog")))
        self.assertTrue(all(v < 0 for v in RE.conv_levels(CAND[3], PARAMS, "trig1")))


class Stimuli(unittest.TestCase):
    def test_campaigns_name_only_known_benches(self):
        for name, benches in RE.CAMPAIGNS.items():
            self.assertTrue(all(b in RE.ALL_BENCHES for b in benches), name)
        self.assertIn(RE.CONTROL_BENCH, RE.CAMPAIGNS["conv74"])
        self.assertTrue(all(RE.STIM_EDGE[RE.conv_split(b)[0]] == "cinf" for b in RE.CAMPAIGNS["conv74c"]))

    def test_opstart_request_has_no_uic_and_one_level(self):
        import types
        pdk = types.SimpleNamespace(variant="gf180mcuD")
        req = RE.make_request(RE.OPSTART_BENCH, CAND[1], pdk, [], PARAMS)
        self.assertNotIn("uic", req["analysis"]["args"])
        self.assertEqual(req["corners"]["supply_v"], {"vamp": [CAND[1].cap_rated_v]})
        req = RE.make_request("trigc_b1m", CAND[1], pdk, [], PARAMS)
        self.assertTrue(req["analysis"]["args"].endswith(" uic"))
        self.assertEqual(len(req["corners"]["supply_v"]["vamp"]), 5)

    def test_cinf_edge_is_smooth_and_reaches_both_rails(self):
        import math

        def fe(u):
            return math.exp(-1 / max(u, 1e-6))

        def edge(x):
            u = min(max(x, 0), 1)
            return fe(u) / (fe(u) + fe(1 - u))
        self.assertEqual(edge(0.0), 0.0)
        self.assertEqual(edge(1.0), 1.0)
        self.assertAlmostEqual(edge(0.5), 0.5)
        # flat at both ends: the first difference vanishes faster than the step
        h = 1e-3
        self.assertLess(edge(h) / h, 1e-100)
        self.assertLess((1 - edge(1 - h)) / h, 1e-100)
        lines = RE.edge_lines("cinf")
        self.assertIn("af_fe(u) {exp(-1/max(u,1e-6))}", lines[0])


class Prediction(unittest.TestCase):
    def test_parameters_parse(self):
        self.assertEqual(PERR, [])

    def test_matches_the_62_level_prediction(self):
        # pre-breakdown the oxide holds the applied level; the E-model then
        # reproduces the #62 bench's level-based expectation at every level
        cand = CAND[1]
        vbd = RE.vbd_ref(cand, PARAMS)
        for frac, ubd, want in ((0.9, 0.5, 0), (0.9, RE.UBD_LOW, 0), (0.95, 0.5, 0), (0.95, RE.UBD_LOW, 1),
                                (1.0, 0.5, 1), (1.1, 0.5, 1)):
            lo, hi = RE.damage_prediction(cand, PARAMS, frac * vbd, ubd)
            self.assertEqual(RE.predict_state(lo, hi), want, (frac, ubd, lo, hi))
        lo, hi = RE.damage_prediction(cand, PARAMS, cand.cap_rated_v, 0.5)
        self.assertEqual(RE.predict_state(lo, hi), 0)

    def test_boundary_is_not_scored(self):
        self.assertIsNone(RE.predict_state(1.0, 1.04))

    def test_half_formed_filament_is_a_miss(self):
        self.assertTrue(RE.latched_as_predicted(1.0, 1))
        self.assertTrue(RE.latched_as_predicted(0.0, 0))
        self.assertFalse(RE.latched_as_predicted(0.6, 1))
        self.assertFalse(RE.latched_as_predicted(0.0, 1))


class Decks(unittest.TestCase):
    def test_one_cell_per_deck_and_variant_is_the_only_difference(self):
        import tempfile
        import types
        with tempfile.TemporaryDirectory() as tmp:
            stub = Path(tmp) / "design.ngspice"
            stub.write_text(".param sw_stat_global = 0\n")
            pdk = types.SimpleNamespace(design_ngspice=stub, variant="gf180mcuD")
            for n, cand in CAND.items():
                defaults = RE.CHAR.parse_defaults(ROOT / "design" / "netlists" / cand.netlist)
                for stim in RE.CONV_STIMULI:
                    bodies = {}
                    for v in RE.CONV_VARIANTS:
                        body, ms = RE.body_conv(pdk, cand, defaults, ROOT / "sim" / "cell-breakdown-model",
                                                "/opt/pdk/gf180mcuD", f"{stim}_{v}", PARAMS)
                        cells = [ln for ln in body.splitlines() if ln.startswith("X")]
                        self.assertEqual(len(cells), 1, (n, stim, v))
                        # all but the cell line, its CN probes and the title are identical
                        bodies[v] = [ln for ln in body.splitlines()
                                     if not ln.startswith(("X", "*", "BD")) and "variant" not in ln]
                        names = {m["name"] for m in ms}
                        self.assertEqual("st" in names, v.startswith("b1"))
                    self.assertTrue(all(b == bodies["st"] for b in bodies.values()), (n, stim))

if __name__ == "__main__":
    unittest.main()
