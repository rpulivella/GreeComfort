"""The GitHub REST calls the merge-readiness scripts make, with an explicit token only."""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from typing import Any

restRoot: str = "https://api.github.com"
repositoryOwner: str = "rpulivella"
repositoryName: str = "GreeComfort"
repositoryUrl: str = f"{restRoot}/repos/{repositoryOwner}/{repositoryName}"
defaultBaseBranch: str = "develop"


def resolveToken() -> str:
    """Return GITHUB_TOKEN or GH_TOKEN; there is deliberately no keyring fallback, so a missing token fails loudly."""
    for variableName in ("GITHUB_TOKEN", "GH_TOKEN"):
        value = os.environ.get(variableName)
        if value is None:
            continue
        if not value.strip():
            raise RuntimeError(f"{variableName} is set but empty, which is a misconfiguration")
        return value.strip()
    raise RuntimeError("No GitHub token: set GITHUB_TOKEN or GH_TOKEN")


def requestJson(url: str, token: str, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    """Perform one authenticated JSON request and return the decoded body, raising GitHub's own message."""
    body = json.dumps(payload).encode() if payload is not None else None
    request = urllib.request.Request(url, data=body, method=method)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Content-Type", "application/json")
    request.add_header("User-Agent", "greecomfort-merge-readiness")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read()
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")
        raise RuntimeError(f"GitHub answered {exc.code} for {method} {url}: {detail}") from exc


def formatPullRequestRef(number: int) -> str:
    """Return a pull request reference in the house form."""
    return f"PR #{number}"
