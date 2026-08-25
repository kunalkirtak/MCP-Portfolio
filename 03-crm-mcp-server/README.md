# CRM MCP Server

A small, realistic CRM (customers + interactions) exposed to an AI agent
through the **Model Context Protocol (MCP)**. This is **Project 3** in a
three-part MCP portfolio:

1. GitHub MCP Server — read-only research over public GitHub repositories
2. Database MCP Server — safe, structured access to a relational database
3. **CRM MCP Server** (this project) — combines reading business context
   *and* performing controlled business actions

Where Project 2 focused on safe *reading*, this project demonstrates safe
*reading and writing*: an agent can look up customers, understand their
history, and take a small set of explicit, validated actions — without
ever touching raw SQL or an unrestricted "update anything" endpoint.

---

## Overview

The server sits in front of a SQLite-backed CRM with two tables,
`customers` and `interactions`. It exposes:

- **6 tools** — search, read, and a small set of explicit write operations
- **2 resources** — a human-readable customer profile and a schema reference
- **1 prompt** — a template that turns a customer + goal into a structured
  follow-up instruction for an agent (no LLM call inside the server itself)

The whole project runs offline, with no API keys and no paid services, and
is designed to work reliably on the Claude Free tier inside Google Colab.

## Why MCP for CRM?

A CRM is exactly the kind of system where you don't want an AI agent to
have unrestricted access: customer data is sensitive, and a wrong "update"
or "delete" can be costly. MCP gives the agent a fixed menu of typed,
documented tools instead of a database connection. The agent can only do
what the server's tool definitions allow — it can search, read context via
resources, and perform the handful of business actions the server chooses
to expose. Everything else is simply not reachable.

## Architecture

```text
                     AI Agent
                        |
                    MCP Client
                        |
                   MCP Protocol
                        |
                  CRM MCP Server
               /        |        \
            Tools    Resources   Prompts
               \        |        /
                  CRM Database
                        |
                     SQLite
```

## MCP Capabilities

- **MCP Server** (`server.py`) — built on `mcp.server.MCPServer`, exposing
  tools, resources, and a prompt via decorators (`@mcp_server.tool()`,
  `@mcp_server.resource(...)`, `@mcp_server.prompt()`).
- **MCP Client** (`client_demo.py`) — built on `mcp.Client`, connected
  in-process to the server object (no subprocess or network transport
  needed for the demo).
- **Tools** — typed, validated functions the agent can call to search or
  mutate CRM data.
- **Resources** — read-only, URI-addressable context the agent can fetch
  before deciding what to do.
- **Prompts** — reusable instruction templates parameterized by arguments.
- **Structured output** — every tool returns a JSON-serializable dict, so
  responses are easy for an agent (or a test) to parse.

## CRM Schema

### `customers`

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `name` | TEXT | |
| `email` | TEXT | unique |
| `company` | TEXT | |
| `country` | TEXT | |
| `industry` | TEXT | |
| `status` | TEXT | one of `lead`, `prospect`, `customer`, `inactive` |
| `created_at` | TEXT | ISO 8601 timestamp |
| `last_contacted_at` | TEXT | ISO 8601 timestamp, nullable |

### `interactions`

| Field | Type | Notes |
|---|---|---|
| `id` | INTEGER | primary key |
| `customer_id` | INTEGER | foreign key → `customers.id` |
| `interaction_type` | TEXT | one of `email`, `call`, `meeting`, `demo`, `note` |
| `note` | TEXT | max 2000 characters |
| `interaction_date` | TEXT | ISO 8601 timestamp |
| `created_at` | TEXT | ISO 8601 timestamp |

One customer has many interactions. `PRAGMA foreign_keys = ON` is set on
every connection, and interactions cascade-delete with their customer.

## Tools

### `find_customers`
- **Purpose:** search customers by free text and/or filters.
- **Inputs:** `query` (optional str, matches name/email/company/industry),
  `status` (optional str), `company` (optional str), `limit` (int, default 10).
- **Validation:** `1 <= limit <= 20`; `status` must be an allowed value.
- **Output:** `{ count, customers: [...] }`
- **Example:** `find_customers(query="Nimbus")` → the Nimbus Logix account.

### `get_customer`
- **Purpose:** full context for one customer.
- **Inputs:** `customer_id` (positive int).
- **Output:** `{ customer, interaction_count, recent_interactions }`, or
  `{ error }` if the customer does not exist.

### `update_customer_status`
- **Purpose:** the *only* way to change a customer record through this
  server. There is intentionally no generic "update customer fields" tool.
- **Inputs:** `customer_id` (positive int), `status` (must be one of the
  four allowed statuses).
- **Behavior:** validates the customer and status, updates the status, and
  updates `last_contacted_at`.
- **Output:** `{ customer: {...updated...} }`

### `add_interaction`
- **Purpose:** append-only logging of a CRM interaction.
- **Inputs:** `customer_id` (positive int), `interaction_type` (one of the
  five allowed types), `note` (non-empty, ≤ 2000 characters).
- **Behavior:** inserts the interaction and updates `last_contacted_at`.
- **Output:** `{ interaction: {...} }`

### `get_interactions`
- **Purpose:** interaction history for a customer, newest first.
- **Inputs:** `customer_id` (positive int), `limit` (int, default 10, `1..20`).
- **Output:** `{ customer_id, count, interactions: [...] }`

### `customer_pipeline_summary`
- **Purpose:** high-level pipeline snapshot.
- **Inputs:** none.
- **Output:** counts per status, `total_customers`, and a simple
  `conversion_rate` (`customer_count / total_customers`), with an
  explanatory note — this is an overall snapshot, not a cohort or
  time-windowed conversion metric, and no stronger claim is made.

