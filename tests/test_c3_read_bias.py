"""Regression tests for the Candidate 3 read-bias study (issue #75).

Covers: the scenario bias reaches the generated deck; failed / missing /
non-converged corners cannot pass the feasibility verdict; Candidates 1/2 (and
Candidate 3's historical placeholder benches) generate exactly the decks and
requests committed by the #62 records. unittest; also runs under pytest. No
simulator is invoked.
"""
import json
import re
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EXP = ROOT / "sim" / "cell-breakdown-model"
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(EXP / "run_experiment.py", "bdm_run_experiment")


X = _load()
BY_N = {c.n: c for c in X.CHAR.CANDIDATES}


def fake_pdk(tmp: Path):
    dn = tmp / "design.ngspice"
    dn.write_text("* comment\n.option scale=1.0u\n")
    return types.SimpleNamespace(design_ngspice=dn, variant="gf180mcuD", variant_dir=tmp, revision="test")


def sc(name):
    return X.BIAS_BY_NAME[name]


def corner_vals(sc_, off=1e-13, un=1e-13, pw=1e-6, pm=2e-6):
    """A fully populated, passing set of derived values for one corner and one scenario."""
    v = {}
    for sg in ("s1g1", "s1g2", "s2g1", "s2g2"):
        for b in X.BIAS_TAGS:
            v[f"ioff_{sc_.name}_{sg}_{b}"] = off
            v[f"ioffp_{sc_.name}_{sg}_{b}"] = off
        v[f"iun_{sc_.name}_{sg}"] = un
        v[f"iread_pw_{sc_.name}_{sg}"] = pw
        v[f"iread_pm_{sc_.name}_{sg}"] = pm
    return v


