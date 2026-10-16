"""Targeted tests for sim/harness/pdk.py and design/lib-pdk-root.sh revision
pinning. Stdlib unittest; fake PDK trees in a temp dir. Run:

    python3 -m unittest discover -s sim/harness/tests
"""

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(HERE.parent.parent))
from harness import pdk as P  # noqa: E402

OLD = "c6d73a35f524070e85faff4a6a9eef49553ebc2b"


def make_tree(root: Path, sources: str | None) -> Path:
    variant = root / "gf180mcuD"
    ng = variant / "libs.tech" / "ngspice"
    ng.mkdir(parents=True)
    for name in ("design.ngspice", "sm141064.ngspice", "smbb000149.ngspice"):
        (ng / name).write_text("*\n")
    if sources is not None:
        (variant / "SOURCES").write_text(sources)
    return variant


class ResolvePdk(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)
        self._env = dict(os.environ)
        for k in ("GF180_PDK_PATH", "PDK_ROOT", "PDK"):
            os.environ.pop(k, None)
        self.addCleanup(lambda: (os.environ.clear(), os.environ.update(self._env)))

    def test_matching_sources_passes(self):
        v = make_tree(self.tmp, f"open_pdks {P.PINNED_OPEN_PDKS}\n")
        paths = P.resolve_pdk(str(self.tmp))
        self.assertEqual(paths.revision, P.PINNED_OPEN_PDKS)
        self.assertEqual(paths.variant_dir, v)

    def test_mismatched_sources_fails_naming_both_hashes(self):
        make_tree(self.tmp, f"open_pdks {OLD}\n")
        with self.assertRaises(P.PDKRevisionMismatchError) as cm:
            P.resolve_pdk(str(self.tmp))
        msg = str(cm.exception)
        self.assertIn(OLD, msg)
        self.assertIn(P.PINNED_OPEN_PDKS, msg)
        self.assertIn(str(self.tmp / "gf180mcuD"), msg)

    def test_missing_sources_fails(self):
        make_tree(self.tmp, None)
        with self.assertRaises(P.PDKRevisionMismatchError):
            P.resolve_pdk(str(self.tmp))

    def test_sources_without_open_pdks_line_fails(self):
        make_tree(self.tmp, "something_else abc\n")
        with self.assertRaises(P.PDKRevisionMismatchError):
            P.resolve_pdk(str(self.tmp))

    def test_volare_style_tree_at_old_pin_fails(self):
        root = self.tmp / ".volare"
        make_tree(root, f"open_pdks {OLD}\n")
        with self.assertRaises(P.PDKNotFoundError):
            P.resolve_pdk(str(root))

    def test_gf180_pdk_path_mismatch_fails(self):
        v = make_tree(self.tmp, f"open_pdks {OLD}\n")
        os.environ["GF180_PDK_PATH"] = str(v)
        with self.assertRaises(P.PDKRevisionMismatchError):
            P.resolve_pdk()

    def test_gf180_pdk_path_match_passes(self):
        v = make_tree(self.tmp, f"open_pdks {P.PINNED_OPEN_PDKS}\n")
        os.environ["GF180_PDK_PATH"] = str(v)
        self.assertEqual(P.resolve_pdk().revision, P.PINNED_OPEN_PDKS)

    def test_default_root_is_ciel(self):
        self.assertEqual(P.DEFAULT_PDK_ROOT, "~/.ciel")


@unittest.skipUnless(shutil.which("bash"), "bash required")
class ShellLib(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp)

    def run_lib(self, root: Path, home: Path | None = None):
        env = {"PATH": os.environ["PATH"], "HOME": str(home or self.tmp / "nohome"),
               "PDK_ROOT": str(root)}
        script = (f'source "{REPO}/design/lib-pdk-root.sh"; '
                  'resolve_pdk_root gf180mcuD/libs.tech/ngspice')
        return subprocess.run(["bash", "-c", script], env=env,
                              capture_output=True, text=True)

    def test_pin_matches_python_constant(self):
        out = subprocess.run(
            ["bash", "-c", f'source "{REPO}/design/lib-pdk-root.sh"; echo "$PINNED_OPEN_PDKS"'],
            capture_output=True, text=True)
        self.assertEqual(out.stdout.strip(), P.PINNED_OPEN_PDKS)

    def test_match_passes(self):
        make_tree(self.tmp / "r", f"open_pdks {P.PINNED_OPEN_PDKS}\n")
        r = self.run_lib(self.tmp / "r")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), str(self.tmp / "r"))

    def test_mismatch_fails(self):
        make_tree(self.tmp / "r", f"open_pdks {OLD}\n")
        r = self.run_lib(self.tmp / "r")
        self.assertEqual(r.returncode, 1)
        self.assertIn(OLD, r.stderr)
        self.assertIn(P.PINNED_OPEN_PDKS, r.stderr)

    def test_missing_sources_fails(self):
        make_tree(self.tmp / "r", None)
        self.assertEqual(self.run_lib(self.tmp / "r").returncode, 1)


if __name__ == "__main__":
    unittest.main()
