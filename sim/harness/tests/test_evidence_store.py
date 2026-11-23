"""Tests for sim/harness/evidence_store.py with a stubbed `klt` (fail-closed paths).

    python3 -m unittest discover -s sim/harness/tests
"""

import contextlib
import io
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
h = hashlib.sha256(data).hexdigest()
objdir = os.environ.get("STUB_OBJECT_DIR")
if objdir:
    open(os.path.join(objdir, h), "wb").write(data)
doc = json.load(open(m)) if os.path.exists(m) else {"schema_version": 1, "entries": []}
doc["entries"].append({"sha256": h, "size": len(data), "kind": "evidence",
    "producer": {"tool": "klt", "version": "0", "loom.repo": "o/n", "commit": None},
    "uri": "artifact:evidence/o__n/" + h[:2] + "/" + h, "name": name})
json.dump(doc, open(m, "w"))
sys.exit(0)
'''

GET_STUB = r'''#!/usr/bin/env python3
import hashlib, json, os, sys
a = sys.argv[1:]
if a[:2] != ["artifact", "get"]:
    sys.exit(int(os.environ.get("STUB_HELP_RC", "0")) if a[:3] == ["artifact", "put", "--help"] else 2)
out, ref = a[a.index("-o") + 1], a[-1]
man, sel = ref.split("#", 1)
e = next(x for x in json.load(open(man))["entries"] if x.get("name") == sel or x["sha256"] == sel)
data = open(os.path.join(os.environ["STUB_OBJECT_DIR"], e["sha256"]), "rb").read()
if hashlib.sha256(data).hexdigest() != e["sha256"]:
    print("sha mismatch", file=sys.stderr); sys.exit(1)
