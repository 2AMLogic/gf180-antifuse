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

    def run_helper(self, *args, pdk_root=None):
        env = {"PATH": os.environ["PATH"], "HOME": str(self.home)}
        if pdk_root is not None:
            env["PDK_ROOT"] = str(pdk_root)
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

    def test_collapses_pdk_root_outside_home_to_conventional_tilde_form(self):
        # A host can resolve the PDK via $PDK_ROOT outside $HOME, where the
        # plain ~-under-HOME collapse cannot fire (issue #316). The scrubber
        # canonicalizes the resolved root to ~/<basename> -- the same portable
        # form the committed reports carry for the ~/.ciel and ~/.volare
        # search roots -- while $HOME-resolved shapes still collapse to ~/.
        pdk = self.tmp / "opt" / "gf180"
        report = {
            "schema_version": 1,
            "status": "ok",
            "provenance": {
                "pdk": {
                    "source": f"search root: {pdk}",
                    "ambiguous_sources": [f"search root: {self.home}/.volare"],
                },
            },
            "layer_map": {"path": f"{pdk}/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map"},
        }
        src = self.tmp / "raw.json"
        dst = self.tmp / "scrubbed.json"
        src.write_text(json.dumps(report))
        r = self.run_helper(src, dst, pdk_root=pdk)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = {
            "schema_version": 1,
            "status": "ok",
            "provenance": {
                "pdk": {
                    "source": "search root: ~/gf180",
                    "ambiguous_sources": ["search root: ~/.volare"],
                },
            },
            "layer_map": {"path": "~/gf180/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map"},
        }
        self.assertEqual(dst.read_text(), json.dumps(expected, indent=2) + "\n")

    def test_pdk_root_rule_matches_on_a_path_component_boundary(self):
        # The $PDK_ROOT collapse must not fire on a text prefix (review of
        # issue #316): a sibling sharing the prefix is a directory the
        # scrubber has no rule for, so it survives the scrub as an absolute
        # path and the flow scripts' lint-envelope guard stops the run --
        # collapsing it would instead pass the lint and record a ~/location
        # that exists on no host.
        pdk = self.tmp / "opt" / "gf180"
        report = {
            "schema_version": 1,
            "status": "ok",
            "layer_map": {"path": f"{pdk}/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map"},
            "tool": {"cache": f"{pdk}-scratch/uvcache/x.so"},
            "sibling_root": f"{pdk}0/other/thing",
        }
        src = self.tmp / "raw.json"
        dst = self.tmp / "scrubbed.json"
        src.write_text(json.dumps(report))
        r = self.run_helper(src, dst, pdk_root=pdk)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = {
            "schema_version": 1,
            "status": "ok",
            "layer_map": {"path": "~/gf180/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map"},
            "tool": {"cache": f"{pdk}-scratch/uvcache/x.so"},
            "sibling_root": f"{pdk}0/other/thing",
        }
        self.assertEqual(dst.read_text(), json.dumps(expected, indent=2) + "\n")

    def test_pdk_root_bare_root_collapses_before_non_path_characters(self):
        # The bare-root replacement must keep firing when $PDK_ROOT is
        # followed by a non-path character rather than end of string -- the
        # shape provenance.pdk.source / ambiguous_sources[] prose can carry
        # when several search roots are listed in one string.
        pdk = self.tmp / "opt" / "gf180"
        report = {
            "schema_version": 1,
            "status": "ok",
            "provenance": {"pdk": {"roots": f"{pdk}, {self.home}/.volare"}},
        }
        src = self.tmp / "raw.json"
        dst = self.tmp / "scrubbed.json"
        src.write_text(json.dumps(report))
        r = self.run_helper(src, dst, pdk_root=pdk)
        self.assertEqual(r.returncode, 0, r.stderr)
        expected = {
            "schema_version": 1,
            "status": "ok",
            "provenance": {"pdk": {"roots": "~/gf180, ~/.volare"}},
        }
        self.assertEqual(dst.read_text(), json.dumps(expected, indent=2) + "\n")

    def test_pdk_root_outside_home_survives_scrub_without_pdk_root_env(self):
        # The negative control for the lint-envelope guard the flow scripts run
        # after this helper (issue #316): with no $PDK_ROOT to canonicalize
        # against, a PDK root outside $HOME survives the scrub as an absolute
        # path while every $HOME-shaped check reads clean. The scrubber alone
        # is not sufficient; the lint is what stops the leak.
        pdk = self.tmp / "opt" / "gf180"
        report = {
            "schema_version": 1,
            "status": "ok",
            "provenance": {"pdk": {"source": f"search root: {pdk}"}},
            "layer_map": {"path": f"{pdk}/gf180mcuD/libs.tech/klayout/tech/gf180mcu.map"},
        }
        src = self.tmp / "raw.json"
        dst = self.tmp / "scrubbed.json"
        src.write_text(json.dumps(report))
        r = self.run_helper(src, dst)
        self.assertEqual(r.returncode, 0, r.stderr)
        out = dst.read_text()
        self.assertNotIn(str(self.home), out)
        self.assertNotIn("~/", out)
        self.assertIn(str(pdk), out)


if __name__ == "__main__":
    unittest.main()