class BiasReachesDeck(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.pdk = fake_pdk(self.tmp)
        self.cand = BY_N[3]
        self.defaults = X.CHAR.parse_defaults(ROOT / "design" / "netlists" / self.cand.netlist)
        self.body, self.ms = X.body_bias(self.pdk, self.cand, self.defaults, self.tmp, "/opt/pdk/gf180mcuD")

    def test_every_scenario_bias_in_deck(self):
        for s in X.BIAS_SCENARIOS:
            self.assertIn(f"VWLON_{s.name} WLON_{s.name} 0 DC {X.fmt(s.wl_on)}", self.body, s.name)
            self.assertIn(f"EBL_{s.name} BLS_{s.name} 0 BL 0 {X.fmt(s.rail_scale)}", self.body, s.name)
            if s.vb_mode == "fixed":
                self.assertIn(f"VVB_{s.name} VB_{s.name} 0 DC {X.fmt(s.vb_v)}", self.body, s.name)
            else:
                self.assertIn(f"BVB_{s.name} VB_{s.name} 0 V = 'v(bls_{s.name}) + {X.fmt(s.vb_v)}'", self.body, s.name)

    def test_programmed_and_unprogrammed_share_the_scenario_bias(self):
        # un_, pm_, pw_ instances of one scenario must be wired to that scenario's WL-on and well nets
        for s in X.BIAS_SCENARIOS:
            for kind in ("un", "pm", "pw"):
                pat = rf"^X_{kind}_{s.name}_s1g1 B_{kind}_{s.name}_s1g1 WLON_{s.name} PL VB_{s.name} "
                self.assertRegex(self.body, re.compile(pat, re.M), (s.name, kind))
            # and the OFF-state (leakage) instances use the SAME well net and rail
            self.assertRegex(self.body, re.compile(rf"^X_off_{s.name}_s1g1_lo B_off_{s.name}_s1g1_lo WLLO PL VB_{s.name} ", re.M))
            self.assertRegex(self.body, re.compile(rf"^X_offp_{s.name}_s1g1_lo B_offp_{s.name}_s1g1_lo WLLO PL VB_{s.name} ", re.M))
            self.assertRegex(self.body, re.compile(rf"^VM_off_{s.name}_s1g1_lo BLS_{s.name} ", re.M))

    def test_programmed_variants_are_programmed(self):
        self.assertRegex(self.body, r"X_pm_s0_placeholder_s1g1 .* cell_candidate3_bd .* bden=1 prog=1 dyn=0 zrf=0")
        self.assertRegex(self.body, r"X_pw_s0_placeholder_s1g1 .* prog=1 dyn=0 zrf=\{bd_zrf_wc\}")
        self.assertRegex(self.body, r"X_offp_s0_placeholder_s1g1_lo .* prog=1")
        self.assertRegex(self.body, r"X_un_s0_placeholder_s1g1 .* prog=0")

    def test_every_measurement_is_a_meas_card_with_unique_name(self):
        names = [m["name"] for m in self.ms]
        self.assertEqual(len(names), len(set(names)))
        self.assertTrue(all(m["spice"].startswith(".meas dc ") for m in self.ms))
        # 9 scenarios x (2 voltages + 4 sub-configs x (3 off + 3 offp + 3 current + 2 vcn))
        self.assertEqual(len(names), len(X.BIAS_SCENARIOS) * (2 + 4 * 11))

    def test_placeholder_scenario_is_the_historical_bias(self):
        s0 = sc("s0_placeholder")
        self.assertEqual((s0.rail_scale, s0.wl_on, s0.vb_mode, s0.vb_v), (1.0, self.cand.wl_on, "fixed", self.cand.vb))

    def test_only_candidate_3(self):
        with self.assertRaises(ValueError):
            X.body_bias(self.pdk, BY_N[1], self.defaults, self.tmp, "/x")

    def test_request_sweeps_the_read_rail_over_all_pvt(self):
        _, ms = X.body_bias(self.pdk, self.cand, self.defaults, self.tmp, "/x")
        params, err = X.CHECK.parse_params((X.BD_DIR / "breakdown_params.spice").read_text())
        self.assertFalse(err)
        req = X.make_request(X.BIAS_BENCH, self.cand, self.pdk, ms, params)
        self.assertEqual(req["backend"], "batch")
        self.assertEqual(len(req["corners"]["process"]), 5)
        self.assertEqual(len(req["corners"]["temperature_c"]), 3)
        self.assertEqual(len(req["corners"]["supply_v"]["vbl"]), 3)
        self.assertEqual(req["analysis"]["kind"], "dc")

    def test_chosen_scenario_exists(self):
        self.assertIn(X.CHOSEN_C3_SCENARIO, X.BIAS_BY_NAME)


class FeasibilityVerdict(unittest.TestCase):
    S = sc("s3_vb_track")

    def stats(self, corners, status=None):
        status = status or {c: "pass" for c in corners}
        return X.bias_stats(corners, status, self.S)

    def test_feasible_when_window_open_everywhere(self):
        st = self.stats({"c1": corner_vals(self.S), "c2": corner_vals(self.S, off=5e-13)})
        self.assertTrue(st["common_iref"])
        self.assertFalse(st["failed"])
        self.assertGreater(st["window"], 1.0)

    def test_programmed_below_leakage_is_infeasible(self):
        st = self.stats({"c1": corner_vals(self.S, off=1e-9, pw=1e-12)})
        self.assertFalse(st["common_iref"])
        self.assertEqual(st["per_corner_bad"], ["c1"])

    def test_one_bad_corner_fails_the_scenario(self):
        st = self.stats({"c1": corner_vals(self.S), "c2": corner_vals(self.S, pw=1e-12)})
        self.assertFalse(st["per_corner_bad"] == [])
        self.assertFalse(st["common_iref"])

    def test_failed_corner_is_reported_not_dropped(self):
        good = corner_vals(self.S)
        st = self.stats({"c1": good, "c2": corner_vals(self.S)}, {"c1": "pass", "c2": "fail"})
        self.assertEqual([f[0] for f in st["failed"]], ["c2"])
        self.assertFalse(st["common_iref"])

    def test_missing_measurement_is_a_failed_corner(self):
        v = corner_vals(self.S)
        del v[f"iread_pw_{self.S.name}_s2g2"]
        st = self.stats({"c1": v})
        self.assertEqual([f[0] for f in st["failed"]], ["c1"])
        self.assertFalse(st["common_iref"])

    def test_none_measurement_is_a_failed_corner(self):
        v = corner_vals(self.S)
        v[f"ioff_{self.S.name}_s1g1_lo"] = None
        st = self.stats({"c1": v})
        self.assertEqual([f[0] for f in st["failed"]], ["c1"])
        self.assertFalse(st["common_iref"])

    def test_no_resolved_corner_cannot_pass(self):
        self.assertFalse(self.stats({}).get("common_iref"))
        self.assertFalse(self.stats({"c1": {}}, {"c1": "pass"})["common_iref"])

    def test_zero_leakage_is_floored_not_trusted(self):
        # exact 0.0 A leakage (cancelling terms) must not make the bound 0
        st = self.stats({"c1": corner_vals(self.S, off=0.0, un=0.0, pw=1e-6)})
        self.assertAlmostEqual(st["rows"]["c1"]["i_sneak_f"], 31 * X.DEFAULT_ABSTOL)
        self.assertGreater(st["rows"]["c1"]["i_zero_f"], 0.0)
        # a programmed current below the solver floor bound is infeasible even though the measured leakage is 0
        st = self.stats({"c1": corner_vals(self.S, off=0.0, un=0.0, pw=1e-12)})
        self.assertFalse(st["common_iref"])

    def test_programmed_off_leakage_counts(self):
        v = corner_vals(self.S, off=1e-13)
        v[f"ioffp_{self.S.name}_s2g1_hi"] = 5e-10
        st = self.stats({"c1": v})
        self.assertAlmostEqual(st["rows"]["c1"]["i_off"], 5e-10)

    def test_common_iref_fails_when_leaky_corner_exceeds_weak_corner(self):
        a = corner_vals(self.S, off=1e-13, pw=1e-8)
        b = corner_vals(self.S, off=1e-9, pw=1e-3)
        st = self.stats({"a": a, "b": b})
        self.assertEqual(st["per_corner_ok"], 2)
        self.assertFalse(st["common_iref"])


class JunctionChecks(unittest.TestCase):
    def test_forward_biased_source_junction_flagged(self):
        s = sc("s8_vb_track_m0v3")
        vals = {"c": {f"vbl_{s.name}": 1.0, f"vvb_{s.name}": 0.5, f"vcn_pw_{s.name}_s1g1": 0.0}}
        v = X.bias_voltages(vals, s, (3.0, 3.3, 3.6))
        self.assertAlmostEqual(v["src_well_min"], -0.5)
        self.assertFalse(v["fwd_ok"])

    def test_tracked_well_is_reverse_biased(self):
        s = sc("s3_vb_track")
        vals = {"c": {f"vbl_{s.name}": 1.1, f"vvb_{s.name}": 1.1, f"vcn_pw_{s.name}_s1g1": 0.04}}
        v = X.bias_voltages(vals, s, (3.0, 3.3, 3.6))
        self.assertTrue(v["fwd_ok"] and v["gate_ok"] and v["cap_ok"])
        self.assertAlmostEqual(v["gate_well_max"], 3.6 - 1.1)

    def test_deep_negative_wl_exceeds_gate_rating_at_high_well(self):
        s = X.ReadBias("t", 1.0, -3.0, "fixed", 3.3, "")
        vals = {"c": {"vbl_t": 1.0, "vvb_t": 3.3, "vcn_pw_t_s1g1": 0.3}}
        v = X.bias_voltages(vals, s, (3.0, 3.3, 3.6))
        self.assertFalse(v["gate_ok"])


class OtherCandidatesUnchanged(unittest.TestCase):
    """The #62 benches must regenerate exactly what the committed records ran."""

    def test_candidate_bias_constants_pinned(self):
        pins = {1: (3.3, 3.3, 0.0), 2: (5.0, 5.0, 0.0), 3: (0.0, -3.3, 3.3)}
        for n, (wl_on, moscap_wl_on, vb) in pins.items():
            c = BY_N[n]
            self.assertEqual((c.wl_on, c.moscap_wl_on, c.vb), (wl_on, moscap_wl_on, vb), n)
        self.assertEqual(X.CHAR.V_READ_NOM, 1.0)
        self.assertEqual(X.CHAR.SUPPLY_TOL, 0.10)

    def _committed(self):
        out = []
        for body in sorted((EXP / "corners").glob("*/*/body.spice")):
            rid, bench = body.parent.parent.name, body.parent.name
            if bench not in X.BENCHES:      # records of this issue (bias_op) are new, not regression
                continue
            n = int(re.search(r"Candidate (\d)", body.read_text()).group(1))
            out.append((rid, bench, n, body))
        # a later record of the same (candidate, bench) supersedes an earlier one (the
        # 2026-10-09 trigger benches were re-run with `uic`); the latest is what the script must reproduce
        latest = {}
        for item in out:
            latest[(item[2], item[1])] = item   # sorted by record id, so the last one wins
        return sorted(latest.values())

    def test_there_are_committed_decks_for_all_candidates(self):
        self.assertEqual({n for _, _, n, _ in self._committed()}, {1, 2, 3})

    def test_requests_regenerate_identically(self):
        params, err = X.CHECK.parse_params((X.BD_DIR / "breakdown_params.spice").read_text())
        self.assertFalse(err)
        tmp = Path(tempfile.mkdtemp())
        pdk = fake_pdk(tmp)
        for rid, bench, n, body in self._committed():
            cand = BY_N[n]
            defaults = X.CHAR.parse_defaults(ROOT / "design" / "netlists" / cand.netlist)
            _, ms = X.build_body(bench, pdk, cand, defaults, body.parent, X.FLEET_PDK_VARIANT_DIR)
            want = json.loads((body.parent / "request.json").read_text())
            got = X.make_request(bench, cand, pdk, ms, params)
            self.assertEqual(got, want, f"{rid} {bench} candidate {n}")

    def test_bodies_regenerate_identically(self):
        params, err = X.CHECK.parse_params((X.BD_DIR / "breakdown_params.spice").read_text())
        tmp = Path(tempfile.mkdtemp())
        pdk = fake_pdk(tmp)
        marker = "* --- end inline ---\n"
        for rid, bench, n, body in self._committed():
            cand = BY_N[n]
            defaults = X.CHAR.parse_defaults(ROOT / "design" / "netlists" / cand.netlist)
            # the lib root is whatever the committed run baked in: /opt/pdk/... for the 2026-10 records, the
            # submit host's own variant dir for klt >= 0.8 runs (sim/harness/pdk.py, issue #99 re-pin)
            m = re.search(r"^\.lib (\S+)/libs\.tech/", body.read_text(), re.M)
            lib_root = m.group(1) if m else X.FLEET_PDK_VARIANT_DIR
            got, _ = X.build_body(bench, pdk, cand, defaults, body.parent, lib_root)
            self.assertEqual(got.split(marker, 1)[1], body.read_text().split(marker, 1)[1],
                             f"{rid} {bench} candidate {n}")


class DecisionRecord(unittest.TestCase):
    def test_decision_record_names_the_chosen_scenario_and_a_bias_record(self):
        text = (ROOT / "spec" / "candidate3-read-bias-decision.md").read_text()
        self.assertIn(X.CHOSEN_C3_SCENARIO, text)
        recs = [p for p in (EXP / "records").glob("*.md") if "read-bias study" in p.read_text()
                or "Candidate 3 / Region III read bias" in p.read_text()]
        self.assertTrue(recs, "no #75 bias record committed")
        self.assertTrue(any(p.stem in text for p in recs), "decision record cites no bias record id")


if __name__ == "__main__":
    unittest.main()
