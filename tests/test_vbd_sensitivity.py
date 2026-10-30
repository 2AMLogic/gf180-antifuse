"""Tests for the V_bd sensitivity override (issue #130). unittest; no simulator.

The override must (a) leave the parsed shared parameters and the parameter file alone,
(b) set bd_ebd per candidate to sourced V_bd / tox, (c) reach the generated deck after the
wrapper include, (d) be absent from the assumed-V_bd decks, and (e) tag the record.
"""
import sys
import tempfile
import types
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
from harness.modload import load_module  # noqa: E402


def _load():
    return load_module(ROOT / "sim" / "cell-breakdown-model" / "run_experiment.py", "bdm_vbd_run_experiment")


X = _load()
BY_N = {c.n: c for c in X.CHAR.CANDIDATES}
PARAMS, _ERR = X.CHECK.parse_params((X.BD_DIR / "breakdown_params.spice").read_text())


def fake_pdk(tmp: Path):
    dn = tmp / "design.ngspice"
    dn.write_text("* comment\n.option scale=1.0u\n")
    return types.SimpleNamespace(design_ngspice=dn, variant="gf180mcuD", variant_dir=tmp, revision="test")


class VbdSensitivity(unittest.TestCase):
    def tearDown(self):
        X.apply_vbd_case(PARAMS, None, 1)

    def test_params_file_still_clean(self):
        self.assertEqual(_ERR, [])
        self.assertEqual(PARAMS["bd_ebd"]["provenance"], "assumed")
        self.assertEqual(PARAMS["bd_ebd"]["value"], 1.0e9)

    def test_vbd_ref_equals_sourced_value_per_candidate(self):
        for case, table in X.SOURCED_VBD.items():
            for n, vbd in table.items():
                p = X.apply_vbd_case(PARAMS, case, n)
                self.assertAlmostEqual(X.vbd_ref(BY_N[n], p), vbd, places=9, msg=(case, n))
                self.assertEqual(p["bd_ebd"]["provenance"], "sensitivity")
                self.assertEqual(PARAMS["bd_ebd"]["value"], 1.0e9, "parsed shared parameter must not be mutated")

    def test_sourced_values_match_the_evidence_note(self):
        note = (ROOT / "docs" / "breakdown-vbd-sources.md").read_text()
        for n, (typ, floor) in {1: (9, 7), 2: (16, 12), 3: (8.8, 7)}.items():
            self.assertEqual((X.SOURCED_VBD["typ"][n], X.SOURCED_VBD["floor"][n]), (typ, floor))
        self.assertIn("| 1 | thin 3.3 V, NMOS cap", note)

    def test_override_reaches_deck_after_wrapper_include(self):
        tmp = Path(tempfile.mkdtemp())
        cand = BY_N[2]
        p = X.apply_vbd_case(PARAMS, "floor", 2)
        hdr = X.body_header(fake_pdk(tmp), tmp, "t", cand, "trigger", "/opt/pdk/gf180mcuD")
        inc = hdr.index(".include")
        self.assertIn(f".param bd_ebd = {p['bd_ebd']['value']:.9g}", hdr[inc:])
        self.assertAlmostEqual(p["bd_ebd"]["value"], 12.0 / 1.52e-8, delta=1.0)

    def test_assumed_run_has_no_override(self):
        tmp = Path(tempfile.mkdtemp())
        X.apply_vbd_case(PARAMS, "typ", 1)
        X.apply_vbd_case(PARAMS, None, 1)
        hdr = X.body_header(fake_pdk(tmp), tmp, "t", BY_N[1], "trigger", "/opt/pdk/gf180mcuD")
        self.assertNotIn("bd_ebd", hdr)

    def test_record_is_tagged_as_sensitivity(self):
        p = X.apply_vbd_case(PARAMS, "typ", 3)
        txt = X.tag_record("# Record x\n\n- **Record ID**: x\n- **Claim**: y\n", X.sensitivity_block("typ", 3, p))
        lines = txt.splitlines()
        self.assertTrue(lines[3].startswith("- **V_bd SENSITIVITY POINT (`typ`), NOT a parameter update**"))
        self.assertIn("8.8 V", lines[3])
        self.assertEqual(X.tag_record("a\n- **Record ID**: x\n", ""), "a\n- **Record ID**: x\n")


if __name__ == "__main__":
    unittest.main()
