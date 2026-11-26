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


class QuoteRangePairTests(unittest.TestCase):
    """Pure-function tests for the quote_values numeral matcher (issue #414).

    The three pilot quote formats the matcher must handle: the plain
    '2.49..2.91' band form (with the sibling-interval 'or' in the same
    span), the '(y 2.75..3.17)' pad form, and the cand3 offset form
    '3.28..3.70 = 2.49 + DPAD .. 2.91 + DPAD'.
    """

    def test_three_pilot_quote_formats(self):
        self.assertEqual(
            clc.quote_range_pairs("access 2.49..2.91 or 2.91..3.33, capacitor 4.07..4.49"),
            [(2.49, 2.91), (2.91, 3.33), (4.07, 4.49)],
        )
        self.assertEqual(
            clc.quote_range_pairs("gate pad (y 2.75..3.17) overlaps"),
            [(2.75, 3.17)],
        )
        self.assertEqual(
            clc.quote_range_pairs(
                "access 3.28..3.70 = 2.49 + DPAD .. 2.91 + DPAD at the raised ring"
            ),
            [(3.28, 3.7), (2.49, 2.91)],
        )
        self.assertEqual(
            clc.quote_range_pairs("gate pad (x DX+0.43..DX+0.85, y 2.75..3.17)"),
            [(0.43, 0.85), (2.75, 3.17)],
        )

    def test_range_dots_are_not_eaten_as_a_decimal_point(self):
        self.assertEqual(clc.quote_range_pairs("2.49..2.91"), [(2.49, 2.91)])
        self.assertEqual(clc.quote_range_pairs("2.49 .. 2.91"), [(2.49, 2.91)])
        self.assertEqual(clc.quote_range_pairs("2.49 + DPAD..2.91 + DPAD"), [(2.49, 2.91)])
        self.assertEqual(clc.quote_range_pairs("DX+0.43..DX+0.85"), [(0.43, 0.85)])

    def test_unrelated_numerals_do_not_create_or_break_pairs(self):
        self.assertEqual(
            clc.quote_range_pairs("a 0.42 x 0.42 rect; access 2.49..2.91 done 5"),
            [(2.49, 2.91)],
        )

    def test_non_range_neighbours_are_not_pairs(self):
        self.assertEqual(clc.quote_range_pairs("2.91 or 2.91"), [])
        self.assertEqual(clc.quote_range_pairs("3.70 = 2.49"), [])
        self.assertEqual(clc.quote_range_pairs("no numerals at all"), [])


