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
from harness import report  # noqa: E402

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
        self.assertIn("ss_-40c_bl0p90v", report.object_table(rows))

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


if __name__ == "__main__":
    unittest.main()
