# Contributing to GreeComfort

GreeComfort is built through an agentic harness. This guide is the single source of truth for how change flows into the repository: commits, branches, pull requests and merges. Adapted from pybers, without its tickets, CHANGELOG or release tags.

## How a pull request is referenced

Pull requests are written `PR #38` in prose, never a bare number and never a bare `#`. GreeComfort has no ticket system, so nothing else takes a `#`.

## Commit message format

One scannable line per commit: `<prefix>: <summary>`.

Rules: single line, no body, no footer; at most 60 characters; imperative mood; a Conventional-Commits-inspired prefix always, from the closed set `feat` `fix` `perf` `refactor` `style` `docs` `chore`. Writing or changing tests is `chore`, since `test` would not say whether a test was written or run. Never a `Co-Authored-By` trailer, it breaks the one-line log.

```
fix: compare eco shutoff setpoint in °C, not display unit
refactor: report climate temperatures in native °C
chore: bump version to 1.1.0
```

## Branch strategy

**`develop` is the one long-lived trunk branch**, the default, and what gets deployed. There is no `main` and there are no release branches.

```
per change:  <type>/<verbose-slug>  ->  draft PR into develop  ->  merge  ->  delete branch
```

- **`develop`** stays green. Everything merges through a pull request; nothing is committed on `develop` directly.
- **`type`** is one of `feature`, `fix`, `refactor`, `docs` or `chore`.
- **The branch prefix and the commit prefix are two different axes.** A `refactor/` branch normally carries several `refactor:` commits and then `fix:`, `chore:` or `docs:` as the work turns.
- **Every pull request stands alone.** Branches and pull requests are never stacked on one another; a PR that depends on another waits until that one merges, then branches from `develop`.
- **A version bump is its own `chore:` commit**, last on the branch, in `custom_components/gree_comfort/manifest.json`.

## What review-ready means

Every pull request opens as a **draft**, and nothing runs on GitHub while it is one. A pull request leaves draft when two things are true, and not before:

1. Tests appropriate to the change exist and pass, and cover the risky logic it touches.
2. The preflight passes: `scripts/pr-preflight-check.py` runs every gate in one pass (pytest, the
   prose gate, ruff and the JSON gate) and reports them together.

`/pr-review-code` checks both, reviews the diff, and is the only thing that takes a pull request out of draft.

## What GitHub checks

Nothing runs on a draft. Once a pull request leaves draft, two checks run:

- **`preflight`**, the same gates as the local preflight, one step per gate.
- **`hassfest`**, Home Assistant's own validator for the manifest, translations, icons and services.

`/pr-merge` refuses while either is red or missing.

## Merging

A real merge, never a squash by default, so each commit keeps its place in history. The merge commit's subject is `PR #<N>: <PR title>` with no body, so `git log` on `develop` shows which pull request each merge brought in. `/pr-merge` owns the command.

## Releases

A release is a tag on `develop`; there are no release branches. The version is the `version` in
`custom_components/gree_comfort/manifest.json`, SemVer, and a tag matches it exactly.

```
v1.1.2-b01    # a beta, published as a GitHub pre-release for testing
v1.1.2        # the same code with the version line changed, accepted after testing, published as a GitHub Release
```

- **A beta is tagged `v<version>-b<NN>`**, `-b01` first and the iteration incremented for a rebuild
  of the same version, and `manifest.json` carries the same version as the tag. It is published as
  a GitHub pre-release, which the Marketplace offers only to users who turn on a repository's
  Pre-release switch, so the owner installs and tests it the way every user installs a release.
- **An accepted build is tagged `v<version>`** and published as a GitHub Release, because the
  Marketplace reads the version its users see from the release's tag name. Its notes list the pull
  requests merged since the previous release, grouped as fixes, changes and housekeeping, since
  there is no CHANGELOG.
- **A final is exactly what was tested**: it differs from its accepted beta by the version line in
  `manifest.json` and nothing else.
- Never reuse a tag. `/release-tag` owns the procedure.

## Build and verify

```bash
uv venv -p <python version> .venv   # at or above requires-python in pyproject.toml, and one Home Assistant supports
VIRTUAL_ENV=.venv uv pip install -r requirements_test.txt
.venv/bin/python3 -m pytest tests                 # the suite
.venv/bin/python3 scripts/pr-preflight-check.py   # every gate, what CI runs
```

`requirements_test.txt` pins `pytest-homeassistant`, Home Assistant's own test package, whose release number is the Home Assistant release the suite runs against. The simulated unit in `tests/conftest.py` answers at the network boundary, so request building, encryption and `SyncState` run for real.

Every commit leaves the test suite green. No exceptions.
