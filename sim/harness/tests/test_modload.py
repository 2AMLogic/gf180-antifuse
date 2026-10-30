"""Targeted tests for sim/harness/modload.py.  Run:

    python3 -m unittest discover -s sim/harness/tests
"""

import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from harness.modload import load_module  # noqa: E402


class LoadModule(unittest.TestCase):
    def _write(self, text):
        d = tempfile.TemporaryDirectory()
        self.addCleanup(d.cleanup)
        p = Path(d.name) / "m.py"
        p.write_text(text)
        return p

    def test_loads_and_registers(self):
        mod = load_module(self._write("X = 7\n"), "modload_probe_a")
        self.addCleanup(sys.modules.pop, "modload_probe_a", None)
        self.assertEqual(mod.X, 7)
        self.assertIs(sys.modules["modload_probe_a"], mod)

    def test_registered_before_exec(self):
        mod = load_module(self._write("import sys\nSELF = sys.modules[__name__]\n"), "modload_probe_b")
        self.addCleanup(sys.modules.pop, "modload_probe_b", None)
        self.assertIs(mod.SELF, mod)

    def test_missing_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            load_module(HERE / "nope.py", "modload_probe_c")


if __name__ == "__main__":
    unittest.main()
