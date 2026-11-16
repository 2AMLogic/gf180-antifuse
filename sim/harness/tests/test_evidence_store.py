"""Tests for sim/harness/evidence_store.py with a stubbed `klt` (fail-closed paths).

    python3 -m unittest discover -s sim/harness/tests
"""

import json
import stat
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from harness import evidence_store as E  # noqa: E402

STUB = r'''#!/usr/bin/env python3
import hashlib, json, os, sys
a = sys.argv[1:]
if a[:3] == ["artifact", "put", "--help"]:
    sys.exit(int(os.environ.get("STUB_HELP_RC", "0")))
if os.environ.get("STUB_PUT_FAIL_ON") and a[-1].endswith(os.environ["STUB_PUT_FAIL_ON"]):
    print("broker_unreachable", file=sys.stderr); sys.exit(1)
m, name, f = a[a.index("--manifest") + 1], a[a.index("--name") + 1], a[-1]
data = open(f, "rb").read()
doc = json.load(open(m)) if os.path.exists(m) else {"schema_version": 1, "entries": []}
h = hashlib.sha256(data).hexdigest()
doc["entries"].append({"sha256": h, "size": len(data), "kind": "evidence",
    "producer": {"tool": "klt", "version": "0", "loom.repo": "o/n", "commit": None},
    "uri": "artifact:evidence/o__n/" + h[:2] + "/" + h, "name": name})
json.dump(doc, open(m, "w"))
'''


