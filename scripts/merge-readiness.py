#!/usr/bin/env python3
"""\
GreeComfort merge-readiness report, adapted from pybers.

`collect` runs on the pull request's branch and writes the facts it gathers to a file.
`check` reads that file as data, adds what only the GitHub API and the network can answer,
renders one comment and fails on red. `report` runs the default branch's code and posts
that comment, replacing an earlier one. Keeping them apart is what makes write access safe
in the posting half: it executes nothing the branch carries.

Usage:
    python3 scripts/merge-readiness.py collect --pull-request 42 --base origin/develop --output results.json
    python3 scripts/merge-readiness.py check --results results.json --comment merge-readiness.md
    python3 scripts/merge-readiness.py report --results results.json --comment merge-readiness.md
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

import github_api as api
import merge_readiness_lib as checks
import merge_readiness_presenter as presenter
from rich.console import Console

console: Console = Console()

# The workflow checks this report waits on and restates, in the order the comment lists them.
awaitedChecks: tuple[str, ...] = ("preflight", "hassfest")
checkAttempts: int = 40
checkPauseSeconds: float = 15.0
failedExitCode: int = 1
errorExitCode: int = 2


def readResolvedPackages() -> list[list[str]]:
    """Return what a fresh install resolved, which is what an advisory applies to."""
    listed = subprocess.run([sys.executable, "-m", "pip", "list", "--format=json"], capture_output=True, text=True, check=False)
    if listed.returncode != 0:
        return []
    return [[entry["name"], entry["version"]] for entry in json.loads(listed.stdout)]


def waitForCheck(token: str, sha: str, name: str) -> str:
    """Return one check's conclusion for a commit, waiting for it; a skipped draft run is never the answer."""
    url = f"{api.repositoryUrl}/commits/{sha}/check-runs?per_page=100"
    for attempt in range(checkAttempts):
        runs = api.requestJson(url, token)["check_runs"]
        decided = [
            run for run in runs
            if run["name"] == name and run["status"] == "completed" and run["conclusion"] not in (None, "skipped")
        ]
        if decided:
            return str(max(decided, key=lambda run: str(run["started_at"]))["conclusion"])
        if attempt < checkAttempts - 1:
            time.sleep(checkPauseSeconds)
    return ""


def readPullRequestFacts(token: str, number: int) -> dict[str, Any]:
    payload = api.requestJson(f"{api.repositoryUrl}/pulls/{number}", token)
    return {
        "title": payload.get("title", ""),
        "body": payload.get("body") or "",
        "base": payload.get("base", {}).get("ref", api.defaultBaseBranch),
    }


def readCommitsBehind(token: str, base: str, head: str) -> int:
    return int(api.requestJson(f"{api.repositoryUrl}/compare/{base}...{head}", token).get("behind_by", 0))


def findReportComment(token: str, number: int) -> int | None:
    for comment in api.requestJson(f"{api.repositoryUrl}/issues/{number}/comments?per_page=100", token):
        if presenter.commentMarker in (comment.get("body") or ""):
            return int(comment["id"])
    return None


def postReportComment(token: str, number: int, body: str) -> str:
    """Post the report, or replace the one an earlier run left, and say which."""
    existing = findReportComment(token, number)
    if existing is None:
        api.requestJson(f"{api.repositoryUrl}/issues/{number}/comments", token, method="POST", payload={"body": body})
        return "posted"
    api.requestJson(f"{api.repositoryUrl}/issues/comments/{existing}", token, method="PATCH", payload={"body": body})
    return "replaced"


def checkPullRequest(facts: checks.BranchFacts, token: str) -> list[checks.CheckResult]:
    """Run every check, in the order the comment lists them."""
    pullRequest = readPullRequestFacts(token, facts.pullRequest)
    behind = readCommitsBehind(token, pullRequest["base"], facts.headSha)
    template = facts.template or checks.templatePath.read_text()
    return [
        *[checks.checkWorkflowCheck(name, waitForCheck(token, facts.headSha, name)) for name in awaitedChecks],
        checks.checkTemplate(checks.findBodyFindings(pullRequest["body"], template)),
        checks.checkChecklist(pullRequest["body"]),
        checks.checkTitle(pullRequest["title"]),
        checks.checkCommitSubjects(facts),
        checks.checkBranchCurrent(behind, pullRequest["base"]),
        checks.checkDependencies(facts),
    ]


def runCollect(arguments: argparse.Namespace) -> int:
    facts = checks.collectBranchFacts(arguments.base, arguments.pull_request, branch=arguments.branch or "", headSha=arguments.head_sha or "")
    facts.resolvedPackages = readResolvedPackages()
    Path(arguments.output).write_text(json.dumps(facts.toDictionary(), indent=1))
    console.print(f"[green]collected[/] this branch's facts into {arguments.output}")
    return 0


def runCheck(arguments: argparse.Namespace) -> int:
    """Check the pull request and write the comment, failing on red; this job holds no write access."""
    facts = checks.BranchFacts.fromDictionary(json.loads(Path(arguments.results).read_text()))
    results = checkPullRequest(facts, api.resolveToken())
    verdict = checks.readVerdict(results)
    body = presenter.renderComment(results, facts, datetime.now(UTC))
    Path(arguments.comment).write_text(body)
    presenter.reportResults(console, results, verdict)
    for command in presenter.renderAnnotations(results):
        print(command)
    if summaryPath := os.environ.get("GITHUB_STEP_SUMMARY"):
        Path(summaryPath).write_text(body)  # the same report as the comment, so the two never disagree
    return failedExitCode if verdict == checks.failed else 0


def runReport(arguments: argparse.Namespace) -> int:
    """Post the comment the check rendered; this half decides nothing."""
    facts = checks.BranchFacts.fromDictionary(json.loads(Path(arguments.results).read_text()))
    body = Path(arguments.comment).read_text()
    if not facts.pullRequest:
        console.print("[red]the collected facts name no pull request[/]")
        return errorExitCode
    if arguments.dry_run:
        console.print(body, markup=False, highlight=False)
        return 0
    outcome = postReportComment(api.resolveToken(), facts.pullRequest, body)
    console.print(f"{outcome} the report on {api.formatPullRequestRef(facts.pullRequest)}")
    return 0


def buildParser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="merge-readiness.py", description="Report merge readiness as one comment on a pull request.")
    commands = parser.add_subparsers(required=True)

    collect = commands.add_parser("collect", help="gather the branch's facts for the checking half")
    collect.add_argument("--pull-request", type=int, required=True)
    collect.add_argument("--base", default=f"origin/{api.defaultBaseBranch}")
    collect.add_argument("--branch", help="its head branch, which a merge checkout hides")
    collect.add_argument("--head-sha", help="its head commit, not the merge commit")
    collect.add_argument("--output", default="merge-readiness.json")
    collect.set_defaults(handler=runCollect)

    check = commands.add_parser("check", help="check the pull request and write the comment, posting nothing")
    check.add_argument("--results", required=True)
    check.add_argument("--comment", default="merge-readiness.md")
    check.set_defaults(handler=runCheck)

    report = commands.add_parser("report", help="post the rendered comment")
    report.add_argument("--results", required=True)
    report.add_argument("--comment", required=True)
    report.add_argument("--dry-run", action="store_true", help="print, post nothing")
    report.set_defaults(handler=runReport)
    return parser


def main() -> int:
    arguments = buildParser().parse_args()
    try:
        return int(arguments.handler(arguments))
    except Exception as exc:  # noqa: BLE001 - a report never shows a traceback
        console.print(f"[red]{exc}[/]")
        return errorExitCode


if __name__ == "__main__":
    sys.exit(main())
