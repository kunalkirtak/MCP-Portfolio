# Database MCP Server

A Model Context Protocol (MCP) server that exposes a small, realistic
e-commerce analytics database (SQLite) to an AI agent through **safe,
parameterized tools** — with no arbitrary SQL execution.

## Overview

This project demonstrates how to give an AI agent controlled access to
structured business data. The agent can search customers, analyze
orders, rank products, and pull sales summaries — all through typed,
validated MCP tools, plus MCP resources for schema discovery and a
prompt template for guiding analytics questions.

Everything runs locally (or in Google Colab) with:

- **No API keys**
- **No paid services**
- **No Docker**
- **No external database** — just a local SQLite file

## Why MCP + Databases?

Giving an LLM direct, unrestricted database access is risky: a model can
be prompted (accidentally or adversarially) into writing destructive or
overly broad SQL. MCP lets us put a well-defined interface — tools with
fixed input schemas — between the agent and the data. The agent can
only do what the server explicitly allows, and the server is the one
place all data-access logic (and validation) lives. This is the same
principle behind least-privilege APIs, applied to LLM agents.

## Architecture

```text
                 AI Agent
                    |
                MCP Client
                    |
             MCP Protocol
                    |
          Database MCP Server
          /        |        \
       Tools    Resources   Prompts
          \        |        /
              DB Layer (database.py)
                  |
               SQLite (ecommerce.db)
```

- **Tools** perform validated, parameterized business operations.
- **Resources** expose read-only, human-readable documents (schema,
  per-customer context).
- **Prompts** generate structured instruction text for an agent — they
  do not call any LLM themselves.
- **DB Layer** (`database.py`) is the only code that touches SQL. It is
  completely independent of MCP and is unit-testable on its own.

## MCP Capabilities

| Capability | What it means here |
|---|---|
| **Tools** | 5 typed functions the agent can call (`query_customers`, `customer_order_summary`, `top_products`, `sales_summary`, `order_status_summary`). Each validates its inputs and returns structured JSON. |
| **Resources** | `db://schema` (static schema doc) and `db://customer/{customer_id}` (dynamic, per-customer context) — read-only documents an agent can fetch. |
| **Prompts** | `analytics_prompt(question)` — generates a structured instruction template; it does not call an LLM. |
| **Client** | `client_demo.py` shows an MCP `Client` discovering and calling everything above, with no AI API involved. |
| **Structured output** | Tools return dictionaries, which the SDK serializes into both text content and `structured_content` for the calling agent. |

## Database Schema

**customers** — `id, name, email, country, segment, created_at`
Segments: `Standard`, `Premium`, `Enterprise`.

**products** — `id, name, category, price, stock`

**orders** — `id, customer_id, order_date, status, total_amount`
Statuses: `pending`, `processing`, `shipped`, `delivered`, `cancelled`.
Foreign key: `customer_id -> customers.id`.

**order_items** — `id, order_id, product_id, quantity, unit_price`
Foreign keys: `order_id -> orders.id`, `product_id -> products.id`.

`PRAGMA foreign_keys = ON` is set on every connection.

## Tools

### 1. `query_customers`
Search customers with optional filters.
- **Inputs:** `name` (optional substring), `country` (optional exact), `segment` (optional exact, one of the three allowed values), `limit` (int, 1-20, default 10)
- **Output:** `{ "customers": [...], "count": N }`
- **Example:** `query_customers(segment="Premium", limit=5)`

### 2. `customer_order_summary`
Order analytics for one customer.
- **Inputs:** `customer_id` (int)
- **Output:** `{ customer, order_count, total_spent, average_order_value, last_order_date, status_breakdown }`
- **Example:** `customer_order_summary(customer_id=1)`

### 3. `top_products`
Highest-revenue products, optionally by category.
- **Inputs:** `limit` (int, 1-20, default 5), `category` (optional exact)
- **Output:** `{ "products": [{product_id, product_name, category, units_sold, revenue}, ...], "count": N }`
- **Example:** `top_products(limit=5)`

### 4. `sales_summary`
Overall business analytics, optionally scoped to a date range.
- **Inputs:** `start_date`, `end_date` (optional, ISO `YYYY-MM-DD`)
- **Output:** `{ total_orders, total_revenue, average_order_value, unique_customers, cancelled_orders, top_category }`
- **Example:** `sales_summary(start_date="2023-06-01", end_date="2023-06-30")`

### 5. `order_status_summary`
Order counts grouped by status.
- **Inputs:** none
- **Output:** `{ "pending": N, "processing": N, "shipped": N, "delivered": N, "cancelled": N }`

## Resources

- **`db://schema`** — static, human-readable schema description: tables,
  columns, relationships, and business meanings (e.g. how "revenue" is
  computed). Meant to be read by an agent before running analytics.
- **`db://customer/{customer_id}`** — dynamic resource returning a
  readable profile + order stats + recent orders for one customer.
  Returns a clean "not found" message for nonexistent IDs instead of
  raising an error.

## Prompt

- **`analytics_prompt(question)`** — returns instruction text that
  walks an agent through: inspecting the schema, choosing the right
  tool(s), retrieving data, avoiding unsupported assumptions, explaining
  the result, and noting limitations. It never calls an LLM itself; it
  only produces the prompt text.

## Safety Architecture

**There is no `execute_sql`, `run_query`, or `raw_sql` tool in this
project, and there never will be.** This is a deliberate design choice,
not an oversight.

```text
Agent
 |
 v
Safe MCP Tool         (fixed name, fixed typed parameters)
 |
 v
Validated Parameters  (limits clamped, enums checked, dates validated)
 |
 v
Parameterized SQL     (built in database.py, "?" placeholders only)
 |
 v
SQLite
```

