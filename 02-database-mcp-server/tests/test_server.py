"""
tests/test_server.py

Deterministic pytest suite for the Database MCP Server.

All tests run against a temporary, isolated SQLite database (created in
a pytest tmp_path) so they never touch or corrupt the main demo database
(ecommerce.db). No API keys or external services are used.

Note on async: the project intentionally depends on nothing beyond
`mcp[cli]` and `pytest` (see requirements.txt), so these tests avoid the
`pytest-asyncio` plugin and instead drive the async MCP client with a
small `run()` helper built on `asyncio.run`.

Run with:
    pytest -q
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any, Coroutine

import pytest

# Make the project root importable when pytest is run from the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import database as db  # noqa: E402
import seed_database  # noqa: E402
import server  # noqa: E402
from mcp import Client  # noqa: E402


def run(coro: Coroutine[Any, Any, Any]) -> Any:
    """Run an async coroutine from a synchronous pytest test function."""
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def test_db_path(tmp_path, monkeypatch):
    """Point both database.py and server.py at an isolated, seeded
    temporary database for the duration of a test."""
    path = tmp_path / "test_ecommerce.db"
    monkeypatch.setattr(db, "DB_PATH", path)
    monkeypatch.setattr(server.db, "DB_PATH", path)
    seed_database.seed(path)
    return path


async def _call_tool(name: str, arguments: dict[str, Any] | None = None):
    async with Client(server.mcp) as client:
        return await client.call_tool(name, arguments or {})


async def _read_resource(uri: str):
    async with Client(server.mcp) as client:
        return await client.read_resource(uri)


async def _get_prompt(name: str, arguments: dict[str, str]):
    async with Client(server.mcp) as client:
        return await client.get_prompt(name, arguments)


async def _list_tools():
    async with Client(server.mcp) as client:
        return await client.list_tools()


# ---------------------------------------------------------------------------
# 1. Database initialization
# ---------------------------------------------------------------------------

def test_database_initialization(test_db_path):
    counts = db.table_counts(test_db_path)
    assert counts["customers"] == 20
    assert counts["products"] == 10
    assert counts["orders"] == 40
    assert counts["order_items"] > 0


# ---------------------------------------------------------------------------
# 2. Tool discovery
# ---------------------------------------------------------------------------

def test_tool_discovery(test_db_path):
    tools = run(_list_tools())
    names = {t.name for t in tools.tools}
    assert names == {
        "query_customers",
        "customer_order_summary",
        "top_products",
        "sales_summary",
        "order_status_summary",
    }


# ---------------------------------------------------------------------------
# 3. Customer search
# ---------------------------------------------------------------------------

def test_customer_search_basic(test_db_path):
    result = run(_call_tool("query_customers", {"limit": 5}))
    assert result.is_error is False
    data = result.structured_content
    assert data["count"] == 5
    assert len(data["customers"]) == 5


# ---------------------------------------------------------------------------
# 4. Customer filtering
# ---------------------------------------------------------------------------

def test_customer_filtering_by_segment(test_db_path):
    result = run(_call_tool("query_customers", {"segment": "Premium", "limit": 20}))
    data = result.structured_content
    assert data["count"] > 0
    assert all(c["segment"] == "Premium" for c in data["customers"])


def test_customer_filtering_by_country(test_db_path):
    result = run(_call_tool("query_customers", {"country": "USA", "limit": 20}))
    data = result.structured_content
    assert all(c["country"] == "USA" for c in data["customers"])


# ---------------------------------------------------------------------------
# 5. Customer order summary
# ---------------------------------------------------------------------------

def test_customer_order_summary(test_db_path):
    result = run(_call_tool("customer_order_summary", {"customer_id": 1}))
    assert result.is_error is False
    data = result.structured_content
    assert data["customer"]["id"] == 1
    assert data["order_count"] >= 1
    assert "status_breakdown" in data


# ---------------------------------------------------------------------------
# 6. Top products
# ---------------------------------------------------------------------------

def test_top_products(test_db_path):
    result = run(_call_tool("top_products", {"limit": 3}))
    assert result.is_error is False
    data = result.structured_content
    assert data["count"] == 3
    revenues = [p["revenue"] for p in data["products"]]
    assert revenues == sorted(revenues, reverse=True)


# ---------------------------------------------------------------------------
# 7. Sales summary
# ---------------------------------------------------------------------------

def test_sales_summary(test_db_path):
    result = run(_call_tool("sales_summary", {}))
    assert result.is_error is False
    data = result.structured_content
    assert data["total_orders"] == 40
    assert data["unique_customers"] > 0
    assert data["total_revenue"] > 0


# ---------------------------------------------------------------------------
# 8. Order status summary
# ---------------------------------------------------------------------------

def test_order_status_summary(test_db_path):
    result = run(_call_tool("order_status_summary", {}))
    assert result.is_error is False
    data = result.structured_content
    assert set(data.keys()) == {"pending", "processing", "shipped", "delivered", "cancelled"}
    assert sum(data.values()) == 40


# ---------------------------------------------------------------------------
# 9. Schema resource
# ---------------------------------------------------------------------------

def test_schema_resource(test_db_path):
    result = run(_read_resource("db://schema"))
    text = result.contents[0].text
    assert "customers" in text
    assert "orders" in text
    assert "order_items" in text


# ---------------------------------------------------------------------------
# 10. Dynamic customer resource
# ---------------------------------------------------------------------------

def test_dynamic_customer_resource(test_db_path):
    result = run(_read_resource("db://customer/1"))
    text = result.contents[0].text
    assert "Customer #1" in text
    assert "Recent orders" in text


# ---------------------------------------------------------------------------
# 11. Analytics prompt
# ---------------------------------------------------------------------------

def test_analytics_prompt(test_db_path):
    result = run(
        _get_prompt("analytics_prompt", {"question": "Which segment spends the most?"})
    )
    text = result.messages[0].content.text
    assert "Which segment spends the most?" in text
    assert "db://schema" in text


# ---------------------------------------------------------------------------
# 12. Invalid customer ID
# ---------------------------------------------------------------------------

def test_invalid_customer_id(test_db_path):
    result = run(_call_tool("customer_order_summary", {"customer_id": -1}))
    assert result.is_error is True
    assert "Invalid customer_id" in result.content[0].text


# ---------------------------------------------------------------------------
# 13. Invalid limit
# ---------------------------------------------------------------------------

def test_invalid_limit(test_db_path):
    result = run(_call_tool("query_customers", {"limit": 999}))
    assert result.is_error is True
    assert "Invalid limit" in result.content[0].text


# ---------------------------------------------------------------------------
# 14. Invalid date
# ---------------------------------------------------------------------------

def test_invalid_date(test_db_path):
    result = run(_call_tool("sales_summary", {"start_date": "13/40/2023"}))
    assert result.is_error is True
    assert "Invalid start_date" in result.content[0].text


# ---------------------------------------------------------------------------
# 15. Nonexistent customer
# ---------------------------------------------------------------------------

def test_nonexistent_customer_tool(test_db_path):
    result = run(_call_tool("customer_order_summary", {"customer_id": 99999}))
    assert result.is_error is True
    assert "Customer not found" in result.content[0].text


def test_nonexistent_customer_resource(test_db_path):
    result = run(_read_resource("db://customer/99999"))
    text = result.contents[0].text
    assert "No customer found" in text


# ---------------------------------------------------------------------------
# Extra: invalid segment is rejected up front
# ---------------------------------------------------------------------------

def test_invalid_segment_rejected(test_db_path):
    result = run(_call_tool("query_customers", {"segment": "NotASegment"}))
    assert result.is_error is True
    assert "Invalid segment" in result.content[0].text
