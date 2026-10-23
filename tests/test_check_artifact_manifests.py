"""Tests for scripts/check_artifact_manifests.py (unittest; also runs under pytest)."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_artifact_manifests as cam  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "artifact_manifests"


def errs(name):
    return cam.check_text((FIX / name).read_text())


class CheckTextTests(unittest.TestCase):
    def test_good_passes(self):
        self.assertEqual(errs("good.manifest.json"), [])

    def test_non_artifact_uri_rejected(self):
        self.assertTrue(any("artifact:" in e for e in errs("bad_uri.manifest.json")))

    def test_storage_locator_rejected(self):
        self.assertTrue(any("locator" in e for e in errs("bad_s3.manifest.json")))

    def test_unknown_field_rejected(self):
        self.assertTrue(any("field set" in e for e in errs("bad_field.manifest.json")))

    def test_invalid_json_rejected(self):
        self.assertTrue(any("invalid JSON" in e for e in cam.check_text("{")))


class TrackedBytesTests(unittest.TestCase):
    def test_committed_object_bytes_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            data = b"raw evidence"
            (root / "run.log").write_bytes(data)
            subprocess.run(["git", "-C", str(root), "add", "run.log"], check=True)
            doc = json.loads((FIX / "good.manifest.json").read_text())
            doc["entries"][0].update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
            m = root / "m.manifest.json"
            text = json.dumps(doc)
            self.assertEqual(cam.check_text(text), [])
            e = cam.check_no_tracked_bytes({m: text}, root)
            self.assertTrue(e and "committed AND stored" in e[0], e)

    def test_unrelated_tracked_file_passes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            subprocess.run(["git", "init", "-q", str(root)], check=True)
            (root / "a.txt").write_bytes(b"abcd")
            subprocess.run(["git", "-C", str(root), "add", "a.txt"], check=True)
            text = (FIX / "good.manifest.json").read_text()
            self.assertEqual(cam.check_no_tracked_bytes({root / "m": text}, root), [])


if __name__ == "__main__":
    unittest.main()
