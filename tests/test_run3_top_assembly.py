"""Offline checks for the run3 chip assembly (issue #211).

Runs without `klt` and without regenerating the GDS: validates the assembler's
derived tables against the committed sources they must agree with.

  1. the placement table: 36 rows, 31 placed, the five excluded rows are
     exactly the undrawn cell's instances; every placed instance's plate pin
     sits at its pad's y (the straight HV-route invariant);
  2. every placed cell names a committed cell GDS, and every excluded cell is
     the generator's NO_DRAWN_CELL point;
  3. the pad ring: 48 signal pads + 8 power pads, the 40 connected pads
     labelled with their pad-table signals, the 16 unconnected ones
     unlabelled, and no two pads of one edge overlapping;
  4. the connectivity net list: 31 straight plate routes + the nine bundle
     nets + the substrate strap, every pin reference naming a declared block
     port, and the pairwise keep-clear assertion passing (the same assertion
     the assembler hard-fails on before writing a request);
  5. the routing planes: no two bundle nets share a plane where their
     bounding boxes overlap (BL metal4 / WL metal3 / VB metal2 / PL metal5).
"""
import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "layout" / "run3_top"))

import assemble_run3_top as asm  # noqa: E402


class Run3TopAssemblyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pads = asm.build_pads(
            json.loads((ROOT / "layout" / "run3_top" / "pad_table.json").read_text())
        )
        cls.rows = asm.build_placement()
        cls.nets, cls.paths = asm.build_connectivity(cls.rows, cls.pads)

    def test_placement_shape(self):
        self.assertEqual(len(self.rows), 36)
        placed = [r for r in self.rows if r["placed"]]
        excluded = [r for r in self.rows if not r["placed"]]
        self.assertEqual(len(placed), 31)
        self.assertEqual(
            {r["cell"] for r in excluded}, asm.gen.NO_DRAWN_CELL
        )
        self.assertEqual({r["cell"] for r in placed} - asm.gen.NO_DRAWN_CELL,
                         set(asm.PIN_OFFSET_UM))

    def test_plate_pins_are_pad_aligned(self):
        for row in self.rows:
            if not row["placed"]:
                continue
            px, py = pad_centre = asm.pad_centre(row["pad"])
            self.assertEqual(row["pin_um"][1], py, row["name"])
            self.assertTrue(170.0 < row["pin_um"][0] < 1806.0, row["name"])

    def test_placed_cells_exist_as_committed_gds(self):
        for row in self.rows:
            if not row["placed"]:
                continue
            gds = ROOT / "layout" / row["cell"] / f"{row['cell']}.gds"
            self.assertTrue(gds.is_file(), gds)

    def test_pad_ring(self):
        signal = [p for p in self.pads if p["pad"].startswith("L")]
        power = [p for p in self.pads if p["pad"].startswith("PWR")]
        self.assertEqual(len(signal), 48)
        self.assertEqual(len(power), 8)
        self.assertEqual(sum(1 for p in self.pads if p["label"]), 40)
        placed_ids = {r["pad"] for r in self.rows if r["placed"]}
        for p in signal:
            if p["pad"] in placed_ids or p["signal"] in asm.BUNDLE_NETS:
                self.assertEqual(p["label"], p["signal"], p["pad"])
            else:
                self.assertIsNone(p["label"], p["pad"])

    def test_pad_ring_edges_do_not_overlap(self):
        by_edge = {}
        for p in self.pads:
            by_edge.setdefault(round(p["y"], 3), []).append(p)
        for y, group in by_edge.items():
            group.sort(key=lambda p: p["x"])
            for a, b in zip(group, group[1:]):
                self.assertGreaterEqual(b["x"] - a["x"], asm.PAD_SIDE_UM,
                                        f"pads overlap at y={y}")

    def test_connectivity_net_list(self):
        pl = [n for n in self.nets if n["net"].startswith("PL_")]
        bundles = [n for n in self.nets if n["net"] in asm.BUNDLE_NETS]
        substrate = [n for n in self.nets if n["net"] == asm.SUBSTRATE_NET]
        self.assertEqual(len(pl), 31)
        self.assertEqual(len(bundles), 9)
        self.assertEqual(len(substrate), 1)
        block_ports = {}
        for block in self._blocks():
            for port in block.get("ports", []):
                block_ports.setdefault(block["id"], set()).add(port["name"])
        for net in self.nets:
            for pin in net["pins"]:
                self.assertIn(pin["block"], block_ports, net["net"])
                self.assertIn(pin["port"], block_ports[pin["block"]], net["net"])

    def test_wl_antenna_clamps(self):
        # one n-diode clamp per WL net (issue #404): each WL net carries a
        # diode pin and a clamp leg tied to its own group's top pin; the C3
        # companion substrate tap hangs off the substrate net, never off a
        # WL net (a substrate tap on a signal net extracts as an ohmic tie).
        by_net = {n["net"]: n for n in self.nets}
        for d in asm.wl_diode_placements(self.rows):
            net = by_net[d["net"]]
            diode_pins = [p for p in net["pins"]
                          if p["block"] == f"diode_{d['net']}"]
            self.assertEqual(len(diode_pins), 1, d["net"])
            for pin in net["pins"]:
                self.assertNotEqual(pin["block"], "substrate_tap_c3", net["net"])
        substrate = by_net[asm.SUBSTRATE_NET]
        taps = [p for p in substrate["pins"] if p["block"] == "substrate_tap_c3"]
        self.assertEqual(len(taps), 1)
        branch = asm.c3_tap_branch(self.rows)
        diode = {d["net"]: d for d in asm.wl_diode_placements(
            self.rows)}["WL_C3_Amin"]
        # the tap sits within DF.14's 20 um diamond of the C3 clamp body
        self.assertLess(abs(branch["tap_x"] - diode["x"])
                        + abs(branch["tap_y"] - diode["y"]), 20.0)

    def test_keep_clear_assertion_passes(self):
        # Re-runs the assembler's own pairwise keep-clear check; it hard-exits
        # on any violation, so reaching the end means clean.
        asm.check_keep_clear(self.paths, asm.BUNDLE_WIDTH_UM, margin_um=3.0)

    def test_bundle_planes_do_not_share_crossing_paths(self):
        planes = {}
        for net, (role, _tx, _px, _ca) in asm.BUNDLE_NETS.items():
            planes.setdefault(role, set()).add(net)
        self.assertEqual(planes.get("metal4"),
                         {"BL_C1_Amin", "BL_C1_A2x", "BL_C2_Amin", "BL_C3_Amin"})
        self.assertEqual(planes.get("metal3"),
                         {"WL_C1_Amin", "WL_C1_A2x", "WL_C2_Amin", "WL_C3_Amin"})
        self.assertEqual(planes.get("metal2"), {"VBW_C3"})
        # the substrate strap shares metal2 with VBW_C3: its strap stays left
        # of the VBW trunk, and its only VBW-x-range geometry is the C3 tap
        # branch, whose segments are each either above every VBW segment or
        # left of the VBW trunk (issue #404).
        vss = self.paths[asm.SUBSTRATE_NET]["metal2"]
        vbw = self.paths["VBW_C3"]["metal2"]
        strap, tap_branch = vss[:-3], vss[-3:]
        strap_x = [x for seg in strap for x in (seg[0], seg[2])]
        vbw_x = [x for seg in vbw for x in (seg[0], seg[2])]
        vbw_y = [y for seg in vbw for y in (seg[1], seg[3])]
        self.assertLess(max(strap_x), min(vbw_x))
        for seg in tap_branch:
            seg_y = [seg[1], seg[3]]
            seg_x = [seg[0], seg[2]]
            self.assertTrue(max(seg_y) > max(vbw_y) + 3.0
                            or max(seg_x) < min(vbw_x), seg)

    def test_substrate_strap_has_no_pad(self):
        substrate = [n for n in self.nets if n["net"] == asm.SUBSTRATE_NET][0]
        for pin in substrate["pins"]:
            self.assertNotEqual(pin["block"], "padring")
        self.assertEqual(len(substrate["pins"]), 22)

    def test_post_fix_stage_reports(self):
        # The committed stage evidence (issue #404): the precheck's DRC stage
        # at gf180mcuD carries only the out-of-scope PCell-exception class
        # and DBU; the antenna stage's WL findings are fixed and only the
        # operator-deferred private-plate Metal5 group remains; the density
        # stage is clean.
        stage = json.loads(
            (ROOT / "layout/run3_top/drc_stage_report.json").read_text())
        self.assertEqual(stage["rule_counts"],
                         {"CO.4": 80, "DBU": 1, "DF.6_MV": 10, "PL.4_MV": 10})
        antenna = json.loads(
            (ROOT / "layout/run3_top/drc_antenna_report.json").read_text())
        self.assertEqual(antenna["rule_counts"],
                         {"ANT.16_i_ANT.6": 26, "ANT.16_ii_ANT.6": 5})
        density = json.loads(
            (ROOT / "layout/run3_top/drc_density_report.json").read_text())
        self.assertEqual(density["rule_counts"], {})

    def _blocks(self):
        """The request's block list, rebuilt cheaply (no klt calls)."""
        blocks = [{"id": sid, "ports": [{"name": p["label"]} for p in self.pads
                                        if keep(p) and p["label"]]}
                  for sid, keep in asm.PADRING_STRIPS.items()]
        for row in self.rows:
            if row["placed"]:
                blocks.append({"id": row["name"],
                               "ports": [{"name": p} for p in
                                         ("BL", "WL", "PL", "VB")]})
        for d in asm.wl_diode_placements(self.rows):
            blocks.append({"id": f"diode_{d['net']}",
                           "ports": [{"name": "A"}]})
        blocks.append({"id": "substrate_tap_c3", "ports": [{"name": "B"}]})
        return blocks


if __name__ == "__main__":
    unittest.main()
