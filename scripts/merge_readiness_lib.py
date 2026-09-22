"""\
The checks behind the merge-readiness report, and the facts a branch supplies them.
Adapted from pybers without its ticket, CHANGELOG and golden-file checks.

Split in two because the halves run with different trust: collecting runs on the pull
request's branch with no write access, checking reads those facts as data only. Every
function returns a result and prints nothing, so each check is testable offline.
"""
from __future__ import annotations

import json
import re
import subprocess
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

repositoryRoot: Path = Path(__file__).resolve().parent.parent
templatePath: Path = repositoryRoot / "pr_template.md"
manifestPath: Path = repositoryRoot / "custom_components" / "gree_comfort" / "manifest.json"
requirementsPath: Path = repositoryRoot / "requirements_test.txt"

osvBatchUrl: str = "https://api.osv.dev/v1/querybatch"
pypiRoot: str = "https://pypi.org/pypi"
networkTimeoutSeconds: float = 30.0

# The closed prefix set and limits /commit and /pr-draft state.
commitPrefixes: tuple[str, ...] = ("feat", "fix", "perf", "refactor", "style", "docs", "chore")
maximumSubjectLength: int = 60
maximumTitleLength: int = 72
maximumBodyLengthMultiple: int = 2

passed: str = "passed"
failed: str = "failed"
attention: str = "attention"
skipped: str = "skipped"


@dataclass(frozen=True)
class CheckResult:
    """One named check, its verdict, and the one line a reader needs; `attention` means a person decides."""

    name: str
    status: str
    detail: str


