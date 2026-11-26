"""Regression checks for stale or falsely passing routed characterization evidence."""

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "rtl/characterization"))
import report as char  # noqa: E402
import replay_sdf  # noqa: E402


class DigitalCharacterization(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.evidence = [
            char.read(ROOT / p)
            for p in (char.PNR, char.STA, f"rtl/sta/{char.TOP}.sta.json", char.FV, char.SDF, char.CAMPAIGN)
        ]

    def check_bad(self, stream_index, modify, diagnostic):
        evidence = list(self.evidence)
        evidence[stream_index] = copy.deepcopy(evidence[stream_index])
        modify(evidence[stream_index])
        with self.assertRaisesRegex((KeyError, ValueError), diagnostic):
            char.measure(*evidence)

    def test_committed_record_is_fresh(self):
        for path, expected in char.render().items():
            self.assertEqual((ROOT / path).read_text(), expected)

    def test_missing_or_duplicate_corner(self):
        self.check_bad(1, lambda sta: sta["corners"].pop(), "STA corner set")
        self.check_bad(1, lambda sta: sta["corners"].append(sta["corners"][0]), "duplicate corner")

    def test_missing_measurement_or_flattened_functional_campaign(self):
        self.check_bad(1, lambda sta: sta["corners"][0].pop("fmax_mhz"), "fmax_mhz")
        self.check_bad(5, lambda campaign: campaign["runs"].pop(), "missing or unexpected functional corner")
        self.check_bad(
            5, lambda c: c["runs"][1].update(sdf_sha256=c["runs"][0]["sdf_sha256"]), "share a delay file"
        )

    def test_failed_required_test_and_invalid_stress_control(self):
        self.check_bad(
            5, lambda c: c["runs"][0]["outcomes"].update(program_full_sequence="failed"), "failed required test"
        )
        self.check_bad(5, lambda c: c["runs"][-1].update(status="pass"), "25 ns timing control")
        self.check_bad(4, lambda envelope: envelope["tests"][0].update(status="failed"), "failed required test")

    def test_swapped_non_nominal_sta_files(self):
        def swap(campaign):
            first, second = campaign["runs"][:2]
            first["sdf_sha256"], second["sdf_sha256"] = second["sdf_sha256"], first["sdf_sha256"]

        self.check_bad(5, swap, "wrong STA file")

    def test_physical_timing_sections_survive_a_split_diagnostic(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "antifuse_digital_top.tt_025C_1v80.sdf"
            source.write_bytes(b"(DELAYFILE\n (TIMINGCHECK (WIDTH ...))\n (TIMINGCHECK\n )\n)\n")
            native = copy.deepcopy(self.evidence[4])
            native["provenance"]["sdf_sha256"] = replay_sdf.digest(source)
            warning = native["environment"]["sdf"]["dropped"]["timingcheck"]

            def observed():
                return replay_sdf.observed(native, "tt_025C_1v80", 50, source)

            warning["count"] = 1
            one_warning = observed()
            warning["count"] = 2
            self.assertEqual(observed(), one_warning)
            self.assertEqual(one_warning["unsupported_timingcheck_sections"], 2)
            for invalid in (0, 3):
                warning["count"] = invalid
                with self.assertRaisesRegex(ValueError, "invalid timing-check diagnostics"):
                    observed()

    def test_source_hash_change(self):
        changed = copy.deepcopy(self.evidence[5])
        changed["source_sha256"]["rtl/sta/antifuse_digital_top.spef"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "source hash mismatch.*spef"):
            char.check_inputs(changed)

    def test_output_hash_covers_the_report_bytes(self):
        outputs = char.render()
        envelope = json.loads(outputs[char.ENVELOPE])
        expected = "sha256:" + hashlib.sha256(outputs[char.REPORT].encode()).hexdigest()
        self.assertEqual(envelope["provenance"]["input"]["content_hash"], expected)
