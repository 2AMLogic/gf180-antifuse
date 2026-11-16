"""--analyze-report grades only: it must imply --no-write (issue #349).

    python3 -m unittest discover -s sim/array-slice-bench -p 'test_*.py'

Grades a committed single-process klt report and asserts that no record, report
or per-region measurement file is created or modified: the append-only evidence
directories stay byte-identical. A single-process grading cannot satisfy the
PVT-on-every-recorded-result rule, so nothing may reach the evidence tree.
"""

import contextlib
import hashlib
import sys
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(HERE))
import run_bench as RB  # noqa: E402

REPORT = HERE / "reports" / "20261009-021330-3010ff8" / "slice_i_ii_ff.report.json"

EVIDENCE_DIRS = (
    HERE / "records",
    HERE / "reports",
    REPO / "measurements" / "array-slice-bench",
)


def tree_state():
    out = {}
    for d in EVIDENCE_DIRS:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out[str(p.relative_to(REPO))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


class AnalyzeReportWritesNothing(unittest.TestCase):
    def run_main(self, *extra):
        old = sys.argv
        sys.argv = ["run_bench.py", "--analyze-report", str(REPORT), *extra]
        try:
            return RB.main()
        finally:
            sys.argv = old

    def test_analyze_report_implies_no_write(self):
        before = tree_state()
        rc = self.run_main("--slice", "slice_i_ii")
        self.assertEqual(rc, 3, "verdict must match the --no-write baseline (violations in this ff report)")
        self.assertEqual(tree_state(), before)

    def test_analyze_report_without_slice_writes_nothing(self):
        """No --slice grades the one report against every slice; slice_ii_iii's
        columns are absent from this slice_i_ii report so grading itself may
        fail -- either way the write path is unreachable."""
        before = tree_state()
        with contextlib.suppress(Exception):
            self.run_main()
        self.assertEqual(tree_state(), before)


if __name__ == "__main__":
    unittest.main()
