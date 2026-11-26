"""Tests for design/check-geometry-basis.py (unittest; also runs under pytest).

The script is hyphen-named and not importable, so parser-level cases load it
via importlib and exit-code cases run it as a subprocess with --root pointed
at a copy of tests/fixtures/geometry-basis.
"""
import importlib.util
import json
import re
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
        self.assertIn("4 divergences", r.stdout)

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


class RatifiedLevelsMatchSpecTests(unittest.TestCase):
    """The gate's hard-coded ratified table is pinned to the spec.

    A level in RATIFIED_CAP_MIN_UM that disagrees with
    spec/capacitor-geometry-decision.md fails here (and, via the derived
    owner/status compared against the committed record, turns the gate red on
    the next restatement) - the spec is the source of truth and the gate does
    not get to relax it. Parsing the spec happens here in the suite only; the
    gate itself stays stdlib-runtime-only with no markdown parsing.
    """

    REGION_ROW_RE = re.compile(
        r"^\|\s*(?:I|II|III)\s*\|\s*`(\w+)`\s*\|\s*([\d.]+) x ([\d.]+)\s*\|"
        r"\s*[\d.]+\s*\|\s*([\d.]+) x ([\d.]+)\s*\|")

    def spec_rows(self) -> dict[str, tuple[float, float, float, float]]:
        spec = (ROOT / "spec" / "capacitor-geometry-decision.md").read_text()
        rows: dict[str, tuple[float, float, float, float]] = {}
        for line in spec.splitlines():
            m = self.REGION_ROW_RE.match(line)
            if m:
                dev, w, l, w2, l2 = m.groups()
                self.assertNotIn(dev, rows, f"duplicate region row for {dev}")
                rows[dev] = (float(w), float(l), float(w2), float(l2))
        return rows

    def test_all_three_devices_rated(self):
        rows = self.spec_rows()
        self.assertEqual(set(rows), set(cgb.RATIFIED_CAP_MIN_UM))

    def test_table_matches_spec_minimum_levels(self):
        for dev, (w, l, _w2, _l2) in self.spec_rows().items():
            self.assertEqual(cgb.RATIFIED_CAP_MIN_UM[dev], (w, l), dev)

    def test_spec_2x_doubles_w_at_fixed_l_matching_gate_convention(self):
        for dev, (w, l, w2, l2) in self.spec_rows().items():
            self.assertEqual(w2, 2 * w, dev)
            self.assertEqual(l2, l, dev)
            # the gate derives the 2x level the same way sim_geometry does
            self.assertEqual(cgb.ratified_cap_value_um(cgb.RATIFIED_CAP_MIN_UM[dev], "2x", "cap_w"), w2 * 1e-6, dev)
            self.assertEqual(cgb.ratified_cap_value_um(cgb.RATIFIED_CAP_MIN_UM[dev], "2x", "cap_l"), l * 1e-6, dev)


class CapOwnerDerivationTests(unittest.TestCase):
    """Per-entry owner/status derivation against the ratified level."""

    RAT_NMOS03 = cgb.RATIFIED_CAP_MIN_UM["cap_nmos_03v3"]  # 1.0 x 0.28 um

    def test_drawn_stale_sim_conforms_is_redraw_owned(self):
        status, owner = cgb.cap_owner_status(1e-6, 0.42e-6, 1e-6)
        self.assertEqual(status, cgb.STATUS_DRAWN_STALE)
        self.assertEqual(owner, cgb.REDRAW_OWNER)
        self.assertIn("#296", owner)

    def test_drawn_conforms_sim_stale_is_regeneration_owned_not_redraw(self):
        status, owner = cgb.cap_owner_status(1e-6, 0.28e-6, 0.28e-6)
        self.assertEqual(status, cgb.STATUS_SIM_STALE)
        self.assertEqual(owner, cgb.REGEN_OWNER)
        self.assertNotIn("#296", owner)
        self.assertIn("design/README.md open item 1(a)", owner)

    def test_both_stale_names_both(self):
        status, owner = cgb.cap_owner_status(1e-6, 0.56e-6, 0.70e-6)
        self.assertEqual(status, cgb.STATUS_BOTH_STALE)
        self.assertEqual(owner, cgb.BOTH_OWNERS)
        self.assertIn("#296", owner)
        self.assertIn("design/README.md open item 1(a)", owner)

    def test_no_closed_issue_named_as_live_owner(self):
        for owner in (cgb.REDRAW_OWNER, cgb.REGEN_OWNER, cgb.BOTH_OWNERS):
            self.assertNotIn("#292", owner)
            self.assertNotIn("#294", owner)

    def test_min_level_ratified_value_metres(self):
        self.assertEqual(cgb.ratified_cap_value_um(self.RAT_NMOS03, "min", "cap_w"), 1.0e-6)
        self.assertEqual(cgb.ratified_cap_value_um(self.RAT_NMOS03, "min", "cap_l"), 0.28e-6)


