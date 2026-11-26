"""Offline checks for the run3 chip assembly (issue #211).

Runs without `klt` and without regenerating the GDS: validates the assembler's
derived tables against the committed sources they must agree with.

  1. the placement table: 36 rows, 31 placed, the five excluded rows are
     exactly the undrawn cell's instances; every placed instance's plate pin
     sits at its pad's y (the straight HV-route invariant);
  2. every placed cell names a committed cell GDS, and every excluded cell is
     the assembler's pending C2-Amin-G2x split;
  3. the pad ring: 48 signal pads + 8 power pads, the 40 connected pads
     labelled with their pad-table signals, the 16 unconnected ones
     unlabelled, and no two pads of one edge overlapping;
  4. the connectivity net list: 31 straight plate routes + the nine bundle
     nets + the substrate strap, every pin reference naming a declared block
     port, and the pairwise keep-clear assertion passing (the same assertion
     the assembler hard-fails on before writing a request);
  5. the routing planes: no two bundle nets share a plane where their
     bounding boxes overlap (BL metal4 / WL metal3 / VB metal2 / PL metal5);
  6. --check's release guard (issue #568): the check stops before composing
     under any klt release but the recorded one, and still byte-compares
     under it.
"""
import ast
import contextlib
import hashlib
import io
import json
import re
import sys
import tempfile
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
        _, cls.paths = asm.build_connectivity(cls.rows, cls.pads)
        with tempfile.TemporaryDirectory() as tmp, mock.patch.object(
                asm.subprocess, "run", return_value=mock.Mock(returncode=0)):
            request, _ = asm.compose_request(cls.rows, cls.pads, Path(tmp))
        cls.nets = request["connectivity"]
        cls.block_ports = {
            block["id"]: [port["name"] for port in block["cell"]["ports"]]
            for block in request["blocks"]
        }

    def test_placement_shape(self):
        self.assertEqual(len(self.rows), 36)
        placed = [r for r in self.rows if r["placed"]]
        excluded = [r for r in self.rows if not r["placed"]]
        self.assertEqual(len(placed), 31)
        self.assertEqual(
            {r["cell"] for r in excluded}, asm.PENDING_ASSEMBLY
        )
        self.assertEqual({r["cell"] for r in placed} - asm.PENDING_ASSEMBLY,
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

    def test_pad_ports_match_labelled_pads_on_each_strip(self):
        for strip_id, keep in asm.PADRING_STRIPS.items():
            with self.subTest(strip=strip_id):
                labels = [pad["label"] for pad in self.pads
                          if keep(pad) and pad["label"]]
                self.assertCountEqual(self.block_ports[strip_id], labels)

    def _bundle_patch_centres(self, pads):
        # x centre of each bundle landing rect in the fixup script's rect
        # list, by net: the 31 plate-pin rects come first, then one per
        # BUNDLE_NETS entry in its iteration order.
        rows = asm.build_placement()
        script = asm.mt1_fixup_script(Path("unused.gds"), rows, pads)
        loop = next(line for line in script.splitlines()
                    if line.startswith("for x0, y0, x1, y1 in "))
        rects = ast.literal_eval(loop[len("for x0, y0, x1, y1 in "):-1])
        placed = sum(1 for r in rows if r["placed"])
        self.assertEqual(len(rects), placed + len(asm.BUNDLE_NETS))
        return {net: (x0 + x1) / 2.0 for net, (x0, _y0, x1, _y1)
                in zip(asm.BUNDLE_NETS, rects[placed:])}

    def test_bundle_landing_patches_are_centred_on_their_pads(self):
        # Each bundle landing patch takes its x from the pad record its net
        # is labelled on (BOTTOM_PAD_X through build_pads); BUNDLE_NETS holds
        # no pad coordinate of its own.
        by_label = {p["label"]: p for p in self.pads if p["label"]}
        for net, centre in self._bundle_patch_centres(self.pads).items():
            self.assertEqual(centre, by_label[net]["x"], net)

    def test_moved_bottom_pad_carries_its_landing_patch(self):
        # Issue #563: a bottom-edge floorplan edit is one change to
        # BOTTOM_PAD_X. Moving L37 (BL_C1_Amin) in memory moves its drawn
        # pad and its landing patch together; the other eight stay put.
        pad_table = json.loads(
            (ROOT / "layout" / "run3_top" / "pad_table.json").read_text())
        before = self._bundle_patch_centres(self.pads)
        moved_x = asm.BOTTOM_PAD_X["L37"] + 5.0
        with mock.patch.dict(asm.BOTTOM_PAD_X, {"L37": moved_x}):
            moved = asm.build_pads(pad_table)
            after = self._bundle_patch_centres(moved)
        self.assertEqual([p["x"] for p in moved if p["pad"] == "L37"],
                         [moved_x])
        self.assertEqual(after["BL_C1_Amin"], moved_x)
        del after["BL_C1_Amin"], before["BL_C1_Amin"]
        self.assertEqual(after, before)

    def test_connectivity_net_list(self):
        pl = [n for n in self.nets if n["net"].startswith("PL_")]
        bundles = [n for n in self.nets if n["net"] in asm.BUNDLE_NETS]
        substrate = [n for n in self.nets if n["net"] == asm.SUBSTRATE_NET]
        self.assertEqual(len(pl), 31)
        self.assertEqual(len(bundles), 9)
        self.assertEqual(len(substrate), 1)
        for net in self.nets:
            for pin in net["pins"]:
                self.assertIn(pin["block"], self.block_ports, net["net"])
                self.assertIn(pin["port"], self.block_ports[pin["block"]], net["net"])
            for leg in net.get("legs", []):
                self.assertIn(leg["from_pin"], net["pins"], net["net"])
                self.assertIn(leg["to_pin"], net["pins"], net["net"])

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
        _role, trunk_x, _ca = asm.BUNDLE_NETS["WL_C3_Amin"]
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
        for net, (role, _tx, _ca) in asm.BUNDLE_NETS.items():
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


class CheckKltReleaseTests(unittest.TestCase):
    """--check's release guard (issue #568), offline: ``klt --version`` is
    stubbed and every geometry step is mocked, so no klt is installed and
    nothing is composed."""

    @classmethod
    def setUpClass(cls):
        provenance = json.loads(
            (ROOT / "layout/run3_top/compose_report.json").read_text()
        )["provenance"]
        cls.release = provenance["klt_version"]
        cls.command = asm.PINNED_CHECK_COMMAND.format(
            klt_reinstall_spec=provenance["klt_reinstall_spec"])

    def run_check(self, klt_on_path, drift=("", "")):
        """Run ``main(['--check'])`` with ``klt --version`` answering
        `klt_on_path` (the version it prints, or an exception it raises) and
        every geometry step mocked: the chip and the LVS reference regenerate
        to the committed bytes with `drift[0]` / `drift[1]` appended. Returns
        (SystemExit's code, or None where main() returns; stdout; the
        subprocess.run replacement; the compose_request replacement)."""
        run = (mock.Mock(side_effect=klt_on_path)
               if isinstance(klt_on_path, Exception)
               else mock.Mock(return_value=mock.Mock(
                   returncode=0, stdout=f"klt {klt_on_path}\n", stderr="")))
        compose = mock.Mock()
        out = io.StringIO()
        reference = (ROOT / "layout/run3_top"
                     / "lvs_reference_drawn.spice").read_text()
        with tempfile.TemporaryDirectory() as tmp:
            composed = Path(tmp) / "run3_top.gds"
            composed.write_bytes(
                (ROOT / "layout/run3_top/run3_top.gds").read_bytes()
                + drift[0].encode())
            compose.return_value = ({}, composed)
            with mock.patch.object(sys, "argv",
                                   ["assemble_run3_top.py", "--check"]), \
                    mock.patch.object(asm.subprocess, "run", run), \
                    mock.patch.multiple(
                        asm,
                        compose_request=compose,
                        run_klt_compose=mock.Mock(return_value="{}"),
                        assert_composed=mock.Mock(return_value={"blocks": []}),
                        apply_mt1_fixup=mock.Mock(),
                        fill_density=mock.Mock(return_value=composed),
                        emit_lvs_reference=mock.Mock(
                            return_value=reference + drift[1])), \
                    contextlib.redirect_stdout(out):
                try:
                    asm.main()
                except SystemExit as e:
                    code = e.code
                else:
                    code = None
        return code, out.getvalue(), run, compose

    def assert_stopped_before_composing(self, reported, *diagnostic):
        """The check exited nonzero naming the recorded release, `reported`
        and the pinned command, composed nothing (the version probe is the
        only subprocess it launched), and gave no drift report."""
        code, out, run, compose = self.run_check(reported)
        self.assertNotIn(code, (None, 0))
        for text in ("wrong klt release", f"`klt {self.release}`", self.command,
                     *diagnostic):
            self.assertIn(text, code)
        self.assertNotIn("drift", code.lower())
        self.assertNotIn("rewrite", code.lower())
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [["klt", "--version"]])
        compose.assert_not_called()
        self.assertNotIn("DRIFT", out)
        return code

    def test_check_stops_before_composing_on_a_development_build(self):
        """The regression case: a development build that shares the recorded
        release's number is still a different release."""
        code = self.assert_stopped_before_composing(
            f"{self.release}.dev111+g978f7464fae1",
            f"`klt {self.release}.dev111+g978f7464fae1`")
        self.assertIn("development suffix", code)

    def test_check_stops_on_every_release_but_the_recorded_one(self):
        """The full reported version is compared -- not a prefix, not the
        number before a suffix -- and a klt that reports nothing at all
        (none on PATH here) stops the check the same way."""
        self.assert_stopped_before_composing("0.9.3.dev5725",
                                             "`klt 0.9.3.dev5725`")
        self.assert_stopped_before_composing("0.9.20", "`klt 0.9.20`")
        self.assert_stopped_before_composing(
            FileNotFoundError(2, "No such file or directory: 'klt'"),
            "no klt on PATH")

    def test_check_needs_the_recorded_release_to_compare_against(self):
        """Without both provenance fields there is no release to verify
        against: the check stops and says what it could not read, rather
        than compose or compare under an unverified klt."""
        partial = json.dumps({"provenance": {"klt_version": self.release}})
        for content in (None, partial):
            with self.subTest(report=content):
                with tempfile.TemporaryDirectory() as tmp:
                    if content is not None:
                        (Path(tmp) / "compose_report.json").write_text(content)
                    with mock.patch.object(asm, "HERE", Path(tmp)):
                        code, out, _run, compose = self.run_check(self.release)
                    self.assertNotIn(code, (None, 0))
                    self.assertIn("cannot name the recorded klt release", code)
                    self.assertIn("klt_reinstall_spec", code)
                    self.assertNotIn("drift", code.lower())
                    compose.assert_not_called()
                    self.assertEqual(out, "")

    def test_check_compares_the_committed_bytes_under_the_recorded_release(self):
        """Under the recorded release the guard stands aside: the version
        probe is the only subprocess, the geometry runs, and both committed
        artifacts come back OK."""
        code, out, run, compose = self.run_check(self.release)
        self.assertIsNone(code)
        compose.assert_called_once()
        self.assertEqual([c.args[0] for c in run.call_args_list],
                         [["klt", "--version"]])
        self.assertEqual([line.split()[:2] for line in out.splitlines()],
                         [["OK:", name] for name in asm.ARTIFACTS])

    def test_check_still_fails_on_drifted_content_under_the_recorded_release(self):
        """A real content difference in either artifact still fails the check
        with its drift report and rewrite advice -- the path a wrong release
        is kept from reaching."""
        for which, name in enumerate(asm.ARTIFACTS):
            with self.subTest(artifact=name):
                drift = ["", ""]
                drift[which] = "\n* drifted"
                code, out, _run, compose = self.run_check(self.release, drift)
                compose.assert_called_once()
                self.assertNotIn(code, (None, 0))
                self.assertIn(f"DRIFT: {name}: regenerated sha256 ", out)
                self.assertEqual(
                    code, "regeneration drifted; run without --check to rewrite")

    def test_pinned_check_command_is_documented(self):
        """The README's chip assembly section and the module docstring both
        carry the runnable command the guard names, built from the recorded
        reinstall spec: a pin bump that misses one fails here."""
        self.assertIn(self.command,
                      (ROOT / "layout/run3_top/README.md").read_text())
        self.assertIn(self.command, asm.__doc__)


if __name__ == "__main__":
    unittest.main()
