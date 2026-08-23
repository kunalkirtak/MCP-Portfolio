"""Tests for the GitHub MCP Server.

All GitHub HTTP calls are mocked via unittest.mock.patch on
`server.requests.get`, so these tests are deterministic, never touch the
network, and never require a GITHUB_TOKEN.

These tests use the MCP Client against the real in-memory server object
(no subprocess, no transport). Each async test is a plain `def` that wraps
its body with `asyncio.run(...)`, so no extra test-runner plugin
(e.g. pytest-asyncio) is required - only mcp[cli], requests, and pytest,
per the project's minimal dependency policy.

Run:
    pytest -q
"""

from __future__ import annotations

import asyncio
import base64
from unittest.mock import MagicMock, patch

import pytest

from mcp import Client

from server import mcp


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_async(coro):
    """Run an async test body to completion (no pytest-asyncio needed)."""
    return asyncio.run(coro)


def _fake_response(status_code: int, json_body=None, headers=None, ok=None):
    """Build a MagicMock that behaves like a `requests.Response`."""
    response = MagicMock()
    response.status_code = status_code
    response.ok = ok if ok is not None else 200 <= status_code < 300
    response.headers = headers or {}
    if json_body is not None:
        response.json.return_value = json_body
    else:
        response.json.side_effect = ValueError("no JSON body")
    return response


def _readme_json(text: str) -> dict:
    return {
        "content": base64.b64encode(text.encode("utf-8")).decode("ascii"),
        "encoding": "base64",
    }


# ---------------------------------------------------------------------------
# 1. Server starts / imports
# ---------------------------------------------------------------------------


def test_server_imports_and_has_a_name():
    assert mcp is not None
    assert mcp.name == "GitHub MCP Server"


# ---------------------------------------------------------------------------
# 2. Tool discovery
# ---------------------------------------------------------------------------


def test_tool_discovery_lists_expected_tools():
    async def scenario():
        async with Client(mcp) as client:
            result = await client.list_tools()
            return {tool.name for tool in result.tools}

    names = run_async(scenario())
    assert names == {"search_repositories", "get_repository", "list_issues"}


# ---------------------------------------------------------------------------
# 3. search_repositories
# ---------------------------------------------------------------------------


def test_search_repositories_returns_structured_results():
    fake_items = {
        "items": [
            {
                "full_name": "octocat/hello-world",
                "description": "A test repo",
                "stargazers_count": 42,
                "language": "Python",
                "html_url": "https://github.com/octocat/hello-world",
            }
        ]
    }

    async def scenario():
        with patch("server.requests.get", return_value=_fake_response(200, fake_items)):
            async with Client(mcp) as client:
                return await client.call_tool(
                    "search_repositories", {"query": "hello world", "limit": 5}
                )

    result = run_async(scenario())
    assert result.is_error is False
    data = result.structured_content
    assert data["query"] == "hello world"
    assert data["count"] == 1
    assert data["repositories"][0]["full_name"] == "octocat/hello-world"
    assert data["repositories"][0]["stars"] == 42


# ---------------------------------------------------------------------------
# 4. get_repository
# ---------------------------------------------------------------------------


def test_get_repository_returns_structured_metadata():
    fake_repo = {
        "name": "hello-world",
        "full_name": "octocat/hello-world",
        "description": "A test repo",
        "stargazers_count": 42,
        "forks_count": 7,
        "language": "Python",
        "default_branch": "main",
        "html_url": "https://github.com/octocat/hello-world",
    }

    async def scenario():
        with patch("server.requests.get", return_value=_fake_response(200, fake_repo)):
            async with Client(mcp) as client:
                return await client.call_tool(
                    "get_repository", {"owner": "octocat", "repo": "hello-world"}
                )

    result = run_async(scenario())
    assert result.is_error is False
    data = result.structured_content
    assert data["full_name"] == "octocat/hello-world"
    assert data["forks"] == 7
    assert data["default_branch"] == "main"


# ---------------------------------------------------------------------------
# 5. list_issues
# ---------------------------------------------------------------------------


