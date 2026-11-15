"""Tests for design/check-geometry-basis.py (unittest; also runs under pytest).

The script is hyphen-named and not importable, so parser-level cases load it
via importlib and exit-code cases run it as a subprocess with --root pointed
at a copy of tests/fixtures/geometry-basis.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPT = ROOT / "design" / "check-geometry-basis.py"
FIX = ROOT / "tests" / "fixtures" / "geometry-basis"

_spec = importlib.util.spec_from_file_location("check_geometry_basis", SCRIPT)
cgb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cgb)


def make_tree(tmp: Path) -> Path:
    root = tmp / "repo"
    shutil.copytree(FIX / "design", root / "design")
    shutil.copytree(FIX / "layout", root / "layout")
    return root


def run_check(root=None, *extra):
    cmd = [sys.executable, "-I", str(SCRIPT), *extra]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True)


def record_of(root: Path) -> dict:
    return json.loads((root / "design" / "geometry-basis.json").read_text())


def write_record(root: Path, rec: dict) -> None:
    (root / "design" / "geometry-basis.json").write_text(json.dumps(rec, indent=2))


class CellNameParserTests(unittest.TestCase):
    def test_base_form_is_min_min(self):
        self.assertEqual(cgb.parse_cell_name("cell_candidate1"), (1, "min", "min"))

    def test_both_axes_named(self):
        self.assertEqual(cgb.parse_cell_name("cell_candidate1_A2x_G2x"), (1, "2x", "2x"))
        self.assertEqual(cgb.parse_cell_name("cell_candidate1_A2x_Gmin"), (1, "2x", "min"))
        self.assertEqual(cgb.parse_cell_name("cell_candidate1_Amin_G2x"), (1, "min", "2x"))
        self.assertEqual(cgb.parse_cell_name("cell_candidate3_Amin_G2x"), (3, "min", "2x"))

    def test_single_axis_form_absent_token_is_min(self):
        self.assertEqual(cgb.parse_cell_name("cell_candidate1_A2x"), (1, "2x", "min"))
        self.assertEqual(cgb.parse_cell_name("cell_candidate1_G2x"), (1, "min", "2x"))

    def test_explicit_min_min(self):
        self.assertEqual(cgb.parse_cell_name("cell_candidate1_Amin_Gmin"), (1, "min", "min"))

    def test_unparseable_names_rejected(self):
        for name in ("cell_candidate1_bogus", "cell_candidate1_A2x_G2x_extra",
                     "cell_candidateX", "slice_i_ii"):
            self.assertIsNone(cgb.parse_cell_name(name), name)


class ExitCodeTests(unittest.TestCase):
    def test_real_tree_passes(self):
        r = run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_fixture_measured_set_equals_record_passes(self):
        with tempfile.TemporaryDirectory() as d:
            r = run_check(make_tree(Path(d)))
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("3 divergences", r.stdout)

    def test_unrecorded_divergence_from_tree_edit_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            ref = root / "layout" / "cell_candidate2" / "lvs_reference.spice"
            ref.write_text(ref.read_text().replace("L=0.60u", "L=0.70u"))
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unrecorded divergence", r.stdout)
        self.assertIn("cell_candidate2", r.stdout)
        self.assertIn("acc_l", r.stdout)

    def test_record_entry_removed_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = record_of(root)
            rec["divergences"] = [e for e in rec["divergences"]
                                  if not (e["cell"] == "cell_candidate2" and e["parameter"] == "cap_l")]
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unrecorded divergence", r.stdout)
        self.assertIn("cap_l", r.stdout)

    def test_stale_recorded_numbers_fail(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = record_of(root)
            for e in rec["divergences"]:
                if e["cell"] == "cell_candidate2" and e["parameter"] == "acc_w":
                    e["simulated"] = 6e-07
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale record entry", r.stdout)
        self.assertIn("cell_candidate2 acc_w", r.stdout)

    def test_stale_entry_for_cell_gone_from_tree_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            shutil.rmtree(root / "layout" / "cell_candidate2")
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale record entry", r.stdout)
        self.assertIn("cell_candidate2", r.stdout)

    def test_new_drawn_cell_discovered_by_glob_and_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            new = root / "layout" / "cell_candidate2_A2x_G2x"
            new.mkdir()
            (new / "lvs_reference.spice").write_text(
                ".subckt cell_candidate2_A2x_G2x BL WL PL VB\n"
                "XM1 BL WL CN VB nfet_10v0_asym L=0.60u W=100u nf=1 m=1\n"
                "XC1 CN PL cap_nmos_06v0 c_width=4e-6 c_length=1e-6 m=1\n"
                ".ends\n")
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("cell_candidate2_A2x_G2x", r.stdout)
        self.assertIn("unrecorded divergence", r.stdout)

    def test_missing_lvs_reference_reported_not_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            (root / "layout" / "cell_candidate2" / "lvs_reference.spice").unlink()
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("lvs_reference.spice", r.stdout)
        self.assertIn("cell_candidate2", r.stdout)

    def test_unparseable_cell_name_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            bogus = root / "layout" / "cell_candidate2_bogus"
            bogus.mkdir()
            (bogus / "lvs_reference.spice").write_text(
                ".subckt cell_candidate2_bogus BL WL PL VB\n.ends\n")
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("unparseable bitcell cell name", r.stdout)

    def test_missing_instance_line_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            ref = root / "layout" / "cell_candidate2" / "lvs_reference.spice"
            ref.write_text(ref.read_text().replace("XM1", "*XM1"))
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no XM1 instance line", r.stdout)

    def test_missing_record_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            (root / "design" / "geometry-basis.json").unlink()
            r = run_check(root)
        self.assertEqual(r.returncode, 2)

    def test_malformed_record_json_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            (root / "design" / "geometry-basis.json").write_text("{not json")
            r = run_check(root)
        self.assertEqual(r.returncode, 2)

    def test_record_without_divergences_key_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            write_record(root, {"coverage_gaps": []})
            r = run_check(root)
        self.assertEqual(r.returncode, 2)

    def test_record_entry_missing_owner_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = record_of(root)
            del rec["divergences"][0]["owner"]
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("owner", r.stderr)


class EdgeCaseTests(unittest.TestCase):
    def test_multifinger_access_compared_at_total_width(self):
        rec = json.loads((FIX / "design" / "geometry-basis.json").read_text())
        e = next(e for e in rec["divergences"]
                 if e["cell"] == "cell_candidate2" and e["parameter"] == "acc_w")
        self.assertEqual(e["drawn"], 8e-06)
        self.assertEqual(e["ratio"], 16.0)
        self.assertIn("nf=2", e.get("drawn_note", ""))

    def test_scale_suffix_and_exponent_literals_compare_equal(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            ref = root / "layout" / "cell_candidate2" / "lvs_reference.spice"
            ref.write_text(ref.read_text().replace("c_width=0.42u", "c_width=4.2e-7"))
            r = run_check(root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_zero_divergence_tree_passes_with_only_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            tmp = Path(d)
            root = tmp / "repo"
            shutil.copytree(FIX / "design", root / "design")
            (root / "design" / "netlists" / "cell_candidate2.spice").unlink()
            (root / "layout").mkdir()
            shutil.copytree(FIX / "layout" / "cell_candidate1", root / "layout" / "cell_candidate1")
            shutil.copytree(FIX / "layout" / "cell_candidate1_A2x_G2x",
                            root / "layout" / "cell_candidate1_A2x_G2x")
            rec = record_of(root)
            rec["divergences"] = []
            rec["coverage_gaps"] = [g for g in rec["coverage_gaps"] if g["candidate"] == 1]
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_emit_record_output_restates_a_green_record(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            emitted = run_check(root, "--emit-record")
            self.assertEqual(emitted.returncode, 0, emitted.stderr)
            (root / "design" / "geometry-basis.json").write_text(emitted.stdout)
            r = run_check(root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
