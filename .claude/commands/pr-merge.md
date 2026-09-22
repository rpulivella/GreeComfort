---
description: Merge a reviewed pull request and get develop current. The only skill that runs gh pr merge.
argument-hint: <optional PR number; resolved from the current branch if omitted>
---

# /pr-merge

The last step of the workflow. `/pr-draft` creates the pull request, and this one merges
it. GreeComfort has no ticket system, so there is no ticket to close and no board to move.

## Steps

1. **Resolve the pull request** from `$ARGUMENTS` (`PR #42`, `#42`, `42`, URL), or with
   `gh pr view --json number -q .number` on the current branch. **Read what it printed.**
   A bare number is the PR, `no pull requests found` means there is none, and anything
   else means the question could not be asked at all. Those are three different facts,
   and only one of them is "no pull request".
2. **Refuse on an unclean state.** Run `git status --short --branch` and stop if either is
   true, saying which:
   - the working tree is dirty (untracked `CLAUDE.md` is expected and does not count);
   - the branch is `ahead` of its remote.

   Both merge a tree that differs from the one that was reviewed. Neither is waivable:
   commit or push first.
3. **Refuse on anything but passing checks.** Run `gh pr checks <N>` and `gh pr view <N>
   --json isDraft,mergeable`. Stop on a draft, on `mergeable` other than `MERGEABLE`, or
   on any check that is failing, pending or unreadable. `preflight` and `hassfest` must
   both be present and passing; a missing one means CI did not run, and that is a
   refusal. If the branch is behind `develop`, say so and let the user decide.
4. **Compose the merge subject: `PR #<N>: <PR title>`.** The PR title already follows the
   house format, so the subject reads `PR #4: fix: infer hvac_action from settled TemSen
   steps`. The PR identifier leads so `git log` on `develop` shows which pull request
   each merge brought in. The merge commit has no body. The `PR #<N>: ` prefix does not
   count toward the title's length limit. `--subject` is required exactly so that
   GitHub's generated default ("Merge pull request …") never lands. Present the subject
   and wait for approval.
5. **Merge, pinned to the reviewed head:**
   ```
   gh pr merge <N> --merge --subject "PR #<N>: <PR title>" --body "" \
     --match-head-commit "$(git rev-parse HEAD)" --delete-branch
   ```
   `--match-head-commit` refuses the merge if the remote head moved after step 2.
   `--delete-branch` removes the remote and local branch.
6. **Get `develop` current, and read what the pull printed.**
   ```
   git checkout develop
   git pull origin develop
   ```
   The remote and the branch are named rather than left to tracking configuration. A pull
   that fails prints an error, changes nothing, and leaves a stale `develop` behind, so
   the merge looks complete when it is not. Confirm the merge commit is in `git log`
   rather than assuming it arrived.
7. **Report** the merge commit, whether the branch was deleted, and the state of
   `develop`.

## A real merge is the default

A branch usually carries genuinely separate concerns and each commit earned its place, so
squashing destroys which change was which. **`--squash` is the exception**, and it fits
only when the branch is one logical change whose history is fixup churn rather than
separable steps. Say in the report why it was chosen.

## Hard rules

- **Never merge a draft.**
- **Never merge with a dirty tree or unpushed commits.**
- **Never merge with failing, pending or unreadable checks.**
- **Never let GitHub's default merge subject land.** `--subject "PR #<N>: <PR title>"` always.
- **Never merge without the user approving the subject.**
- Nothing here needs a script of its own. Every action is `gh pr merge` or plain git.

$ARGUMENTS