@dataclass
class BranchFacts:
    """What the branch supplies, as plain data the checking half reads."""

    branch: str = ""
    headSha: str = ""
    pullRequest: int = 0
    commitSubjects: list[str] = field(default_factory=list)
    resolvedPackages: list[list[str]] = field(default_factory=list)
    declaredPackages: list[str] = field(default_factory=list)
    template: str = ""

    def toDictionary(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def fromDictionary(cls, stored: dict[str, Any]) -> BranchFacts:
        """Build facts from a stored file, ignoring fields this copy lacks, since the halves run different copies."""
        known = {item.name for item in fields(cls)}
        return cls(**{name: value for name, value in stored.items() if name in known})


def runGit(arguments: list[str]) -> str:
    """Run one git command in the repository and return its output."""
    completed = subprocess.run(["git", "-C", str(repositoryRoot), *arguments], capture_output=True, text=True, check=False)
    if completed.returncode != 0:
        raise RuntimeError(f"git {' '.join(arguments)} failed: {completed.stderr.strip()}")
    return completed.stdout.strip()


def readDeclaredPackages() -> list[str]:
    """Return every package the test requirements and the manifest declare."""
    declared = [line.strip() for line in requirementsPath.read_text().splitlines() if line.strip() and not line.startswith("#")]
    declared += json.loads(manifestPath.read_text()).get("requirements", [])
    return [re.split(r"[<>=!~\[; ]", entry, maxsplit=1)[0] for entry in declared]


def collectBranchFacts(base: str, pullRequest: int, branch: str = "", headSha: str = "") -> BranchFacts:
    """Gather what the checking half needs; branch and head come from the caller because a PR checkout is a detached merge commit."""
    facts = BranchFacts(
        branch=branch or runGit(["rev-parse", "--abbrev-ref", "HEAD"]),
        headSha=headSha or runGit(["rev-parse", "HEAD"]),
        pullRequest=pullRequest,
        # --no-merges, because the checkout's own merge commit is GitHub's, not the author's
        commitSubjects=runGit(["log", "--no-merges", f"{base}..{headSha or 'HEAD'}", "--format=%s"]).splitlines(),
        declaredPackages=readDeclaredPackages(),
    )
    if templatePath.is_file():
        facts.template = templatePath.read_text()
    return facts


def formatList(items: list[str]) -> str:
    """Join names as a sentence does, with a conjunction before the last."""
    if len(items) < 2:
        return "".join(items)
    return ", ".join(items[:-1]) + f" and {items[-1]}"


def checkWorkflowCheck(name: str, conclusion: str) -> CheckResult:
    """Report what another workflow's own check concluded for this commit."""
    if conclusion == "success":
        return CheckResult(name, passed, f"{name} passed")
    if conclusion in ("skipped", ""):
        return CheckResult(name, skipped, f"{name} did not run")
    return CheckResult(name, failed, f"{name} ended as {conclusion}")


def isHouseSubject(subject: str, limit: int) -> bool:
    prefixes = "|".join(commitPrefixes)
    return len(subject) <= limit and re.fullmatch(rf"(?:{prefixes}): \S.*", subject) is not None


def checkCommitSubjects(facts: BranchFacts) -> CheckResult:
    """Report any commit subject outside the house format /commit states."""
    if not facts.commitSubjects:
        return CheckResult("Commit Subjects", skipped, "This branch carries no commits of its own")
    wrong = [subject for subject in facts.commitSubjects if not isHouseSubject(subject, maximumSubjectLength)]
    if wrong:
        return CheckResult(
            "Commit Subjects", failed,
            f"{len(wrong)} subject(s) break the house format or exceed {maximumSubjectLength} characters: "
            + formatList([f"`{subject}`" for subject in wrong]),
        )
    return CheckResult("Commit Subjects", passed, f"All {len(facts.commitSubjects)} subjects follow the house format")


def checkTitle(title: str) -> CheckResult:
    """Report whether the PR title follows the house format, since /pr-merge makes it the merge subject."""
    if isHouseSubject(title, maximumTitleLength):
        return CheckResult("PR Title", passed, "The title follows the house format")
    return CheckResult("PR Title", failed, f"`{title}` is not `<prefix>: <summary>` within {maximumTitleLength} characters")


def checkBranchCurrent(behind: int, base: str) -> CheckResult:
    """Report whether the branch has fallen behind the base it will merge into."""
    if behind == 0:
        return CheckResult("Base Branch", passed, f"This branch is up to date with {base}")
    return CheckResult("Base Branch", attention, f"This branch is {behind} commits behind {base}")


def readHeadings(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.startswith("## ")]


def readBoldRuns(text: str) -> list[str]:
    """Return every line that is entirely bold, which renders like a heading."""
    return [line.strip() for line in text.splitlines() if re.fullmatch(r"\*\*[^*]+\*\*", line.strip())]


def readCheckboxLabels(text: str) -> list[str]:
    """Return every checkbox label with its state discarded; `NA ` counts as a state."""
    labels: list[str] = []
    for line in text.splitlines():
        matched = re.match(r"\s*- (?:\[[ xX]\]\s*|NA\s+)(.+?)\s*$", line)
        if matched:
            labels.append(matched.group(1))
    return labels


def countProseWords(text: str) -> int:
    """Return the word count with HTML comments removed, since those are drafter instructions."""
    return len(re.findall(r"\S+", re.sub(r"<!--.*?-->", " ", text, flags=re.DOTALL)))


def findBodyFindings(body: str, template: str) -> list[str]:
    """Return every way a body departs from its template."""
    findings: list[str] = []
    templateHeadings, headings = readHeadings(template), readHeadings(body)
    invented = [heading for heading in headings if heading not in templateHeadings]
    if invented:
        findings.append(f"{len(invented)} heading(s) the template does not carry: " + ", ".join(invented))
    missing = [heading for heading in templateHeadings if heading not in headings]
    if missing:
        findings.append(f"{len(missing)} template heading(s) missing: " + ", ".join(missing))
    if not invented and not missing and headings != templateHeadings:
        findings.append(f"headings are out of the template's order, expected {templateHeadings}")
    templateBold = set(readBoldRuns(template))
    inventedBold = [run for run in readBoldRuns(body) if run not in templateBold]
    if inventedBold:
        findings.append(f"{len(inventedBold)} bold line(s) reading as a heading: " + ", ".join(inventedBold))
    templateLabels = set(readCheckboxLabels(template))
    reworded = [label for label in readCheckboxLabels(body) if label not in templateLabels]
    if reworded:
        findings.append(f"{len(reworded)} checkbox(es) the template does not carry: " + ", ".join(reworded))
    ceiling = countProseWords(template) * maximumBodyLengthMultiple
    words = countProseWords(body)
    if words > ceiling:
        findings.append(f"body is {words} words against a ceiling of {ceiling}")
    if "<!--" in body:
        findings.append("the body still carries template instructions (`<!-- -->`)")
    return findings


def checkTemplate(findings: list[str]) -> CheckResult:
    if not findings:
        return CheckResult("PR Template", passed, "This PR matches the template")
    return CheckResult("PR Template", failed, ". ".join(findings))


def checkChecklist(body: str) -> CheckResult:
    """Report any checklist line neither checked nor marked NA, which is a question nobody answered."""
    waiting = [line.split("] ", 1)[-1].strip() for line in body.splitlines() if re.match(r"\s*- \[ \]", line)]
    if waiting:
        subject = "checkbox is" if len(waiting) == 1 else "checkboxes are"
        return CheckResult("Checklist", failed, f"{len(waiting)} {subject} neither checked nor NA: " + formatList(waiting))
    return CheckResult("Checklist", passed, "Every checkbox is checked or NA")


def readVerdict(results: list[CheckResult]) -> str:
    """Return the one verdict a set of checks carries, worst first."""
    statuses = {result.status for result in results}
    if failed in statuses:
        return failed
    if attention in statuses:
        return attention
    return passed


def readAdvisories(packages: list[list[str]]) -> dict[str, list[str]]:
    """Ask OSV, in one batch request, which of these exact versions carry a published advisory."""
    if not packages:
        return {}
    queries = [{"package": {"name": name, "ecosystem": "PyPI"}, "version": version} for name, version in packages]
    request = urllib.request.Request(
        osvBatchUrl, data=json.dumps({"queries": queries}).encode(), headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(request, timeout=networkTimeoutSeconds) as response:
        payload = json.loads(response.read())
    found: dict[str, list[str]] = {}
    for (name, version), result in zip(packages, payload.get("results", []), strict=False):
        identifiers = [entry.get("id", "") for entry in result.get("vulns", [])]
        if identifiers:
            found[f"{name} {version}"] = identifiers
    return found


def readYankedPackages(packages: list[list[str]]) -> list[str]:
    """Return each resolved version PyPI has withdrawn."""
    yanked: list[str] = []
    for name, version in packages:
        url = f"{pypiRoot}/{urllib.parse.quote(name)}/{urllib.parse.quote(version)}/json"
        try:
            with urllib.request.urlopen(url, timeout=networkTimeoutSeconds) as response:
                payload = json.loads(response.read())
        except urllib.error.HTTPError:
            continue
        if payload.get("info", {}).get("yanked"):
            yanked.append(f"{name} {version}")
    return yanked


def checkDependencies(facts: BranchFacts) -> CheckResult:
    """Report advisories and yanks against the declared packages a fresh install resolved."""
    declared = {package.lower() for package in facts.declaredPackages}
    watched = [[name, version] for name, version in facts.resolvedPackages if name.lower() in declared]
    if not watched:
        return CheckResult("Dependencies", skipped, "This install resolved no declared dependency")
    advisories, yanked = readAdvisories(watched), readYankedPackages(watched)
    if advisories or yanked:
        lines = [f"- {package} has advisory {formatList(ids)}" for package, ids in sorted(advisories.items())]
        lines += [f"- {package} is withdrawn from PyPI" for package in sorted(yanked)]
        return CheckResult("Dependencies", failed, "\n".join(lines))
    noun = "package" if len(watched) == 1 else "packages"
    return CheckResult("Dependencies", passed, f"{len(watched)} resolved {noun}, no advisories, none withdrawn")
