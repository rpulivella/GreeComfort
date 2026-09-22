---
description: Create and push an annotated release tag on develop, and publish release notes for a final.
argument-hint: <release type and version, e.g. "beta 1.1.2" or "final 1.1.2">
---

# /release-tag

Create an annotated release tag on `develop`, adapted from pybers. There are no release
branches; the tag alone records exactly what shipped. GreeComfort has no CHANGELOG, so a
final release's notes are the pull requests merged since the previous final, published as a
GitHub Release.

## What each tag means

- **`release/v<version>-b<NN>`**, an internal marker for a build deployed to the live Home
  Assistant for testing. Never published as a GitHub Release.
- **`v<version>`**, a build accepted after live testing, published as a GitHub Release. HACS
  reads the version its users see from this tag name, which is why it carries no prefix.

## Steps

1. Parse `$ARGUMENTS` for the type. If ambiguous, ask.
   - `beta <version> [iteration]` → `release/v<version>-b<NN>` (default `b01`)
   - `final <version>` → `v<version>`, plus a GitHub Release
2. Verify the state:
   - `git status --short --branch`: on `develop`, clean, not behind `origin/develop`.
   - `git log --oneline -3`: the commit being tagged looks right.
   - The `version` in `custom_components/gree_comfort/manifest.json` equals `<version>`.
   - `git tag -l "release/v<version>-*" "v<version>"`: the tag does not exist yet. Never reuse a tag.
3. **Confirm the tag matches what is deployed.** A tag records what ran live, so the tagged
   commit's integration must be byte-identical to the deployed copy. The deployed location
   is machine-specific and recorded in the git-ignored `CLAUDE.local.md`, never in this repository:
   ```
   diff -rq --exclude __pycache__ --exclude .DS_Store \
     custom_components/gree_comfort <deployed>/custom_components/gree_comfort
   ```
   Any difference is a refusal: deploy first, or tag the commit that is deployed.
4. **For a final**, draft the notes from the pull requests merged since the previous final
   (or since the start, for the first): `gh pr list --state merged --base develop --json
   number,title,mergedAt`. Group them as **Fixes** (`fix:` titles), **Changes** (`feat:`,
   `refactor:`, `perf:`) and **Housekeeping** (`chore:`, `docs:`, `style:`), one line each as
   `PR #<N>: <title>`, plus one sentence on what live testing covered.
5. **Show the exact tag, the commit, and (for a final) the notes. Wait for approval.**
6. Create the annotated tag: `git tag -a <tag> -m "<tag>"`.
7. **Do not push automatically.** Show `git push origin <tag>` and ask. For a final, after
   the push, publish the notes: `gh release create <tag> --title "v<version>" --notes-file
   <file outside the repository>`.

## Tag format reference

```
release/v1.1.2-b01     # deployed for live testing, internal only
v1.1.2                 # accepted after live testing, a GitHub Release
```

## Hard rules

- Never push a tag or publish a release without explicit user confirmation.
- Always lowercase prefix; always a `v` before the version; leading zeros on iterations
  (`-b01`, never `-b1`).
- Never reuse a tag; increment the iteration for a rebuild.
- Never tag a commit whose integration differs from what is deployed.

$ARGUMENTS
