"""GitHub MCP Server - client demo.

Connects an MCP client directly to the in-process GitHub MCP server (no
subprocess, no HTTP transport needed) and demonstrates every capability the
server exposes:

    A. Tool discovery
    B. search_repositories
    C. get_repository
    D. list_issues
    E. the github://repo/{owner}/{repo}/readme resource
    F. the repository_research_prompt prompt

This does NOT require any AI API (no Claude/OpenAI/Gemini key). It talks to
the live GitHub REST API, so results depend on network access and GitHub's
unauthenticated rate limit (60 requests/hour per IP). Set GITHUB_TOKEN in
your environment for a much higher limit.

Run:
    python client_demo.py
"""

from __future__ import annotations

import asyncio
import textwrap

from mcp import Client

from server import mcp

# A stable, well-known public repository used throughout the demo.
DEMO_OWNER = "modelcontextprotocol"
DEMO_REPO = "python-sdk"


def _print_header(title: str) -> None:
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)


def _print_error_safe(label: str, exc: Exception) -> None:
    print(f"  [!] {label} failed: {exc}")


async def demo_tool_discovery(client: Client) -> None:
    _print_header("A. Tool discovery")
    result = await client.list_tools()
    for tool in result.tools:
        print(f"  - {tool.name}: {tool.description}")


async def demo_search_repositories(client: Client) -> None:
    _print_header("B. search_repositories")
    result = await client.call_tool(
        "search_repositories",
        {"query": "modelcontextprotocol language:python", "limit": 5},
    )
    if result.is_error:
        _print_error_safe("search_repositories", RuntimeError(result.content[0].text))
        return
    data = result.structured_content
    print(f"  Query: {data['query']}  (showing {data['count']} results)")
    for repo in data["repositories"]:
        print(f"  - {repo['full_name']} ({repo['stars']} stars, {repo['language']})")
        print(f"    {repo['html_url']}")


async def demo_get_repository(client: Client) -> None:
    _print_header("C. get_repository")
    result = await client.call_tool(
        "get_repository", {"owner": DEMO_OWNER, "repo": DEMO_REPO}
    )
    if result.is_error:
        _print_error_safe("get_repository", RuntimeError(result.content[0].text))
        return
    data = result.structured_content
    print(f"  {data['full_name']}")
    print(f"  Description: {data['description']}")
    print(f"  Stars: {data['stars']}  Forks: {data['forks']}  Language: {data['language']}")
    print(f"  Default branch: {data['default_branch']}")
    print(f"  URL: {data['html_url']}")


async def demo_list_issues(client: Client) -> None:
    _print_header("D. list_issues")
    result = await client.call_tool(
        "list_issues",
        {"owner": DEMO_OWNER, "repo": DEMO_REPO, "state": "open", "limit": 5},
    )
    if result.is_error:
        _print_error_safe("list_issues", RuntimeError(result.content[0].text))
        return
    data = result.structured_content
    print(f"  {data['owner']}/{data['repo']} - {data['count']} {data['state']} issue(s) shown")
    for issue in data["issues"]:
        print(f"  - #{issue['number']} {issue['title']} (by {issue['author']})")
        print(f"    {issue['html_url']}")


async def demo_readme_resource(client: Client) -> None:
    _print_header("E. github://repo/{owner}/{repo}/readme resource")
    uri = f"github://repo/{DEMO_OWNER}/{DEMO_REPO}/readme"
    result = await client.read_resource(uri)
    text = result.contents[0].text
    preview = textwrap.shorten(text.replace("\n", " "), width=300, placeholder=" ...")
    print(f"  URI: {uri}")
    print(f"  Preview: {preview}")


async def demo_research_prompt(client: Client) -> None:
    _print_header("F. repository_research_prompt")
    result = await client.get_prompt(
        "repository_research_prompt",
        {
            "owner": DEMO_OWNER,
            "repo": DEMO_REPO,
            "research_question": (
                "What problem does this repository solve and what are its "
                "major features?"
            ),
        },
    )
    for message in result.messages:
        print(f"  [{message.role}]")
        print(textwrap.indent(message.content.text, "    "))


async def main() -> None:
    print("GitHub MCP Server - Client Demo")
    print(f"Target repository for the demo: {DEMO_OWNER}/{DEMO_REPO}")

    async with Client(mcp) as client:
        await demo_tool_discovery(client)
        await demo_search_repositories(client)
        await demo_get_repository(client)
        await demo_list_issues(client)
        await demo_readme_resource(client)
        await demo_research_prompt(client)

    print("\nDone.")


if __name__ == "__main__":
    asyncio.run(main())
