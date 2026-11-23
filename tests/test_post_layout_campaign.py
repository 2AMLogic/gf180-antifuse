"""Post-layout probe (issue #447): extraction gate, bound-point check, replay.

No simulator and no fleet; operates on the committed reports and scratch copies.
"""

from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import textwrap
import unittest
from unittest import mock
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PL = REPO / "sim" / "cell-device-characterization" / "klt" / "post-layout"
sys.path.insert(0, str(REPO / "sim"))
sys.path.insert(0, str(PL))
from extraction_check import check_extraction  # noqa: E402
from harness import klt as K  # noqa: E402
from harness.modload import load_module  # noqa: E402

RUN = PL / "runs" / "20261121-073730-17c2f21"
C = load_module(PL / "run_post_layout_campaign.py", "run_post_layout_campaign")


class ExtractionGate(unittest.TestCase):
    def _scratch(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        shutil.copytree(REPO / "layout" / "cell_candidate1", t / "layout" / "cell_candidate1")
        return t

    def test_committed_extractions_usable(self):
        for n in (1, 2, 3):
            self.assertEqual(check_extraction(REPO, n), [])

    def test_stale_gds_and_unbiased_flagged(self):
        t = self._scratch()
        g = t / "layout/cell_candidate1/cell_candidate1.gds"
        g.write_bytes(g.read_bytes() + b"\0")
        rp = t / "layout/cell_candidate1/pex/pex_report.json"
        d = json.loads(rp.read_text())
        d["body_bias"]["status"] = "unbiased"
        rp.write_text(json.dumps(d))
        f = " ".join(check_extraction(t, 1))
        self.assertIn("stale GDS", f)
        self.assertIn("unbiased", f)

    def test_missing_report_flagged(self):
        t = self._scratch()
        (t / "layout/cell_candidate1/pex/pex_report.json").unlink()
        self.assertIn("missing PEX report", check_extraction(t, 1)[0])


class BoundPoints(unittest.TestCase):
    def _run(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        shutil.copytree(RUN, t / "run")
        return t / "run"

    def test_missing_worst_point_suppresses_value(self):
        rd = self._run()
        p = rd / "c1_schematic/ioff/report.json"
        d = json.loads(p.read_text())
        d["corners"] = [c for c in d["corners"] if c["supply_v"]["vwl"] != 0.3]
        p.write_text(json.dumps(d))
        v, _, err = C.leg_ioff_worst(rd, 1, "schematic")
        self.assertIsNone(v)
        self.assertIn("bound points mismatch", err)

    def test_wrong_temperature_suppresses_ron(self):
        rd = self._run()
        p = rd / "c1_extracted/ron/report.json"
        d = json.loads(p.read_text())
        d["corners"][0]["temperature_c"] = 25
        p.write_text(json.dumps(d))
        r, _, _, err = C.leg_ron(rd, 1, "extracted")
        self.assertIsNone(r)
        self.assertIn("bound points mismatch", err)

    def test_committed_run_complete(self):
        s = C.collect(RUN)
        for c in s["cells"].values():
            self.assertIsNone(c["ioff"]["schematic_error"])
            self.assertIsNone(c["ron"]["extracted_error"])
            self.assertIsNotNone(c["ron"]["delta"])


class DutIdentity(unittest.TestCase):
    def _run(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        shutil.copytree(RUN, t / "run")
        return t / "run"

    def test_schematic_report_in_extracted_slot_suppresses_pair(self):
        rd = self._run()
        for w in ("ioff", "ron"):
            shutil.copy(rd / f"c3_schematic/{w}/report.json", rd / f"c3_extracted/{w}/report.json")
        s = C.collect(rd)["cells"]["3"]
        self.assertIsNone(s["ron"]["delta"])
        self.assertIsNone(s["ioff"]["delta"])
        self.assertIn("extracted leg", s["ron"]["extracted_error"])
        self.assertIsNone(s["ron"]["schematic_error"])

    def test_sha_mismatch_flagged_with_leg(self):
        rd = self._run()
        p = rd / "c1_extracted/ron/report.json"
        d = json.loads(p.read_text())
        for e in d["environment"]["netlist_closure"]:
            if e["path"].endswith("extracted.spice"):
                e["sha256"] = "0" * 64
        p.write_text(json.dumps(d))
        _, _, _, err = C.leg_ron(rd, 1, "extracted")
        self.assertIn("extracted leg", err)
        self.assertIn("sha256 mismatch", err)


class SubmitAndResume(unittest.TestCase):
    def _stand_in(self, t: Path, rd_src: Path) -> str:
        """A `klt` that answers with the recorded report for whichever -o dir it is given."""
        f = t / "fakeklt.py"
        f.write_text(textwrap.dedent(f"""
            import sys
            out = sys.argv[sys.argv.index("-o") + 1].rstrip("/").split("/")
            print(open("{rd_src}/" + out[-2] + "/" + out[-1] + "/report.json").read())
        """))
        return f"{sys.executable} {f}"

    def test_fresh_submit_and_one_missing_resume_through_runner(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        rd = t / "run"
        shutil.copytree(RUN, rd)
        victim = rd / "c2_extracted/ron"
        orig = (victim / "report.json").read_text()
        shutil.rmtree(victim)
        env = {"KLT_CMD": self._stand_in(t, RUN), "KLT_SIM_BACKEND": "local"}
        with mock.patch.dict(os.environ, env):
            C.submit_all(rd, 1, only_missing=True)                  # resume: one missing
            self.assertTrue((victim / "report.json").is_file())
            self.assertTrue((victim / "report.json.sha256").is_file())
            self.assertIsNotNone(C.RK.load_report(rd, "c2_extracted", "ron"))
            fresh = t / "fresh"
            C.submit_all(fresh, 2)                                  # fresh submission
        self.assertFalse((rd / "submit-errors.txt").exists())
        self.assertFalse((fresh / "submit-errors.txt").exists())
        for n in (1, 2, 3):
            for leg in ("schematic", "extracted"):
                self.assertTrue((fresh / f"c{n}_{leg}/ron/report.json").is_file())
        self.assertIn('"corners"', orig)

    def _arg_recorder(self, t: Path) -> str:
        """A `klt` that records its argv and answers with the recorded report."""
        f = t / "argklt.py"
        f.write_text(textwrap.dedent(f"""
            import sys
            with open("{t}/args", "a") as fh:
                fh.write(" ".join(sys.argv[1:]) + "\\n")
            out = sys.argv[sys.argv.index("-o") + 1].rstrip("/").split("/")
            print(open("{RUN}/" + out[-2] + "/" + out[-1] + "/report.json").read())
        """))
        return f"{sys.executable} {f}"

    def test_batch_submit_waits_for_capacity_local_does_not(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        klt = self._arg_recorder(t)
        rd = t / "rd"
        with mock.patch.dict(os.environ, {"KLT_CMD": klt, "KLT_SIM_BACKEND": "batch"}):
            C.submit_one(rd, "c1_schematic", "ioff")
        with mock.patch.dict(os.environ, {"KLT_CMD": klt, "KLT_SIM_BACKEND": "local"}):
            C.submit_one(rd, "c1_extracted", "ioff")
        batch, local = (t / "args").read_text().splitlines()
        self.assertIn("--backend batch", batch)
        self.assertIn("--wait-for-capacity 600", batch)
        self.assertIn("--backend local", local)
        self.assertNotIn("--wait-for-capacity", local)

    def test_submit_one_uses_shared_backoff_and_capacity_wait(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        seen = []

        def fake(request, outdir, backend=None, **kw):
            seen.append({"request": Path(request), "outdir": Path(outdir),
                         "backend": backend, **kw})
            return {"error": {"code": "batch_no_capacity"}}, ""

        original = K.run_klt
        K.run_klt = fake
        self.addCleanup(setattr, K, "run_klt", original)
        with mock.patch.dict(os.environ, {"KLT_SIM_BACKEND": "batch"}):
            sub, w, ok, _ = C.submit_one(t, "c1_schematic", "ioff")
        self.assertEqual((sub, w), ("c1_schematic", "ioff"))
        self.assertFalse(ok)
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0]["retry"], K.BACKOFF)
        self.assertEqual(seen[0]["backend"], "batch")
        self.assertEqual(seen[0]["capacity_wait_s"], "600")
        self.assertEqual(seen[0]["request"], C.REQ_DIR / "c1_schematic" / "ioff.json")
        self.assertEqual(seen[0]["outdir"], t / "c1_schematic" / "ioff")

    def test_failed_submit_keeps_diagnostics(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        f = t / "bad.py"
        f.write_text("import sys\nprint('no json')\nsys.stderr.write('boom')\nsys.exit(3)\n")
        with mock.patch.dict(os.environ, {"KLT_CMD": f"{sys.executable} {f}", "KLT_SIM_BACKEND": "local"}):
            sub, w, ok, detail = C.submit_one(t, "c1_schematic", "ioff")
        self.assertFalse(ok)
        saved = (t / "c1_schematic/ioff/report.json").read_text()
        # Under the shared harness a no-JSON failure folds both output tails
        # into the diagnostic written to report.json (and submit-errors.txt);
        # there is no separate stderr.txt for it.
        self.assertIn("exit 3", saved)
        self.assertIn("no json", saved)
        self.assertIn("boom", saved)
        self.assertEqual(saved, detail)
        self.assertFalse((t / "c1_schematic/ioff/stderr.txt").exists())


class ReadmeDisposition(unittest.TestCase):
    def test_body_bias_and_usable_set_follow_findings(self):
        s = C.collect(RUN)
        s["cells"]["1"]["extraction_findings"] = ["body_bias.status is 'unbiased', not 'biased'"]
        with mock.patch.object(C, "body_bias_status", lambda n: "unbiased" if n == 1 else "biased"):
            txt = C.render_readme(RUN, s)
        self.assertNotIn("All three extractions are usable", txt)
        self.assertNotIn("\"biased\"` for all three cells", txt)
        self.assertIn("C1 `unbiased`", txt)
        self.assertIn("Extractions usable: C3, C2", txt)
        self.assertIn("unusable (pair suppressed above): C1", txt)

    def test_all_usable_text_kept(self):
        txt = C.render_readme(RUN, C.collect(RUN))
        self.assertIn("All three extractions are usable", txt)


class SummaryReplay(unittest.TestCase):
    def test_identical_replay_and_resume_preserve_original(self):
        t = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, t)
        a = C.write_summary(t, {"x": 1})
        self.assertEqual(C.write_summary(t, {"x": 1}), a)          # identical replay
        b = C.write_summary(t, {"x": 2})                            # recovered result
        self.assertNotEqual(a, b)
        self.assertEqual(json.loads(a.read_text()), {"x": 1})       # original kept
        self.assertEqual(C.write_summary(t, {"x": 2}), b)


if __name__ == "__main__":
    unittest.main()
