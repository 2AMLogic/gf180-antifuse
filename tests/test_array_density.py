"""Bind the optional density stream and its signoff results to one layout revision."""

import gzip
from hashlib import sha256
import json
from pathlib import Path
import unittest


ARRAY = Path(__file__).resolve().parents[1] / "layout/array_32x32"
FILLED = ARRAY / "density"


def read_report(name):
    with gzip.open(FILLED / name, "rt") as report:
        return json.load(report)


class ArrayDensityTest(unittest.TestCase):
    def test_delivered_layout_and_report_provenance(self):
        evidence = json.loads((FILLED / "evidence.json").read_text())
        self.assertEqual(
            sha256((ARRAY / "array_32x32.gds").read_bytes()).hexdigest(),
            evidence["input_gds_sha256"],
        )
        with gzip.open(FILLED / "array_32x32.gds.gz", "rb") as stream:
            digest = sha256()
            while chunk := stream.read(1024 * 1024):
                digest.update(chunk)
        layout = digest.hexdigest()
        self.assertEqual(layout, evidence["delivered_gds_sha256"])
        native = read_report("native-drc.json.gz")
        curated = read_report("curated-drc.json.gz")
        lvs = read_report("curated-lvs.json.gz")
        for report in (native, curated, lvs):
            self.assertEqual(
                report["provenance"]["input"]["content_hash"], "sha256:" + layout
            )
        self.assertTrue(native["coverage_assertion"]["satisfied"])
        self.assertEqual(
            len(native["coverage_assertion"]["observed_names"]),
            evidence["native_drc"]["filled_category_count"],
        )
        self.assertEqual(
            native["rule_counts"], evidence["native_drc"]["remaining_rules"]
        )
        self.assertEqual(
            native["violation_count"], evidence["native_drc"]["after_markers"]
        )
        self.assertTrue(
            set(evidence["native_drc"]["cleared_density_markers"]).isdisjoint(
                native["rule_counts"]
            )
        )
        self.assertEqual(curated["violation_count"], evidence["curated_drc"]["markers"])
        self.assertEqual(lvs["counts"], evidence["curated_lvs"]["counts"])
        match = evidence["native_lvs"]
        self.assertEqual(match["tested_gds_sha256"], layout)
        self.assertTrue(match["strict_match"])
        with gzip.open(FILLED / match["cross_reference"], "rb") as cross_reference:
            self.assertEqual(
                sha256(cross_reference.read()).hexdigest(),
                match["cross_reference_sha256"],
            )
        controls = evidence["native_lvs_mutations"]
        self.assertEqual(set(controls), {"select_open", "row_short", "missing_pwell"})
        for result in controls.values():
            self.assertFalse(result["strict_match"])
