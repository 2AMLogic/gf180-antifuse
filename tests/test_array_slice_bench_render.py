"""Offline record/CSV render regression tests for sim/array-slice-bench (issue #517).

The #517 split (run_bench.py -> model.py + render.py + CLI facade) had to
keep every rendered byte identical. These tests re-render, offline from the
committed reports only (no klt, no writes):

* slice mode, from reports/20261009-021330-3010ff8: the per-region
  measurement view and the record text, compared byte-for-byte against
  golden fixtures under tests/fixtures/render/ (test artifacts, not
  evidence). The committed measurements/*.md of that run cannot serve as
  golden files: it predates the per-report-sha line format, exactly as the
  programming-yield split (#470) found frozen records unusable directly.
  The git sha and clock are pinned so the record's provenance and
  timestamp lines are compared too.
* full-band mode, from reports/20261016-015644-361e4f1b-fullband: the
  per-region measurement view and the per-corner CSV compared byte-for-
  byte against the committed measurement files (the split's acceptance
  gate), and the record body against a golden fixture -- the committed
  record itself predates the artifact-store Links line, so only the
  fixture reflects the current renderer.

Loads run_bench.py through the facade (harness.modload), as
tests/test_array_slice_bench_sidecar.py does. unittest; also runs under
pytest.
"""
from __future__ import annotations

import datetime as dt
import json
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "sim"))
import harness.report as HR  # noqa: E402
from harness.modload import load_module  # noqa: E402

ASB = ROOT / "sim" / "array-slice-bench"
MEAS = ROOT / "measurements" / "array-slice-bench"
FIX = ROOT / "tests" / "fixtures" / "render"

RB = load_module(ASB / "run_bench.py", "asb_render_run_bench")
F = load_module(ASB / "fullband.py", "asb_render_fullband")
G, B = RB.G, RB.B

SLICE_RID = "20261009-021330-3010ff8"
FB_RID = "20261016-015644-361e4f1b-fullband"
PINNED_SHA = "0" * 40
PINNED_NOW = dt.datetime(2026, 11, 24, 12, 0, 0, tzinfo=dt.timezone.utc)
FB_SHA = "361e4f1bcd93" + "0" * 28        # the committed run's HEAD (record uses sha[:12] only)
FB_NOW = dt.datetime(2026, 10, 16, 2, 21, 21, tzinfo=dt.timezone.utc)   # the committed run's timestamp


def _slice_sections():
    """Re-render both slice sections from the committed reports (they are
    coverage-elided, so no digest is attestable and the sha lines take the
    deterministic `none attestable` branch)."""
    sections = []
    for sl in list(G.SLICES):
        reps = [(proc, json.loads((ASB / "reports" / SLICE_RID / f"{sl}_{proc}.report.json").read_text()))
                for proc in B.PROCESS]
        report = RB.merge_reports([r for _p, r in reps])
        payloads = {proc: RB.slim_payload(r) for proc, r in reps}
        per = RB.analyze(sl, report, ROOT)
        sec, _reach, _iso, _errors = RB.slice_section(
            sl, report, per, {k: s for k, (_t, s) in payloads.items()}, write=True)
        sections.append(sec)
    return sections


def _fullband_points():
    pg, nat, sel = [], [], []
    for name in list(G.BAND_SLICES):
        reports = {}
        for variant in B.LEAK_VARIANTS:
            reports[variant] = {}
            for proc in B.PROCESS:
                rp = ASB / "reports" / FB_RID / f"leak_{variant}_{name}_{proc}.report.json"
                reports[variant][proc] = json.loads(rp.read_text())
        pg += F.analyze_pgoff(name, reports["pgoff"])
        nat += F.analyze_nat(name, reports["nat"])
        sel += F.analyze_sel(name, reports["sel"])
    return pg, nat, sel


class SliceModeGolden(unittest.TestCase):
    def test_measurement_view_matches_golden(self):
        sections = _slice_sections()
        self.assertEqual(RB.slice_measurement_view(SLICE_RID, sections),
                         (FIX / "array-slice-bench-slice-measurement.md").read_text())

    def test_record_matches_golden_with_pinned_sha_and_clock(self):
        sections = _slice_sections()
        with mock.patch.object(HR, "git_out", return_value=PINNED_SHA):
            text = RB.write_records(SLICE_RID, sections, True, PINNED_NOW, repo=ROOT)
        self.assertEqual(text, (FIX / "array-slice-bench-slice-record.md").read_text())


class FullBandGolden(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pg, cls.nat, cls.sel = _fullband_points()

    def test_measurement_view_matches_committed_evidence(self):
        self.assertEqual(RB.fullband_measurement_view(F, FB_RID, self.pg, self.sel),
                         (MEAS / f"{FB_RID}.md").read_text())

    def test_csv_matches_committed_evidence(self):
        self.assertEqual(RB.fullband_csv(self.pg), (MEAS / f"{FB_RID}.csv").read_text())

    def test_record_body_matches_golden(self):
        sel_bad = sum(0 if r["ok"] else 1 for r in self.sel)
        floor_n = sum(1 for r in self.pg if r["floor_dominated"])
        jobs = []
        for name in list(G.BAND_SLICES):
            for variant in B.LEAK_VARIANTS:
                for proc in B.PROCESS:
                    rp = ASB / "reports" / FB_RID / f"leak_{variant}_{name}_{proc}.report.json"
                    r = json.loads(rp.read_text())
                    jobs.append(f"- `{variant}` {name} {proc}: " + ", ".join(RB._jobs_line({proc: r})) +
                                f"; corners {r['corner_count']} (pass {r['passed']}, fail {r['failed']}, "
                                f"error {r['errored']}, inconclusive {r['inconclusive']})")
        body = RB.fullband_record_body(F, FB_RID, FB_SHA, False, FB_NOW,
                                       self.pg, self.nat, self.sel, floor_n, sel_bad, jobs)
        self.assertEqual(body, (FIX / "array-slice-bench-fullband-record.md").read_text())


if __name__ == "__main__":
    unittest.main()
