"""Facade introspection tests for sim/program-read-legs (issue #476).

run_experiment.py is the CLI facade over model.py + render.py, re-exporting
their surface through a module ``__getattr__`` (plus a subset eagerly at
import). ``dir()`` does not consult ``__getattr__``, so the facade also
defines ``__dir__`` (#476, the same fix #465 applied to
cell-breakdown-model): these tests pin that parity -- every public name of
the two library modules is visible to ``dir()`` and resolves by ``getattr``
through the facade, and the facade's own names (eagerly re-exported or
defined here) stay listed. unittest; also runs under pytest. No simulator
is invoked.
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "program-read-legs" / "run_experiment.py", "prl_facade_run_experiment")


RE = _load()


class DirParity(unittest.TestCase):
    def test_dir_does_not_raise_and_is_sorted(self):
        d = dir(RE)
        self.assertIsInstance(d, list)
        self.assertEqual(d, sorted(d))

    def test_dir_lists_reexported_library_names(self):
        d = dir(RE)
        self.assertIn("corner_label", d)   # model.py's, not eagerly re-exported
        self.assertIn("cp_lower", d)       # model.py's Clopper-Pearson lower bound
        self.assertIn("sci", d)            # render.py's number formatter

    def test_every_public_sibling_name_is_listed_and_resolves(self):
        d = dir(RE)
        for n in dir(RE.M) + dir(RE.RENDER):
            if n.startswith("_"):
                continue
            self.assertIn(n, d, n)
            self.assertTrue(hasattr(RE, n), n)

    def test_own_facade_names_stay_listed(self):
        for n in ("main", "run_klt", "run_mc", "WORK", "M", "RENDER", "B", "MC_N", "bench_defs"):
            self.assertIn(n, dir(RE), n)


if __name__ == "__main__":
    unittest.main()
