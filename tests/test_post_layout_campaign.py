"""Post-layout probe (issue #447): extraction gate, bound-point check, replay.

No simulator and no fleet; operates on the committed reports and scratch copies.
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PL = REPO / "sim" / "cell-device-characterization" / "klt" / "post-layout"
sys.path.insert(0, str(REPO / "sim"))
sys.path.insert(0, str(PL))
from extraction_check import check_extraction  # noqa: E402
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
