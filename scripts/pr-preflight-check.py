#!/usr/bin/env python3
"""\
Pull Request Preflight Check

Run every gate this repository has, in one pass, and report all of them, so one run lists
everything to fix rather than the first thing. Adapted from pybers' preflight.

Run it with the project venv: `.venv/bin/python3 scripts/pr-preflight-check.py`.
Every gate is repository-wide and asks git nothing, so it runs unchanged on a shallow CI
checkout.
"""
from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from rich.console import Console
from rich.markup import escape

console: Console = Console()


@dataclass(frozen=True)
class GateResult:
    """One gate's verdict, its one-line summary, and everything it printed."""

    name: str
    passed: bool
    summary: str
    output: str


def findRepositoryRoot() -> Path:
    """Return the repository root, so the script runs from any directory."""
    return Path(__file__).resolve().parent.parent


def loadStandardsModule():
    """Return the standards checker as a module; its file name has a hyphen, so import by string."""
    if str(findRepositoryRoot()) not in sys.path:
        sys.path.insert(0, str(findRepositoryRoot()))
    return importlib.import_module("scripts.standards-check")


def runTests() -> GateResult:
    """Run the whole pytest suite in this process, with a coverage report and no threshold."""
    import pytest

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = pytest.main(["-q", "-p", "no:cacheprovider", "--cov", "--cov-report=term", "tests"])
    output = buffer.getvalue().strip()
    lastLine = output.splitlines()[-1] if output else "pytest printed nothing"
    return GateResult("pytest", int(code) == 0, lastLine, output)


def runJson() -> GateResult:
    """Parse every JSON the integration ships and every one at the root, which HA and HACS read."""
    root = findRepositoryRoot()
    files = sorted((root / "custom_components").rglob("*.json")) + sorted(root.glob("*.json"))
    broken: list[str] = []
    for path in files:
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            broken.append(f"{path.relative_to(findRepositoryRoot())}: {exc}")
    summary = f"{len(files)} file(s) parsed, {len(broken)} invalid"
    return GateResult("json", not broken, summary, "\n".join(broken))


def runStandards() -> GateResult:
    """Check every prose file in the repository, failing only on a FAILURE; a warning never gates."""
    standards = loadStandardsModule()
    warnings: list[str] = []
    findings: list[tuple[str, Path, int, str]] = []
    # The checker's own --all scope, so this inherits its skip rules rather than copying them
    scope = argparse.Namespace(paths=[], all=True)
    files = standards.collectFiles(scope, warnings)
    for path in files:
        standards.checkFile(path, findings)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = standards.report(findings, files, warnings)
    failures = sum(1 for finding in findings if finding[0] == "FAIL")
    summary = f"{len(files)} file(s) checked, {failures} failure(s)"
    return GateResult("standards", code == 0, summary, buffer.getvalue().strip())


# Every gate, in the order a reader most wants them; --gate selects one during development.
gates: dict[str, Callable[[], GateResult]] = {
    "pytest": runTests,
    "standards": runStandards,
    "json": runJson,
}


def runGates(names: list[str]) -> list[GateResult]:
    """Run each named gate to completion; a gate that cannot run becomes a failing result."""
    results: list[GateResult] = []
    for name in names:
        try:
            results.append(gates[name]())
        except Exception as exc:  # noqa: BLE001 - one broken gate must not hide the others
            results.append(GateResult(name, False, "could not run", f"{type(exc).__name__}: {exc}"))
    return results


def report(results: list[GateResult]) -> int:
    """Print every verdict, then each failing gate's full output, and return the exit code."""
    for result in results:
        mark = "[green]PASS[/]" if result.passed else "[red]FAIL[/]"
        console.print(f"{mark} [bold]{escape(result.name)}[/]  {escape(result.summary)}")

    failed = [result for result in results if not result.passed]
    if not failed:
        console.print(f"\n[green]All {len(results)} gate(s) passed.[/]")
        return 0
    for result in failed:
        console.print(f"\n[bold red]{escape(result.name)}[/]")
        console.print(result.output or "(no output)", markup=False, highlight=False)
    console.print(f"\n[red]{len(failed)} of {len(results)} gate(s) failed:[/] {escape(', '.join(r.name for r in failed))}")
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(prog="pr-preflight-check.py", description="Run every GreeComfort gate in one pass.")
    parser.add_argument("--gate", action="append", choices=sorted(gates), help="run only this gate, repeatable")
    arguments = parser.parse_args()
    with contextlib.chdir(findRepositoryRoot()):
        return report(runGates(arguments.gate or list(gates)))


if __name__ == "__main__":
    sys.exit(main())
