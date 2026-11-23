"""Facade introspection tests for sim/programming-yield (issue #476).

The #466 split moved the library surface into model.py + render.py and left
run_experiment.py as the CLI facade re-exporting both through a module
``__getattr__``. ``dir()`` does not consult ``__getattr__``, so the facade
also defines ``__dir__`` (#476, the same fix #465 applied to
cell-breakdown-model): these tests pin that parity -- every public name of
the two library modules is visible to ``dir()`` and resolves by ``getattr``
through the facade (the pre-split single file exposed all of them), and the
``PARAMS`` dict main() updates in place still reads through to model.py.
unittest; also runs under pytest. No simulator is invoked.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "programming-yield" / "run_experiment.py", "py_facade_run_experiment")


RE = _load()


class DirParity(unittest.TestCase):
    def test_dir_does_not_raise_and_is_sorted(self):
        d = dir(RE)
        self.assertIsInstance(d, list)
        self.assertEqual(d, sorted(d))

    def test_dir_lists_reexported_library_names(self):
        d = dir(RE)
        self.assertIn("wilson", d)          # model.py's binomial interval helper
        self.assertIn("load_run", d)        # model.py's, called by the CLI's render_only()
        self.assertIn("render_record", d)   # render.py's, called by the CLI

    def test_every_public_sibling_name_is_listed_and_resolves(self):
        d = dir(RE)
        for n in dir(RE.M) + dir(RE.RENDER):
            if n.startswith("_"):
                continue
            self.assertIn(n, d, n)
            self.assertTrue(hasattr(RE, n), n)

    def test_own_facade_names_stay_listed(self):
        for n in ("main", "smoke", "render_only", "run_group", "snapshot",
                  "KLT_CMD", "M", "RENDER", "BM", "CHAR", "CHECK", "BD_DIR"):
            self.assertIn(n, dir(RE), n)


class ReadThrough(unittest.TestCase):
    def test_params_update_reads_through_facade(self):
        # main() updates model.py's PARAMS dict in place; the facade must
        # keep resolving PARAMS through __getattr__ to that same dict, not
        # freeze a copy at load time.
        RE.M.PARAMS["_facade_probe"] = 1.25
        try:
            self.assertIn("PARAMS", dir(RE))
            self.assertIs(RE.PARAMS, RE.M.PARAMS)
            self.assertEqual(RE.PARAMS["_facade_probe"], 1.25)
        finally:
            del RE.M.PARAMS["_facade_probe"]
        self.assertNotIn("_facade_probe", RE.PARAMS)


if __name__ == "__main__":
    unittest.main()