Every tool exposes a fixed, narrow operation (search customers, rank
products, summarize orders, etc.). The agent can vary *parameters*
within validated bounds, but it can never change *what kind of query*
runs or *which table/columns* are touched. This removes an entire class
of prompt-injection and SQL-injection risk that a generic
"ask the database anything" tool would introduce.

## Installation

```bash
git clone <your-repo-url>
cd database-mcp-server
pip install -q "mcp[cli]" pytest
python seed_database.py
```

## Google Colab

Run each of the following in its own Colab cell.

**1. Install dependencies**
```bash
!pip install -q "mcp[cli]" pytest
```

**2. Create the project directory**
```python
!mkdir -p database-mcp-server/tests
%cd database-mcp-server
```

**3. Create the files**

Use `%%writefile` cells (or upload the repo files directly) to create
`database.py`, `seed_database.py`, `server.py`, `client_demo.py`,
`requirements.txt`, `.gitignore`, and `tests/test_server.py` with the
contents from this README/repo.

**4. Seed the database**
```bash
!python seed_database.py
```

**5. Run the tests**
```bash
!pytest -q
```

**6. Run the client demo**
```bash
!python client_demo.py
```

**7. (Optional) Launch the MCP Inspector**
```bash
!mcp dev server.py
```
> The Inspector opens a local web UI. In a hosted Colab runtime you may
> need to use Colab's port-forwarding/proxy support to view it, or run
> this step on a local machine instead — it is entirely optional and
> everything else in this project works without it.

## Local Usage

```bash
python seed_database.py     # create + seed the SQLite database
pytest -q                   # run the test suite
python client_demo.py       # run the end-to-end MCP client demo
python server.py            # run the server directly over stdio
```

## Running Tests

```bash
pytest -q
```

Tests use an isolated temporary SQLite database (via pytest's
`tmp_path` fixture) so they never touch `ecommerce.db`. No network
access or API key is required.

## MCP Inspector

The [MCP Inspector](https://modelcontextprotocol.io) is an optional
browser-based tool for exploring a running MCP server. With the current
MCP Python SDK (`mcp[cli]`), launch it against this server with:

```bash
mcp dev server.py
```

From the Inspector UI you can:
- Browse and call all 5 **tools** with a form-based UI
- Read the **`db://schema`** and **`db://customer/{customer_id}`** resources
- View and render the **`analytics_prompt`**
- Inspect the JSON schema the server advertises for each tool
- See the raw request/response for every call you make

This is purely a development/debugging aid — the project (tests, client
demo, and server) works fully without ever launching the Inspector.

## Example Agent Workflows

```text
"Show me our premium customers."
  -> query_customers(segment="Premium")

"Who are our highest-value customers?"
  -> query_customers(...) then customer_order_summary(customer_id=...) per customer

"Which products generate the most revenue?"
  -> top_products(limit=5)

"What is the current order distribution?"
  -> order_status_summary()

"Give me the sales summary."
  -> sales_summary()
```

## Project Structure

```text
database-mcp-server/
│
├── server.py
├── client_demo.py
├── database.py
├── seed_database.py
├── requirements.txt
├── README.md
├── screenshot/
├── notebook/
│    └── database_mcp_server.ipynb
└── tests/
    └── test_server.py
```

## Security Considerations

- **Parameterized SQL only.** Every query in `database.py` uses `?`
  placeholders; user-supplied values are never concatenated into SQL
  strings.
- **Input validation at the tool boundary.** `limit` is clamped to
  1-20, `segment`/`status` are checked against fixed allow-lists, and
  dates are validated against `YYYY-MM-DD` before touching the
  database.
- **No arbitrary SQL tool**, by design (see "Safety Architecture" above).
- **Least privilege.** Each tool does exactly one narrow thing; there is
  no generic "query anything" capability for an agent to misuse.
- **No stack traces over MCP.** Errors are caught and re-raised as
  clean `ToolError` messages; internal exception details are not leaked
  to the client.
- **Sensitive data.** The sample data is entirely synthetic. In a real
  deployment, columns like `email` would need access controls,
  masking, or redaction policies appropriate to the data's sensitivity.

## Limitations

- The dataset is small (20 customers, 10 products, 40 orders) and meant
  for demonstration, not production-scale analytics.
- SQLite is single-file and not designed for concurrent multi-writer
  workloads; this is fine for a local/demo MCP server, not a production
  service.
- There is no authentication or authorization layer — anyone who can
  reach the server can call any tool.
- Date filtering in `sales_summary` is a simple string comparison over
  ISO dates (which works correctly for `YYYY-MM-DD` but is not a full
  date-range query engine).
- The `analytics_prompt` only generates instruction text; it does not
  call or evaluate against any LLM itself.

## Future Improvements

*(Not implemented — noted here to show awareness of production concerns.)*

- PostgreSQL adapter for multi-writer, larger-scale deployments
- Authentication and authorization
- Role-based access control per tool/resource
- Pagination for large result sets
- Caching of expensive aggregate queries
- Audit logging of tool calls
- Larger, more varied sample datasets
- Streamable HTTP transport for remote deployments
- Query cost/complexity controls

## Portfolio Value

This project demonstrates:

- **MCP server/client design** — tools, resources (static + dynamic),
  and prompts, built on the current MCP Python SDK
- **Python backend engineering** — clean separation of database and
  protocol logic, type hints, docstrings
- **SQL and database design** — normalized schema, foreign keys,
  aggregation queries, parameterized statements
- **Agent/tool safety** — deliberately constrained tool surface instead
  of exposing raw SQL
- **Testing** — a deterministic pytest suite covering happy paths and
  error handling, isolated from the demo database
- **Backend engineering judgment** — knowing what *not* to build (no
  Docker, no external DB, no arbitrary SQL) for a project at this scale
