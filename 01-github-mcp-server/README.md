# GitHub MCP Server

A compact, portfolio-quality **Model Context Protocol (MCP) server** that lets an AI agent search GitHub repositories, inspect repository metadata, list issues, and read a repository's README — all through the official GitHub REST API. Project 1 of an MCP portfolio, built with the **MCP Python SDK v2**.

> Runs entirely on the free tier: no OpenAI/Anthropic/Gemini API key needed, no Docker, no database. Just Python + the GitHub REST API.

---

## Quick Start (Google Colab)

Paste this into a Colab cell to set everything up:

```python
!pip install -q "mcp[cli]" requests pytest
```

Then create the project files (copy each file below into its own Colab cell using `%%writefile`, for example):

```python
%%writefile server.py
# ... paste the contents of server.py here ...
```

Repeat for `client_demo.py`, `tests/test_server.py` (create the `tests/` folder first with `!mkdir -p tests`), `requirements.txt`, `.env.example`, and `.gitignore`.

Once the files exist, run the client demo directly in the notebook:

```python
!python client_demo.py
```

And run the tests:

```python
!pytest -q
```

No GitHub token, no Docker, and no persistent server process are required for any of this — everything above runs to completion and exits.

---

## 1. Overview

This project is a **GitHub MCP Server**: an MCP server that exposes GitHub repository data (search results, repository metadata, issues, and READMEs) to any MCP-compatible client or AI agent through three tools, one resource, and one prompt. It demonstrates how MCP separates "giving an AI agent access to real-world data" from "the AI model itself" — the server knows nothing about Claude, OpenAI, or Gemini; it just speaks MCP.

## 2. What is MCP?

The **Model Context Protocol (MCP)** is an open standard for connecting AI applications to external tools and data sources — think of it as "a web API, but designed for LLMs." An MCP **server** exposes capabilities (tools, resources, prompts); an MCP **client** (embedded in an AI application, or a script like `client_demo.py` in this repo) discovers and calls those capabilities over a standardized protocol, without either side needing to know the other's internal implementation.

## 3. Architecture

```text
AI Agent / MCP Client
        |
        | MCP (in-process, stdio, or HTTP)
        v
GitHub MCP Server (server.py)
   |            |            |
 Tools       Resource      Prompt
   |            |            |
   +------------+------------+
                |
           GitHub REST API
        (api.github.com)
```

- **Tools** (`search_repositories`, `get_repository`, `list_issues`) — model-controlled actions that call the GitHub REST API.
- **Resource** (`github://repo/{owner}/{repo}/readme`) — application-controlled data: a repository's README, decoded to plain text.
- **Prompt** (`repository_research_prompt`) — a reusable, user-controlled template that instructs an agent how to research a repository using the tools and resource above.

## 4. Features

| Capability | Name | Description |
|---|---|---|
| Tool | `search_repositories` | Search GitHub repositories by query string. Returns `full_name`, `description`, `stars`, `language`, `html_url` for each match. |
| Tool | `get_repository` | Get metadata for one repository: `name`, `full_name`, `description`, `stars`, `forks`, `language`, `default_branch`, `html_url`. |
| Tool | `list_issues` | List a repository's issues (`open`, `closed`, or `all`), returning `number`, `title`, `state`, `author`, `html_url`, `created_at`. Pull requests are filtered out. |
| Resource | `github://repo/{owner}/{repo}/readme` | Fetches and base64-decodes a repository's README via the GitHub Contents API. Errors are handled inline and returned as readable text rather than raised as protocol errors. |
| Prompt | `repository_research_prompt` | Given `owner`, `repo`, and a `research_question`, produces step-by-step instructions telling an agent which tools/resource to call, in what order, to answer the question. |

## 5. Project Structure

```text
github-mcp-server/
│
├── server.py
├── client_demo.py
├── requirements.txt
├── .env.example
├── .gitignore
├── README.md
│
└── tests/
    └── test_server.py
```

## 6. Technologies

