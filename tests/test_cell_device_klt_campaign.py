"""sim/cell-device-characterization routes klt submissions through the shared harness.

Issue #301 (operator ruling 2026-11-23, option a): the campaign's ``submit_one``
calls ``K.run_klt(..., retry=K.BACKOFF)`` instead of a hand-rolled ``klt sim``
subprocess, and ``--resume`` stays, re-expressed on top of the harness call.
No simulator and no fleet: the shared ``K.run_klt`` is replaced by a recorder,
so these tests pin the campaign-specific contract -- launcher parsing, report
and digest bytes, failure evidence, selective resubmission -- while the harness
policy itself stays covered by ``sim/harness/tests/test_klt.py``.

Stdlib unittest (``tests/`` is discovered by ``npm run check:ci``).
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

SIM = Path(__file__).resolve().parent.parent / "sim"
sys.path.insert(0, str(SIM))

from harness import klt as K  # noqa: E402
from harness import report as R  # noqa: E402
from harness.modload import load_module  # noqa: E402

CAMPAIGN = SIM / "cell-device-characterization" / "klt" / "run_klt_campaign.py"

#: A minimal corners report with populated coverage id lists, so the committed
#: form differs from the full dump and the sidecar attests something.
GOOD_REPORT = {
    "corner_count": 2,
    "passed": 2,
    "corners": [
        {"corner_id": "typical_27c", "status": "pass",
         "measurements": [{"name": "ibl", "value": 1.0e-12}]},
        {"corner_id": "ff_125c", "status": "pass",
         "measurements": [{"name": "ibl", "value": 2.0e-12}]},
    ],
    "coverage": {"checked": ["a/observation", "b/observation"], "n_checked": 2},
}

ERROR_REPORT = {"error": {"code": "batch_job_failed", "message": "job command exited 1"}}

DIAG = "exit 1 (attempt 2)\nstdout:\nnot json\nstderr:\nkaput\n"


def committed_bytes(report: dict) -> tuple[str, str]:
    """The bytes the pre-#301 writer produced for the same parsed report.

    The old ``write_report`` parsed klt's stdout and called the shared
    serializer; feeding it ``json.dumps(report)`` as stdout yields exactly
    ``R.klt_report_payload`` of the round-tripped dict.
    """
    return R.klt_report_payload(json.loads(json.dumps(report)), indent=2)


class CampaignTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = load_module(CAMPAIGN, "cdc_klt_campaign_test")

    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.tmp = Path(td.name).resolve()

    def _record(self, result_for=None):
        """Swap ``K.run_klt`` for a recorder; ``result_for(req) -> (rep, diag)``."""
        seen: list[dict] = []

        def fake(request, outdir, backend=None, **kw):
            seen.append({"request": Path(request), "outdir": Path(outdir),
                         "backend": backend, **kw})
            if result_for is None:
                return GOOD_REPORT, ""
            return result_for(Path(request))

        original = K.run_klt
        K.run_klt = fake
        self.addCleanup(setattr, K, "run_klt", original)
        return seen

    def _env(self, **values):
        """Pin env vars for one test; missing keys are removed."""
        for k in ("KLT_CMD", "KLT_SIM_BACKEND"):
            original = os.environ.get(k)
            if original is None:
                self.addCleanup(os.environ.pop, k, None)
            else:
                self.addCleanup(os.environ.__setitem__, k, original)
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class HarnessRoutingTest(CampaignTestCase):
    def test_submit_one_uses_shared_backoff_and_quoted_launcher(self):
        self._env(KLT_CMD="uvx --from 'klayout-tools==0.7.0' klt", KLT_SIM_BACKEND="batch")
        seen = self._record()
        self.mod.submit_one(self.tmp, "c1_access-min_cap-min", "ioff")
        self.assertEqual(len(seen), 1)
        self.assertEqual(seen[0]["klt_cmd"], ["uvx", "--from", "klayout-tools==0.7.0", "klt"])
        self.assertIs(seen[0]["retry"], K.BACKOFF)
        # backend stays env-selected: klt itself reads KLT_SIM_BACKEND.
        self.assertIsNone(seen[0]["backend"])
        sub = "c1_access-min_cap-min"
        self.assertEqual(seen[0]["request"], self.mod.REQ_DIR / sub / "ioff.json")
        self.assertEqual(seen[0]["outdir"], self.tmp / sub / "ioff")

    def test_submit_one_defaults_to_the_klt_launcher(self):
        self._env(KLT_CMD=None)
        seen = self._record()
        self.mod.submit_one(self.tmp, "c1_access-min_cap-min", "ron")
        self.assertEqual(seen[0]["klt_cmd"], ["klt"])


class ReportPersistenceTest(CampaignTestCase):
    def _run_one(self, result):
        self._record(lambda req: result)
        return self.mod.submit_one(self.tmp, "c1_access-min_cap-min", "ioff")[2]

    def _files(self):
        out = self.tmp / "c1_access-min_cap-min" / "ioff"
        return (out / "report.json", out / "report.json.sha256", out / "stderr.txt")

    def test_success_bytes_match_the_old_writer(self):
        ok = self._run_one((GOOD_REPORT, ""))
        self.assertTrue(ok)
        rep, side, err = self._files()
        text, sha = committed_bytes(GOOD_REPORT)
        self.assertEqual(rep.read_text(), text)
        self.assertEqual(side.read_text(), sha + "\n")
        self.assertFalse(err.exists())

    def test_success_preserves_nonempty_stderr(self):
        self._run_one((GOOD_REPORT, "warning: something\n"))
        _, _, err = self._files()
        self.assertEqual(err.read_text(), "warning: something\n")

    def test_parsed_error_saved_as_json_with_empty_stderr(self):
        ok = self._run_one((ERROR_REPORT, ""))
        self.assertFalse(ok)
        rep, side, err = self._files()
        self.assertEqual(rep.read_text(), json.dumps(ERROR_REPORT, indent=2) + "\n")
        self.assertFalse(side.exists())
        self.assertFalse(err.exists())

    def test_none_report_saves_the_harness_diagnostic(self):
        ok = self._run_one((None, DIAG))
        self.assertFalse(ok)
        rep, side, _ = self._files()
        self.assertEqual(rep.read_text(), DIAG)
        self.assertFalse(side.exists())


class SubmitErrorsTest(CampaignTestCase):
    def test_failures_are_named_with_details_in_submit_errors(self):
        def result_for(req: Path):
            if req.name == "ioff.json" and req.parent.name == "c1_access-min_cap-min":
                return None, DIAG
            if req.name == "ron.json" and req.parent.name == "c1_access-min_cap-min":
                return ERROR_REPORT, ""
            return GOOD_REPORT, ""

        self._record(result_for)
        self.mod.submit_all(self.tmp, [1], parallel=1)
        errs = (self.tmp / "submit-errors.txt").read_text()
        self.assertIn("== c1_access-min_cap-min/ioff", errs)
        self.assertIn(DIAG, errs)
        self.assertIn("== c1_access-min_cap-min/ron", errs)
        self.assertIn("batch_job_failed", errs)
        self.assertNotIn("== c1_access-min_cap-2x_cap-min", errs)


class ResumeTest(CampaignTestCase):
    def _seed(self, rundir: Path):
        """A mixed run: one valid, one missing, one diagnostic, one error JSON."""
        valid_text, valid_sha = committed_bytes(GOOD_REPORT)
        for sub in self.mod.sub_names(1):
            for w in ("ioff", "ron"):
                out = rundir / sub / w
                out.mkdir(parents=True)
                if (sub, w) in (("c1_access-min_cap-min", "ioff"), ("c1_access-min_cap-2x", "ioff"),
                                ("c1_access-min_cap-2x", "ron")):
                    (out / "report.json").write_text(valid_text)
                    (out / "report.json.sha256").write_text(valid_sha + "\n")
                elif (sub, w) == ("c1_access-2x_cap-min", "ioff"):
                    (out / "report.json").write_text(DIAG)
                elif (sub, w) == ("c1_access-2x_cap-min", "ron"):
                    (out / "report.json").write_text(json.dumps(ERROR_REPORT, indent=2) + "\n")
                # c1_access-min_cap-min/ron and both c1_access-2x_cap-2x stay absent.

    def test_resume_skips_usable_reports_and_resubmits_the_rest(self):
        rundir = self.tmp / "runs" / "20261123-000000-deadbee"
        self._seed(rundir)
        valid_text, valid_sha = committed_bytes(GOOD_REPORT)
        seen = self._record()
        self.mod.submit_all(rundir, [1], parallel=1, only_missing=True)

        submitted = {f"{s['request'].parent.name}/{s['request'].stem}" for s in seen}
        self.assertEqual(submitted, {
            "c1_access-min_cap-min/ron",        # no report at all
            "c1_access-2x_cap-min/ioff",        # saved diagnostic: not a report
            "c1_access-2x_cap-min/ron",         # error object without corners
            "c1_access-2x_cap-2x/ioff",
            "c1_access-2x_cap-2x/ron",
        })
        kept = rundir / "c1_access-min_cap-min" / "ioff"
        self.assertEqual((kept / "report.json").read_text(), valid_text)
        self.assertEqual((kept / "report.json.sha256").read_text(), valid_sha + "\n")

    def test_ingest_only_submits_nothing(self):
        rundir = self.tmp / "runs" / "20261123-000000-deadbee"
        self._seed(rundir)
        seen = self._record()
        ingested = []
        original = self.mod.ingest
        self.mod.ingest = lambda rd, cands: ingested.append((rd, cands))
        self.addCleanup(setattr, self.mod, "ingest", original)
        rc = self.mod.main(["--ingest-only", str(rundir), "--candidates", "1"])
        self.assertEqual(rc, 0)
        self.assertEqual(seen, [])
        self.assertEqual(ingested, [(rundir.resolve(), [1])])


if __name__ == "__main__":
    unittest.main()
