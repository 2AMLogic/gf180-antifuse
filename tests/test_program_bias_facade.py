"""Facade introspection tests for sim/program-bias-scheme (issue #503).

The #503 split moved the library surface into model.py + render.py and left
run_experiment.py as the CLI facade re-exporting both through a module
``__getattr__`` (plus a subset eagerly at import). ``dir()`` does not
consult ``__getattr__``, so the facade also defines ``__dir__`` (the same
fix #465 applied to cell-breakdown-model and #476 to programming-yield):
these tests pin that parity -- every public name of the two library modules
is visible to ``dir()`` and resolves by ``getattr`` through the facade (the
pre-split single file exposed all of them), and the cell-breakdown-model
module state render.py's common_header reads at call time still reads
through to the owning module. unittest; also runs under pytest. No
simulator is invoked.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "program-bias-scheme" / "run_experiment.py", "pbs_facade_run_experiment")


RE = _load()


class DirParity(unittest.TestCase):
    def test_dir_does_not_raise_and_is_sorted(self):
        d = dir(RE)
        self.assertIsInstance(d, list)
        self.assertEqual(d, sorted(d))

    def test_dir_lists_reexported_library_names(self):
        d = dir(RE)
        self.assertIn("off_level", d)          # model.py's, not eagerly re-exported
        self.assertIn("EXISTING_PROGC", d)     # model.py's, read by compare_vbd.py
        self.assertIn("sci", d)                # render.py's number formatter
        self.assertIn("gwd_verdict", d)        # render.py's, not eagerly re-exported

    def test_every_public_sibling_name_is_listed_and_resolves(self):
        d = dir(RE)
        for n in dir(RE.M) + dir(RE.RENDER):
            if n.startswith("_"):
                continue
            self.assertIn(n, d, n)
            self.assertTrue(hasattr(RE, n), n)

    def test_own_facade_names_stay_listed(self):
        for n in ("main", "smoke", "render_only", "M", "RENDER", "CB", "CHAR", "BENCHES",
                  "load_saved", "render_pl", "render_retab", "P", "shutil", "THIS_DIR"):
            self.assertIn(n, dir(RE), n)


class ReadThrough(unittest.TestCase):
    def test_vbd_override_reads_through_cb(self):
        # render.py's common_header reads CB.VBD_EBD_OVERRIDE at call time;
        # the override is armed in place on cell-breakdown-model's model.py
        # by apply_vbd_case, and the CB facade re-exports it dynamically.
        # The facade here must keep resolving CB to that one module object,
        # never a frozen copy of its attributes.
        owner = RE.CB.M
        old = owner.VBD_EBD_OVERRIDE
        try:
            owner.VBD_EBD_OVERRIDE = 3.5
            self.assertIs(RE.CB, RE.M.CB)
            self.assertEqual(RE.CB.VBD_EBD_OVERRIDE, 3.5)
        finally:
            owner.VBD_EBD_OVERRIDE = old
        self.assertEqual(RE.CB.VBD_EBD_OVERRIDE, old)


if __name__ == "__main__":
    unittest.main()