- Python 3.10+
- [MCP Python SDK v2](https://github.com/modelcontextprotocol/python-sdk) (`mcp.server.MCPServer`, `mcp.Client`)
- GitHub REST API
- `requests`
- `pytest`
- Google Colab (for running/testing)

## 7. Installation

```bash
pip install -q "mcp[cli]" requests pytest
```

Or, from `requirements.txt`:

```bash
pip install -r requirements.txt
```

## 8. Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `GITHUB_TOKEN` | No | A GitHub [personal access token](https://github.com/settings/tokens). If set, requests are authenticated, raising the GitHub API rate limit from 60/hour (unauthenticated) to 5,000/hour. Without it, everything still works — you'll just hit rate limits sooner if you make many requests. |

Copy `.env.example` to `.env` and fill in your token if you have one:

```bash
cp .env.example .env
```

The server reads it with `os.getenv("GITHUB_TOKEN")` — no `python-dotenv` dependency is used; export the variable in your shell (or in Colab, `os.environ["GITHUB_TOKEN"] = "..."`) before running.

**The code never contains a real token.** `.env` is git-ignored.

## 9. Run Client Demo

```bash
python client_demo.py
```

This connects an MCP client directly to the in-process server (no subprocess, no HTTP transport) and demonstrates: tool discovery, `search_repositories`, `get_repository`, `list_issues`, reading the README resource, and generating a `repository_research_prompt`. It requires no AI API key — it's a plain MCP protocol demonstration, not an LLM-powered agent.

## 10. Run Tests

```bash
pytest -q
```

All GitHub HTTP calls are mocked (`unittest.mock.patch` on `server.requests.get`), so the test suite is deterministic, runs offline, and never requires `GITHUB_TOKEN`.

## 11. MCP Inspector

For interactive, visual exploration of the server during development, use the official MCP Inspector via the SDK's CLI:

```bash
mcp dev server.py
```

This starts the server and opens the MCP Inspector UI, where you can call tools, read resources, and fetch prompts by hand. The Inspector is a development convenience only — it is **not required** to run or test the project; `client_demo.py` and `pytest` work independently of it.

## 12. Example Workflows

Once connected via an MCP client (or through the Inspector), you can ask an agent things like:

```text
"Search for Python MCP repositories."
"Get repository information for modelcontextprotocol/python-sdk."
"Show open issues for modelcontextprotocol/python-sdk."
"Read the repository README for modelcontextprotocol/python-sdk."
"Research the FastAPI repository: what problem does it solve, what are its
 major features, and what's currently being tracked in its open issues?"
```

## 13. MCP Concepts Demonstrated

- **MCP Server** — `server.py` builds an `MCPServer` instance and registers tools, a resource, and a prompt on it.
- **MCP Client** — `client_demo.py` and `tests/test_server.py` connect via `mcp.Client`, using the in-memory transport (no subprocess or network socket needed to talk to the server object itself).
- **Tools** — model-controlled actions with typed inputs/outputs (`search_repositories`, `get_repository`, `list_issues`).
- **Resources** — application-controlled, URI-addressed data (`github://repo/{owner}/{repo}/readme`).
- **Prompts** — reusable, user-invoked templates (`repository_research_prompt`).
- **Structured output** — tools return `TypedDict` shapes, so results arrive as validated, structured JSON (`result.structured_content`) in addition to human-readable text.
- **Error handling** — input validation and GitHub API failures (404, 403/rate limit, timeouts, connection errors, malformed responses) are all converted into clear `ValueError` messages, which the MCP framework surfaces as `is_error=True` tool results instead of raw stack traces.

## 14. Security

- **Never commit tokens.** `.env` is listed in `.gitignore`; `.env.example` ships with an empty value.
- **Use environment variables** (`GITHUB_TOKEN`) for credentials — never hardcode them in source.
- **Least privilege.** If you create a GitHub token for this project, scope it to the minimum needed (for public repo read access, a token with no scopes, or `public_repo` only, is sufficient).
- **Rate limits are respected**, not bypassed: the server surfaces GitHub's 403 rate-limit responses as clear errors rather than retrying aggressively or silently failing.
- **Input validation** bounds every user-controlled parameter (`limit` clamped to 1–20, `state` restricted to an allow-list, `owner`/`repo`/`query` required to be non-empty) before any network call is made.

## 15. Limitations

- Read-only: this server only reads GitHub data. It cannot create issues, open pull requests, or write to repositories.
- Unauthenticated requests are capped at 60/hour by GitHub; heavy use requires `GITHUB_TOKEN`.
- `search_repositories` uses GitHub's repository *search* endpoint, which has its own (lower) rate limit than other REST endpoints.
- The README resource assumes UTF-8 text content; binary or non-UTF-8 READMEs are decoded with `errors="replace"` rather than rejected outright.
- No pagination beyond a single page (`limit`, capped at 20) is implemented for search results or issue lists.

## 16. Future Improvements

Not implemented here, but natural next steps for this portfolio project:

- Pagination across multiple pages of results
- Support for GitHub organizations (not just single repos)
- Pull request tools (currently `list_issues` explicitly filters PRs out)
- Commit history tools
- Additional repository search filters (topics, license, pushed-date, etc.)
- Response caching to reduce API calls
- More advanced authentication (GitHub Apps, OAuth device flow)
- Streamable HTTP deployment (this server currently runs over stdio / in-memory transport; MCP v2 also supports Streamable HTTP for networked deployments)

## 17. Portfolio Value

This project demonstrates:

- Building a real MCP server from scratch with the current MCP Python SDK v2, including tools, a resource, and a prompt.
- Integrating a third-party REST API (GitHub) with proper authentication handling, timeouts, and graceful error handling (404s, rate limits, network failures).
- Writing deterministic, mocked unit tests for an MCP server using the MCP `Client` against an in-process server object — no live network dependency in CI.
- Structuring a small backend project (input validation, typed structured output, clear error messages) to a standard suitable for a public GitHub repository.

It does **not** claim to be a production deployment — there's no auth server, no persistence layer, and no HTTP hosting configured. It's a focused, honest demonstration of MCP server engineering fundamentals.
