"""Targeted tests for build_report.py. Stdlib unittest; builds a tiny synthetic
evidence tree in a temp dir (no ngspice, no PDK). Run:

    python3 -m unittest discover -s sim/characterization-report/tests
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import build_report as B  # noqa: E402

REPO = HERE.parent.parent.parent
PDK = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"
EXP = "sim/cell-device-characterization"
CORNER = "typical_27c_bl1p00v"
SNAP = ("*snap\n.subckt cell_candidateN BL WL PL VB  wcap=1e-6 lcap=1e-6 "
        "wacc=0.30u lacc=0.55u\n.ends\n")


def write(p: Path, text: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def access_log(ioff, ron):
    return "".join(f"{k} = {v:.6e}\n" for k, v in
                   (("ioff_lo", ioff), ("ioff_mid", ioff * 2), ("ioff_hi", ioff * 3), ("ron", ron)))


def cap_log(c):
    return "".join(f"ilk_{i} = 0.000000e+00\ncval_{i} = {c:.6e}\n" for i in range(1, 6))


def record_text(rid, region, cand, ioff_hi, ron, supersedes="(none)", pdk=PDK):
    return (f"# Record {rid}\n\n- **Record ID**: {rid}\n"
            f"- **Claim**: x. Region {region} / Candidate {cand} (y)\n"
            f"- **Netlist provenance**: schematic (design/netlists/c{cand}.spice, clean tree at run time)\n"
            f"  - worst-case I_off = {ioff_hi:.4e} A -> z\n  - R_on = {ron:.4e} ohm (worst)\n"
            f"  - PDK: `gf180mcuD`, open_pdks `{pdk}` (see)\n"
            f"- **Timestamp / author**: t, a\n- **Supersedes**: {supersedes}\n")


class Fixture:
    """Two regions with deliberately different values."""

    def __init__(self, tmp: Path):
        self.root = tmp
        self.rids = {"I": "20260101-000001-aaaaaaa", "II": "20260101-000002-aaaaaaa"}
        self.vals = {"I": (1e-13, 1e4, 2e-17), "II": (5e-10, 60.0, 9e-15)}
        recs = []
        for n, (reg, rid) in enumerate(self.rids.items(), 1):
            ioff, ron, cap = self.vals[reg]
            write(tmp / f"design/netlists/cell_candidate{n}.spice", SNAP)
            write(tmp / f"{EXP}/netlist-snapshots/{rid}.spice", SNAP)
            for geom, mult in (("min", 1), ("2x", 2)):
                d = f"{EXP}/corners/{rid}/access-min_cap-{geom}"
                write(tmp / d / f"{CORNER}.log", access_log(ioff * mult, ron * mult))
                write(tmp / d / "moscap_typical_27c_nosupply.log", cap_log(cap * mult))
            write(tmp / f"{EXP}/records/{rid}.md",
                  record_text(rid, reg, n, ioff * 3 * 2, ron * 2))
            recs.append({"record_id": rid, "region": reg, "candidate": n,
                         "design_netlist": f"design/netlists/cell_candidate{n}.spice"})
        stim = {"off_gate_bias_v": [-0.3, 0.0, 0.3], "on_gate_bias_v": 3.3,
                "cv_bias_v": [-3.3, -1.65, 0.0, 1.65, 3.3]}
        self.manifest = {
            "generator_version": B.GENERATOR_VERSION, "experiment_dir": EXP, "pdk_revision": PDK,
            "required_regions": ["I", "II"],
            "grid": {"access_process": ["typical"], "moscap_process": ["moscap_typical"],
                     "temps_c": [27], "access_supply": ["bl1p00v"], "sizing_levels": ["min"],
                     "geometry_levels": ["min", "2x"], "fast_hot_corner": CORNER,
                     "slow_cold_corner": CORNER},
            "stimulus": {"1": stim, "2": stim}, "measurement_notes": ["n"], "records": recs,
        }
        self.pin()

    def pin(self):
        for sel in self.manifest["records"]:
            rid = sel["record_id"]
            sel["record_sha256"] = B.sha256_file(self.root / f"{EXP}/records/{rid}.md")
            sel["snapshot_sha256"] = B.sha256_file(self.root / f"{EXP}/netlist-snapshots/{rid}.spice")
            sel["logs_tree_sha256"] = B.logs_tree_digest(self.root, self.root / f"{EXP}/corners/{rid}")
        self.path = self.root / "sim/characterization-report/inputs.json"
        write(self.path, json.dumps(self.manifest, indent=2) + "\n")

    def build(self):
        rep, md, _ = B.build(self.root, self.path)
        return rep, md

    def region(self, rep, reg):
        return next(r for r in rep["regions"] if r["region"] == reg)


class SyntheticTests(unittest.TestCase):
    def setUp(self):
        self._t = tempfile.TemporaryDirectory()
        self.addCleanup(self._t.cleanup)
        self.fx = Fixture(Path(self._t.name))

    def kinds(self, rep):
        return {d["kind"] for d in rep["disclosures"]}

    def test_split_populations_never_pooled(self):
        rep, md = self.fx.build()
        r1, r2 = self.fx.region(rep, "I"), self.fx.region(rep, "II")
        for reg, r in (("I", r1), ("II", r2)):
            ioff, ron, cap = self.fx.vals[reg]
            for geom, mult in (("min", 1), ("2x", 2)):
                e = r["sub_configs"][f"access-min_cap-{geom}"]["access_corners"][CORNER]
                self.assertAlmostEqual(e["ron_ohm"]["value"], ron * mult, places=6)
                self.assertAlmostEqual(e["ioff_a"]["+0.3V"]["value"], ioff * mult * 3, delta=1e-22)
                c = r["sub_configs"][f"access-min_cap-{geom}"]["cap_corners"]["moscap_typical_27c_nosupply"]
                self.assertAlmostEqual(c["capacitance_f"]["+0V"]["value"], cap * mult, delta=1e-22)
        # different geometry sub-configs of one region stay separate and differ
        self.assertNotEqual(
            r1["sub_configs"]["access-min_cap-min"]["worst_case"],
            r1["sub_configs"]["access-min_cap-2x"]["worst_case"])
        # no pooled/aggregate keys anywhere at the report top level
        self.assertFalse({"mean", "average", "pooled", "overall"} & set(rep))

    def test_every_value_has_locator_into_its_own_log(self):
        rep, _ = self.fx.build()
        for r in rep["regions"]:
            for sub in r["sub_configs"].values():
                for cid, e in sub["access_corners"].items():
                    for v in list(e["ioff_a"].values()) + [e["ron_ohm"]]:
                        path, key = v["source"].split("#")
                        self.assertIn(r["record_id"], path)
                        self.assertTrue(path.endswith(f"{cid}.log"))
                        self.assertTrue((self.fx.root / path).is_file())
                        self.assertEqual(B.parse_scalar((self.fx.root / path).read_text(), key), v["value"])

    def test_unmeasured_and_scope_always_disclosed(self):
        rep, md = self.fx.build()
        self.assertEqual({u["quantity"] for u in rep["unmeasured"]},
                         {"programming_yield", "full_sense_margin", "retention"})
        self.assertTrue(all(u["status"] == "unmeasured" for u in rep["unmeasured"]))
        self.assertEqual(rep["status"], "incomplete")
        self.assertFalse(rep["item_8_contract"]["met"])
        self.assertIn("not cover the whole block", rep["scope"])
        self.assertIn("NOT met", md)

    def test_deterministic(self):
        a = B.canonical(self.fx.build()[0])
        b = B.canonical(self.fx.build()[0])
        self.assertEqual(a, b)

    def test_headline_cross_check_consistent(self):
        rep, _ = self.fx.build()
        self.assertEqual(set(self.fx.region(rep, "I")["record_headline_cross_check"]["result"].values()),
                         {"consistent"})

    def test_missing_input_log(self):
        rid = self.fx.rids["II"]
        p = self.fx.root / f"{EXP}/corners/{rid}/access-min_cap-2x/{CORNER}.log"
        p.unlink()
        self.fx.pin()  # re-pin so the hole is a missing corner, not a hash mismatch
        rep, md = self.fx.build()
        self.assertIn("missing_corner", self.kinds(rep))
        self.assertEqual(rep["status"], "incomplete")
        e = self.fx.region(rep, "II")["sub_configs"]["access-min_cap-2x"]["access_corners"][CORNER]
        self.assertEqual(e["status"], "missing")
        self.assertNotIn("ron_ohm", e)
        self.assertIn("MISSING/FAILED", md)
        # region I is unaffected
        self.assertEqual(self.fx.region(rep, "I")["record_status"], "ok")

    def test_missing_record_file(self):
        (self.fx.root / f"{EXP}/records/{self.fx.rids['I']}.md").unlink()
        rep, _ = self.fx.build()
        r = self.fx.region(rep, "I")
        self.assertEqual(r["record_status"], "missing")
        self.assertEqual(r["sub_configs"], {})
        self.assertEqual(rep["status"], "incomplete")

    def test_missing_region_selection(self):
        self.fx.manifest["records"].pop()
        self.fx.pin()
        rep, _ = self.fx.build()
        self.assertIn("missing_region", self.kinds(rep))

    def test_failed_corner(self):
        rid = self.fx.rids["I"]
        write(self.fx.root / f"{EXP}/corners/{rid}/access-min_cap-min/{CORNER}.log",
              "ioff_lo = 1e-13\nError: no convergence\n")
        self.fx.pin()
        rep, _ = self.fx.build()
        self.assertIn("failed_corner", self.kinds(rep))
        self.assertEqual(self.fx.region(rep, "I")["record_status"], "failed")

    def test_hash_mismatch_excludes_values(self):
        rid = self.fx.rids["I"]
        p = self.fx.root / f"{EXP}/corners/{rid}/access-min_cap-min/{CORNER}.log"
        p.write_text(p.read_text() + "\n")  # evidence moved after pinning
        rep, _ = self.fx.build()
        r = self.fx.region(rep, "I")
        self.assertEqual(r["record_status"], "hash_mismatch")
        self.assertEqual(r["sub_configs"], {})

    def test_superseded_record_is_stale(self):
        newer = "20260102-000000-bbbbbbb"
        write(self.fx.root / f"{EXP}/records/{newer}.md",
              record_text(newer, "I", 1, 1.0, 1.0, supersedes=self.fx.rids["I"]))
        rep, _ = self.fx.build()
        r = self.fx.region(rep, "I")
        self.assertEqual(r["record_status"], "superseded")
        self.assertEqual(r["sub_configs"], {})
        self.assertIn(newer, [d["detail"] for d in rep["disclosures"] if d["kind"] == "superseded"][0])
        self.assertEqual(self.fx.region(rep, "II")["record_status"], "ok")

    def test_design_netlist_drift_is_stale(self):
        write(self.fx.root / "design/netlists/cell_candidate2.spice", SNAP + "* edited\n")
        rep, _ = self.fx.build()
        self.assertEqual(self.fx.region(rep, "II")["record_status"], "stale")
        self.assertEqual(rep["status"], "incomplete")

    def test_incompatible_pdk_revision(self):
        rid = self.fx.rids["II"]
        write(self.fx.root / f"{EXP}/records/{rid}.md",
              record_text(rid, "II", 2, 1.0, 1.0, pdk="0" * 40))
        self.fx.pin()
        rep, _ = self.fx.build()
        self.assertEqual(self.fx.region(rep, "II")["record_status"], "incompatible")

    def test_incompatible_region_claim(self):
        self.fx.manifest["records"][0]["region"] = "II"
        self.fx.pin()
        rep, _ = self.fx.build()
        self.assertEqual(self.fx.region(rep, "II")["record_status"] in ("incompatible", "ok"), True)
        self.assertIn("incompatible", self.kinds(rep))

    def test_inconsistent_headline_disclosed(self):
        rid = self.fx.rids["I"]
        write(self.fx.root / f"{EXP}/records/{rid}.md", record_text(rid, "I", 1, 9.9e-3, 2e4))
        self.fx.pin()
        rep, _ = self.fx.build()
        self.assertIn("inconsistent_record_headline", self.kinds(rep))

    def test_envelope_refused_unless_complete(self):
        rep, _ = self.fx.build()
        with self.assertRaises(SystemExit):
            B.envelope_for(rep)

    def test_bundle_is_append_only(self):
        out = self.fx.root / "sim/characterization-report"
        self.assertEqual(B.main(["--root", str(self.fx.root)]), 0)
        self.assertEqual(B.main(["--root", str(self.fx.root), "--check"]), 0)
        bundle = next((out / "bundles").iterdir())
        (bundle / "report.md").write_text("tampered")
        self.assertEqual(B.main(["--root", str(self.fx.root)]), 2)
        self.assertEqual(B.main(["--root", str(self.fx.root), "--check"]), 1)


class CommittedBundleTests(unittest.TestCase):
    def test_committed_bundle_reproduces_byte_for_byte(self):
        self.assertEqual(B.main(["--root", str(REPO), "--check"]), 0)

    def test_committed_report_states_unmeasured_and_scope(self):
        inputs = REPO / "sim/characterization-report/inputs.json"
        rep, _, bid = B.build(REPO, inputs)
        self.assertEqual(rep["status"], "incomplete")
        self.assertEqual([r["region"] for r in rep["regions"]], ["I", "II", "III"])
        self.assertTrue(all(r["record_status"] == "ok" for r in rep["regions"]))
        # three distinct populations: values differ between regions
        worst = {r["region"]: r["sub_configs"]["access-min_cap-min"]["worst_case"]["max_ron_ohm_any_corner"]["value"]
                 for r in rep["regions"]}
        self.assertEqual(len(set(worst.values())), 3)


if __name__ == "__main__":
    unittest.main()
