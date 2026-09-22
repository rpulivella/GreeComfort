"""The merge-readiness checks, which are pure and need no token or network."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import merge_readiness_lib as checks  # noqa: E402

TEMPLATE = checks.templatePath.read_text()
BODY = """Branch: `fix/example`

Two sentences about the change.

## Type of change
- [x] Bug fix

## Breaking changes
**Entity additions/removals/renames**: None
**Storage format (`_save_persistent_state`)**: None
**Config entry options**: None

## Checklist
- [x] Self-review done
- NA Entity registry migrations added for any renamed or removed entities
"""


def test_a_conforming_body_passes():
    assert checks.findBodyFindings(BODY, TEMPLATE) == []
    assert checks.checkChecklist(BODY).status == checks.passed


def test_leftover_instructions_and_unanswered_boxes_fail():
    body = BODY.replace("- [x] Self-review done", "<!-- note -->\n- [ ] Self-review done")
    assert any("template instructions" in finding for finding in checks.findBodyFindings(body, TEMPLATE))
    assert checks.checkChecklist(body).status == checks.failed


def test_an_invented_heading_fails():
    assert checks.findBodyFindings(BODY + "\n## Extra\n", TEMPLATE)


@pytest.mark.parametrize(
    ("subject", "ok"),
    [
        ("fix: compare eco shutoff setpoint in °C, not display unit", True),
        ("test: add a thing", False),
        ("fix:missing space", False),
        ("feat: " + "x" * 60, False),
    ],
)
def test_commit_subjects_follow_the_house_format(subject, ok):
    result = checks.checkCommitSubjects(checks.BranchFacts(commitSubjects=[subject]))
    assert (result.status == checks.passed) is ok


def test_verdict_is_the_worst_result():
    results = [checks.CheckResult("a", checks.passed, ""), checks.CheckResult("b", checks.attention, "")]
    assert checks.readVerdict(results) == checks.attention
    results.append(checks.CheckResult("c", checks.failed, ""))
    assert checks.readVerdict(results) == checks.failed
