"""Tests for program-bias-scheme --render on a consumed (store-held) run (issue #356),
and for the --retabulate empty-source refusal (issue #362).

After the evidence store removes a run's in-tree sources, --render must (a) read
through run_dir_for_reading so the stored copy is fetched back, and (b) refuse to
write a record when no reports can be found anywhere: write_once is append-only,
so an empty-convergence record minted from a store/fetch miss could never be
corrected in place. The same refusal applies to --retabulate --retab-src naming
a source record with neither a manifest nor a run dir.
"""
import contextlib
import io
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

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


class RetabGuard(unittest.TestCase):
    def test_retabulate_refuses_empty_source_and_writes_no_record(self):
        # --retab-src naming a record with neither a manifest nor a run dir:
        # no progc_* reports anywhere, so the retabulation must return 2 and
        # write no record (write_once is append-only; an empty one could
        # never be corrected in place).
        with tempfile.TemporaryDirectory() as td:
            old_this, RE.THIS_DIR = RE.THIS_DIR, Path(td)
            try:
                with mock.patch.object(RE.P, "resolve_pdk", return_value=None), \
                     mock.patch.object(RE.shutil, "which", return_value="/usr/bin/true"), \
                     contextlib.redirect_stderr(io.StringIO()) as err:
                    rc = RE.main(["--retabulate", "--candidates", "1", "--retab-src", RID])
            finally:
                RE.THIS_DIR = old_this
            self.assertEqual(rc, 2)
            self.assertEqual(list((Path(td) / "records").glob("*.md")), [])
            self.assertIn(f"no saved progc_* reports for {RID}", err.getvalue())


if __name__ == "__main__":
    unittest.main()