class EvidenceStoreTest(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()
        self.root = self.tmp / "repo"
        self.root.mkdir()
        stub = self.tmp / "klt"
        stub.write_text(STUB)
        stub.chmod(stub.stat().st_mode | stat.S_IXUSR)
        self.klt = [str(stub)]
        self.src = self.tmp / "src"
        self.src.mkdir()
        (self.src / "a.log").write_text("aaa")
        (self.src / "b.log").write_text("bbbb")
        self.files = {"corners/ss_-40c_bl0p90v.log": self.src / "a.log",
                      "corners/ff_125c_bl1p10v.log": self.src / "b.log"}
        self.env = {"KLT_ARTIFACT_BROKER": "http://broker.invalid", "PATH": "/usr/bin:/bin"}

    def store(self, **kw):
        env = {**self.env, **kw.pop("extra", {})}
        env.update(kw.pop("env_override", {}))
        return E.store_run("bench", "rid", self.files, self.root, klt_cmd=self.klt, env=env)

    def tracked_tree(self):
        return sorted(p.relative_to(self.root) for p in (self.root / "manifests").rglob("*") if p.is_file()) \
            if (self.root / "manifests").exists() else []

    def test_success_writes_manifest_with_corner_names(self):
        rows = self.store()
        m = json.loads(E.manifest_path(self.root, "bench", "rid").read_text())
        self.assertEqual({e["name"] for e in m["entries"]}, set(self.files))
        self.assertTrue(all(e["uri"].startswith("artifact:") for e in m["entries"]))
        self.assertEqual({r["name"] for r in rows}, set(self.files))

    def test_broker_unset_fails_closed(self):
        with self.assertRaises(E.EvidenceStoreError):
            E.store_run("bench", "rid", self.files, self.root, klt_cmd=self.klt, env={"PATH": "/bin"})
        self.assertEqual(self.tracked_tree(), [])
        self.assertFalse((self.root / E.SCRATCH_REL).exists())

    def test_klt_without_put_fails_closed(self):
        with self.assertRaises(E.EvidenceStoreError):
            self.store(extra={"STUB_HELP_RC": "2"})
        self.assertEqual(self.tracked_tree(), [])

    def test_broker_unreachable_mid_run_leaves_no_manifest(self):
        with self.assertRaises(E.EvidenceStoreError):
            self.store(extra={"STUB_PUT_FAIL_ON": "ff_125c_bl1p10v.log"})
        self.assertEqual(self.tracked_tree(), [])

    def test_existing_manifest_not_overwritten(self):
        self.store()
        with self.assertRaises(FileExistsError):
            self.store()

    def test_unsafe_name_rejected(self):
        self.files = {"../escape.log": self.src / "a.log"}
        with self.assertRaises(E.EvidenceStoreError):
            self.store()

    def test_publish_run_keeps_corner_paths(self):
        run = self.tmp / "run"
        (run / "ss_-40c" / "regionA").mkdir(parents=True)
        (run / "ss_-40c" / "regionA" / "x.log").write_text("x")
        (run / "ff_125c").mkdir()
        (run / "ff_125c" / "y.log").write_text("yy")
        rows = E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        self.assertEqual({r["name"] for r in rows}, {"ss_-40c/regionA/x.log", "ff_125c/y.log"})

    def work_run(self):
        """A run dir shaped like a real klt run: named outputs + a .work/ scratch tree."""
        run = self.tmp / "workrun"
        corner = "moscap_ff_-40c_vpp13p68v"
        (run / "prog_b0").mkdir(parents=True)
        (run / "prog_b0" / f"{corner}.cir").write_text("* deck\n.end\n")
        (run / "prog_b0" / f"{corner}.log").write_text("ngspice says hello\n")
        work = run / "prog_b0" / ".work" / "klt" / "moscap_ff_13p680V_n40C"
        work.mkdir(parents=True)
        # Skipped: regenerated per-corner ngspice init file.
        (work / ".spiceinit").write_text("set ngbehavior=ps\n")
        # Skipped: klt's internally-named copy of the deck published above.
        (work / "corner.cir").write_text("* deck\n.end\n")
        # Kept: fleet job provenance, the only copy of it.
        (run / "prog_b0" / ".work" / "klt" / "batch-receipt.json").write_text('{"job": "j-1"}')
        # Kept: a simulator log this bench never copies out under a corner-id name.
        (work / "ngspice.log").write_text("twinless log\n")
        return run

    def test_publish_run_skips_only_disposable_work_scratch(self):
        run = self.work_run()
        corner = "moscap_ff_-40c_vpp13p68v"
        rows = E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        self.assertEqual({r["name"] for r in rows}, {
            f"prog_b0/{corner}.cir",
            f"prog_b0/{corner}.log",
            "prog_b0/.work/klt/batch-receipt.json",
            "prog_b0/.work/klt/moscap_ff_13p680V_n40C/ngspice.log",
        })
        m = json.loads(E.manifest_path(self.root, "bench", "rid").read_text())
        self.assertEqual({e["name"] for e in m["entries"]}, {r["name"] for r in rows})

    def test_collect_keeps_work_receipt_even_when_bytes_duplicate(self):
        """Provenance is kept unconditionally, not just when its bytes are unique."""
        run = self.tmp / "dupreceipt"
        (run / ".work" / "klt").mkdir(parents=True)
        (run / "receipt-copy.json").write_text('{"job": "j-1"}')
        (run / ".work" / "klt" / "batch-receipt.json").write_text('{"job": "j-1"}')
        self.assertIn(".work/klt/batch-receipt.json", E.collect_run_files(run))

    def test_collect_never_skips_outside_work(self):
        """A .spiceinit or a duplicate outside .work/ is a named output, not scratch."""
        run = self.tmp / "nowork"
        (run / "corners").mkdir(parents=True)
        (run / ".spiceinit").write_text("set ngbehavior=ps\n")
        (run / "corners" / "a.log").write_text("same bytes\n")
        (run / "corners" / "b.log").write_text("same bytes\n")
        self.assertEqual(set(E.collect_run_files(run)), {".spiceinit", "corners/a.log", "corners/b.log"})

    def test_collect_keeps_work_file_differing_only_in_bytes(self):
        """Same name as a published twin but different bytes: not a double-store."""
        run = self.tmp / "sizes"
        (run / ".work" / "klt" / "c0").mkdir(parents=True)
        (run / "ss_-40c.cir").write_text("* deck A\n")
        (run / ".work" / "klt" / "c0" / "corner.cir").write_text("* deck B\n")  # equal size, different bytes
        self.assertIn(".work/klt/c0/corner.cir", E.collect_run_files(run))

    def test_collect_prefix_applies_to_kept_entries(self):
        run = self.work_run()
        names = set(E.collect_run_files(run, prefix="rid/"))
        self.assertTrue(all(n.startswith("rid/") for n in names))
        self.assertEqual(len(names), 4)

    def test_publish_empty_run_fails_closed(self):
        run = self.tmp / "empty"
        run.mkdir()
        with self.assertRaises(E.EvidenceStoreError):
            E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        self.assertEqual(self.tracked_tree(), [])

    def test_publish_for_runner_ok_and_fail_closed(self):
        run = self.tmp / "run"
        run.mkdir()
        (run / "c1.log").write_text("x")
        self.assertEqual(E.publish_for_runner("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env), 0)
        run2 = self.tmp / "run2"
        run2.mkdir()
        (run2 / "c1.log").write_text("x")
        self.assertEqual(E.publish_for_runner("bench", "rid2", run2, self.root, klt_cmd=self.klt, env={}), 1)
        self.assertFalse(E.manifest_path(self.root, "bench", "rid2").exists())


if __name__ == "__main__":
    unittest.main()
