---
description: Review a draft pull request. Run the preflight first, then review the changed files, and take the PR out of draft only if everything is clean.
argument-hint: <optional PR number; inferred from the branch if omitted>
---

# /pr-review-code

The review half of the workflow, adapted from pybers, and **the only thing in this
repository that takes a pull request out of draft**. `/pr-draft` opens every PR as a draft,
and CI skips drafts, so promotion is the moment CI first spends Actions minutes. This skill
makes sure that spend is on a branch that already passes locally.

## What a review is today

**The preflight, then a reading of the diff.** `scripts/pr-preflight-check.py` runs every
gate in one pass (pytest, the prose gate and the JSON gate) and reports all of them, so a failing
run lists everything to fix rather than the first thing.

**The preflight does not read the pull request itself**, so step 5 also reads the body
against `.github/pull_request_template.md`: every heading present, every checkbox checked or NA, no template
comment left behind.

## Steps

1. **Resolve the pull request** from `$ARGUMENTS` (`PR #42`, `#42`, `42`, URL), or with
   `gh pr view --json number,isDraft -q '"\(.number) \(.isDraft)"'` on the current branch.
   **Read what it printed.** A number is the PR, `no pull requests found` means there is
   none, and anything else means the question could not be asked at all. Those are three
   different facts. Stop if the PR is not a draft, and say so: it was promoted already.
2. **Refuse on an unclean state.** Run `git status --short --branch` and stop if the tree
   is dirty or the branch is ahead of its remote. The
   preflight must run against exactly what the PR carries.
3. **Run the preflight and stop if it fails:**
   ```
   .venv/bin/python3 scripts/pr-preflight-check.py
   ```
   With the project venv, not the system interpreter. Non-zero means **do not review and
   do not promote**: report every failing gate and its reason verbatim, and stop. Do not
   soften a machine reason into something friendlier.
4. **Establish the scope**, which is the changed files and nothing else:
   ```
   git diff develop...HEAD --stat
   git diff develop...HEAD
   ```
5. **Review the diff yourself** for correctness, unit handling (native °C, HA converters),
   tests covering the risky logic, and the house laws in `CLAUDE.md`. Launch a
   `pr-review-toolkit` agent only when the user asks for one, because each costs roughly
   50k tokens.
6. **Report**, separating what you verified by execution from what you only read. Name the
   commands you ran. State what could not be checked, rather than omitting it.
7. **Only on a green preflight with no unresolved finding**, and with the user's approval,
   check `Self-review done` in the body (`gh pr edit <N> --body-file <file>`, the body file
   outside the repository), then promote it:
   ```
   gh pr ready <N>
   ```
   CI then runs `preflight` and `hassfest`. Say that it has started; do not
   wait on it here. `/pr-merge` is where a red or missing check becomes a refusal.

## Waiving a stage

A failing gate may be **waived** only when the failure is provably outside the diff
(`git diff develop...HEAD --name-only` shows the change could not have caused it), the user
agrees, and the waiver is written into the pull request body. Never waive silently, and
never waive more than the one gate in question.

## Hard rules

- **Never promote on a red preflight**, unless the failing gate is waived above.
- **Never promote without the user's approval.**
- **Never launch a review agent unless the user asks for one.**
- **Never edit a body to make a finding go away.**
- **The preflight is repository-wide; the review is diff-wide.** Never narrow the
  preflight to changed files, and never let the review wander outside them.
- Never merge from this skill. `/pr-merge` owns merging, and it refuses a draft.

$ARGUMENTS
