"""GitHub MCP Server.

Exposes three tools (search_repositories, get_repository, list_issues),
one resource (github://repo/{owner}/{repo}/readme), and one prompt
(repository_research_prompt) that let an MCP client explore public GitHub
repositories through the GitHub REST API.

Built with the MCP Python SDK v2 (mcp.server.MCPServer).

Run directly (stdio transport, for Claude Desktop / MCP-compatible clients):
    python server.py

Inspect during development:
    mcp dev server.py
"""

from __future__ import annotations

import base64
import os
from typing import Any, TypedDict

import requests

from mcp.server import MCPServer

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPServer(
    "GitHub MCP Server",
    instructions=(
        "Tools for searching GitHub repositories, reading repository "
        "metadata, listing issues, and reading a repository's README. "
        "Works without authentication, but honors GITHUB_TOKEN if set."
    ),
)

GITHUB_API_BASE = "https://api.github.com"
REQUEST_TIMEOUT_SECONDS = 10
DEFAULT_LIMIT = 5
MIN_LIMIT = 1
MAX_LIMIT = 20
VALID_ISSUE_STATES = ("open", "closed", "all")


# ---------------------------------------------------------------------------
# Structured output shapes
# ---------------------------------------------------------------------------


class RepositorySummary(TypedDict):
    full_name: str
    description: str | None
    stars: int
    language: str | None
    html_url: str


class SearchRepositoriesResult(TypedDict):
    query: str
    count: int
    repositories: list[RepositorySummary]


class RepositoryInfo(TypedDict):
    name: str
    full_name: str
    description: str | None
    stars: int
    forks: int
    language: str | None
    default_branch: str
    html_url: str


class IssueSummary(TypedDict):
    number: int
    title: str
    state: str
    author: str | None
    html_url: str
    created_at: str


class ListIssuesResult(TypedDict):
    owner: str
    repo: str
    state: str
    count: int
    issues: list[IssueSummary]


# ---------------------------------------------------------------------------
# GitHub REST API helper
# ---------------------------------------------------------------------------


