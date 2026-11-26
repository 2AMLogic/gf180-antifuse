"""sim/program-read-legs delegates fleet-refusal retry to the shared harness policy.

Issue #277. ``sim/harness/klt.py`` owns fleet-refusal retry as policy ("A fleet
refusal (concurrency cap / no capacity) is transient and is retried as the SAME
request after a pause, bounded by ``RetryPolicy``. Nothing else is retried"), and
this driver's wrapper must opt into it like the other batch drivers rather than
re-deriving a retry loop of its own. No simulator: the shared ``K.run_klt`` is
replaced by a recorder, and the one end-to-end case drives a fake ``klt`` script.

Stdlib unittest (``tests/`` is discovered by ``npm run check:ci``).
"""

from __future__ import annotations

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))

from harness import klt as K  # noqa: E402
from harness.modload import load_module  # noqa: E402

DRIVER = SIM / "program-read-legs" / "run_experiment.py"


class RetryPolicyDelegationTest(unittest.TestCase):
    """The driver's ``run_klt`` wrapper hands the harness a real retry policy."""

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(DRIVER, "prl_run_retry_test")

    def _record_calls(self) -> list[dict]:
        """Swap ``K.run_klt`` for a recorder; return the list of kwargs seen."""
        seen: list[dict] = []

        def fake(request, outdir, backend=None, **kw):
            seen.append({"request": request, "outdir": outdir, "backend": backend, **kw})
            return {"corners": []}, ""

        original = K.run_klt
        K.run_klt = fake
        self.addCleanup(setattr, K, "run_klt", original)
        return seen

    def test_wrapper_passes_the_shared_backoff_policy(self):
        seen = self._record_calls()
        self.mod.run_klt(Path("r.json"), Path("out"), "batch")
        self.assertEqual(len(seen), 1)
        self.assertIs(seen[0].get("retry"), K.BACKOFF)

    def test_wrapper_policy_is_a_bounded_multi_submit_wait(self):
        """Generic form: dropping the ``retry=`` kwarg falls back to ``NO_RETRY``.

        ``NO_RETRY`` (``max_submits=1``) means the harness never waits out a
        capacity refusal for this driver at all, which is the defect #277 fixes.
        """
        seen = self._record_calls()
        self.mod.run_klt(Path("r.json"), Path("out"), "batch")
        policy = seen[0].get("retry")
        self.assertIsInstance(policy, K.RetryPolicy)
        self.assertGreater(policy.max_submits, 1)
        self.assertIsNot(policy, K.NO_RETRY)
        # More patience than the hand-rolled loop this replaces (3 submits, 15 s apart).
        self.assertGreater(policy.budget_s if policy.budget_s is not None else float("inf"), 600)


class NoReportIsNotReplayedTest(unittest.TestCase):
    """End-to-end through the real harness: only a refusal is retried.

    Pins the behavior change #277 accepts -- a submit that returns no report is
    no longer blindly replayed by the driver -- at the driver's own call path.
    """

    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(DRIVER, "prl_run_noreport_test")

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()

    def _fake_klt(self, stdout: str) -> Path:
        script = self.tmp / "klt"
        script.write_text(f'#!/bin/sh\necho \'{stdout}\'\necho "$@" >> "{self.tmp}/submits"\n')
        script.chmod(script.stat().st_mode | stat.S_IXUSR)
        return script

    def _submits(self) -> int:
        log = self.tmp / "submits"
        return len(log.read_text().splitlines()) if log.exists() else 0

    def test_a_submit_with_no_json_report_is_submitted_once(self):
        script = self._fake_klt("ngspice exploded, no JSON here")
        original = os.environ.get("KLT")
        os.environ["KLT"] = str(script)
        if original is None:
            self.addCleanup(os.environ.pop, "KLT", None)
        else:
            self.addCleanup(os.environ.__setitem__, "KLT", original)

        report, diag = self.mod.run_klt(self.tmp / "r.json", self.tmp / "out", "batch")

        self.assertIsNone(report)
        self.assertIn("no JSON here", diag)
        self.assertEqual(self._submits(), 1)


if __name__ == "__main__":
    unittest.main()
