"""Tests for program-bias-scheme --render on a consumed (store-held) run (issue #356).

After the evidence store removes a run's in-tree sources, --render must (a) read
through run_dir_for_reading so the stored copy is fetched back, and (b) refuse to
write a record when no reports can be found anywhere: write_once is append-only,
so an empty-convergence record minted from a store/fetch miss could never be
corrected in place.
"""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "program-bias-scheme" / "run_experiment.py", "pbs_render_run_experiment")


RE = _load()
BY_N = {c.n: c for c in RE.CHAR.CANDIDATES}
PARAMS, _ERR = RE.CB.CHECK.parse_params((RE.CB.BD_DIR / "breakdown_params.spice").read_text())
RID = "19700101-000000-nosuchrun"


class LoadSavedBaseDir(unittest.TestCase):
    def test_load_saved_honors_base_dir(self):
        base = Path(tempfile.mkdtemp()) / "fetched"
        (base / "plb_st").mkdir(parents=True)
        (base / "plb_st" / "submit-error.txt").write_text("boom\n")
        res = RE.load_saved(BY_N[1], RID, PARAMS, base_dir=base)
        self.assertEqual(set(res), {"plb_st"})
        self.assertEqual(res["plb_st"].status, "submit-error")
        self.assertIn("boom", res["plb_st"].error)

    def test_load_saved_missing_base_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            res = RE.load_saved(BY_N[1], RID, PARAMS, base_dir=Path(td) / "fetched")
        self.assertEqual(res, {})


class RenderOnlyGuard(unittest.TestCase):
    def test_render_only_refuses_empty_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as td:
            old_this, RE.THIS_DIR = RE.THIS_DIR, Path(td)
            try:
                rc = RE.render_only(None, BY_N[1], RID, PARAMS)
            finally:
                RE.THIS_DIR = old_this
            self.assertEqual(rc, 2)
            self.assertFalse((Path(td) / "records" / f"{RID}.md").exists())


if __name__ == "__main__":
    unittest.main()
