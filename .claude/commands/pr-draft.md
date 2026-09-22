---
description: Create a pull request from the current feature branch into develop
---

# /pr-draft

Create a pull request from the current feature branch into `develop`.

## Steps

1. Run `git branch --show-current`. If the branch is `develop`, stop — never PR from develop to develop.
2. Run `git log develop..HEAD --oneline` to understand all commits in this branch.
3. Run `git diff develop...HEAD --stat` to see what files changed.
4. Check push status with `git status -sb`. If the branch is ahead of remote, push first with `git push`.
5. Read `pr_template.md` at the repo root.
6. Fill the template. Its `<!-- -->` comments are instructions for the drafter; follow them and leave them out of the body. Rules:
   - **Title**: short imperative summary of what the branch adds/fixes — max 72 chars. Do not repeat the branch name verbatim.
   - **Branch**: fill in the current branch name.
   - **Intro paragraph**: 2–3 sentences from the commit log and diff describing what this PR achieves and why.
   - **Type of change**: keep only the one that applies, remove the rest.
   - **Breaking changes**: fill honestly — note `None` for each section that does not apply. Entity renames and storage changes are the two most common breaking surfaces for this integration.
   - **Checklist**: check what is genuinely true. Unchecked means **not done**, so an item
     that cannot apply moves to the end of the list with `NA` in place of its checkbox
     (`- NA Entity registry migrations ...`). That records it as considered rather than
     skipped, which deleting it would lose. Say in the body why, when the reason is worth
     knowing. **Type of change** keeps its own rule and deletes instead, because its boxes
     are alternatives rather than obligations.
7. **STOP. Present the full PR title and body for approval before creating anything.**
   Do not call `gh` until the user says yes (or equivalent).
8. Create the PR with:
   ```
   gh pr create --base develop --title "..." --body "$(cat <<'EOF'
   ...
   EOF
   )"
   ```
   Use `--draft` only if the user explicitly requests it.
9. Output the PR URL.

## Hard rules
- NEVER target any branch other than `develop`
- NEVER add "Co-Authored-By", "Generated with Claude Code", or any AI attribution anywhere
- NEVER push without confirming first
- NEVER create the PR without showing the full body and getting approval
- NEVER add sections not in the template

$ARGUMENTS
