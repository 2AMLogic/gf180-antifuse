"""Targeted tests for sim/harness/klt.py: retry only on fleet refusal, absolute
outdir. Stdlib unittest; fake `klt` scripts in a temp dir. Run:

    python3 -m unittest discover -s sim/harness/tests
"""

import os
import stat
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent))
from harness import klt as K  # noqa: E402


class RunKltTest(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name).resolve()

    def fake(self, name: str, stdout: str) -> list[str]:
        p = self.tmp / name
        p.write_text(f"#!/bin/sh\necho '{stdout}'\necho \"$@\" >> {self.tmp}/{name}.args\n")
        p.chmod(p.stat().st_mode | stat.S_IXUSR)
        return [str(p)]

    def calls(self, name: str) -> list[str]:
        return (self.tmp / f"{name}.args").read_text().splitlines()

    def test_success_and_absolute_outdir(self):
        cmd = self.fake("ok", '{"corners": []}')
        cwd = os.getcwd()
        os.chdir(self.tmp)
        self.addCleanup(os.chdir, cwd)
        rep, _ = K.run_klt(Path("r.json"), Path("rel/out"), "local", klt_cmd=cmd)
        self.assertEqual(rep, {"corners": []})
        args = self.calls("ok")[0].split()
        self.assertEqual(args[args.index("-o") + 1], str(self.tmp / "rel" / "out"))
        self.assertEqual(args[-2:], ["--backend", "local"])

    def test_refusal_retried_up_to_max_submits(self):
        cmd = self.fake("busy", '{"error": "BATCH_MAX_CONCURRENT_INSTANCES"}')
        rep, _ = K.run_klt(self.tmp / "r.json", self.tmp / "o", "batch", klt_cmd=cmd,
                           retry=K.RetryPolicy(max_submits=3, base_s=0))
        self.assertIn("error", rep)
        self.assertEqual(len(self.calls("busy")), 3)

    def test_other_error_not_retried(self):
        cmd = self.fake("bad", '{"error": "boom"}')
        K.run_klt(self.tmp / "r.json", self.tmp / "o", "batch", klt_cmd=cmd,
                  retry=K.RetryPolicy(max_submits=3, base_s=0))
        self.assertEqual(len(self.calls("bad")), 1)

    def test_no_json_returns_none(self):
        cmd = self.fake("junk", "not json")
        rep, diag = K.run_klt(self.tmp / "r.json", self.tmp / "o", None, klt_cmd=cmd)
        self.assertIsNone(rep)
        self.assertIn("not json", diag)


if __name__ == "__main__":
    unittest.main()
