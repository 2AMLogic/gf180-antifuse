"""Facade introspection tests for sim/array-slice-bench (issue #517).

The #517 split moved the grading and aggregation library into model.py and
the Markdown/CSV renderers into render.py, leaving run_bench.py as the CLI
facade re-exporting both through a module ``__getattr__`` (plus a subset
eagerly at import) -- the same decomposition #461, #466, #471 and #503
applied to the sibling experiments. ``dir()`` does not consult
``__getattr__``, so the facade also defines ``__dir__``: these tests pin
that parity (every public name of the two library modules is visible to
``dir()`` and resolves by ``getattr`` through the facade), that fullband.py
shares -- not re-declares -- the selected-path thresholds from model.py and
``REGION_NAME`` / the number formatter from render.py, and that the split
retired the mutable module-global ``_CELLS`` cache and the unused
``per_slice_summary`` plumbing. unittest; also runs under pytest. No
simulator is invoked.
"""
import inspect
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402

ASB = ROOT / "sim" / "array-slice-bench"


def _load():
    return load_module(ASB / "run_bench.py", "asb_facade_run_bench")


RB = _load()


class DirParity(unittest.TestCase):
    def test_dir_does_not_raise_and_is_sorted(self):
        d = dir(RB)
        self.assertIsInstance(d, list)
        self.assertEqual(d, sorted(d))

    def test_dir_lists_reexported_library_names(self):
        d = dir(RB)
        self.assertIn("grade_corner", d)        # model.py's grading
        self.assertIn("load_netlist_cells", d)  # model.py's committed-cell map
        self.assertIn("region_tables", d)       # model.py's aggregation
        self.assertIn("fmt_e", d)               # render.py's number formatter
        self.assertIn("REGION_NAME", d)         # render.py's region names
        self.assertIn("slice_section", d)       # render.py's slice renderer

    def test_every_public_sibling_name_is_listed_and_resolves(self):
        d = dir(RB)
        for n in dir(RB.M) + dir(RB.RENDER):
            if n.startswith("_"):
                continue
            self.assertIn(n, d, n)
            self.assertTrue(hasattr(RB, n), n)

    def test_own_facade_names_stay_listed(self):
        for n in ("main", "run_full_band", "finish_full_band", "run_klt", "merge_reports",
                  "slim_payload", "write_report_and_digest", "git", "analyze", "slice_section",
                  "write_records", "slice_measurement_view", "fullband_csv", "M", "RENDER",
                  "G", "B", "ES", "K", "R", "HERE", "REPO"):
            self.assertIn(n, dir(RB), n)

    def test_pre_split_names_still_resolve_through_the_facade(self):
        # the pre-split single file exposed these; library callers (and the
        # sim-level tests) keep resolving them on run_bench.
        for n in ("ETA_MIN", "RETURN_MIN", "BL_MIN", "PL_MAX", "ISO_MAX", "R_FIL",
                  "sub_combo", "grade_corner", "analyze", "region_tables",
                  "REGION_NAME", "fmt_e", "slice_section", "orientation_section",
                  "write_records", "_jobs_line"):
            self.assertTrue(hasattr(RB, n), n)


class FullBandSharesTheLibrary(unittest.TestCase):
    """fullband.py must import the shared constants/formatter, not re-declare
    them (the duplicate declarations the split retired)."""

    @classmethod
    def setUpClass(cls):
        cls.F = load_module(ASB / "fullband.py", "asb_facade_fullband")
        # other test modules re-register the fixed sim_asb_* names, so compare
        # against the copies fullband.py actually bound, not RB's.
        cls.M = cls.F.ASB_M
        cls.R = cls.F.ASB_R

    def test_thresholds_are_model_py_s_objects(self):
        self.assertIs(self.F.ETA_MIN, self.M.ETA_MIN)
        self.assertIs(self.F.BL_MIN, self.M.BL_MIN)
        self.assertIs(self.F.RETURN_MIN, self.M.RETURN_MIN)
        self.assertEqual((self.F.ETA_MIN, self.F.BL_MIN, self.F.RETURN_MIN), (0.80, 0.98, 0.95))

    def test_region_name_and_formatter_are_render_py_s_objects(self):
        self.assertIs(self.F.REGION_NAME, self.R.REGION_NAME)
        self.assertIs(self.F.e, self.R.fmt_e)

    def test_fullband_still_owns_its_analysis_surface(self):
        for n in ("AnalysisError", "budget", "analyze_pgoff", "analyze_nat", "analyze_sel",
                  "budget_table", "pvt_table", "sel_table", "summary_lines"):
            self.assertTrue(hasattr(self.F, n), n)


class RetiredStateAndPlumbing(unittest.TestCase):
    def test_no_mutable_cell_cache_exists(self):
        self.assertFalse(hasattr(RB, "_CELLS"))
        self.assertFalse(hasattr(RB.M, "_CELLS"))
        self.assertNotIn("_CELLS", (ASB / "model.py").read_text())
        self.assertNotIn("_CELLS", (ASB / "render.py").read_text())

    def test_grade_corner_carries_the_sub_combination(self):
        # sub_combo's ("cap", "acc") now travels inside each graded corner,
        # so region_tables never needs a pre-populated slice-global cache.
        self.assertTrue("cells" in inspect.signature(RB.M.sub_combo).parameters)

    def test_write_records_drops_unused_per_slice_summary(self):
        params = inspect.signature(RB.write_records).parameters
        self.assertNotIn("per_slice_summary", params)
        for p in ("record_id", "sections", "clean", "now", "repo"):
            self.assertIn(p, params)

    def test_repo_is_a_parameter_not_a_frozen_constant(self):
        # the CLI passes its own REPO at call time; the library default only
        # serves standalone use.
        for fn in (RB.M.load_netlist_cells, RB.M.analyze, RB.RENDER.orientation_section, RB.RENDER.write_records):
            self.assertIn("repo", inspect.signature(fn).parameters, fn.__name__)


if __name__ == "__main__":
    unittest.main()
