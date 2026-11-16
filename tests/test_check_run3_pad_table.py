"""Tests for scripts/check_run3_pad_table.py (unittest; also runs under pytest)."""
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_run3_pad_table as cr  # noqa: E402

sys.path.insert(0, str(ROOT / "layout" / "run3_top"))
import generate_run3_top as gen  # noqa: E402

FLOORPLAN = ROOT / "spec" / "run3-test-chip-floorplan.md"
DECISION = ROOT / "spec" / "capacitor-geometry-decision.md"
PAD_TABLE = ROOT / "layout" / "run3_top" / "pad_table.json"
NETLIST = ROOT / "layout" / "run3_top" / "run3_top.spice"


def committed():
    """(floorplan record text, parsed pad_table.json, netlist text), all committed."""
    return (FLOORPLAN.read_text(), json.loads(PAD_TABLE.read_text()),
            NETLIST.read_text())


def drawn_refs():
    return {p.parent.name: p.read_text()
            for p in sorted((ROOT / "layout").glob("cell_*/lvs_reference.spice"))}


class CommittedArtifactsTests(unittest.TestCase):
    """The shipped artifacts must pass the check on a clean tree."""

    def test_committed_pair_agrees_with_floorplan_record(self):
        rec, table, net = committed()
        self.assertEqual(cr.check_pad_table(rec, table, net), [])

    def test_committed_netlist_geometry_matches_its_sources(self):
        _, _, net = committed()
        self.assertEqual(
            cr.check_geometry(net, DECISION.read_text(), drawn_refs()), [])

    def test_pad_table_covers_48_slots(self):
        _, table, _ = committed()
        self.assertEqual([p["pad"] for p in table["pads"]],
                         [f"L{i:02d}" for i in range(1, 49)])

    def test_unused_pads_need_no_port(self):
        # Directional check: UNUSED_1..3 have no netlist port and must not fail.
        _, table, net = committed()
        ports = cr.parse_netlist(net)["ports"]
        self.assertNotIn("UNUSED_1", ports)
        rec, _, _ = committed()
        self.assertEqual(cr.check_pad_table(rec, table, net), [])


class GeneratorTests(unittest.TestCase):
    def test_output_is_deterministic(self):
        self.assertEqual(gen.emit_netlist(), gen.emit_netlist())
        self.assertEqual(gen.emit_pad_table(), gen.emit_pad_table())

    def test_committed_artifacts_match_regeneration(self):
        self.assertEqual(gen.emit_netlist(), NETLIST.read_text())
        self.assertEqual(gen.emit_pad_table(), PAD_TABLE.read_text())

    def test_parser_does_not_absorb_other_tables(self):
        rows, errs = cr.parse_floorplan_pads(FLOORPLAN.read_text())
        # Exactly the pad table's 48 rows: the instance-count and core-area
        # budget tables must not be absorbed.
        self.assertEqual(errs, [])
        self.assertEqual([r["pad"] for r in rows],
                         [f"L{i:02d}" for i in range(1, 49)])
        self.assertEqual(rows[0]["signal"], "PL_C1_Amin_Gmin_1")
        self.assertEqual(rows[47]["signal"], "UNUSED_3")


