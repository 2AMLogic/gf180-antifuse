"""Facade and offline rendering tests for sim/integrated-transition (issue #524).

render.py holds the Markdown/CSV renderers; run_bench.py is the CLI facade
re-exporting it through ``__getattr__`` / ``__dir__``. The rendering test
re-grades the committed report archives offline (no simulator) and checks the
rendered text is byte-identical to the committed measurement files.
"""
import datetime as dt
import inspect
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402

IT = ROOT / "sim" / "integrated-transition"
RB = load_module(IT / "run_bench.py", "it_facade_run_bench")
RID = "20261016-054944-66fb0003"


class Facade(unittest.TestCase):
    def test_dir_sorted_and_lists_render_names(self):
        d = dir(RB)
        self.assertEqual(d, sorted(d))
        for n in ("table_armed", "csv_rows", "render_record", "render_measurement_md", "write_records",
                  "CHECKS", "STATEMENT", "main", "grade_slice", "compact", "RENDER"):
            self.assertIn(n, d, n)

    def test_every_public_render_name_resolves(self):
        for n in dir(RB.RENDER):
            if not n.startswith("_"):
                self.assertTrue(hasattr(RB, n), n)

    def test_dead_code_is_gone(self):
        self.assertFalse(hasattr(RB, "sub_name"))
        self.assertNotIn("report_paths", inspect.signature(RB.write_records).parameters)
        self.assertNotIn("hashlib", (IT / "run_bench.py").read_text())
        self.assertNotIn("defaultdict", (IT / "analyze.py").read_text())


@unittest.skipUnless((IT / "reports" / RID).is_dir(), "committed report archives not staged")
class OfflineRender(unittest.TestCase):
    def test_regrade_renders_committed_measurements_byte_identical(self):
        comps = {sl: {(p, t): RB.load(IT / "reports" / RID / f"{sl}_{p}{'' if t == 'A' else '_x'}.report.json.gz")
                      for p in RB.B.PROCESS for t in RB.B.TIER_POINTS} for sl in RB.B.SLICE_CELLS}
        rows, stress, bad = [], {}, 0
        for sl, c in comps.items():
            r, st, b, _ = RB.grade_slice(sl, c)
            rows += r
            RB.A.merge_stress(stress, st)
            bad += b
        blocks = RB.build_blocks(rows, stress)
        meas = ROOT / "measurements" / "integrated-transition"
        self.assertEqual(RB.render_measurement_md(RID, blocks), (meas / f"{RID}.md").read_text())
        self.assertEqual("\n".join(RB.csv_rows(rows)) + "\n", (meas / f"{RID}.csv").read_text())
        n_units = sum(len(c["points"]) for cs in comps.values() for c in cs.values())
        rec = RB.render_record(RID, blocks, n_units, len(rows), bad, True,
                               dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc), "0" * 12, comps)
        self.assertIn(f"# Record {RID}", rec)
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            RB.write_records(RID, rows, stress, comps, bad, True, dt.datetime(2026, 1, 1, tzinfo=dt.timezone.utc),
                             "0" * 12, repo=td, here=td / "sim")
            self.assertEqual((td / "sim" / "records" / f"{RID}.md").read_text(), rec)


if __name__ == "__main__":
    unittest.main()
