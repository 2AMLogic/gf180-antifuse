"""The `<report>.json.sha256` sidecar is written only when the full text was held.

Issue #330. The sidecar's only meaning is the sha256 of the report's full,
un-elided text -- the thing that makes a committed elision auditable against
a re-fetched raw klt report. ``--analyze-report`` reads its report off disk,
and the file a developer points it at is usually an already-elided committed
report: the elision is a no-op on it, so a digest written there would attest
the elided file sitting beside it, not the raw report it claims to attest --
an inverted, misleading attestation in append-only evidence. ``slim_payload``
therefore reports ``None`` (no attestable digest) for already-elided input
and the write sites skip only the sidecar. The "already elided" decision is
structural (``harness.report.coverage_is_elided``: a coverage id value that
is not a list), never a marker-text match -- reports committed before the
marker moved to report.py carry an older ``slim()`` marker.

Stdlib unittest (``tests/`` is discovered by ``npm run check:ci``).
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))

from harness import report as R  # noqa: E402
from harness.modload import load_module  # noqa: E402

BENCH = SIM / "array-slice-bench" / "run_bench.py"
MOD = load_module(BENCH, "array_slice_bench_run_bench_test")

# A committed, already-elided slice report (premise-guarded below).
COMMITTED = (SIM / "array-slice-bench" / "reports" / "20261009-021330-3010ff8"
             / "slice_i_ii_ff.report.json")
# A raw, un-elided klt report (the same fixture test_report_elision.py uses).
RAW = (SIM / "cell-device-characterization" / "klt" / "runs"
       / "20261009-014137-8d6e70b" / "c1_access-2x_cap-2x" / "ioff" / "report.json")


def committed_report() -> dict:
    return json.loads(COMMITTED.read_text())


def raw_report() -> dict:
    return json.loads(RAW.read_text())


def slim_text(report: dict) -> str:
    return json.dumps(report, indent=None, separators=(",", ":")) + "\n"


class Premise(unittest.TestCase):
    """Guard the fixtures: one committed/elided, one raw/intact."""

    def test_committed_fixture_is_already_elided(self):
        self.assertIsInstance(committed_report()["coverage"]["checked"], str)

    def test_raw_fixture_still_carries_the_id_lists(self):
        self.assertIsInstance(raw_report()["coverage"]["checked"], list)


class CoverageIsElided(unittest.TestCase):
    """Structural, list/str-based -- never a marker-text match."""

    def test_recognises_the_current_marker(self):
        self.assertTrue(R.coverage_is_elided(R.elide_coverage(raw_report())))

    def test_recognises_the_older_slim_marker(self):
        # The marker text moved to report.py after some reports were
        # committed; a marker-matching predicate would silently miss exactly
        # those reports -- the ones --analyze-report is most likely pointed at.
        old = {"coverage": {"checked": "<4608 entries elided by run_bench.py slim()>"}}
        self.assertTrue(R.coverage_is_elided(old))

    def test_arbitrary_str_value_counts_as_elided(self):
        self.assertTrue(R.coverage_is_elided({"coverage": {"checked": "anything"}}))

    def test_both_id_keys_present_as_lists_is_not_elided(self):
        self.assertFalse(R.coverage_is_elided(
            {"coverage": {"checked": ["a"], "inapplicable": [{"reason": "x"}]}}))

    def test_empty_lists_are_not_elided(self):
        self.assertFalse(R.coverage_is_elided({"coverage": {"checked": [], "inapplicable": []}}))

    def test_no_coverage_key_is_not_elided(self):
        self.assertFalse(R.coverage_is_elided({"corners": []}))

    def test_one_elided_one_intact_id_key_is_elided(self):
        # No honest full text exists for a half-elided report either.
        self.assertTrue(R.coverage_is_elided(
            {"coverage": {"checked": "<2 entries elided>", "inapplicable": []}}))


class SlimPayloadDigest(unittest.TestCase):
    def test_raw_report_digest_is_the_sha256_of_its_full_text(self):
        rep = raw_report()
        text, sha = MOD.slim_payload(rep)
        self.assertEqual(text, slim_text(R.elide_coverage(rep)))
        self.assertEqual(sha, hashlib.sha256(slim_text(rep).encode()).hexdigest())

    def test_already_elided_report_has_no_attestable_digest(self):
        rep = committed_report()
        text, sha = MOD.slim_payload(rep)
        self.assertIsNone(sha)
        self.assertEqual(text, slim_text(rep))

    def test_elision_is_idempotent_and_then_unattestable(self):
        once = R.elide_coverage(raw_report())
        twice = R.elide_coverage(once)
        self.assertEqual(twice, once)
        _text, sha = MOD.slim_payload(twice)
        self.assertIsNone(sha)


class WriteSite(unittest.TestCase):
    def test_digest_payload_writes_report_and_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            rp = Path(d) / "slice_all.report.json"
            MOD.write_report_and_digest(rp, ("full-text-attested\n", "abc123"))
            self.assertEqual(rp.read_text(), "full-text-attested\n")
            self.assertEqual(rp.with_name(rp.name + ".sha256").read_text(), "abc123\n")

    def test_digestless_payload_writes_report_but_no_sidecar(self):
        with tempfile.TemporaryDirectory() as d:
            rp = Path(d) / "slice_all.report.json"
            MOD.write_report_and_digest(rp, ("elided text\n", None))
            self.assertEqual(rp.read_text(), "elided text\n")
            self.assertFalse(rp.with_name(rp.name + ".sha256").exists())


if __name__ == "__main__":
    unittest.main()
