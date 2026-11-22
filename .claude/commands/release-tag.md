---
description: Create and push an annotated release tag on develop, and publish a beta as a pre-release or a final as a release.
argument-hint: <release type and version, e.g. "beta 1.1.2" or "final 1.1.2">
---

# /release-tag

Create an annotated release tag on `develop`, adapted from pybers. There are no release
branches; the tag alone records exactly what shipped. GreeComfort has no CHANGELOG, so the notes
of a beta and of a final are the pull requests merged since the previous final, published on
GitHub.

## What each tag means

- **`v<version>-b<NN>`**, a beta: a build published as a GitHub pre-release for testing. The
  Marketplace offers it only to users who turn on a repository's Pre-release switch, so the owner
  installs it the way every user installs a release. `manifest.json` carries the same version,
  `<version>-b<NN>`.
- **`v<version>`**, a build accepted after testing, published as a GitHub Release. Its code is the
  accepted beta's with only the version line changed.

The Marketplace reads the version its users see from the tag name, which is why a tag carries a `v`
and no other prefix.

## Steps

1. Parse `$ARGUMENTS` for the type. If ambiguous, ask.
   - `beta <version> [iteration]` → tag `v<version>-b<NN>` (default `b01`)
   - `final <version>` → tag `v<version>`
2. Verify the state:
   - `git status --short --branch`: on `develop`, clean, not behind `origin/develop`.
   - `git log --oneline -3`: the commit being tagged looks right.
   - The `version` in `custom_components/gree_comfort/manifest.json` equals the tag without its
     leading `v`: `<version>-b<NN>` for a beta, `<version>` for a final.
   - `git tag -l "<tag>"` prints nothing: the tag does not exist yet. Never reuse a tag.
   - `health` is green on the commit. This prints `completed success` and nothing else is accepted:
     ```
     gh api "repos/{owner}/{repo}/actions/workflows/health.yml/runs?head_sha=$(git rev-parse HEAD)" \
       --jq '.workflow_runs[] | "\(.status) \(.conclusion)"'
     ```
3. **For a final, confirm it is the accepted beta.** The latest beta of this version is the build
   that was tested, so `git diff --stat <that beta tag> HEAD` must list
   `custom_components/gree_comfort/manifest.json` and nothing else. Ask the user to confirm that the
   beta was installed through the Marketplace and accepted, and that the version shown for Gree
   Comfort under Settings > Updates equals the beta tag without its `v`. Any other difference is a
   refusal: tag another beta first.
4. **Draft the notes** from the pull requests merged since the previous final (or since the start,
   for the first). The subjects of the merge commits already read `PR #<N>: <title>`:
   ```
   git log --first-parent --merges --format=%s <previous final tag>..HEAD
   ```
   The notes are one opening sentence, then the groups, one line per pull request as
   `PR #<N>: <title>`, and nothing else. Group by the prefixes of each pull request's commits:
   **Fixes** (`fix:`), **Changes** (`feat:`, `refactor:`, `perf:`) and **Housekeeping** (`chore:`,
   `docs:`, `style:`), using the most user-visible prefix when a pull request mixes them. The
   opening sentence of a final reads like "This release makes routine compatibility and logging
   improvements." and of a beta "This is beta <NN> of <version>, for testing."
5. **Show the exact tag, the commit, and the notes. Wait for approval.**
6. Create the annotated tag: `git tag -a <tag> -m "<tag>"`.
7. **Do not push automatically.** Show `git push origin <tag>` and ask. After the push, publish from
   a notes file outside the repository, adding `--prerelease` for a beta and nothing for a final:
   ```
   gh release create <tag> --verify-tag --title "<tag>" --notes-file <file> [--prerelease]
   ```
8. **Read it back.** `gh release view <tag> --json tagName,isDraft,isPrerelease,publishedAt` shows
   it is not a draft and that `isPrerelease` is `true` for a beta and `false` for a final, and
   `git ls-remote origin "<tag>^{}"` equals `git rev-parse "<tag>^{commit}"`. Report what was read.

## Tag format reference

```
v1.1.2-b01     # a beta, a GitHub pre-release for testers who opt in
v1.1.2         # accepted after testing, a GitHub Release
```

## Hard rules

- Never push a tag or publish a release without explicit user confirmation.
- Always lowercase; always a `v` before the version; leading zeros on iterations (`-b01`, never
  `-b1`).
- Never reuse a tag; increment the iteration for a rebuild.
- Never publish a beta without `--prerelease`, and never publish a final with it.
- Never tag a commit whose `manifest.json` version differs from the tag, or on which `health` is
  not green.
- Never tag a final whose code differs from its accepted beta beyond the version line.

$ARGUMENTS