class PadTableSeedMismatchTests(unittest.TestCase):
    """Each seeded mismatch mutates the committed-good text and must fail
    with a message naming the offending pad or port."""

    def test_renamed_pad_id_rejected(self):
        rec, table, net = committed()
        bad = rec.replace("| L17 |", "| L99 |")
        e = cr.check_pad_table(bad, table, net)
        self.assertTrue(any("L99" in x and "L17" in x for x in e), e)

    def test_record_slot_type_change_rejected(self):
        rec, table, net = committed()
        bad = rec.replace(
            "| L37 | `BL_C1_Amin` | analog (bench sources/senses) | analog slot |",
            "| L37 | `BL_C1_Amin` | analog (bench sources/senses) | bidir slot |")
        e = cr.check_pad_table(bad, table, net)
        self.assertTrue(any("L37" in x and "slot" in x for x in e), e)

    def test_json_slot_type_change_rejected(self):
        rec, table, net = committed()
        bad = json.loads(json.dumps(table))
        for p in bad["pads"]:
            if p["pad"] == "L37":
                p["slot_type"] = "bidir"
        e = cr.check_pad_table(rec, bad, net)
        self.assertTrue(any("L37" in x and "slot_type" in x for x in e), e)

    def test_deleted_row_breaks_slot_type_total(self):
        rec, table, net = committed()
        bad = "\n".join(l for l in rec.splitlines() if not l.startswith("| L48 |"))
        e = cr.check_pad_table(bad, table, net)
        self.assertTrue(any("total" in x and "37" in x for x in e), e)

    def test_port_without_pad_rejected(self):
        rec, table, net = committed()
        bad = rec.replace("| L01 | `PL_C1_Amin_Gmin_1` |",
                          "| L01 | `PL_C1_Amin_Gmin_9` |")
        e = cr.check_pad_table(bad, table, net)
        self.assertTrue(any("PL_C1_Amin_Gmin_1" in x and "no pad" in x for x in e), e)

    def test_signal_mismatch_rejected(self):
        rec, table, net = committed()
        bad = rec.replace("| L02 | `PL_C1_Amin_Gmin_2` |",
                          "| L02 | `PL_C1_Amin_Gmin_3` |")
        e = cr.check_pad_table(bad, table, net)
        self.assertTrue(any("L02" in x for x in e), e)


class GeometrySeedMismatchTests(unittest.TestCase):
    def test_capacitor_width_drift_rejected(self):
        _, _, net = committed()
        bad = net.replace(
            "XC1 CN PL cap_nmos_03v3 c_width=1.0u c_length=0.28u m=1",
            "XC1 CN PL cap_nmos_03v3 c_width=1.1u c_length=0.28u m=1")
        self.assertNotEqual(bad, net)
        e = cr.check_geometry(bad, DECISION.read_text(), drawn_refs())
        self.assertTrue(any("cell_candidate1" in x and "capacitor" in x for x in e), e)

    def test_access_width_drift_rejected(self):
        _, _, net = committed()
        bad = net.replace(
            "XM1 BL WL CN VB nfet_06v0 L=0.70u W=0.42u nf=1 m=1",
            "XM1 BL WL CN VB nfet_06v0 L=0.70u W=0.43u nf=1 m=1")
        self.assertNotEqual(bad, net)
        e = cr.check_geometry(bad, DECISION.read_text(), drawn_refs())
        self.assertTrue(any("cell_candidate1" in x and "access" in x for x in e), e)

    def test_capacitor_device_drift_rejected(self):
        _, _, net = committed()
        bad = net.replace("XC1 CN PL cap_pmos_03v3", "XC1 CN PL cap_nmos_03v3")
        self.assertNotEqual(bad, net)
        e = cr.check_geometry(bad, DECISION.read_text(), drawn_refs())
        self.assertTrue(any("cell_candidate3" in x and "capacitor" in x for x in e), e)

    def test_netlist_cell_without_drawn_counterpart_rejected(self):
        _, _, net = committed()
        bad = net.replace(
            ".subckt cell_candidate2_Amin_G2x", ".subckt cell_candidate2_G2x")
        self.assertNotEqual(bad, net)
        e = cr.check_geometry(bad, DECISION.read_text(), drawn_refs())
        self.assertTrue(any("cell_candidate2_G2x" in x for x in e), e)


class CliTests(unittest.TestCase):
    def test_cli_exit_codes(self):
        script = str(ROOT / "scripts" / "check_run3_pad_table.py")
        ok = subprocess.run([sys.executable, "-I", script], capture_output=True)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        self.assertEqual(ok.stdout, b"")  # clean tree prints nothing alarming


if __name__ == "__main__":
    unittest.main()