## Resources

- **`crm://schema`** — static, human-readable description of the tables,
  their relationship, and the allowed status/interaction-type values.
- **`crm://customer/{customer_id}`** — a readable profile for one customer
  (name, company, status, last contacted, interaction count, recent
  interactions), meant to give an agent context *before* it calls a write
  tool. Handles a missing customer with a clean message rather than an
  exception.

## Prompt

- **`sales_followup_prompt(customer_id, goal)`** — produces a structured
  instruction telling the agent to: retrieve customer context, inspect
  recent interactions, re-read the stated goal, decide what's relevant,
  draft a follow-up, and avoid inventing facts not present in the CRM
  data. The server does **not** call an LLM — it only generates the
  instruction text for an agent to act on.

## Agent Safety

This project is built around one central design decision: **the agent
never gets direct database access.**

Explicitly **not** exposed:
- `execute_sql` / `raw_sql`
- `update_customer_anything` (a generic field-update tool)
- `delete_customer` / `delete_all`

Instead, every mutation is one of exactly two narrow, named operations —
`update_customer_status` and `add_interaction` — each with its own
validation. If a future need arises (e.g. updating a customer's email),
it should be added as its own explicit, validated tool, not by loosening
an existing one.

```text
AI Agent
   |
   | structured MCP tool call
   v
Validation
   |
   v
Explicit CRM Operation
   |
   v
Parameterized SQL
   |
   v
SQLite
```

All SQL in `database.py` is parameterized (`cursor.execute(sql, params)`);
no user-supplied value is ever concatenated into a query string.

## Installation

```bash
git clone <this-repo-url>
cd crm-mcp-server
pip install -r requirements.txt
```

## Google Colab

```python
# 1. Install dependencies
!pip install -q "mcp[cli]" pytest

# 2. Create the project directory
!mkdir -p crm-mcp-server/tests
%cd crm-mcp-server

# 3. Create the files
# (paste the contents of database.py, seed_database.py, server.py,
#  client_demo.py, tests/test_server.py, requirements.txt, .gitignore
#  into files with those exact names and paths)

# 4. Seed the database
!python seed_database.py

# 5. Run the tests
!pytest -q

# 6. Run the client demo
!python client_demo.py

# 7. (Optional) Inspect the server with MCP Inspector — see below.
# Inspector needs a local Node.js/npx environment; it will not run
# inside a hosted Colab session, so this step is best done locally.
```

## Local Usage

```bash
python seed_database.py   # creates crm.db and seeds it (idempotent)
pytest -q                 # run the test suite
python client_demo.py     # walk through every tool, resource, and prompt
```

## Tests

```bash
pytest -q
```

The suite uses a temporary SQLite database per test run (via the
`CRM_DB_PATH` environment variable), so it never touches `crm.db` and
never requires network access. Async MCP calls use `anyio`'s pytest
plugin, which ships as a dependency of the `mcp` package — no extra test
dependency beyond `requirements.txt` is needed.

## MCP Inspector

The official MCP Inspector can be launched with the `mcp` CLI that ships
with `mcp[cli]`:

```bash
mcp dev server.py:mcp_server
```

This opens a local web UI where you can browse and call:
- tools (with their input schemas)
- resources (static and templated)
- prompts
- and inspect raw tool-call requests/responses

Inspector is a development convenience only — the project runs and is
fully tested without it.

## Example Agent Workflows

```text
"Find all prospects at Acme."
"Show me the interaction history for customer 1."
"Move customer 1 from lead to prospect."
"Record that customer 1 requested a product demo."
"What does our current CRM pipeline look like?"
"Prepare a follow-up plan after the customer's demo."
```

## Project Structure

```text
crm-mcp-server/
│
├── server.py
├── client_demo.py
├── database.py
├── seed_database.py
├── requirements.txt
├── .gitignore
├── README.md
│
└── tests/
    └── test_server.py
```

## Security Considerations

- **Explicit operations only** — two narrow write tools, no generic update.
- **Parameterized SQL** everywhere; no string concatenation of user input.
- **Input validation** on every tool: ID types, allowed statuses, allowed
  interaction types, note length, and limit ranges are all checked before
  touching the database.
- **No arbitrary SQL** tool exists, and none is planned.
- **Least privilege** — the server's surface area is the six tools above;
  nothing else in the database is reachable.
- **Sensitive CRM information** — customer emails and interaction notes
  are real business data in a production setting; this demo uses
  synthetic data only.
- **Audit logging** — not implemented here, but a natural extension: every
  tool call already has enough information (`customer_id`, operation,
  timestamp) to log for an audit trail.

## Limitations

- Single-tenant, no authentication or authorization — anyone with access
  to the server can call any tool.
- No pagination beyond the `limit` parameter; large CRMs would need it.
- No update path for fields other than `status` (by design, but a real
  CRM would need e.g. editing contact details).
- SQLite is fine for a portfolio demo; a production CRM would use a
  server-grade database.
- `customer_pipeline_summary`'s conversion rate is a simple overall
  snapshot, not a time-windowed or cohort-based metric.

## Future Improvements

- Authentication and authorization
- Role-based access control
- Audit logs
- Approval workflows for sensitive status changes
- PostgreSQL adapter
- Real CRM integrations (Salesforce, HubSpot, etc.)
- Streamable HTTP transport
- Multi-tenant support
- Pagination for large result sets

## Portfolio Value

This project demonstrates:
- Model Context Protocol server and client development
- Python backend engineering
- Relational database design (SQLite, foreign keys, indices)
- Safe agent-tool integration patterns
- Deliberate, explicit tool design over generic CRUD
- Automated testing with pytest and deterministic fixtures
- Structured, agent-friendly outputs
