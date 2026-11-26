"""Facade introspection tests for sim/cell-breakdown-model (issue #465).

The #464 split moved the library surface into model.py + render.py and left
run_experiment.py as the CLI facade re-exporting both through a module
``__getattr__``. ``dir()`` does not consult ``__getattr__``, so the facade
also defines ``__dir__`` (#465): these tests pin that parity -- every public
name of the two library modules is visible to ``dir()`` and resolves by
``getattr`` through the facade (the pre-split single file exposed all of
them), and module state the library mutates in place still reads through to
the owning module. unittest; also runs under pytest. No simulator is invoked.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "cell-breakdown-model" / "run_experiment.py", "bdm_facade_run_experiment")


RE = _load()


class DirParity(unittest.TestCase):
    def test_dir_does_not_raise_and_is_sorted(self):
        d = dir(RE)
        self.assertIsInstance(d, list)
        self.assertEqual(d, sorted(d))

    def test_dir_lists_reexported_library_names(self):
        d = dir(RE)
        self.assertIn("derive", d)             # model.py's, read by the CLI's smoke()
        self.assertIn("sensitivity_block", d)  # model.py's, called by the CLI
        self.assertIn("render_any", d)         # render.py's, called by the CLI
        self.assertIn("make_request", d)       # benches.py's, called by the CLI

    def test_every_public_sibling_name_is_listed_and_resolves(self):
        d = dir(RE)
        for n in dir(RE.M) + dir(RE.DECKS) + dir(RE.RENDER):
            if n.startswith("_"):
                continue
            self.assertIn(n, d, n)
            self.assertTrue(hasattr(RE, n), n)

    def test_own_facade_names_stay_listed(self):
        for n in ("main", "smoke", "run_klt", "KLT_CMD", "M", "DECKS", "RENDER"):
            self.assertIn(n, dir(RE), n)


class ReadThrough(unittest.TestCase):
    def test_vbd_override_reads_through_facade(self):
        # `VBD_EBD_OVERRIDE` is armed in place in model.py (apply_vbd_case);
        # the facade must neither freeze it at load time nor hide it from dir().
        old = RE.M.VBD_EBD_OVERRIDE
        try:
            RE.M.VBD_EBD_OVERRIDE = 3.5
            self.assertIn("VBD_EBD_OVERRIDE", dir(RE))
            self.assertEqual(RE.VBD_EBD_OVERRIDE, 3.5)
        finally:
            RE.M.VBD_EBD_OVERRIDE = old
        self.assertEqual(RE.VBD_EBD_OVERRIDE, old)


if __name__ == "__main__":
    unittest.main()