def test_list_issues_filters_out_pull_requests():
    fake_issues = [
        {
            "number": 1,
            "title": "Real issue",
            "state": "open",
            "user": {"login": "alice"},
            "html_url": "https://github.com/octocat/hello-world/issues/1",
            "created_at": "2026-01-01T00:00:00Z",
        },
        {
            "number": 2,
            "title": "This is actually a PR",
            "state": "open",
            "user": {"login": "bob"},
            "html_url": "https://github.com/octocat/hello-world/pull/2",
            "created_at": "2026-01-02T00:00:00Z",
            "pull_request": {"url": "https://api.github.com/..."},
        },
    ]

    async def scenario():
        with patch("server.requests.get", return_value=_fake_response(200, fake_issues)):
            async with Client(mcp) as client:
                return await client.call_tool(
                    "list_issues",
                    {"owner": "octocat", "repo": "hello-world", "state": "open", "limit": 5},
                )

    result = run_async(scenario())
    assert result.is_error is False
    data = result.structured_content
    assert data["count"] == 1
    assert data["issues"][0]["number"] == 1
    assert data["issues"][0]["author"] == "alice"


# ---------------------------------------------------------------------------
# 6. README resource
# ---------------------------------------------------------------------------


def test_readme_resource_decodes_base64_content():
    async def scenario():
        with patch(
            "server.requests.get",
            return_value=_fake_response(200, _readme_json("# Hello\n\nWorld.")),
        ):
            async with Client(mcp) as client:
                return await client.read_resource(
                    "github://repo/octocat/hello-world/readme"
                )

    result = run_async(scenario())
    text = result.contents[0].text
    assert text == "# Hello\n\nWorld."


def test_readme_resource_handles_missing_readme_cleanly():
    async def scenario():
        with patch(
            "server.requests.get",
            return_value=_fake_response(404, {"message": "Not Found"}),
        ):
            async with Client(mcp) as client:
                return await client.read_resource(
                    "github://repo/octocat/does-not-exist/readme"
                )

    result = run_async(scenario())
    text = result.contents[0].text
    assert "Could not load README" in text


# ---------------------------------------------------------------------------
# 7. Repository research prompt
# ---------------------------------------------------------------------------


def test_repository_research_prompt_includes_inputs():
    async def scenario():
        async with Client(mcp) as client:
            return await client.get_prompt(
                "repository_research_prompt",
                {
                    "owner": "octocat",
                    "repo": "hello-world",
                    "research_question": "What does this repo do?",
                },
            )

    result = run_async(scenario())
    assert len(result.messages) == 1
    text = result.messages[0].content.text
    assert "octocat/hello-world" in text
    assert "What does this repo do?" in text
    assert "get_repository" in text
    assert "list_issues" in text


# ---------------------------------------------------------------------------
# 8. Invalid input
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "arguments",
    [
        {"query": "", "limit": 5},
        {"query": "test", "limit": 0},
        {"query": "test", "limit": 21},
    ],
)
def test_search_repositories_rejects_invalid_input(arguments):
    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool("search_repositories", arguments)

    result = run_async(scenario())
    assert result.is_error is True


def test_list_issues_rejects_invalid_state():
    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool(
                "list_issues",
                {"owner": "octocat", "repo": "hello-world", "state": "bogus"},
            )

    result = run_async(scenario())
    assert result.is_error is True


def test_get_repository_rejects_empty_owner():
    async def scenario():
        async with Client(mcp) as client:
            return await client.call_tool(
                "get_repository", {"owner": "", "repo": "hello-world"}
            )

    result = run_async(scenario())
    assert result.is_error is True


# ---------------------------------------------------------------------------
# 9. GitHub API error handling
# ---------------------------------------------------------------------------


def test_get_repository_handles_404_cleanly():
    async def scenario():
        with patch(
            "server.requests.get",
            return_value=_fake_response(404, {"message": "Not Found"}),
        ):
            async with Client(mcp) as client:
                return await client.call_tool(
                    "get_repository", {"owner": "octocat", "repo": "does-not-exist"}
                )

    result = run_async(scenario())
    assert result.is_error is True
    assert "not found" in result.content[0].text.lower()


def test_search_repositories_handles_rate_limit_cleanly():
    headers = {"X-RateLimit-Remaining": "0"}

    async def scenario():
        with patch(
            "server.requests.get",
            return_value=_fake_response(
                403, {"message": "rate limit exceeded"}, headers=headers
            ),
        ):
            async with Client(mcp) as client:
                return await client.call_tool("search_repositories", {"query": "test"})

    result = run_async(scenario())
    assert result.is_error is True
    assert "rate limit" in result.content[0].text.lower()


def test_get_repository_handles_network_error_cleanly():
    import requests as requests_module

    async def scenario():
        with patch(
            "server.requests.get",
            side_effect=requests_module.exceptions.ConnectionError("boom"),
        ):
            async with Client(mcp) as client:
                return await client.call_tool(
                    "get_repository", {"owner": "octocat", "repo": "hello-world"}
                )

    result = run_async(scenario())
    assert result.is_error is True
    assert "could not reach the github api" in result.content[0].text.lower()
