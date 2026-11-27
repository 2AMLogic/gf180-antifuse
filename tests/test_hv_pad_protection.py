"""Offline checks for the HV pad protection model, grading rules and record renderer."""

from __future__ import annotations

import contextlib
import inspect
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))

from harness import numfmt  # noqa: E402
from harness.modload import load_module  # noqa: E402

PAD = SIM / "hv-pad-protection"
RUN = load_module(PAD / "run_experiment.py", "hv_pad_run")
V = RUN.V

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


class RunnerTests(unittest.TestCase):
    r = RUN

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

    def test_smoke_propagates_corner_status_and_prints_diagnostics(self):
        cases = [
            ("pass", {"corners": [{"status": "pass", "measurements": [{"name": "vox_max", "value": 1.02}]}]},
             0, ("pass", "{'vox_max': 1.02}")),
            ("error", {"corners": [{"status": "error", "measurements": [],
                                    "diagnostics": [{"code": "engine_aborted"}]}]},
             1, ("error", "{}", "engine_aborted")),
            ("timeout", {"corners": [{"status": "timeout", "measurements": [{"name": "vox_max", "value": None}],
                                      "diagnostics": [{"code": "wall_timeout"}]}]},
             1, ("timeout", "{'vox_max': None}", "wall_timeout")),
            ("empty", {"corners": []}, 1, ("smoke FAILED:",)),
        ]
        for label, report, expected_rc, fragments in cases:
            with self.subTest(case=label), tempfile.TemporaryDirectory() as td:
                out = io.StringIO()
                run_klt = mock.Mock(return_value=(report, ""))
                with mock.patch.dict(os.environ, {}, clear=False), \
                        mock.patch.object(self.r, "REPO_ROOT", Path(td)), \
                        mock.patch.object(self.r.CB.K, "run_klt", run_klt), \
                        contextlib.redirect_stdout(out):
                    rc = self.r.main(["--smoke", "3:astd_f"])
                self.assertEqual(rc, expected_rc)
                run_klt.assert_called_once()
                printed = out.getvalue()
                for fragment in fragments:
                    self.assertIn(fragment, printed)


class FacadeTests(unittest.TestCase):
    def test_public_model_and_render_names_are_discoverable(self):
        names = dir(RUN)
        for module in (RUN.M, RUN.RENDER):
            for name in dir(module):
                if not name.startswith("_"):
                    self.assertIn(name, names)
                    self.assertTrue(hasattr(RUN, name), name)
        self.assertIs(RUN.RENDER.M, RUN.M)
        self.assertIs(RUN.corner_id, RUN.M.corner_id)
        self.assertIs(RUN.render_bench, RUN.RENDER.render_bench)
        with self.assertRaises(AttributeError):
            getattr(RUN, "missing_pad_helper")

    def test_retired_plumbing_and_shared_deck_formatter(self):
        self.assertFalse(hasattr(RUN, "shutil"))
        self.assertFalse(hasattr(V, "JUNCTION_BV"))
        self.assertNotIn("defs", inspect.signature(RUN.render).parameters)
        self.assertEqual(list(inspect.signature(RUN.render_bench).parameters), ["a", "bench", "rows"])
        self.assertIs(RUN.fnum, numfmt.fmt)


class RecordTests(unittest.TestCase):
    cand = next(c for c in RUN.CHAR.CANDIDATES if c.n == 3)
    rid = "20261117-053800-d84a86d"

    def test_collect_preserves_failed_corners_and_normalizes_measurements(self):
        c = {"process": "ss", "temperature_c": -39.99, "supply_v": {"vamp": -8.69}}
        vals = {"vox_max": 8.0, "ifil_max": 1e-3}
        report = {"corners": [
            {**c, "status": "pass", "measurements": [{"name": k.upper(), "value": v} for k, v in vals.items()]},
            {**c, "process": "typical", "status": "pass", "measurements": [
                {"name": "vox_max", "value": 5.0}, {"name": "ifil_max", "value": 0.0}]},
            {**c, "process": "ff", "status": "timeout", "measurements": [{"name": "vox_max", "value": 20.0}]},
        ]}
        self.assertEqual(RUN.corner_id(c), "ss_-40c_pl-8p69v")
        rows = RUN.collect(report, RUN.bench_defs(3)["cx_f"], self.cand, 7.9)
        self.assertEqual(rows, [
            {"cid": "ss_-40c_pl-8p69v", "level": -8.69, "status": "pass", "vals": vals, "codes": []},
            {"cid": "typical_-40c_pl-8p69v", "level": -8.69, "status": "pass",
             "vals": {"vox_max": 5.0, "ifil_max": 0.0}, "codes": ["function:cell-voltage-short", "function:program-state"]},
            {"cid": "ff_-40c_pl-8p69v", "level": -8.69, "status": "timeout", "vals": {"vox_max": 20.0},
             "codes": ["error:timeout"]},
        ])
        lines = []
        RUN.render_bench(lines.append, "cx_f", rows)
        self.assertIn("| -8.69 | 2/3 | 1/2 | 8 | 0.001 | `error:timeout` x1; "
                      "`function:cell-voltage-short` x1; `function:program-state` x1 |", lines)

    def test_render_matches_committed_astd_record(self):
        # Offline table fixture: repeat the published maxima for the nine corners at each level.
        maxima = [
            (0.983, 0.00374, 9.83e-10, 4.83e-11, 0.0321),
            (1.01,  0.00439, 1.01e-9,  6.77e-11, 0.0673),
            (1.02,  0.00449, 1.02e-9,  5.02e-11, 0.0751),
            (1.02,  0.00452, 1.02e-9,  5.31e-11, 0.079),
            (1.07,  0.00503, 1.07e-9,  2.64e-11, 0.168),
        ]
        levels = RUN.levels(self.cand, 7.9)
        rows = []
        for level, (voltage, ipad, ifil, idvdd, idvss) in zip(levels, maxima):
            vals = dict(vpad_max=voltage, vpl_max=voltage, vox_max=voltage, ipad_max=ipad,
                        ifil_max=ifil, idvdd_hold=idvdd, idvss_hold=idvss)
            codes = V.check_corner("astd", level, 7.9, 3, vals)
            rows.extend([dict(level=level, status="pass", vals=vals, codes=codes)] * 9)
        record = RUN.render(self.rid, self.cand, 7.9, levels, {"astd_f": rows}, False)
        self.assertEqual(record.encode(), (PAD / "records" / f"{self.rid}.md").read_bytes())

    def test_explicit_provenance_and_failed_submission(self):
        record = RUN.render(self.rid, self.cand, 7.9, RUN.levels(self.cand, 7.9),
                            {"cx_f": "submit failed: offline"}, True, git_sha="abc1234")
        self.assertIn("- **Git**: `abc1234` (working tree dirty at run time)\n", record)
        self.assertTrue(record.endswith("#### `cx_f`\n\nNO RESULT: submit failed: offline\n\n"))


if __name__ == "__main__":
    unittest.main()
