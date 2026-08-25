"""
server.py

Database MCP Server.

Exposes a small e-commerce analytics SQLite database to an AI agent
through the Model Context Protocol (MCP):

    * Tools     -> safe, parameterized business operations
    * Resources -> read-only schema + customer context documents
    * Prompt    -> a structured analytics prompt template

SAFETY DESIGN
-------------
This server intentionally does NOT expose a generic "run SQL" tool.
There is no `execute_sql`, `run_query`, or `raw_sql` tool anywhere in
this file. Every tool below accepts a small set of typed, validated
parameters and internally builds a single parameterized SQL query
(see database.py). This means an AI agent driving this server can
never submit arbitrary SQL, regardless of how it is prompted.

    Agent -> Safe MCP Tool -> Validated Parameters -> Parameterized SQL -> SQLite

See the README ("Safety Architecture") for the full rationale.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import database as db
from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

# ---------------------------------------------------------------------------
# Server instance
# ---------------------------------------------------------------------------

mcp = MCPServer(
    name="database-mcp-server",
    title="Database MCP Server",
    instructions=(
        "This server exposes a read-only view of a small e-commerce "
        "analytics database. Use the tools to search customers, analyze "
        "orders, and retrieve sales analytics. Read the 'db://schema' "
        "resource first to understand the data model. There is no tool "
        "for arbitrary SQL execution by design."
    ),
    version="1.0.0",
)

_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _validate_date(value: str, field_name: str) -> None:
    """Validate an ISO date string (YYYY-MM-DD). Raises ToolError if invalid."""
    if not _DATE_RE.match(value):
        raise ToolError(
            f"Invalid {field_name}: {value!r}. Expected ISO format YYYY-MM-DD."
        )


def _validate_limit(limit: int, minimum: int = 1, maximum: int = 20) -> None:
    """Validate that a limit parameter is within an allowed range."""
    if not (minimum <= limit <= maximum):
        raise ToolError(
            f"Invalid limit: {limit}. Must be between {minimum} and {maximum}."
        )


# ---------------------------------------------------------------------------
# TOOL 1 — query_customers
# ---------------------------------------------------------------------------

@mcp.tool()
def query_customers(
    name: str | None = None,
    country: str | None = None,
    segment: str | None = None,
    limit: int = 10,
) -> dict[str, Any]:
    """Search customers using safe, optional filters.

    Args:
        name: Optional substring to match against the customer's name.
        country: Optional exact country match.
        segment: Optional exact segment match ('Standard', 'Premium', 'Enterprise').
        limit: Maximum number of results to return (1-20). Defaults to 10.

    Returns:
        A dict with the matching customers and the count returned.
    """
    _validate_limit(limit)

    if segment is not None and segment not in db.ALLOWED_SEGMENTS:
        raise ToolError(
            f"Invalid segment: {segment!r}. Allowed values: {list(db.ALLOWED_SEGMENTS)}."
        )

    try:
        customers = db.query_customers(
            db.DB_PATH, name=name, country=country, segment=segment, limit=limit
        )
    except Exception as exc:  # pragma: no cover - defensive, DB errors are rare
        raise ToolError(f"Database error while searching customers: {exc}") from exc

    return {"customers": customers, "count": len(customers)}


# ---------------------------------------------------------------------------
# TOOL 2 — customer_order_summary
# ---------------------------------------------------------------------------

@mcp.tool()
def customer_order_summary(customer_id: int) -> dict[str, Any]:
    """Return order analytics for a single customer.

    Args:
        customer_id: The numeric id of the customer.

    Returns:
        A dict containing the customer's profile, order_count,
        total_spent, average_order_value, last_order_date, and a
        status_breakdown (counts of orders per status).
    """
    if customer_id <= 0:
        raise ToolError(f"Invalid customer_id: {customer_id}. Must be a positive integer.")

    try:
        summary = db.customer_order_summary(db.DB_PATH, customer_id)
    except Exception as exc:  # pragma: no cover
        raise ToolError(f"Database error while summarizing customer orders: {exc}") from exc

    if summary is None:
        raise ToolError(f"Customer not found: {customer_id}")

    return summary


# ---------------------------------------------------------------------------
# TOOL 3 — top_products
# ---------------------------------------------------------------------------

@mcp.tool()
def top_products(limit: int = 5, category: str | None = None) -> dict[str, Any]:
    """Identify the highest-revenue products, optionally within a category.

    Args:
        limit: Maximum number of products to return (1-20). Defaults to 5.
        category: Optional exact category match.

    Returns:
        A dict with a list of products (product_id, product_name,
        category, units_sold, revenue), sorted by revenue descending.
    """
    _validate_limit(limit)

    try:
        products = db.top_products(db.DB_PATH, limit=limit, category=category)
    except Exception as exc:  # pragma: no cover
        raise ToolError(f"Database error while ranking products: {exc}") from exc

    return {"products": products, "count": len(products)}


# ---------------------------------------------------------------------------
# TOOL 4 — sales_summary
# ---------------------------------------------------------------------------

@mcp.tool()
def sales_summary(
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Provide overall business analytics, optionally scoped to a date range.

    Args:
        start_date: Optional inclusive ISO start date (YYYY-MM-DD).
        end_date: Optional inclusive ISO end date (YYYY-MM-DD).

    Returns:
        A dict with total_orders, total_revenue, average_order_value,
        unique_customers, cancelled_orders, and top_category.
    """
    if start_date is not None:
        _validate_date(start_date, "start_date")
    if end_date is not None:
        _validate_date(end_date, "end_date")
    if start_date is not None and end_date is not None and start_date > end_date:
        raise ToolError(
            f"Invalid date range: start_date ({start_date}) is after end_date ({end_date})."
        )

    try:
        return db.sales_summary(db.DB_PATH, start_date=start_date, end_date=end_date)
    except Exception as exc:  # pragma: no cover
        raise ToolError(f"Database error while computing sales summary: {exc}") from exc


