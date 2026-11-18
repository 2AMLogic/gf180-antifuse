"""Guard on the generated plan-body block in WORK_PLAN.md (#430).

The Guide's plan-body generator (`render_plan_body` in the installed Guide
role) emits only `*(curated)*` / `*(architect)*` / `*(hermit)*` annotations —
never `*(held)*`. A hand-applied `*(held)*` row suffix inside the
`<!-- guide:plan-body:start -->` / `<!-- guide:plan-body:end -->` markers is
therefore not reproducible from the generator and reappears or drifts on
Guide runs (issue #420, recurrence #430). This test pins the #420 ruling at
the repo level: the generated region must contain no such annotation.

Read-only: this test never modifies WORK_PLAN.md or any Guide-owned file.
(unittest; also runs under pytest.)
"""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

START = "<!-- guide:plan-body:start -->"
END = "<!-- guide:plan-body:end -->"
BANNED = "*(held)*"


def extract_plan_body(text):
    """Return the generated region between the markers (markers excluded).

    Raises ValueError with a clear message when either marker is missing, so
    a malformed file fails loudly instead of passing vacuously.
    """
    head, sep, rest = text.partition(START)
    if not sep:
        raise ValueError(f"no {START} marker found in WORK_PLAN.md")
    body, sep, _tail = rest.partition(END)
    if not sep:
        raise ValueError(f"no {END} marker found in WORK_PLAN.md")
    return body


def check_work_plan(text):
    """Return a list of error strings for generator-foreign annotations."""
    try:
        body = extract_plan_body(text)
    except ValueError as exc:
        return [str(exc)]
    # The body's first line is the remainder of the start-marker's own line.
    first_body_line = text[: text.index(START)].count("\n") + 1
    errors = []
    for offset, line in enumerate(body.splitlines()):
        if BANNED in line:
            errors.append(
                "%s suffix inside the generated plan-body block (line %d): %r"
                " — the plan-body generator never emits this annotation;"
                " regenerate the block wholesale (#420, #430)"
                % (BANNED, first_body_line + offset, line.strip())
            )
    return errors


def errs(text):
    return check_work_plan(text)


def work_plan_errors():
    return errs((ROOT / "WORK_PLAN.md").read_text())


HOLD_FIXTURE = """\
# Work Plan

<!-- guide:plan-body:start -->
## Ready

- **#12**: fix the thing
- **#99**: other thing *(held)*
<!-- guide:plan-body:end -->
"""

CLEAN_FIXTURE = """\
# Work Plan

Hand notes with *(held)* outside the markers are fine.

<!-- guide:plan-body:start -->
## Ready

- **#12**: fix the thing
<!-- guide:plan-body:end -->

Trailing *(held)* prose is outside the block too.
"""


class CommittedWorkPlanTests(unittest.TestCase):
    def test_committed_work_plan_has_no_held_annotations(self):
        self.assertEqual(work_plan_errors(), [])


class ExtractPlanBodyTests(unittest.TestCase):
    def test_extracts_region_between_markers(self):
        body = extract_plan_body(HOLD_FIXTURE)
        self.assertIn("**#99**", body)
        self.assertNotIn("guide:plan-body", body)

    def test_missing_start_marker_fails_clearly(self):
        with self.assertRaises(ValueError) as ctx:
            extract_plan_body("# Work Plan\n\nno markers here\n")
        self.assertIn("plan-body:start", str(ctx.exception))

    def test_unclosed_start_marker_fails_clearly(self):
        with self.assertRaises(ValueError) as ctx:
            extract_plan_body(START + "\nbody without end\n")
        self.assertIn("plan-body:end", str(ctx.exception))


class CheckWorkPlanTests(unittest.TestCase):
    def test_held_suffix_inside_block_fails(self):
        errors = errs(HOLD_FIXTURE)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("*(held)*", errors[0])
        self.assertIn("line 7", errors[0])

    def test_held_outside_markers_not_flagged(self):
        self.assertEqual(errs(CLEAN_FIXTURE), [])

    def test_missing_markers_reported_not_vacuous(self):
        errors = errs("# Work Plan\n\nno markers\n")
        self.assertEqual(len(errors), 1)
        self.assertIn("plan-body:start", errors[0])


if __name__ == "__main__":
    unittest.main()