class QuoteSpellsRangeTests(unittest.TestCase):
    """Tolerance behaviour of the quote_values check (1 nm, matching bbox_matches)."""

    RIGHT = "access 2.49..2.91 or 2.91..3.33, capacitor 4.07..4.49"
    TOL = 0.001

    def test_exact_match(self):
        self.assertTrue(clc.quote_spells_range(self.RIGHT, 2.49, 2.91, self.TOL))
        self.assertTrue(clc.quote_spells_range(self.RIGHT, 2.91, 3.33, self.TOL))
        self.assertTrue(clc.quote_spells_range(self.RIGHT, 4.07, 4.49, self.TOL))

    def test_within_tolerance_matches(self):
        self.assertTrue(clc.quote_spells_range(self.RIGHT, 2.4901, 2.91, self.TOL))
        self.assertTrue(clc.quote_spells_range(self.RIGHT, 2.49, 2.9109, self.TOL))

    def test_beyond_tolerance_fails(self):
        # 0.0011 um off is outside the 1 nm tolerance; 0.04 um is the
        # #391/#401 drift class and must never match.
        self.assertFalse(clc.quote_spells_range(self.RIGHT, 2.4901 + 0.001, 2.91, self.TOL))
        self.assertFalse(clc.quote_spells_range(self.RIGHT, 2.45, 2.91, self.TOL))
        self.assertFalse(clc.quote_spells_range(self.RIGHT, 4.03, 4.49, self.TOL))

    def test_reversed_pair_order_is_not_a_match(self):
        self.assertFalse(clc.quote_spells_range("3.33..2.91", 2.91, 3.33, self.TOL))

    def test_sibling_interval_numerals_do_not_satisfy_a_pair(self):
        """Curator's bypass shape: the shared quote still carries the sibling
        interval's numerals, but no adjacent pair spells the dropped band."""
        sibling_only = "access 2.91..3.33, capacitor 4.07..4.49"
        self.assertFalse(clc.quote_spells_range(sibling_only, 2.49, 2.91, self.TOL))
        self.assertTrue(clc.quote_spells_range(sibling_only, 2.91, 3.33, self.TOL))


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

    def test_quote_values_index_out_of_range_is_exit_2(self):
        """A quote_values entry naming a component absent from bbox_um is a
        malformed claim, rejected fails-closed (issue #414 AC)."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["quote_values"] = {"bottom": 9, "top": 3}
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("quote_values", r.stderr)
        self.assertIn("cand1-amin-g2x-vb-access-north-band", r.stderr)

    def test_quote_values_unknown_component_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["quote_values"] = {"middle": 1, "top": 3}
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("middle", r.stderr)

    def test_quote_values_single_component_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["quote_values"] = {"bottom": 1}
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("at least two", r.stderr)

    def test_quote_values_non_object_is_exit_2(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0]["quote_values"] = "access 2.49..2.91"
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("quote_values", r.stderr)


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
            rec["claims"][0]["layer"] = "37/0"  # Via2 is absent from the bitcell straps.
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("no shapes", r.stdout)

    def _coordinated_edit(self, root: Path, new_quote: str) -> None:
        """The #414 bypass shape: edit README prose AND every claim's
        readme_quote to the same wrong text, leaving bbox_um untouched."""
        readme = root / "layout" / "README.md"
        text = readme.read_text()
        self.assertIn(RIGHT_QUOTE, text)
        readme.write_text(text.replace(RIGHT_QUOTE, new_quote))
        rec = read_claims(root)
        for c in rec["claims"]:
            if c["readme_quote"] == RIGHT_QUOTE:
                c["readme_quote"] = new_quote
        write_claims(root, rec)

    def test_coordinated_readme_and_quote_edit_fails_via_quote_values(self):
        """Issue #414 filer's scenario: README line and the four cand1
        claims' readme_quote all moved to the pre-#405 wrong text while
        bbox_um stays at the measured values. Both #407 ends pass; the
        quote_values end must fail with exit 1 naming the entries."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            self._coordinated_edit(root, WRONG_QUOTE)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        # The two #407 ends pass -- that is the bypass this issue closes.
        self.assertNotIn("readme_quote not found", r.stdout)
        self.assertNotIn("bbox differs from GDS", r.stdout)
        # The correspondence end fails, naming each entry and the numeral.
        self.assertIn("quote_values", r.stdout)
        for cid in (
            "cand1-amin-g2x-vb-access-north-band",
            "cand1-a2x-g2x-vb-access-north-band",
            "cand1-amin-g2x-vb-capacitor-north-band",
            "cand1-a2x-g2x-vb-capacitor-north-band",
        ):
            self.assertIn(f"FAIL {cid}", r.stdout)
        self.assertIn("2.49", r.stdout)
        self.assertIn("4.07", r.stdout)

    def test_sibling_interval_only_edit_fails_the_dropped_claim(self):
        """Curator's variant: a 'fix' that keeps only the sibling interval's
        numbers. The surviving band's claim passes; the dropped band's claim
        must fail at the quote_values end despite its numerals (2.91) still
        being present in the quote as the sibling's endpoint."""
        sibling_only = "access 2.91..3.33, capacitor 4.07..4.49"
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            self._coordinated_edit(root, sibling_only)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL cand1-amin-g2x-vb-access-north-band", r.stdout)
        self.assertIn("quote_values", r.stdout)
        for cid in (
            "cand1-a2x-g2x-vb-access-north-band",
            "cand1-amin-g2x-vb-capacitor-north-band",
            "cand1-a2x-g2x-vb-capacitor-north-band",
        ):
            self.assertNotIn(f"FAIL {cid}", r.stdout)

    def test_deleting_quote_values_from_pilot_claims_fails_coverage_guard(self):
        """Issue #419: every pilot quote spells at least one '<num>..<num>'
        pair, so deleting quote_values -- the 'fix' that #417's failure text
        invites -- must fail the coverage guard, not pass as it did before
        #414."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            for c in rec["claims"]:
                c.pop("quote_values", None)
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("coverage guard", r.stdout)
        pilot = json.loads((ROOT / "layout" / "geometry-claims.json").read_text())
        for c in pilot["claims"]:
            self.assertIn(f"FAIL {c['id']}", r.stdout)

    def test_three_file_coordinated_edit_with_deleted_quote_values_fails(self):
        """Issue #419's measured residual: README prose, the sidecar
        readme_quote and the quote_values field all moved/deleted together
        passed at exit 0 with the prose number wrong; the coverage guard
        must fail it while the two #407 ends still pass."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            self._coordinated_edit(root, WRONG_QUOTE)
            rec = read_claims(root)
            for c in rec["claims"]:
                if c["readme_quote"] == WRONG_QUOTE:
                    c.pop("quote_values", None)
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        # The two #407 ends pass -- the bypass this guard closes.
        self.assertNotIn("readme_quote not found", r.stdout)
        self.assertNotIn("bbox differs from GDS", r.stdout)
        self.assertIn("coverage guard", r.stdout)
        for cid in (
            "cand1-amin-g2x-vb-access-north-band",
            "cand1-a2x-g2x-vb-access-north-band",
            "cand1-amin-g2x-vb-capacitor-north-band",
            "cand1-a2x-g2x-vb-capacitor-north-band",
        ):
            self.assertIn(f"FAIL {cid}", r.stdout)

    def test_interval_claim_without_quote_values_fails_naming_pairs(self):
        """AC: the guard fails a claim with an interval-spelling readme_quote
        and no quote_values, naming every unpinned pair; sibling claims that
        keep the field stay green."""
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = read_claims(root)
            rec["claims"][0].pop("quote_values")
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL cand1-amin-g2x-vb-access-north-band", r.stdout)
        self.assertIn("coverage guard", r.stdout)
        self.assertIn("[(2.49, 2.91), (2.91, 3.33), (4.07, 4.49)]", r.stdout)
        for cid in (
            "cand1-a2x-g2x-vb-access-north-band",
            "cand1-amin-g2x-vb-capacitor-north-band",
            "cand1-a2x-g2x-vb-capacitor-north-band",
        ):
            self.assertNotIn(f"FAIL {cid}", r.stdout)

    def test_pairless_quote_without_quote_values_behaves_as_before(self):
        """The surviving #414 AC, scoped by #419: a claim whose quote pins no
        '<num>..<num>' interval may omit quote_values and behave exactly as
        before."""
        pairless = "gate pad overlaps the lower of the two rings' metal north"
        old = "gate pad (y 2.75..3.17) overlaps the lower of the two rings' metal north"
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            readme = root / "layout" / "README.md"
            text = readme.read_text()
            self.assertIn(old, text)
            readme.write_text(text.replace(old, pairless))
            rec = read_claims(root)
            for c in rec["claims"]:
                if c["readme_quote"] == old:
                    c["readme_quote"] = pairless
                    c.pop("quote_values", None)
            write_claims(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("9 geometry claims checked, 0 failed", r.stdout)

    def test_quote_values_tolerance_boundary_end_to_end(self):
        """A coordinated 0.0001 um nudge (inside the 1 nm tolerance) passes;
        a 0.0011 um nudge (outside) fails at the quote_values end."""
        within = "access 2.4901..2.9109 or 2.91..3.33, capacitor 4.07..4.49"
        beyond = "access 2.4911..2.9109 or 2.91..3.33, capacitor 4.07..4.49"
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            self._coordinated_edit(root, within)
            r = run_check(root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            self._coordinated_edit(root, beyond)
            r = run_check(root)
        self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
        self.assertIn("FAIL cand1-amin-g2x-vb-access-north-band", r.stdout)
        self.assertIn("quote_values", r.stdout)


if __name__ == "__main__":
    unittest.main()