def _github_headers() -> dict[str, str]:
    """Build the standard GitHub REST API headers, adding auth if available."""
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "github-mcp-server-portfolio-project",
    }
    token = os.getenv("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def _github_request(path: str, params: dict[str, Any] | None = None) -> Any:
    """Call the GitHub REST API and return the decoded JSON body.

    Raises ValueError with a clear, user-facing message on any failure
    (network error, timeout, rate limit, 404, malformed response, etc).
    Never leaks a raw stack trace to the caller.
    """
    url = f"{GITHUB_API_BASE}{path}"
    try:
        response = requests.get(
            url,
            headers=_github_headers(),
            params=params,
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
    except requests.exceptions.Timeout as exc:
        raise ValueError(f"GitHub API request to {path} timed out.") from exc
    except requests.exceptions.ConnectionError as exc:
        raise ValueError(f"Could not reach the GitHub API: {exc}") from exc
    except requests.exceptions.RequestException as exc:
        raise ValueError(f"GitHub API request failed: {exc}") from exc

    if response.status_code == 404:
        raise ValueError(f"GitHub resource not found for path '{path}'.")

    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining == "0":
            raise ValueError(
                "GitHub API rate limit exceeded. Set the GITHUB_TOKEN "
                "environment variable to raise the limit, or try again later."
            )
        raise ValueError(f"GitHub API returned 403 Forbidden for path '{path}'.")

    if response.status_code == 422:
        raise ValueError(
            f"GitHub API rejected the request to '{path}' as invalid "
            f"(422 Unprocessable Entity). Check your input."
        )

    if not response.ok:
        raise ValueError(
            f"GitHub API request to '{path}' failed with status "
            f"{response.status_code}."
        )

    try:
        return response.json()
    except ValueError as exc:
        raise ValueError(f"GitHub API returned a malformed response for '{path}'.") from exc


# ---------------------------------------------------------------------------
# Input validation helpers
# ---------------------------------------------------------------------------


def _validate_limit(limit: int) -> int:
    if not isinstance(limit, int) or isinstance(limit, bool):
        raise ValueError("limit must be an integer.")
    if limit < MIN_LIMIT or limit > MAX_LIMIT:
        raise ValueError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}.")
    return limit


def _validate_non_empty(value: str, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must not be empty.")
    return value.strip()


def _validate_issue_state(state: str) -> str:
    if state not in VALID_ISSUE_STATES:
        raise ValueError(
            f"state must be one of {VALID_ISSUE_STATES}, got '{state}'."
        )
    return state


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def search_repositories(query: str, limit: int = DEFAULT_LIMIT) -> SearchRepositoriesResult:
    """Search GitHub repositories using the GitHub Search API.

    Args:
        query: GitHub search query, e.g. "modelcontextprotocol language:python".
        limit: Maximum number of repositories to return (1-20).
    """
    query = _validate_non_empty(query, "query")
    limit = _validate_limit(limit)

    data = _github_request(
        "/search/repositories",
        params={"q": query, "per_page": limit, "sort": "stars", "order": "desc"},
    )

    items = data.get("items", []) if isinstance(data, dict) else []
    repositories: list[RepositorySummary] = [
        RepositorySummary(
            full_name=item.get("full_name", ""),
            description=item.get("description"),
            stars=item.get("stargazers_count", 0),
            language=item.get("language"),
            html_url=item.get("html_url", ""),
        )
        for item in items[:limit]
    ]

    return SearchRepositoriesResult(
        query=query,
        count=len(repositories),
        repositories=repositories,
    )


@mcp.tool()
def get_repository(owner: str, repo: str) -> RepositoryInfo:
    """Get metadata about a single GitHub repository.

    Args:
        owner: Repository owner (user or organization login).
        repo: Repository name.
    """
    owner = _validate_non_empty(owner, "owner")
    repo = _validate_non_empty(repo, "repo")

    data = _github_request(f"/repos/{owner}/{repo}")

    return RepositoryInfo(
        name=data.get("name", ""),
        full_name=data.get("full_name", ""),
        description=data.get("description"),
        stars=data.get("stargazers_count", 0),
        forks=data.get("forks_count", 0),
        language=data.get("language"),
        default_branch=data.get("default_branch", ""),
        html_url=data.get("html_url", ""),
    )


@mcp.tool()
def list_issues(
    owner: str,
    repo: str,
    state: str = "open",
    limit: int = DEFAULT_LIMIT,
) -> ListIssuesResult:
    """List issues for a GitHub repository.

    Args:
        owner: Repository owner (user or organization login).
        repo: Repository name.
        state: One of "open", "closed", "all".
        limit: Maximum number of issues to return (1-20).
    """
    owner = _validate_non_empty(owner, "owner")
    repo = _validate_non_empty(repo, "repo")
    state = _validate_issue_state(state)
    limit = _validate_limit(limit)

    data = _github_request(
        f"/repos/{owner}/{repo}/issues",
        params={"state": state, "per_page": limit},
    )

    if not isinstance(data, list):
        raise ValueError(f"Unexpected response listing issues for {owner}/{repo}.")

    # The GitHub issues endpoint also returns pull requests; skip those to
    # keep results focused on actual issues.
    issues: list[IssueSummary] = []
    for item in data:
        if "pull_request" in item:
            continue
        user = item.get("user") or {}
        issues.append(
            IssueSummary(
                number=item.get("number", 0),
                title=item.get("title", ""),
                state=item.get("state", ""),
                author=user.get("login"),
                html_url=item.get("html_url", ""),
                created_at=item.get("created_at", ""),
            )
        )
        if len(issues) >= limit:
            break

    return ListIssuesResult(
        owner=owner,
        repo=repo,
        state=state,
        count=len(issues),
        issues=issues,
    )


# ---------------------------------------------------------------------------
# Resource: github://repo/{owner}/{repo}/readme
# ---------------------------------------------------------------------------


@mcp.resource(
    "github://repo/{owner}/{repo}/readme",
    description="The README of a GitHub repository, decoded to plain text.",
    mime_type="text/plain",
)
def repository_readme(owner: str, repo: str) -> str:
    """Fetch and decode a repository's README via the GitHub Contents API."""
    try:
        owner = _validate_non_empty(owner, "owner")
        repo = _validate_non_empty(repo, "repo")
        data = _github_request(f"/repos/{owner}/{repo}/readme")
    except ValueError as exc:
        # Handled cleanly so the resource is always readable, even on error.
        return f"Could not load README for {owner}/{repo}: {exc}"

    encoded_content = data.get("content", "") if isinstance(data, dict) else ""
    encoding = data.get("encoding", "base64") if isinstance(data, dict) else "base64"

    if not encoded_content:
        return f"No README content found for {owner}/{repo}."

    if encoding != "base64":
        return f"Unsupported README encoding '{encoding}' for {owner}/{repo}."

    try:
        decoded_bytes = base64.b64decode(encoded_content)
        return decoded_bytes.decode("utf-8", errors="replace")
    except (ValueError, UnicodeDecodeError) as exc:
        return f"Could not decode README for {owner}/{repo}: {exc}"


# ---------------------------------------------------------------------------
# Prompt: repository_research_prompt
# ---------------------------------------------------------------------------


@mcp.prompt()
def repository_research_prompt(owner: str, repo: str, research_question: str) -> str:
    """Build a research instruction for investigating a GitHub repository.

    Args:
        owner: Repository owner (user or organization login).
        repo: Repository name.
        research_question: What the agent should find out about the repository.
    """
    return (
        f"You are researching the GitHub repository {owner}/{repo}.\n\n"
        f"Research question: {research_question}\n\n"
        "Use the available GitHub MCP tools and resource to investigate:\n"
        f"1. Call get_repository(owner=\"{owner}\", repo=\"{repo}\") to learn "
        "its description, primary language, stars, forks, and default branch.\n"
        f"2. Read the resource github://repo/{owner}/{repo}/readme to understand "
        "what problem the project solves, its major features, and its "
        "architecture.\n"
        f"3. Call list_issues(owner=\"{owner}\", repo=\"{repo}\", state=\"open\") "
        "to see what active problems or requests the maintainers are "
        "currently tracking.\n"
        f"4. Optionally call search_repositories to find related or "
        "competing projects for context.\n\n"
        "Then answer the research question using only information gathered "
        "from these tools and the resource, citing what each tool or "
        "resource call revealed."
    )


if __name__ == "__main__":
    mcp.run()
