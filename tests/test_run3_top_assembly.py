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
        # the substrate strap shares metal2 with VBW_C3; their x-ranges are
        # disjoint (substrate trunk and stubs stay left of the VBW trunk).
        vss = self.paths[asm.SUBSTRATE_NET]["metal2"]
        vbw = self.paths["VBW_C3"]["metal2"]
        vss_x = [x for seg in vss for x in (seg[0], seg[2])]
        vbw_x = [x for seg in vbw for x in (seg[0], seg[2])]
        self.assertLess(max(vss_x), min(vbw_x))

    def test_substrate_strap_has_no_pad(self):
        substrate = [n for n in self.nets if n["net"] == asm.SUBSTRATE_NET][0]
        for pin in substrate["pins"]:
            self.assertNotEqual(pin["block"], "padring")
        self.assertEqual(len(substrate["pins"]), 21)

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
        return blocks


if __name__ == "__main__":
    unittest.main()
