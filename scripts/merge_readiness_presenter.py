"""\
The one place the merge-readiness comment takes its shape. Adapted from pybers.

The marker is the first line and never moves, because later runs find the comment by it.
The verdict says a change is ready for a person to test, never that it is ready to merge.
"""
from __future__ import annotations

from datetime import UTC, datetime

from merge_readiness_lib import BranchFacts, CheckResult, attention, failed, passed, readVerdict, skipped
from rich.console import Console
from rich.markup import escape

commentMarker: str = "<!-- greecomfort-merge-readiness -->"
commentHeading: str = "Merge Readiness"

verdictSymbols: dict[str, str] = {passed: "✅", failed: "❌", attention: "⚠️", skipped: "➖"}
annotationKinds: dict[str, str] = {failed: "error", attention: "warning"}
consoleColors: dict[str, str] = {passed: "green", failed: "red", attention: "yellow", skipped: "dim"}


def formatTimestamp(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def renderComment(results: list[CheckResult], facts: BranchFacts, moment: datetime) -> str:
    """Render the whole comment, marker first; a list rather than a table so it reads in email."""
    verdict = readVerdict(results)
    lines = [commentMarker, f"## {verdictSymbols[verdict]} {commentHeading}", "", renderSummary(results), ""]
    for result in results:
        symbol = verdictSymbols.get(result.status, verdictSymbols[skipped])
        lines += [f"### {symbol} {result.name}", "", result.detail, ""]
    commit = facts.headSha[:12] or "an unknown commit"
    lines += [f"_Checked {formatTimestamp(moment)} against commit {commit}_"]
    return "\n".join(lines) + "\n"


def renderSummary(results: list[CheckResult]) -> str:
    """Count the checks in one line, which is what a reader takes from the top."""
    counts = {status: sum(1 for r in results if r.status == status) for status in (passed, failed, attention, skipped)}
    skips = counts[skipped]
    trailing = "" if not skips else f" with {skips} skip" + ("" if skips == 1 else "s")
    if not counts[failed] and not counts[attention]:
        return f"All checks passed{trailing}"
    parts = []
    if counts[passed]:
        parts.append(f"{counts[passed]} {'check' if counts[passed] == 1 else 'checks'} passed")
    if counts[failed]:
        parts.append(f"{counts[failed]} failed")
    if counts[attention]:
        parts.append(f"{counts[attention]} {'needs' if counts[attention] == 1 else 'need'} a decision")
    if skips:
        parts.append(f"{skips} skip" + ("" if skips == 1 else "s"))
    return ", ".join(parts)


def renderAnnotations(results: list[CheckResult]) -> list[str]:
    """One workflow command per failed or attention check, which GitHub shows above the log."""
    return [f"::{annotationKinds[r.status]} title={r.name}::{r.detail}" for r in results if r.status in annotationKinds]


def reportResults(console: Console, results: list[CheckResult], verdict: str) -> None:
    """Print the same checks to a terminal, for a run made by hand."""
    for result in results:
        color = consoleColors.get(result.status, "dim")
        console.print(f"[{color}]{result.status:9}[/] {escape(result.name)}: {escape(result.detail)}")
    console.print(f"[{consoleColors[verdict]}]verdict: {verdict}[/]")