class DerivedOwnerStatusRecordTests(unittest.TestCase):
    """Integration: the fixture record carries the derived attribution, and a
    record that claims a level conforms when it disagrees with the ratified
    spec levels is a failure, not a silent pass."""

    def test_regen_owned_entry_not_attributed_to_redraw(self):
        with tempfile.TemporaryDirectory() as d:
            rec = record_of(make_tree(Path(d)))
        e = next(e for e in rec["divergences"]
                 if e["cell"] == "cell_candidate1_A2x" and e["parameter"] == "cap_l")
        self.assertEqual(e["owner"], cgb.REGEN_OWNER)
        self.assertNotIn("#296", e["owner"])

    def test_access_entries_untouched(self):
        with tempfile.TemporaryDirectory() as d:
            rec = record_of(make_tree(Path(d)))
        for e in rec["divergences"]:
            if e["parameter"].startswith("acc"):
                self.assertEqual(e["status"], "unresolved", e)
                self.assertEqual(e["owner"], cgb.ACC_OWNER, e)

    def test_record_claiming_conformance_for_spec_disagreeing_level_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = record_of(root)
            # cell_candidate1_A2x cap_l: simulated 1.0 um disagrees with the
            # ratified 0.28 um. Attributing it to the redraw - whose premise
            # is that the simulated side conforms - must fail, not pass.
            for e in rec["divergences"]:
                if e["cell"] == "cell_candidate1_A2x" and e["parameter"] == "cap_l":
                    e["owner"] = cgb.REDRAW_OWNER
                    e["status"] = cgb.STATUS_DRAWN_STALE
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale record entry", r.stdout)
        self.assertIn("cell_candidate1_A2x cap_l", r.stdout)

    def test_stale_recorded_owner_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = record_of(root)
            for e in rec["divergences"]:
                if e["cell"] == "cell_candidate2" and e["parameter"] == "cap_w":
                    e["owner"] = "someone else"
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale record entry", r.stdout)
        self.assertIn("owner now", r.stdout)

    def test_stale_recorded_gap_status_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            rec = record_of(root)
            rec["coverage_gaps"][0]["status"] = "unresolved"
            write_record(root, rec)
            r = run_check(root)
        self.assertEqual(r.returncode, 1)
        self.assertIn("stale record gap", r.stdout)
        self.assertIn("status now", r.stdout)

    def test_unknown_capacitor_device_is_fatal(self):
        with tempfile.TemporaryDirectory() as d:
            root = make_tree(Path(d))
            nl = root / "design" / "netlists" / "cell_candidate1.spice"
            nl.write_text(nl.read_text().replace("cap_nmos_03v3", "cap_unrated_9v9"))
            r = run_check(root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("no ratified capacitor level", r.stderr)

    def test_real_tree_record_round_trips_byte_for_byte(self):
        emitted = run_check(None, "--emit-record")
        self.assertEqual(emitted.returncode, 0, emitted.stderr)
        committed = (ROOT / "design" / "geometry-basis.json").read_text()
        self.assertEqual(emitted.stdout, committed)


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
            emitted = run_check(root, "--emit-record")
            self.assertEqual(emitted.returncode, 0, emitted.stderr)
            rec = json.loads(emitted.stdout)
            self.assertEqual(rec["divergences"], [])
            self.assertTrue(rec["coverage_gaps"])
            (root / "design" / "geometry-basis.json").write_text(emitted.stdout)
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
