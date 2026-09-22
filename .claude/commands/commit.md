---
description: Stage and commit changes following GreeComfort's mandatory commit format.
argument-hint: <optional message hint>
---

# /commit

Stage and commit following this repo's mandatory format. GreeComfort has no ticket system,
so subjects carry no bracketed id.

## Steps

1. Run `git branch --show-current`. **If the branch is `develop`, stop and ask.** Every
   change lands through a pull request from its own `<type>/<slug>` branch (`fix/`,
   `feature/`, `refactor/`, `chore/`), so work sitting on `develop` needs a branch first.
2. Run `git status` and `git diff` (staged + unstaged) to understand what changed. If
   there is nothing to commit, say so and stop.
3. Compose the message:
   - **`<prefix>: <summary>`**, a Conventional-Commits inspired prefix always.
   - **Single line only**, no body, no footer, nothing after the first line.
   - **≤ 60 characters** (aim 50). Imperative mood ("add", "fix", "remove").
   - **No "Co-Authored-By"**, no AI attribution of any kind.
   - **The prefix is chosen per commit, from what that commit did, never from the
     branch.** A `refactor/` branch normally carries `refactor:` several times and then
     `fix:`, `chore:` or `docs:` as the work turns; that is correct, not drift. The branch
     prefix and the commit prefix are two different axes.
4. **STOP. Present the plan and wait for explicit approval.**
   ```
   Proposed commit message:
     <message>

   Files to stage:
     <list>
   ```
   Do not stage or commit until the user says yes. If they suggest a different message,
   update and re-present.
   **This gate is permanent.** No branch, prior "always allow", or standing consent ever
   authorizes committing without asking.
5. Stage the relevant files **by name**. Never `git add -A` or `git add .` unless every
   untracked file is clearly intentional. When one file holds changes for two commits,
   stage a version with only the first change, commit, then restore the full file.
   **Never stage:**
   - `CLAUDE.local.md`, git-ignored and machine-specific (`CLAUDE.md` **is** committed)
   - `.claude/settings.local.json`, `.env`, `.dev.vars`, or anything with secrets
   - `__pycache__/`, `.venv/`, `*.egg-info/`, `dist/`, `build/`, `.pytest_cache/`
   - anything under `workarea/` (scratch space)
6. Before committing, run the preflight and stop if any gate fails:
   ```
   .venv/bin/python3 scripts/pr-preflight-check.py
   ```
   It runs the whole pytest suite, the prose gate over every document, and parses every JSON file
   the integration and HACS read. A
   fresh clone needs the venv first: `uv venv -p 3.14 .venv` then
   `VIRTUAL_ENV=.venv uv pip install -r requirements_test.txt`.
7. Commit with inline `-m` only, **never a heredoc** (heredocs introduce Co-Authored-By
   footers):
   ```
   git commit -m "prefix: description"
   ```
8. Run `git status` to confirm.
9. **Do not push automatically.** Ask first.

## Prefixes

A closed set of seven:

| Prefix | Use for |
|---|---|
| `feat:` | new feature or entity |
| `fix:` | bug fix |
| `perf:` | faster or lighter, no behavior change |
| `refactor:` | restructure without behavior change |
| `style:` | formatting only, no code meaning changes |
| `docs:` | README, comments, documentation |
| `chore:` | config, tooling, manifest, version bumps, skills, templates |

**`test` is deliberately not among them.** It does not say whether a test was written or a
test was run, and a prefix that needs a body to disambiguate it has failed at its one job.
Writing, changing or deleting tests is `chore:`.

## Choosing the boundary

- **One logical change, one commit, at a minimum.** A large change usually earns
  several: the restructure, the behavior it enabled, a fix found while exercising it.
  One commit for a whole pull request is almost always wrong.
- **Small related changes may combine.** A message with "and" or a semicolon in it is
  fine; the sixty-character limit already stops that going far.
- **Every commit's preflight is green.** No exceptions. "It works once the next one lands"
  is not two commits, it is one.
- **Work the branch surfaces belongs to the branch**, in its own commit, even when it
  touches tooling, a skill or a template. It was discovered doing that work and should
  not be buried inside a commit that is not about it.
- **A version bump is its own `chore:` commit**, last on the branch.

## Correct examples

```
fix: compare eco shutoff setpoint in °C, not display unit
refactor: report climate temperatures in native °C
feat: add eco shutoff dwell progress attribute
chore: bump version to 1.1.0
```

## Hard rules

- NEVER produce a multi-line message. NEVER add Co-Authored-By or any AI attribution.
- NEVER exceed 60 characters.
- NEVER commit on `develop` without asking.
- NEVER use `--no-verify`. NEVER push without asking.
- NEVER stage `CLAUDE.local.md`, secrets, build artifacts or `workarea/`.

$ARGUMENTS
