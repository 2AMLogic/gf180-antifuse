"""Full-record regression tests for the sim/programming-yield renderer (issue #470).

The three-module split (#466 / PR #467) left the record renderer without a
committed check: the ephemeral before/after render diff used as the split's
acceptance gate left nothing behind, and records/*.md are frozen evidence
produced by older code, so they cannot serve as golden files directly. These
tests load the runner facade with harness.modload (as
tests/test_program_bias_render.py does), render two saved runs from
sim/programming-yield/corners/ and compare the full Markdown record against
committed golden fixtures under tests/fixtures/render/ (test artifacts, not
evidence): the read-defined Candidate 1 run byte-for-byte (final newline
included), and the Candidate 3 run's upper-bound interpretation with no
programmed-read table. The renderer clock is frozen so the timestamp line is
compared too, and the #62 reference record is pinned so a later evidence
record cannot switch the comparison baseline. Nothing writes: records/ and
corners/ stay untouched.
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
    return load_module(ROOT / "sim" / "programming-yield" / "run_experiment.py", "py_render_run_experiment")


RE = _load()
BY_N = {c.n: c for c in RE.CHAR.CANDIDATES}
PARAMS, _ERR = RE.CHECK.parse_params((RE.BD_DIR / "breakdown_params.spice").read_text())
CORNERS = ROOT / "sim" / "programming-yield" / "corners"
C1_RID = "20261013-200244-7932822"
C3_RID = "20261013-200250-7932822"
STORED_BD = {1: "20261009-020137-66efd11", 3: "20261009-020416-66efd11"}
PDK = types.SimpleNamespace(variant="gf180mcuD", revision="test-revision-0000")
FROZEN = time.struct_time((2026, 11, 22, 12, 34, 56, 6, 326, 0))


def _render(cand_n: int, rid: str) -> tuple[str, object]:
    """Load and render one saved run through the runner facade, clock frozen."""
    with mock.patch.dict(RE.M.PARAMS, PARAMS), \
         mock.patch.object(RE.RENDER, "stored_bd_record", return_value=STORED_BD[cand_n]), \
         mock.patch("time.gmtime", return_value=FROZEN):
        groups, readtab, rerr = RE.load_run(BY_N[cand_n], rid, base_dir=CORNERS / rid)
        out = RE.render_record(PDK, BY_N[cand_n], rid, groups, readtab, rerr, PARAMS, False,
                               RE.I_BOUND_DEFAULT, 100, None, None)
    return out, readtab, groups


class GoldenRecord(unittest.TestCase):
    def test_read_defined_candidate1_record_matches_golden(self):
        out, readtab, groups = _render(1, C1_RID)
        self.assertEqual(len(groups), 10)
        self.assertIsNotNone(readtab)
        golden = (ROOT / "tests" / "fixtures" / "render" / "programming-yield-c1.md").read_text()
        self.assertEqual(golden, out)

    def test_candidate3_reports_upper_bound_and_omits_read_table(self):
        out, readtab, groups = _render(3, C3_RID)
        self.assertEqual(len(groups), 10)
        self.assertIsNone(readtab)
        self.assertIn("read decision: NOT EVALUATED for Candidate 3", out)
        self.assertIn("**upper bounds** on a full read-decision yield", out)
        self.assertNotIn("Programmed-read table", out)


class FacadeSurface(unittest.TestCase):
    def test_facade_resolves_pre_split_surface(self):
        self.assertIs(RE.load_run, RE.M.load_run)
        self.assertIs(RE.render_record, RE.RENDER.render_record)
        self.assertIs(RE.I_BOUND_DEFAULT, RE.M.I_BOUND_DEFAULT)
        self.assertIs(RE.PARAMS, RE.M.PARAMS)

    def test_params_mutation_reads_through_facade_and_is_restored(self):
        self.assertNotIn("probe", RE.PARAMS)
        with mock.patch.dict(RE.M.PARAMS, {"probe": {"value": 1.0}}):
            self.assertIn("probe", RE.PARAMS)
            self.assertEqual(RE.PARAMS["probe"], {"value": 1.0})
        self.assertNotIn("probe", RE.PARAMS)


if __name__ == "__main__":
    unittest.main()
