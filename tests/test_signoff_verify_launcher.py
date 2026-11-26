"""Tests for the grader launcher in signoff/verify.sh (unittest; also runs under
pytest).

verify.sh must grade the committed report through the pinned launcher
KLT=${KLT_CMD:-uvx --from klayout-tools==0.8.0 klt}, never through whatever
`klt` the host has on PATH: a newer host build bundles a different checklist
and fails the byte-compare on a clean tree (issue #469). These tests run
offline -- fake `uvx` / `klt` executables stand in for the real ones and record
their argv, so each test asserts which launcher verify.sh invoked and with what
arguments.
"""
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VERIFY = ROOT / "signoff" / "verify.sh"
PIN = ["--from", "klayout-tools==0.8.0", "klt"]
COMMITTED = '{"tier": null}\n'

GRADER = """\
#!/bin/sh
printf '%s\\n' "$@" >"{FAKE_DIR}/{name}.args"
cat "{FAKE_DIR}/grade.out"
exit 3
"""
HOST_KLT = """\
#!/bin/sh
printf '%s\\n' "$@" >"{FAKE_DIR}/klt.args"
exit 99
"""


def write_fake(path: Path, body: str) -> None:
    path.write_text(body)
    path.chmod(0o755)


class VerifyLauncherTests(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory()
        self.addCleanup(self._td.cleanup)
        self.tmp = Path(self._td.name)
        # Only expose the executables the script and fake graders need. The
        # interpreter's real bin directory may also contain a working uvx.
        self.commands = self.tmp / "commands"
        self.commands.mkdir()
        for name in ("bash", "cat", "diff", "dirname", "mktemp", "python3", "rm"):
            executable = shutil.which(name)
            if executable is None:
                self.skipTest(f"{name} is not on PATH")
            (self.commands / name).symlink_to(executable)
        self.root = self.tmp / "repo"
        signoff = self.root / "signoff"
        signoff.mkdir(parents=True)
        shutil.copy2(VERIFY, signoff / "verify.sh")
        self.manifest = signoff / "manifest.json"
        self.report = signoff / "report.json"
        self.report.write_text(COMMITTED)
        self.set_manifest({"block": "b", "kind": "analog", "evidence": {}})
        self.grade_out = self.tmp / "grade.out"
        self.grade_out.write_text(COMMITTED)

    def set_manifest(self, doc) -> None:
        self.manifest.write_text(json.dumps(doc) + "\n")

    def install(self, *names) -> Path:
        bin_dir = self.tmp / "bin"
        bin_dir.mkdir(exist_ok=True)
        env = {"FAKE_DIR": str(self.tmp)}
        for name in names:
            body = HOST_KLT if name == "klt" else GRADER
            write_fake(bin_dir / name, body.format(**env, name=name))
        return bin_dir

    def run_verify(self, bin_dir: Path, klt_cmd=None):
        env = {"PATH": f"{bin_dir}:{self.commands}",
               "FAKE_DIR": str(self.tmp)}
        if klt_cmd is not None:
            env["KLT_CMD"] = klt_cmd
        return subprocess.run([str(self.root / "signoff" / "verify.sh")],
                              capture_output=True, text=True, env=env)

    def args(self, name):
        path = self.tmp / f"{name}.args"
        if not path.exists():
            return None
        return path.read_text().splitlines()

    def signoff_args(self):
        return ["signoff", "--manifest", str(self.manifest), "--format", "json"]

    def test_default_grades_through_the_pinned_release_not_the_host_klt(self):
        bin_dir = self.install("uvx", "klt")
        r = self.run_verify(bin_dir)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("OK -- committed verdict matches", r.stdout)
        self.assertEqual(self.args("uvx"), PIN + self.signoff_args())
        self.assertIsNone(self.args("klt"), "verify.sh invoked the host klt")

    def test_klt_cmd_override_replaces_the_pinned_launcher(self):
        bin_dir = self.install("uvx", "klt", "hostklt")
        r = self.run_verify(bin_dir, klt_cmd="hostklt --verbose")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.args("hostklt"), ["--verbose"] + self.signoff_args())
        self.assertIsNone(self.args("uvx"), "the pin ran despite KLT_CMD")
        self.assertIsNone(self.args("klt"))

    def test_missing_pinned_launcher_fails_before_grading(self):
        bin_dir = self.install("klt")
        r = self.run_verify(bin_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("'uvx' is not on PATH", r.stderr)
        self.assertIsNone(self.args("klt"), "verify.sh fell back to the host klt")

    def test_missing_override_launcher_is_named_in_the_failure(self):
        bin_dir = self.install("uvx")
        r = self.run_verify(bin_dir, klt_cmd="nosuchlauncher klt")
        self.assertEqual(r.returncode, 1)
        self.assertIn("'nosuchlauncher' is not on PATH", r.stderr)
        self.assertIn("KLT_CMD", r.stderr)
        self.assertIsNone(self.args("uvx"))

    def test_unpinned_citation_still_fails_assertion_1_before_grading(self):
        bin_dir = self.install("uvx", "klt")
        self.set_manifest({"block": "b", "kind": "analog",
                           "evidence": {"1.analog": "a/b.json"}})
        r = self.run_verify(bin_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("is a bare path with no pinned content_hash", r.stderr)
        self.assertIsNone(self.args("uvx"), "a dirty manifest was still graded")

    def test_perturbed_report_still_fails_assertion_3(self):
        bin_dir = self.install("uvx", "klt")
        self.grade_out.write_text('{"tier": "T1"}\n')
        r = self.run_verify(bin_dir)
        self.assertEqual(r.returncode, 1)
        self.assertIn("no longer matches a fresh grading run", r.stderr)
        self.assertNotIn("OK -- committed verdict matches", r.stdout)
        remediation = " ".join(PIN + ["signoff", "--manifest", "signoff/manifest.json",
                                      "--format", "json", ">", "signoff/report.json"])
        self.assertIn(remediation, r.stderr, "remediation is not the pinned grader")


if __name__ == "__main__":
    unittest.main()
