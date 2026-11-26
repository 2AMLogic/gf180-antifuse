"""--analyze-report grades only: it must imply --no-write (issue #349), and
the grading must never reach the live checkout, even when it fails or when the
write path regresses (issue #351).

    python3 -m unittest discover -s sim/array-slice-bench -p 'test_*.py'

Grades a committed single-process klt report and asserts that no record, report
or per-region measurement file is created or modified: run_bench.main() runs
against a throwaway tree holding only the read-only inputs the grading reads
(design/netlists/<slice>.spice), with every write target (records/, reports/,
measurements/) resolving inside the tmp tree -- so a write-path regression is
detected as a change inside the tmp copy instead of corrupting the append-only
evidence directories. A single-process grading cannot satisfy the
PVT-on-every-recorded-result rule, so nothing may reach the evidence tree.
"""

import contextlib
import hashlib
import io
import shutil
import sys
import tempfile
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


def tree_state(dirs, root):
    """{path relative to root: sha256} of every file under dirs -- the state
    the append-only evidence contract says may never change across a call."""
    out = {}
    for d in dirs:
        if not d.exists():
            continue
        for p in sorted(d.rglob("*")):
            if p.is_file():
                out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


@contextlib.contextmanager
def tmp_checkout():
    """Repoint run_bench's HERE/REPO at a throwaway tree for the call.

    The tmp tree carries the only input the --analyze-report path resolves
    through REPO (design/netlists/<slice>.spice); records/, reports/ and
    measurements/ resolve inside it too and start absent, so everything
    main() can write lands in the tmp tree, never in this checkout.
    Repointed back (and the tree deleted) on exit, also when main() raises."""
    tmp = Path(tempfile.mkdtemp(prefix="test-analyze-report-"))
    saved = RB.HERE, RB.REPO
    netlists = tmp / "design" / "netlists"
    netlists.mkdir(parents=True)
    for nl in sorted((REPO / "design" / "netlists").glob("slice_*.spice")):
        shutil.copy(nl, netlists / nl.name)
    RB.REPO = tmp
    RB.HERE = tmp / "sim" / "array-slice-bench"
    try:
        yield ((RB.HERE / "records", RB.HERE / "reports", RB.REPO / "measurements" / "array-slice-bench"), tmp)
    finally:
        RB.HERE, RB.REPO = saved
        shutil.rmtree(tmp, ignore_errors=True)


def _no_klt(*_a, **_k):
    raise AssertionError("run_bench submitted a klt sim during --analyze-report (grades only; nothing is run)")


class AnalyzeReportWritesNothing(unittest.TestCase):
    def run_main(self, *extra):
        """Run RB.main() --analyze-report against the tmp checkout and return
        its return value. Asserts, whichever way the call ends, that the tmp
        evidence tree is byte-identical across it, that the live append-only
        evidence tree is too, and that no klt sim is submitted."""
        real_before = tree_state(EVIDENCE_DIRS, REPO)
        old_argv, old_klt = sys.argv, RB.run_klt
        RB.run_klt = _no_klt
        sys.argv = ["run_bench.py", "--analyze-report", str(REPORT), *extra]
        try:
            with tmp_checkout() as (dirs, root):
                before = tree_state(dirs, root)
                try:
                    return RB.main()
                finally:
                    self.assertEqual(tree_state(dirs, root), before,
                                     "main() wrote into the tmp copy despite --analyze-report")
        finally:
            sys.argv = old_argv
            RB.run_klt = old_klt
            self.assertEqual(tree_state(EVIDENCE_DIRS, REPO), real_before,
                             "the live append-only evidence tree changed")

    def test_analyze_report_implies_no_write(self):
        rc = self.run_main("--slice", "slice_i_ii")
        self.assertEqual(rc, 3, "verdict must match the --no-write baseline (violations in this ff report)")

    def test_analyze_report_without_slice_writes_nothing(self):
        """No --slice grades the one report against every slice. slice_ii_iii's
        window (columns 20-23) is absent from this slice_i_ii report's
        supply_v, so grading stops at the first missing selection key
        (vcsel20) -- the specific failure this test pins; the write path is
        unreachable either way (asserted by run_main)."""
        with self.assertRaises(KeyError):
            self.run_main()

    def test_analyze_report_rejected_with_mode_full_band(self):
        """--mode full-band never grades the report path it is handed, so
        accepting --analyze-report silently would claim a grading that cannot
        happen while full-band submits sims and writes. The combination is an
        argument error: it fires in validation, before any submission (the
        run_klt stub in run_main would fail the test if one were attempted)."""
        with contextlib.redirect_stderr(io.StringIO()) as err:
            with self.assertRaises(SystemExit) as cm:
                self.run_main("--mode", "full-band")
        self.assertEqual(cm.exception.code, 2)
        self.assertIn("--analyze-report", err.getvalue())
        self.assertIn("full-band", err.getvalue())


if __name__ == "__main__":
    unittest.main()
