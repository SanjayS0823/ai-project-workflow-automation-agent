"""GitHub integration: create issues from tasks.

Strictly user-triggered — issues are never created automatically during AI
plan generation. Requires two environment variables:

- ``GITHUB_TOKEN`` — a personal access token with ``repo`` scope
- ``GITHUB_REPO`` — the sandbox/test repository, e.g. ``zeneralabs/sandbox``

Uses only the Python standard library (``urllib``).
"""

import json
import os
import urllib.error
import urllib.request
from typing import List

DEFAULT_API_BASE_URL = "https://api.github.com"


class GitHubIntegrationError(Exception):
    """Base error for the GitHub integration."""


class GitHubNotConfiguredError(GitHubIntegrationError):
    """Raised when GITHUB_TOKEN / GITHUB_REPO are not configured."""


def _api_base_url() -> str:
    return os.getenv("GITHUB_API_BASE_URL", DEFAULT_API_BASE_URL)


def _issue_body(task) -> str:
    """Build the GitHub issue body from a task."""
    lines: List[str] = []
    if task.project:
        lines.append(f"**Project:** {task.project.name}")
    if task.description:
        if lines:
            lines.append("")
        lines.append(task.description)

    context: List[str] = []
    if task.module:
        context.append(f"**Module:** {task.module.name}")
    if task.requirement:
        context.append(f"**Requirement:** {task.requirement.title}")
    if context:
        if lines:
            lines.append("")
        lines.append("  ·  ".join(context))

    if task.acceptance_criteria:
        if lines:
            lines.append("")
        lines.append("**Acceptance criteria:**")
        for criterion in task.acceptance_criteria:
            lines.append(f"- [ ] {criterion.criterion}")

    lines.append("")
    lines.append(
        "_Created from the AI project plan by the Zenera AI Project & "
        "Workflow Automation Agent._"
    )
    return "\n".join(lines)


def _post_issue(owner_repo: str, token: str, title: str, body: str) -> str:
    """Create an issue via the GitHub REST API and return its html_url.

    Separated from the public function so tests can replace it without
    touching the network.
    """
    url = f"{_api_base_url()}/repos/{owner_repo}/issues"
    payload = json.dumps({"title": title, "body": body}).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=payload,
        method="POST",
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type": "application/json",
            "User-Agent": "zenera-ai-planner",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (urllib.error.HTTPError, urllib.error.URLError, OSError) as exc:
        raise GitHubIntegrationError(f"GitHub request failed: {exc}") from exc

    issue_url = result.get("html_url")
    if not isinstance(issue_url, str) or not issue_url:
        raise GitHubIntegrationError(
            "GitHub response did not include an issue URL."
        )
    return issue_url


def create_issue_for_task(task) -> str:
    """Create a GitHub issue for a task (or return its existing issue URL).

    Idempotent: if the task already has an issue URL, it is returned without
    calling the GitHub API again.
    """
    if task.github_issue_url:
        return task.github_issue_url

    token = os.getenv("GITHUB_TOKEN")
    owner_repo = os.getenv("GITHUB_REPO")
    if not token or not owner_repo:
        raise GitHubNotConfiguredError(
            "GitHub integration is not configured. Set GITHUB_TOKEN and "
            "GITHUB_REPO to use it."
        )

    return _post_issue(owner_repo, token, task.title, _issue_body(task))