open(out, "wb").write(data)
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
        get_stub = self.tmp / "klt-get"
        get_stub.write_text(GET_STUB)
        get_stub.chmod(get_stub.stat().st_mode | stat.S_IXUSR)
        self.klt_get = [str(get_stub)]
        self.objdir = self.tmp / "objects"
        self.objdir.mkdir()
        self.src = self.tmp / "src"
        self.src.mkdir()
        (self.src / "a.log").write_text("aaa")
        (self.src / "b.log").write_text("bbbb")
        self.files = {"corners/ss_-40c_bl0p90v.log": self.src / "a.log",
                      "corners/ff_125c_bl1p10v.log": self.src / "b.log"}
        self.env = {"KLT_ARTIFACT_BROKER": "http://broker.invalid", "PATH": "/usr/bin:/bin",
                    "STUB_OBJECT_DIR": str(self.objdir)}

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

    def test_publish_for_runner_post_manifest_cleanup_failure_says_stored(self):
        # A source that cannot be unlinked (here: its directory is read-only,
        # the same non-FileNotFoundError OSError class
        # test_remove_stored_sources_wraps_unlink_failure provokes) fires
        # AFTER the manifest landed, so the message must state the opposite
        # contract: the evidence IS stored, remove the leftovers by hand,
        # do not re-run.
        run = self.tmp / "run"
        ro = run / "ro"
        ro.mkdir(parents=True)
        (ro / "c1.log").write_text("x")
        (run / "c2.log").write_text("y")
        ro.chmod(0o555)
        self.addCleanup(ro.chmod, 0o755)
        with contextlib.redirect_stderr(io.StringIO()) as err:
            rc = E.publish_for_runner("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        self.assertEqual(rc, 1)
        msg = err.getvalue()
        self.assertNotIn("evidence not stored", msg)
        self.assertIn("evidence IS stored", msg)
        self.assertIn("is in place", msg)
        self.assertIn("do NOT re-run", msg)
        self.assertIn(str(ro / "c1.log"), msg)
        self.assertNotIn(str(run / "c2.log"), msg)
        self.assertTrue(E.manifest_path(self.root, "bench", "rid").exists())
        self.assertTrue((ro / "c1.log").exists())
        self.assertFalse((run / "c2.log").exists())
        run3 = self.tmp / "run3"
        run3.mkdir()
        (run3 / "c1.log").write_text("x")
        with contextlib.redirect_stderr(io.StringIO()) as err2:
            self.assertEqual(E.publish_for_runner("bench", "rid3", run3, self.root, klt_cmd=self.klt, env={}), 1)
        self.assertIn("evidence not stored", err2.getvalue())

    def test_publish_run_removes_stored_files_from_run_dir(self):
        run = self.work_run()
        corner = "moscap_ff_-40c_vpp13p68v"
        work = run / "prog_b0" / ".work" / "klt" / "moscap_ff_13p680V_n40C"
        E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        for gone in (run / "prog_b0" / f"{corner}.cir",
                     run / "prog_b0" / f"{corner}.log",
                     run / "prog_b0" / ".work" / "klt" / "batch-receipt.json",
                     work / "ngspice.log"):
            self.assertFalse(gone.exists(), gone)
        # skipped .work scratch was never stored: left as disposable leftovers
        self.assertTrue((work / ".spiceinit").exists())
        self.assertTrue((work / "corner.cir").exists())
        m = json.loads(E.manifest_path(self.root, "bench", "rid").read_text())
        self.assertEqual(len(m["entries"]), 4)

    def test_publish_run_leaves_run_dir_untouched_on_store_error(self):
        run = self.work_run()
        before = {p: p.read_bytes() for p in sorted(run.rglob("*")) if p.is_file()}
        with self.assertRaises(E.EvidenceStoreError):
            E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt,
                          env={**self.env, "STUB_PUT_FAIL_ON": "vpp13p68v.cir"})
        after = {p: p.read_bytes() for p in sorted(run.rglob("*")) if p.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(E.manifest_path(self.root, "bench", "rid").exists())

    def test_publish_run_prunes_dirs_emptied_inside_repo(self):
        run = self.root / "sim" / "bench" / "corners" / "rid"
        run.mkdir(parents=True)
        (run / "c1.log").write_text("x")
        E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        self.assertFalse(run.exists())
        self.assertFalse((self.root / "sim" / "bench").exists())
        self.assertTrue(E.manifest_path(self.root, "bench", "rid").exists())

    def test_store_run_removes_sources_outside_repo_without_pruning(self):
        E.store_run("bench", "rid", self.files, self.root, klt_cmd=self.klt, env=self.env)
        self.assertFalse((self.src / "a.log").exists())
        self.assertFalse((self.src / "b.log").exists())
        self.assertTrue(self.src.is_dir())

    def test_remove_stored_sources_wraps_unlink_failure(self):
        # A non-FileNotFoundError unlink failure (here: the path became a
        # directory) must surface as EvidenceStoreError naming the leftover,
        # not escape store_run as a bare OSError after the manifest landed.
        (self.src / "b.log").unlink()
        (self.src / "b.log").mkdir()
        with self.assertRaises(E.EvidenceStoreError) as cm:
            E._remove_stored_sources(self.files, self.root)
        self.assertIn(str(self.src / "b.log"), str(cm.exception))
        self.assertTrue((self.src / "b.log").is_dir())

    def test_fetch_run_restores_run_dir_layout_and_bytes(self):
        run = self.work_run()
        E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        dest = self.tmp / "fetched"
        out = E.fetch_run("bench", "rid", self.root, dest=dest, klt_cmd=self.klt_get, env=self.env)
        self.assertEqual(out, dest)
        corner = "moscap_ff_-40c_vpp13p68v"
        self.assertEqual((dest / "prog_b0" / f"{corner}.cir").read_text(), "* deck\n.end\n")
        self.assertEqual((dest / "prog_b0" / ".work" / "klt" / "batch-receipt.json").read_text(), '{"job": "j-1"}')
        self.assertEqual((dest / "prog_b0" / ".work" / "klt" / "moscap_ff_13p680V_n40C" / "ngspice.log").read_text(),
                         "twinless log\n")

    def test_fetch_run_subset_of_names(self):
        run = self.tmp / "subset"
        (run / "a").mkdir(parents=True)
        (run / "a" / "x.log").write_text("x")
        (run / "b").mkdir()
        (run / "b" / "y.log").write_text("yy")
        E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        dest = self.tmp / "fetched-subset"
        E.fetch_run("bench", "rid", self.root, dest=dest, klt_cmd=self.klt_get, env=self.env,
                    names={"a/x.log"})
        self.assertTrue((dest / "a" / "x.log").exists())
        self.assertFalse((dest / "b").exists())

    def test_fetch_run_without_manifest_fails_closed(self):
        with self.assertRaises(E.EvidenceStoreError):
            E.fetch_run("bench", "norid", self.root, dest=self.tmp / "f", klt_cmd=self.klt_get, env=self.env)

    def test_run_dir_for_reading_fetches_consumed_run(self):
        run = self.work_run()
        E.publish_run("bench", "rid", run, self.root, klt_cmd=self.klt, env=self.env)
        base = E.run_dir_for_reading("bench", "rid", self.root, run, klt_cmd=self.klt_get, env=self.env)
        self.assertNotEqual(base, run)
        corner = "moscap_ff_-40c_vpp13p68v"
        self.assertTrue((base / "prog_b0" / f"{corner}.log").exists())

    def test_run_dir_for_reading_prefers_committed_bytes(self):
        # pre-adoption run: report bytes still in the tree, manifest also present
        run = self.root / "sim" / "bench" / "corners" / "old"
        (run / "b1").mkdir(parents=True)
        (run / "b1" / "report.json").write_text("{}")
        E.manifest_path(self.root, "bench", "old").parent.mkdir(parents=True, exist_ok=True)
        E.manifest_path(self.root, "bench", "old").write_text('{"schema_version": 1, "entries": []}')
        self.assertEqual(E.run_dir_for_reading("bench", "old", self.root, run,
                                               klt_cmd=self.klt_get, env=self.env), run)

    def test_run_dir_for_reading_without_manifest_returns_run_dir(self):
        run = self.root / "sim" / "bench" / "corners" / "never-published"
        self.assertEqual(E.run_dir_for_reading("bench", "never-published", self.root, run,
                                               klt_cmd=self.klt_get, env=self.env), run)


if __name__ == "__main__":
    unittest.main()
