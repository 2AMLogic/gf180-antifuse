"""Full-record regression test for the sim/cell-breakdown-model standard
record (issue #470).

The three-module split (#461 / PR #464) left the record renderer without a
committed check of a complete rendered record (the existing breakdown tests
exercise convergence, read-bias and sensitivity helpers). This test loads the
runner facade with harness.modload (as tests/test_program_bias_render.py
does), loads the five-bench saved run -- access_op, access_ac, cap_op, cap_ac
and trigger, so render_any takes the standard render_record branch -- from
sim/cell-breakdown-model/corners/ and compares the full Markdown record
against a committed golden fixture under tests/fixtures/render/ (a test
artifact, not evidence), final newline included. The renderer clock is frozen
so the timestamp line is compared too, and the (a2) reproduction reference
record is pinned so a later evidence record cannot switch the comparison
baseline. Nothing writes: records/ and corners/ stay untouched.
"""
import sys
import time
import types
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "cell-breakdown-model" / "run_experiment.py", "cb_render_run_experiment")


RE = _load()
BY_N = {c.n: c for c in RE.CHAR.CANDIDATES}
PARAMS, _ERR = RE.CHECK.parse_params((RE.BD_DIR / "breakdown_params.spice").read_text())
CORNERS = ROOT / "sim" / "cell-breakdown-model" / "corners"
RID = "20261009-020137-66efd11"
STORED_RID = "20260909-232140-b6035cb"
PDK = types.SimpleNamespace(variant="gf180mcuD", revision="test-revision-0000")
FROZEN = time.struct_time((2026, 11, 22, 12, 34, 56, 6, 326, 0))


class GoldenRecord(unittest.TestCase):
    def test_standard_record_matches_golden(self):
        self.assertIs(RE.results_from_reports, RE.M.results_from_reports)
        self.assertIs(RE.render_any, RE.RENDER.render_any)
        with mock.patch.object(RE.RENDER, "stored_record_id", return_value=STORED_RID), \
             mock.patch("time.gmtime", return_value=FROZEN):
            results = RE.results_from_reports(BY_N[1], RID, PARAMS, base_dir=CORNERS / RID)
            out = RE.render_any(PDK, BY_N[1], RID, results, PARAMS, None, None)
        self.assertEqual(set(results), {"access_op", "access_ac", "cap_op", "cap_ac", "trigger"})
        golden = (ROOT / "tests" / "fixtures" / "render" / "cell-breakdown-c1.md").read_text()
        self.assertEqual(golden, out)


if __name__ == "__main__":
    unittest.main()
