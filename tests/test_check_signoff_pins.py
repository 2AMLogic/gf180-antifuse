"""Tests for scripts/check_signoff_pins.py (unittest; also runs under pytest).

Covers the drift cases `klt signoff --check` and verify.sh cannot see: a
stale manifest pin on a row that already grades check_failed, one part of a
compound citation drifting, and the named input artifact changing bytes
(issue #443).
"""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_signoff_pins as csp  # noqa: E402

GDS = "layout/cell_candidate1/cell_candidate1.gds"


def sha(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def write(path: Path, doc) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc, indent=2) + "\n")


def envelope(input_hash: str, style: str = "file", status: str = "clean") -> dict:
    """A minimal klt envelope naming GDS as its input.

    style: 'file' (DRC/ERC top-level file), 'layout' (LVS top-level layout),
    'provenance' (generic attestation provenance.input.path).
    """
    prov = {"input": {"content_hash": input_hash, "role": "layout"}}
    doc = {"schema_version": 1, "status": status, "provenance": prov}
    if style == "file":
        doc["file"] = {"path": GDS, "scope": "repo"}
    elif style == "layout":
        doc["layout"] = {"path": GDS, "scope": "repo"}
    elif style == "provenance":
        prov["input"]["path"] = {"path": GDS, "scope": "repo"}
    else:
        raise ValueError(style)
    return doc


def build_tree(td, gds_bytes=b"gds-bytes", evidence=None) -> Path:
    root = Path(td)
    (root / GDS).parent.mkdir(parents=True, exist_ok=True)
    (root / GDS).write_bytes(gds_bytes)
    h = sha(gds_bytes)
    write(root / "layout/cell_candidate1/drc_native_report.json",
          envelope(h, "file", status="violations"))
    write(root / "layout/cell_candidate1/lvs_report.json", envelope(h, "layout"))
    write(root / "layout/cell_candidate1/erc_report.json", envelope(h, "file"))
    write(root / "signoff/attestations/item-1-digital.json", envelope(h, "provenance"))
    if evidence is None:
        evidence = {
            "3.analog": {"file": "layout/cell_candidate1/drc_native_report.json",
                         "content_hash": h},
            "4.analog": {"file": "layout/cell_candidate1/lvs_report.json",
                         "content_hash": h},
            "1.digital": {"file": "signoff/attestations/item-1-digital.json",
                          "content_hash": h},
            "11.analog": [
                {"file": "layout/cell_candidate1/erc_report.json", "content_hash": h},
                {"file": "layout/cell_candidate1/lvs_report.json", "content_hash": h},
            ],
        }
    write(root / "signoff/manifest.json",
          {"block": "gf180-antifuse", "kind": "mixed-signal", "evidence": evidence})
    return root


class GoodTreeTests(unittest.TestCase):
    def test_all_citation_styles_pass(self):
        """file (DRC/ERC), layout (LVS), provenance.input.path (attestations)
        and a compound citation all resolve and agree."""
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td)
            self.assertEqual(csp.check_pins(root), [])


class StalePinTests(unittest.TestCase):
    def test_stale_pin_on_failing_row_is_reported(self):
        """The #443 case: a row whose envelope grades check_failed renders no
        citation in report.json, so the grader's --check misses a stale pin."""
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td)
            m = json.loads((root / "signoff/manifest.json").read_text())
            m["evidence"]["3.analog"]["content_hash"] = "sha256:" + "0" * 64
            write(root / "signoff/manifest.json", m)
            errs = csp.check_pins(root)
            self.assertEqual(len(errs), 1, errs)
            self.assertIn("3.analog", errs[0])
            self.assertIn(GDS, errs[0])

    def test_compound_part_drift_names_part_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td)
            m = json.loads((root / "signoff/manifest.json").read_text())
            m["evidence"]["11.analog"][1]["content_hash"] = "sha256:" + "1" * 64
            write(root / "signoff/manifest.json", m)
            errs = csp.check_pins(root)
            self.assertEqual(len(errs), 1, errs)
            self.assertIn("11.analog", errs[0])
            self.assertIn("[1]", errs[0])

    def test_envelope_recorded_hash_drift_is_reported(self):
        """Manifest pin and artifact bytes agree, but the envelope's own
        provenance.input.content_hash records a third value."""
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td)
            p = root / "layout/cell_candidate1/drc_native_report.json"
            doc = json.loads(p.read_text())
            doc["provenance"]["input"]["content_hash"] = "sha256:" + "2" * 64
            p.write_text(json.dumps(doc, indent=2) + "\n")
            errs = csp.check_pins(root)
            self.assertEqual(len(errs), 1, errs)
            self.assertIn("3.analog", errs[0])


class ChangedBytesTests(unittest.TestCase):
    def test_moved_gds_fails_even_when_manifest_and_envelope_agree(self):
        """The recurrence guard: geometry moved, pin and envelope still name
        the old hash, so only hashing the bytes catches it."""
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td, gds_bytes=b"old-geometry")
            (root / GDS).write_bytes(b"new-geometry")
            errs = csp.check_pins(root)
            self.assertEqual(len(errs), 5, errs)  # every part citing the GDS
            self.assertIn(GDS, errs[0])
            self.assertTrue(all("now sha256:" in e for e in errs), errs)


class MalformedTests(unittest.TestCase):
    def test_missing_envelope_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td)
            (root / "layout/cell_candidate1/lvs_report.json").unlink()
            errs = csp.check_pins(root)
            self.assertEqual(len(errs), 2, errs)  # 4.analog and 11.analog[1]

    def test_envelope_without_input_path_reported(self):
        with tempfile.TemporaryDirectory() as td:
            root = build_tree(td)
            p = root / "layout/cell_candidate1/lvs_report.json"
            doc = json.loads(p.read_text())
            doc.pop("layout")
            p.write_text(json.dumps(doc, indent=2) + "\n")
            errs = csp.check_pins(root)
            self.assertEqual(len(errs), 2, errs)
            self.assertIn("no input path", errs[0])


if __name__ == "__main__":
    unittest.main()