# ---------------------------------------------------------------------------
# TOOL 5 — order_status_summary
# ---------------------------------------------------------------------------

@mcp.tool()
def order_status_summary() -> dict[str, int]:
    """Show the distribution of orders across all statuses.

    Returns:
        A dict mapping each order status to its count, e.g.
        {"pending": 4, "processing": 5, "shipped": 8, "delivered": 20, "cancelled": 3}.
    """
    try:
        return db.order_status_summary(db.DB_PATH)
    except Exception as exc:  # pragma: no cover
        raise ToolError(f"Database error while summarizing order statuses: {exc}") from exc


# ---------------------------------------------------------------------------
# RESOURCE 1 — db://schema (static)
# ---------------------------------------------------------------------------

_SCHEMA_TEXT = """\
DATABASE SCHEMA — E-Commerce Analytics
=======================================

customers
---------
  id          INTEGER  primary key
  name        TEXT     full name of the customer
  email       TEXT     unique contact email
  country     TEXT     customer's country
  segment     TEXT     one of: Standard, Premium, Enterprise
  created_at  TEXT     ISO date the customer record was created

products
--------
  id       INTEGER  primary key
  name     TEXT     product name
  category TEXT     product category (e.g. Electronics, Furniture)
  price    REAL     unit list price
  stock    INTEGER  units currently in stock

orders
------
  id            INTEGER  primary key
  customer_id   INTEGER  foreign key -> customers.id
  order_date    TEXT     ISO date (YYYY-MM-DD) the order was placed
  status        TEXT     one of: pending, processing, shipped, delivered, cancelled
  total_amount  REAL     total value of the order

order_items
-----------
  id          INTEGER  primary key
  order_id    INTEGER  foreign key -> orders.id
  product_id  INTEGER  foreign key -> products.id
  quantity    INTEGER  units of the product purchased in this order
  unit_price  REAL     price per unit at the time of purchase

Relationships
-------------
  customers (1) --- (many) orders
  orders    (1) --- (many) order_items
  products  (1) --- (many) order_items

Business notes
--------------
  * "revenue" for a product = SUM(order_items.quantity * order_items.unit_price)
    across non-cancelled orders.
  * A customer's "total_spent" = SUM(orders.total_amount) across all of
    their orders (all statuses, including cancelled, unless a tool says
    otherwise).
  * Use the provided tools to query this data. There is no tool for
    arbitrary SQL execution.
"""


@mcp.resource("db://schema")
def schema_resource() -> str:
    """Human-readable description of the database schema, relationships,
    and business meanings. Read this before running analytics."""
    return _SCHEMA_TEXT


# ---------------------------------------------------------------------------
# RESOURCE 2 — db://customer/{customer_id} (dynamic)
# ---------------------------------------------------------------------------

@mcp.resource("db://customer/{customer_id}")
def customer_resource(customer_id: str) -> str:
    """Readable context for a single customer: profile, order count,
    total spent, and recent orders. Handles nonexistent customers cleanly."""
    try:
        cid = int(customer_id)
    except ValueError:
        return f"Invalid customer id: {customer_id!r}. Expected an integer."

    context = db.customer_context(db.DB_PATH, cid)
    if context is None:
        return f"No customer found with id={cid}."

    customer = context["customer"]
    lines = [
        f"Customer #{customer['id']}: {customer['name']}",
        f"  Email:      {customer['email']}",
        f"  Country:    {customer['country']}",
        f"  Segment:    {customer['segment']}",
        f"  Created:    {customer['created_at']}",
        "",
        f"Order count:  {context['order_count']}",
        f"Total spent:  {context['total_spent']}",
        "",
        "Recent orders:",
    ]
    if context["recent_orders"]:
        for order in context["recent_orders"]:
            lines.append(
                f"  - Order #{order['id']} | {order['order_date']} | "
                f"{order['status']} | {order['total_amount']}"
            )
    else:
        lines.append("  (no orders yet)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# PROMPT — analytics_prompt
# ---------------------------------------------------------------------------

@mcp.prompt()
def analytics_prompt(question: str) -> str:
    """Generate a structured instruction for an AI agent to answer a
    business analytics question using this server's tools and resources.

    Args:
        question: The business analytics question to answer, e.g.
            "Which customer segment generates the most revenue?"
    """
    return f"""\
You are a business analyst answering a question using the Database MCP
Server. Follow this process:

QUESTION: {question}

1. Inspect the schema.
   Read the 'db://schema' resource to understand the available tables,
   columns, and relationships before doing anything else.

2. Identify the relevant tools.
   Choose from: query_customers, customer_order_summary, top_products,
   sales_summary, order_status_summary. Do not assume a tool exists if
   it is not in this list — there is no arbitrary SQL tool available.

3. Retrieve structured data.
   Call the appropriate tool(s) with valid, well-formed parameters.
   Use multiple tool calls if the question requires combining data
   (e.g. per-customer detail plus an overall summary).

4. Avoid unsupported assumptions.
   Base your answer only on the data actually returned by the tools.
   Do not invent figures, trends, or customer details that were not
   present in the tool output.

5. Explain the result.
   Present a clear, concise answer to the question, citing the specific
   numbers returned by the tools.

6. Mention limitations when appropriate.
   Note if the available data is too limited to fully answer the
   question (e.g. small sample size, missing date range, no tool that
   directly answers a segment-level revenue breakdown).
"""


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ensure the database exists before serving requests.
    if not Path(db.DB_PATH).exists():
        import seed_database

        seed_database.seed()

    mcp.run()
