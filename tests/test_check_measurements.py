"""Tests for scripts/check_measurements.py (unittest; also runs under pytest)."""
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import check_measurements as cm  # noqa: E402

FIX = ROOT / "tests" / "fixtures" / "measurements"


def errs(name):
    return cm.check_text((FIX / name).read_text())


class CheckTests(unittest.TestCase):
    def test_good_record_passes(self):
        self.assertEqual(errs("good_yield.md"), [])

    def test_row_from_other_region_rejected(self):
        e = errs("bad_row_pooled_region.md")
        self.assertTrue(any("pooled across splits" in x for x in e), e)

    def test_pooled_header_value_rejected(self):
        e = errs("bad_header_pooled_geometry.md")
        self.assertTrue(any("pooled" in x for x in e), e)

    def test_region_list_rejected(self):
        e = errs("bad_region_list.md")
        self.assertTrue(any("Region" in x for x in e), e)

    def test_replicate_count_mismatch_rejected(self):
        t = (FIX / "good_yield.md").read_text().replace(
            "Replicate count**: 5", "Replicate count**: 6")
        self.assertTrue(any("Replicate count" in x for x in cm.check_text(t)))

    def test_row_pulse_condition_mismatch_rejected(self):
        t = (FIX / "good_yield.md").read_text().replace(
            "| 0 | 2 | I | 1 | min | min | V1 |", "| 0 | 2 | I | 1 | min | min | V2 |")
        self.assertTrue(any("pulse_condition" in x for x in cm.check_text(t)))

    def test_candidate_must_match_region(self):
        t = (FIX / "good_yield.md").read_text().replace(
            "**Candidate**: 1", "**Candidate**: 2")
        self.assertTrue(any("Candidate" in x for x in cm.check_text(t)))

    def test_template_is_not_a_valid_record(self):
        e = cm.check_text((ROOT / "measurements" / "TEMPLATE.md").read_text())
        self.assertTrue(any("placeholder" in x for x in e), e)

    def test_cli_exit_codes(self):
        script = str(ROOT / "scripts" / "check_measurements.py")
        ok = subprocess.run([sys.executable, "-I", script, str(FIX / "good_yield.md")])
        bad = subprocess.run(
            [sys.executable, "-I", script, str(FIX / "bad_row_pooled_region.md")],
            capture_output=True)
        self.assertEqual(ok.returncode, 0)
        self.assertEqual(bad.returncode, 1)

    def test_append_only(self):
        script = str(ROOT / "scripts" / "check_measurements.py")
        with tempfile.TemporaryDirectory() as d:
            def git(*a):
                subprocess.run(["git", "-C", d, "-c", "user.name=t",
                                "-c", "user.email=t@t", *a],
                               check=True, capture_output=True)
            git("init", "-q")
            rec = Path(d, "records")
            rec.mkdir()
            f = rec / "r1.md"
            f.write_text((FIX / "good_yield.md").read_text())
            git("add", ".")
            git("commit", "-qm", "base")
            (rec / "r2.md").write_text((FIX / "good_yield.md").read_text())
            git("add", ".")
            run = lambda: subprocess.run(
                [sys.executable, "-I", script, "--base", "HEAD", "records"],
                cwd=d, capture_output=True, text=True)
            self.assertEqual(run().returncode, 0, run().stdout)  # added file ok
            f.write_text(f.read_text() + "\n")
            git("add", ".")
            r = run()
            self.assertEqual(r.returncode, 1)
            self.assertIn("append-only", r.stdout)


if __name__ == "__main__":
    unittest.main()
