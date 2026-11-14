"""Targeted tests for the klt-report elision in sim/harness/report.py.

The elision is the committed form of every klt report this repo writes
(`sim/array-slice-bench/README.md`), so what it must *not* touch is the
interesting part: every measurement value, corner status, diagnostic,
`environment`, `provenance` and coverage counter has to survive byte-identical.
A committed report is used as the fixture so the test is anchored to a real
klt payload, not a hand-built one.  Run:

    python3 -m unittest discover -s sim/harness/tests
"""

import json
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(HERE.parent.parent))
from harness import report as R  # noqa: E402

FIXTURE = (REPO / "sim" / "cell-device-characterization" / "klt" / "runs"
           / "20261009-014137-8d6e70b" / "c1_access-2x_cap-2x" / "ioff" / "report.json")


def fixture_report() -> dict:
    return json.loads(FIXTURE.read_text())


class ElideCoverage(unittest.TestCase):
    def test_fixture_is_the_shape_the_elision_targets(self):
        """Guard the premise: the fixture really does carry populated id lists."""
        cov = fixture_report()["coverage"]
        self.assertGreater(len(cov["checked"]), 0)
        self.assertGreater(len(cov["inapplicable"]), 0)
        self.assertEqual({e["reason"] for e in cov["inapplicable"]},
                         {"characterization_without_limits"})
        self.assertEqual(cov["measurements_with_limits"], 0)

    def test_id_lists_become_counts(self):
        rep = fixture_report()
        n_checked = len(rep["coverage"]["checked"])
        n_inapp = len(rep["coverage"]["inapplicable"])
        out = R.elide_coverage(rep)
        self.assertEqual(out["coverage"]["checked"],
                         f"<{n_checked} entries elided by sim/harness/report.py elide_coverage()>")
        self.assertEqual(out["coverage"]["inapplicable"],
                         f"<{n_inapp} entries elided by sim/harness/report.py elide_coverage()>")

    def test_everything_else_is_byte_identical(self):
        rep = fixture_report()
        out = R.elide_coverage(rep)
        # Every top-level key survives; only the two coverage members differ.
        self.assertEqual(sorted(out), sorted(rep))
        for k in rep:
            if k == "coverage":
                continue
            self.assertEqual(json.dumps(out[k], sort_keys=True),
                             json.dumps(rep[k], sort_keys=True), msg=k)
        # ... including every measurement value and corner status inside `corners`.
        self.assertGreater(len(out["corners"]), 0)
        for a, b in zip(out["corners"], rep["corners"]):
            self.assertEqual(a["status"], b["status"])
            self.assertEqual(a["measurements"], b["measurements"])
        # ... and every coverage counter / short list other than the two id lists.
        for k, v in rep["coverage"].items():
            if k in R.COVERAGE_ID_KEYS:
                continue
            self.assertEqual(out["coverage"][k], v, msg=k)

    def test_does_not_mutate_its_argument(self):
        rep = fixture_report()
        before = json.dumps(rep, sort_keys=True)
        R.elide_coverage(rep)
        self.assertEqual(json.dumps(rep, sort_keys=True), before)

    def test_absent_or_odd_coverage_is_left_alone(self):
        for rep in ({"corners": []},
                    {"coverage": {}},
                    {"coverage": {"checked": "already elided"}},
                    {"coverage": None}):
            self.assertEqual(R.elide_coverage(rep), rep)

    def test_empty_lists_still_elide_to_a_zero_count(self):
        out = R.elide_coverage({"coverage": {"checked": [], "inapplicable": []}})
        self.assertEqual(out["coverage"]["checked"],
                         "<0 entries elided by sim/harness/report.py elide_coverage()>")


class KltReportPayload(unittest.TestCase):
    def test_sha256_is_of_the_full_text_the_runner_would_have_written(self):
        import hashlib
        rep = fixture_report()
        _text, sha = R.klt_report_payload(rep, indent=2)
        full = json.dumps(rep, indent=2) + "\n"
        self.assertEqual(sha, hashlib.sha256(full.encode()).hexdigest())
        # klt's own `--format json` stdout is exactly that serialisation, so the
        # digest attests the bytes the campaign runner received.
        self.assertEqual(full, FIXTURE.read_text())

    def test_text_is_the_elided_report_at_the_requested_indent(self):
        rep = fixture_report()
        text, _sha = R.klt_report_payload(rep, indent=2)
        self.assertTrue(text.endswith("\n"))
        self.assertEqual(json.loads(text), R.elide_coverage(rep))
        self.assertEqual(text, json.dumps(R.elide_coverage(rep), indent=2) + "\n")

    def test_compact_form_matches_array_slice_bench_committed_style(self):
        rep = fixture_report()
        text, _sha = R.klt_report_payload(rep, indent=None, separators=(",", ":"))
        self.assertEqual(text.count("\n"), 1)
        self.assertEqual(json.loads(text), R.elide_coverage(rep))

    def test_elision_actually_saves_the_bulk_of_the_file(self):
        rep = fixture_report()
        text, _sha = R.klt_report_payload(rep, indent=2)
        full = json.dumps(rep, indent=2) + "\n"
        self.assertLess(len(text), len(full) * 0.8)


if __name__ == "__main__":
    unittest.main()
