# MCP Portfolio

A hands-on portfolio of three [Model Context Protocol](https://modelcontextprotocol.io) (MCP) servers, each built from scratch with the **MCP Python SDK v2** to demonstrate a different integration pattern an AI agent needs in the real world: talking to a public REST API, safely querying a relational database, and performing controlled read/write operations on business data.

Every project runs **locally or in Google Colab** with no API keys, no Docker, and no paid services — each one ships with its own MCP server, an in-process client demo, a mocked/offline `pytest` suite, and a Jupyter notebook walkthrough.

## Why this exists

MCP standardizes how an AI agent discovers and calls external tools, resources, and prompts, without the agent or the server needing to know anything about each other's internals. This repo is a deliberate, incremental tour of that idea — starting with pure *reads* against a public API, moving to *safe, parameterized reads* against a database, and finishing with *safe reads and writes* against a CRM — so each project builds on the design lessons of the last.

## Projects

| # | Project | What it shows |
|---|---------|----------------|
| 1 | [`01-github-mcp-server`](./01-github-mcp-server) | Search GitHub repositories, fetch repo metadata, list issues, and read a README — all through the GitHub REST API. Demonstrates tools, a URI-addressed resource, a reusable prompt, and graceful handling of rate limits and API errors. |
| 2 | [`02-database-mcp-server`](./02-database-mcp-server) | Exposes a SQLite e-commerce database (customers, products, orders) through typed, validated tools — no arbitrary SQL execution. Demonstrates least-privilege data access, schema-discovery resources, and an analytics prompt template. |
| 3 | [`03-crm-mcp-server`](./03-crm-mcp-server) | A SQLite-backed CRM (customers + interactions) with search, read, and a small set of explicit write tools. Demonstrates safe *mutation* through a fixed menu of validated actions instead of an open "update anything" endpoint. |

Each project folder is self-contained and has its own detailed README covering architecture, tools/resources/prompts, setup, environment variables, tests, limitations, and possible future improvements.

## Common architecture

Every server in this repo follows the same shape:

```text
AI Agent / MCP Client
        |
        | MCP (in-process / stdio / HTTP)
        v
   MCP Server (server.py)
   /        |          \
 Tools   Resources    Prompts
   \        |          /
        Data Layer
   (GitHub API / SQLite)
```

- **Tools** — model-controlled actions with typed inputs and validated, structured JSON outputs.
- **Resources** — application-controlled, URI-addressable read-only data (e.g. `github://repo/{owner}/{repo}/readme`, `db://schema`).
- **Prompts** — reusable, parameterized instruction templates that guide an agent on how to use the tools/resources — they never call an LLM themselves.
- **Client demo** — a plain MCP `Client`, connected in-process to the server object, that exercises every capability with no LLM or API key involved.
- **Tests** — deterministic and offline: external calls (GitHub HTTP requests, database writes) are mocked or run against a local SQLite file, so the suite never depends on network access or secrets.

## Tech stack

- Python 3.10+
- [MCP Python SDK v2](https://github.com/modelcontextprotocol/python-sdk) (`mcp.server.MCPServer`, `mcp.Client`)
- SQLite (projects 2 and 3)
- `requests` (project 1, for the GitHub REST API)
- `pytest` for offline, mocked test suites
- Jupyter notebooks for an end-to-end runnable walkthrough of each server

## Getting started

Each project can be run independently. General pattern:

```bash
cd 0X-<project-name>
pip install -r requirements.txt

# Run the client demo (no API key required)
python client_demo.py

# Run the tests
pytest -q
```

Some projects seed a local SQLite database first — check that project's README for the exact setup steps (e.g. `seed_database.py` for projects 2 and 3), and for the one optional environment variable used in project 1 (`GITHUB_TOKEN`, to raise GitHub's API rate limit).

For interactive, visual exploration of any server during development, the official MCP Inspector works out of the box:

```bash
mcp dev server.py
```

## Repository structure

```text
MCP-Portfolio/
├── 01-github-mcp-server/     # Public API integration (GitHub REST API)
├── 02-database-mcp-server/   # Safe, parameterized reads (SQLite)
├── 03-crm-mcp-server/        # Safe reads + controlled writes (SQLite CRM)
├── LICENSE
└── README.md
```

## What this portfolio demonstrates

- Building real MCP servers with the current MCP Python SDK v2 — tools, resources, and prompts, not just a toy tool call.
- Integrating an external REST API with proper authentication, timeouts, and error handling.
- Designing tool interfaces that give an agent least-privilege access to sensitive data (no raw SQL execution, no unrestricted "update anything" endpoint).
- Writing deterministic, offline unit tests for MCP servers using the MCP `Client` against an in-process server object.
- Documenting each project to a standard suitable for public review — architecture diagrams, capability tables, environment variables, limitations, and next steps.

These are portfolio-grade demonstrations of MCP server engineering fundamentals, not production deployments — none of them include an auth server, a persistence layer beyond local SQLite, or HTTP hosting configuration.

## License

Released under the [MIT License](./LICENSE).
