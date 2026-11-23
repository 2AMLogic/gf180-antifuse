"""Both breakdown-model consumers must honor the annotated SPICE parameter format."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


class BreakdownParamReaders(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        oxide = load_module(ROOT / "scripts/breakdown_oxide_model.py", "breakdown_oxide_model")
        pad = load_module(ROOT / "sim/hv-pad-protection/run_experiment.py", "hv_pad_run")
        cls.readers = {"oxide": oxide.read_params, "pad": pad.read_params}

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "breakdown_params.spice"

    def test_uppercase_param_returns_float_values(self):
        self.path.write_text("* @param c1_bd_tox unit=m provenance=literature -- oxide thickness\n"
                             ".PARAM c1_bd_tox = 8e-9\n")
        for name, read in self.readers.items():
            with self.subTest(reader=name):
                self.assertEqual(read(self.path), {"c1_bd_tox": 8e-9})

    def test_suffixed_literal_reports_all_parser_errors(self):
        self.path.write_text("* @param c1_bd_tox unit=m provenance=literature -- oxide thickness\n"
                             ".param c1_bd_tox = 7.9n\n"
                             ".param bd_ebd = 1e9\n")
        for name, read in self.readers.items():
            with self.subTest(reader=name):
                with self.assertRaises(ValueError) as error:
                    read(self.path)
                self.assertIn("breakdown_params.spice:2: c1_bd_tox: value '7.9n' is not a plain number",
                              str(error.exception))
                self.assertIn("breakdown_params.spice:3: .param bd_ebd has no `* @param` annotation",
                              str(error.exception))
