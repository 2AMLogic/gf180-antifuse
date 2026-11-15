"""Tests for rtl/scrub_report_paths.py, the shared host-path scrubber that
rtl/pnr/run_pnr.sh and rtl/sta/run_sta.sh both run before committing a report
(issue #285). Stdlib unittest; the helper runs as a subprocess (the same
`python3 -I` invocation the flow scripts use) out of a synthetic repo root and
HOME, so the test controls both prefixes it collapses.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HELPER = ROOT / "rtl" / "scrub_report_paths.py"


class ScrubReportPaths(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self.repo = self.tmp / "repo"
        self.home = self.tmp / "home"
        (self.repo / "rtl" / "pnr").mkdir(parents=True)
        self.home.mkdir()

    def run_helper(self, *args):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        return subprocess.run(
            [sys.executable, "-I", str(HELPER), *(str(a) for a in args)],
            cwd=self.repo, env=env, capture_output=True, text=True)

    def raw_report(self):
        return {
            "schema_version": 1,
            "status": "ok",
            "gds_path": {
                "path": f"{self.repo}/rtl/pnr/antifuse_digital_top.gds",
                "scope": "repo",
            },
            "tech_map": (f"{self.home}/.ciel/gf180mcuD/libs.tech/klayout/"
                         "tech/gf180mcu.map"),
            "search_roots": [
                f"source: search root: {self.home}/.ciel",
                f"source: search root: {self.home}/.volare",
            ],
            "untouched": ["rtl/sta/antifuse_digital_top.spef", 7, None, True],
        }

    def assert_scrubbed(self, text):
        expected = {
            "schema_version": 1,
            "status": "ok",
            "gds_path": {
                "path": "rtl/pnr/antifuse_digital_top.gds",
                "scope": "repo",
            },
            "tech_map": "~/.ciel/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map",
            "search_roots": [
                "source: search root: ~/.ciel",
                "source: search root: ~/.volare",
            ],
            "untouched": ["rtl/sta/antifuse_digital_top.spef", 7, None, True],
        }
        self.assertEqual(text, json.dumps(expected, indent=2) + "\n")

    def test_collapses_repo_and_home_prefixes_with_committed_formatting(self):
        src = self.tmp / "raw.json"
        dst = self.tmp / "scrubbed.json"
        src.write_text(json.dumps(self.raw_report()))
        r = self.run_helper(src, dst)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_scrubbed(dst.read_text())

    def test_single_argument_rewrites_in_place(self):
        report = self.repo / "rtl" / "pnr" / "report.json"
        report.write_text(json.dumps(self.raw_report()))
        r = self.run_helper(report)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assert_scrubbed(report.read_text())


if __name__ == "__main__":
    unittest.main()
