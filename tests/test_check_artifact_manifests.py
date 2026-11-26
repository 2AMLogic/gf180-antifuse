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


class GrandfatheredTests(unittest.TestCase):
    """Tracked-bytes exemption: a file is exempt only when every manifest
    listing its (size, sha256) is on the allowlist (issue #346 ruling)."""

    def _repo(self, td, data=b"raw evidence"):
        root = Path(td)
        subprocess.run(["git", "init", "-q", str(root)], check=True)
        (root / "run.log").write_bytes(data)
        subprocess.run(["git", "-C", str(root), "add", "run.log"], check=True)
        return root

    def _text(self, data):
        doc = json.loads((FIX / "good.manifest.json").read_text())
        doc["entries"][0].update(sha256=hashlib.sha256(data).hexdigest(), size=len(data))
        return json.dumps(doc)

    def test_load_allowlist_parses_comments_and_skips_blanks(self):
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "grandfathered.txt"
            p.write_text("# header citing the ruling\n\ngf.manifest.json\n  other.manifest.json  \n")
            self.assertEqual(cam.load_allowlist(p), frozenset({"gf.manifest.json", "other.manifest.json"}))
            self.assertEqual(cam.load_allowlist(p.parent / "missing.txt"), frozenset())

    def test_new_manifest_not_allowlisted_still_fails(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"raw evidence"
            root = self._repo(td, data)
            m = root / "new.manifest.json"
            e = cam.check_no_tracked_bytes({m: self._text(data)}, root,
                                           frozenset({"old.manifest.json"}))
            self.assertTrue(e and "committed AND stored" in e[0], e)

    def test_shared_sha_allowlisted_and_not_still_fails(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"raw evidence"
            root = self._repo(td, data)
            text = self._text(data)
            ms = {root / "gf.manifest.json": text, root / "new.manifest.json": text}
            e = cam.check_no_tracked_bytes(ms, root, frozenset({"gf.manifest.json"}))
            self.assertTrue(e and "committed AND stored" in e[0], e)
            self.assertTrue("new.manifest.json" in e[0], e)

    def test_allowlisted_manifest_passes(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"raw evidence"
            root = self._repo(td, data)
            text = self._text(data)
            ms = {root / "gf.manifest.json": text, root / "other.manifest.json": text}
            allow = frozenset({"gf.manifest.json", "other.manifest.json"})
            self.assertEqual(cam.check_no_tracked_bytes(ms, root, allow), [])
            self.assertEqual(cam.check_no_tracked_bytes({root / "gf.manifest.json": text}, root,
                                                        frozenset({"gf.manifest.json"})), [])

    def test_empty_allowlist_reproduces_tracked_bytes_failure(self):
        with tempfile.TemporaryDirectory() as td:
            data = b"raw evidence"
            root = self._repo(td, data)
            e = cam.check_no_tracked_bytes({root / "gf.manifest.json": self._text(data)}, root,
                                           frozenset())
            self.assertTrue(e and "committed AND stored" in e[0], e)


if __name__ == "__main__":
    unittest.main()
