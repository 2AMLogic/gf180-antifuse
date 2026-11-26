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
import hashlib
import json
import re
import sys
import unittest
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path
from unittest import mock

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

    def test_wl_clamps_deferred_substrate_tap_drawn(self):
        # The WL antenna remedy is evaluated but NOT drawn (deferred to the
        # operator with the private-plate group, issue #404): no net carries
        # a diode pin. The C3 substrate tap -- the C3 column's only
        # p-substrate tie -- hangs off the substrate net, never off a
        # signal net (a substrate tap on a signal net extracts as an ohmic
        # tie), east of the C3 WL trunk and above the group's top pin.
        for net in self.nets:
            for pin in net["pins"]:
                self.assertFalse(pin["block"].startswith("diode_"),
                                 (net["net"], pin))
                if net["net"] != asm.SUBSTRATE_NET:
                    self.assertNotEqual(pin["block"], "substrate_tap_c3",
                                        net["net"])
        by_net = {n["net"]: n for n in self.nets}
        substrate = by_net[asm.SUBSTRATE_NET]
        taps = [p for p in substrate["pins"] if p["block"] == "substrate_tap_c3"]
        self.assertEqual(len(taps), 1)
        branch = asm.c3_tap_branch(self.rows)
        _role, trunk_x, _pad_x, _ca = asm.BUNDLE_NETS["WL_C3_Amin"]
        c3_top = max(p[1] for r, p in asm.instance_ports(self.rows, "WL")
                     if r["origin"][0] == asm.COL_X_RIGHT)
        self.assertGreater(branch["tap_x"], trunk_x)
        self.assertGreater(branch["tap_y"], c3_top)

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
        # Only shared WL gates have antenna findings on the signed layout.
        # MDN.10c is also present in the same-deck replay of the earlier C2.
        stage = json.loads(
            (ROOT / "layout/run3_top/drc_stage_report.json").read_text())
        self.assertEqual(stage["rule_counts"],
                         {"CO.4": 80, "DBU": 1, "DF.6_MV": 10, "MDN.10c": 5, "PL.4_MV": 10})
        antenna = json.loads(
            (ROOT / "layout/run3_top/drc_antenna_report.json").read_text())
        self.assertEqual(antenna["rule_counts"],
                         {"ANT.16_ii_ANT.4": 29})
        density = json.loads(
            (ROOT / "layout/run3_top/drc_density_report.json").read_text())
        self.assertEqual(density["rule_counts"], {})

    def test_stage_reports_pin_committed_layout(self):
        # Issue #427: every committed *_report.json is pinned by NAME, not
        # by a glob -- the #424 drc_* glob never reached the erc/lvs/
        # economy sign-off reports, and its non-empty guard let a single
        # renamed report silently shrink the pin set while the suite stayed
        # green. Table: report -> the input its provenance must record.
        #   the committed GDS hash: every sign-off report that describes
        #     the committed layout (5 DRC stage reports, ERC, LVS, economy)
        #   the historical diode-drawn GDS: the after-round antenna sweep
        #     ran on the drawn-clamp layout, deliberately not re-run on the
        #     committed one (sha also asserted in test_antenna_ratio_evidence)
        #   None: compose_report.json aggregates the other reports'
        #     verdicts and carries no provenance.input at all
        gds_hash = "sha256:" + hashlib.sha256(
            (ROOT / "layout/run3_top/run3_top.gds").read_bytes()).hexdigest()
        historical_hash = ("sha256:79bc84145a1baf87116b42d7aedee9bd9c69c29b7"
                           "2ce4d46a5a7ab1fa0c679f8")
        expected_inputs = {
            "drc_report.json": gds_hash,
            "drc_stage_report.json": gds_hash,
            "drc_density_report.json": gds_hash,
            "drc_antenna_report.json": gds_hash,
            "erc_report.json": gds_hash,
            "lvs_report.json": gds_hash,
            "economy_report.json": gds_hash,
            "drc_antenna_after_wl_diode_clamp_report.json": historical_hash,
            "compose_report.json": None,
        }
        reports = sorted((ROOT / "layout/run3_top").glob("*_report.json"))
        self.assertEqual({r.name for r in reports}, set(expected_inputs))
        for report in reports:
            recorded = json.loads(report.read_text())["provenance"].get("input")
            recorded_hash = None if recorded is None \
                else recorded["content_hash"]
            self.assertEqual(
                recorded_hash, expected_inputs[report.name], report.name)
        # drc_antenna_stage.lyrdb carries no input hash of its own (its
        # companion .log names only the path it ran on), so its tie to the
        # layout is indirect: its per-rule finding counts must equal the
        # hash-pinned antenna report's rule_counts -- read from the report,
        # not a second set of literals here.
        rdb_counts = Counter(
            item.find("category").text.strip("'")
            for item in ET.parse(
                ROOT / "layout/run3_top/drc_antenna_stage.lyrdb").iter("item"))
        antenna = json.loads(
            (ROOT / "layout/run3_top/drc_antenna_report.json").read_text())
        self.assertEqual(dict(rdb_counts), antenna["rule_counts"])

    def test_antenna_ratio_evidence(self):
        # Issue #422: the README's quoted antenna ratios must trace to a
        # committed artifact. klt's JSON envelope keeps only each finding's
        # category/description/polygon and drops the per-item values the deck
        # attaches (the measured ratio lands in the RDB as a #RATIO tag), so
        # the antenna stage's RDB is committed beside the report, captured
        # like the density stage log by the direct klayout -b invocation its
        # companion .log records.
        ratios = {}
        for item in ET.parse(
                ROOT / "layout/run3_top/drc_antenna_stage.lyrdb").iter("item"):
            cat = item.find("category").text.strip("'")
            for value in item.find("values"):
                text = "".join(value.itertext())
                if text.startswith("[#RATIO]"):
                    ratios.setdefault(cat, []).append(
                        float(text.split("float:")[1]))
        self.assertEqual({c: len(v) for c, v in ratios.items()},
                         {"ANT.16_ii_ANT.4": 29})
        wl = ratios["ANT.16_ii_ANT.4"]
        self.assertAlmostEqual(min(wl), 428.958, places=3)
        self.assertAlmostEqual(max(wl), 1035.402, places=3)
        log = (ROOT / "layout/run3_top/drc_antenna_stage.log").read_text()
        self.assertIn("drc_antenna_stage.lyrdb", log)
        self.assertRegex(log, r"'ANT\.16_ii_ANT\.4'\s*:\s+29 violation")
        # the WL remedy's "after" round -- the drawn-clamp layout whose
        # ANT.16_ii_ANT.4 count is 0 -- re-committed from 9f5dc932, where
        # that layout lived; its input is the diode-drawn GDS (sha pinned),
        # not the committed one.
        after = json.loads(
            (ROOT / "layout/run3_top/"
             "drc_antenna_after_wl_diode_clamp_report.json").read_text())
        self.assertEqual(after["rule_counts"],
                         {"ANT.16_i_ANT.6": 26, "ANT.16_ii_ANT.6": 5})
        self.assertEqual(after["provenance"]["input"]["content_hash"],
                         "sha256:79bc84145a1baf87116b42d7aedee9bd9c69c29b7"
                         "2ce4d46a5a7ab1fa0c679f8")

    def test_lvs_reference_matches_committed_bytes(self):
        committed = (ROOT / "layout/run3_top/lvs_reference_drawn.spice").read_bytes()
        self.assertEqual(asm.emit_lvs_reference(self.rows).encode("utf-8"),
                         committed)

    def test_shared_instance_formatter(self):
        full_lines = asm.gen.format_instance_lines(asm.gen.build_instances())
        placed = [r for r in self.rows if r["placed"]]
        unplaced_names = {r["name"] for r in self.rows if not r["placed"]}
        placed_lines = asm.gen.format_instance_lines(placed)
        self.assertEqual(len(full_lines), 4 + 36)
        self.assertEqual(len(placed_lines), 4 + 31)
        self.assertEqual(
            [ln for ln in full_lines if ln.split()[0] not in unplaced_names],
            placed_lines,
        )
        with mock.patch.object(asm.gen, "format_instance_lines",
                               wraps=asm.gen.format_instance_lines) as fmt:
            text = asm.emit_lvs_reference(self.rows)
        fmt.assert_called_once_with(placed)
        self.assertEqual(
            text.encode("utf-8"),
            (ROOT / "layout/run3_top/lvs_reference_drawn.spice").read_bytes(),
        )

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
        blocks.append({"id": "substrate_tap_c3", "ports": [{"name": "B"}]})
        return blocks


if __name__ == "__main__":
    unittest.main()
