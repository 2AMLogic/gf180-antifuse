"""Tests for scripts/check_layout_geometry_claims.py (unittest; also pytest).

The script is not an importable package module, so parser-level cases load
it via importlib and exit-code cases run it as a subprocess with --root
pointed at a scratch copy of the pilot's files (README, sidecar, three
committed GDS cells). Cases that measure a GDS need the `klayout` binary
and skip with an explicit message when it is absent; the fail-closed and
record-validation cases do not need it and always run.
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
SCRIPT = ROOT / "scripts" / "check_layout_geometry_claims.py"
CLAIM_CELLS = (
    "cell_candidate1_Amin_G2x",
    "cell_candidate1_A2x_G2x",
    "cell_candidate3_Amin_G2x",
)
KLAYOUT = shutil.which("klayout")

_spec = importlib.util.spec_from_file_location("check_layout_geometry_claims", SCRIPT)
clc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(clc)

# The pre-#405 defective candidate-1 bullet text (issue #401, fixed by PR
# #405): three band bottoms quoted 0.04 um low. The README-drift test
# replays exactly this regression.
WRONG_QUOTE = "access 2.45..2.91 or 2.87..3.33, capacitor 4.03..4.49"
RIGHT_QUOTE = "access 2.49..2.91 or 2.91..3.33, capacitor 4.07..4.49"


def make_tree(tmp: Path) -> Path:
    root = tmp / "repo"
    (root / "layout").mkdir(parents=True)
    shutil.copy2(ROOT / "layout" / "README.md", root / "layout" / "README.md")
    shutil.copy2(ROOT / "layout" / "geometry-claims.json", root / "layout" / "geometry-claims.json")
    for cell in CLAIM_CELLS:
        shutil.copytree(ROOT / "layout" / cell, root / "layout" / cell)
    return root


def run_check(root=None, env=None):
    cmd = [sys.executable, "-I", str(SCRIPT)]
    if root is not None:
        cmd += ["--root", str(root)]
    return subprocess.run(cmd, capture_output=True, text=True, env=env)


def read_claims(root: Path) -> dict:
    return json.loads((root / "layout" / "geometry-claims.json").read_text())


def write_claims(root: Path, rec: dict) -> None:
    (root / "layout" / "geometry-claims.json").write_text(json.dumps(rec, indent=2))


class NormalizeWsTests(unittest.TestCase):
    def test_line_wraps_collapse_to_single_spaces(self):
        self.assertEqual(
            clc.normalize_ws("gate pad (x DX+0.43..DX+0.85,\n  y 2.75..3.17)"),
            "gate pad (x DX+0.43..DX+0.85, y 2.75..3.17)",
        )

    def test_leading_and_trailing_whitespace_stripped(self):
        self.assertEqual(clc.normalize_ws("  a\t b  \n"), "a b")


class BboxMatchTests(unittest.TestCase):
    def test_exact_and_within_tolerance_match(self):
        self.assertTrue(clc.bbox_matches([1.1, 2.49, 5.05, 2.91], [1.1, 2.49, 5.05, 2.91], 0.001))
        self.assertTrue(clc.bbox_matches([1.1, 2.4909, 5.05, 2.91], [1.1, 2.49, 5.05, 2.91], 0.001))

    def test_beyond_tolerance_fails(self):
        # The 0.04 um drift class from #391/#401 must not match at 1 nm.
        self.assertFalse(clc.bbox_matches([1.1, 2.45, 5.05, 2.91], [1.1, 2.49, 5.05, 2.91], 0.001))
        self.assertFalse(clc.bbox_matches([1.1, 2.4901 + 0.001, 5.05, 2.91], [1.1, 2.49, 5.05, 2.91], 0.001))

    def test_wrong_arity_never_matches(self):
        self.assertFalse(clc.bbox_matches([1.1, 2.49, 5.05], [1.1, 2.49, 5.05, 2.91], 0.001))


class RecordValidationTests(unittest.TestCase):
    """Malformed records are exit-2 'cannot run'; these need no klayout."""

    def test_missing_record_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d) / "repo"
            (root / "layout").mkdir(parents=True)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("not found", r.stderr)

    def test_duplicate_claim_id_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"].append(dict(rec["claims"][0]))
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("duplicate claim id", r.stderr)

    def test_bad_layer_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["layer"] = "metal1"
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("layer/datatype", r.stderr)

    def test_bad_bbox_arity_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["bbox_um"] = [1.1, 2.49, 5.05]
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("4 numbers", r.stderr)


class KlayoutAbsentFailsClosedTests(unittest.TestCase):
    def test_no_klayout_on_path_is_exit_2_not_skip(self):
        env = {"PATH": ""}
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            r = run_check(root, env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("klayout not found", r.stderr)


@unittest.skipIf(KLAYOUT is None, "klayout binary not on PATH; GDS measurement cannot run")
class MeasurementTests(unittest.TestCase):
    def test_real_tree_passes(self):
        r = run_check()
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("9 geometry claims checked, 0 failed", r.stdout)

    def test_scratch_copy_passes(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            r = run_check(root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_pre405_readme_regression_fails_naming_entries(self):
        """Replay of the #401/#405 defect: the pre-correction band bottoms
        (0.04 um low) are absent prose, so the prose end must fail."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            readme = root / "layout" / "README.md"
            text = readme.read_text()
            self.assertIn(RIGHT_QUOTE, text)
            readme.write_text(text.replace(RIGHT_QUOTE, WRONG_QUOTE))
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        for cid in (
            "cand1-amin-g2x-vb-access-north-band",
            "cand1-a2x-g2x-vb-access-north-band",
            "cand1-amin-g2x-vb-capacitor-north-band",
            "cand1-a2x-g2x-vb-capacitor-north-band",
        ):
            self.assertIn(cid, r.stdout)
        self.assertIn("readme_quote not found", r.stdout)

    def test_bbox_drift_fails_naming_entry(self):
        """The artifact end: claim a 0.04 um-off bbox; the committed GDS must
        contradict it."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["bbox_um"] = [1.1, 2.45, 5.05, 2.91]
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("cand1-amin-g2x-vb-access-north-band", r.stdout)
        self.assertIn("bbox differs from GDS", r.stdout)

    def test_missing_cell_gds_fails_naming_entry(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["cell"] = "cell_candidate9_Amin_G2x"
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("GDS not found", r.stdout)

    def test_missing_subcell_fails_naming_entry(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["subcell"] = "nope__nope"
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("subcell", r.stdout)
        self.assertIn("not found", r.stdout)

    def test_layer_with_no_shapes_fails_naming_entry(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["layer"] = "35/0"
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no shapes", r.stdout)


if __name__ == "__main__":
    unittest.main()
