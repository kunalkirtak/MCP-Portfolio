"""
tests/test_server.py

Deterministic pytest suite for the CRM MCP Server.

Each test gets its own temporary SQLite database (via the CRM_DB_PATH
environment variable) seeded with the same fixed sample data, so tests
never touch a shared or real database and never require network access.

Run with:
    pytest -q
"""

from __future__ import annotations

import os
import sys
import tempfile

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# All async tests in this module use anyio (a dependency of the mcp
# package) rather than pytest-asyncio, so no extra test dependency is
# required beyond what's already in requirements.txt.
pytestmark = pytest.mark.anyio


@pytest.fixture()
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def db_path(monkeypatch, tmp_path):
    """Point CRM_DB_PATH at a fresh temporary file, seed it, and return the path."""
    path = str(tmp_path / "test_crm.db")
    monkeypatch.setenv("CRM_DB_PATH", path)

    # Reload modules that cache no state at import time — database.py reads
    # CRM_DB_PATH per-call via get_db_path(), so no reload is required, but
    # we still import here (after the env var is set) for clarity.
    import database as db
    import seed_database

    db.init_db(path)
    seed_database.seed(path)

    yield path


@pytest.fixture()
def mcp_server(db_path):
    """A fresh MCPServer instance (server.py builds it at import time using
    the already-patched CRM_DB_PATH, so importing here is sufficient)."""
    import importlib
    import server as server_module

    importlib.reload(server_module)
    return server_module.mcp_server


@pytest.fixture()
async def client(mcp_server):
    from mcp import Client

    async with Client(mcp_server) as c:
        yield c


# ---------------------------------------------------------------------------
# 1. Database initialization
# ---------------------------------------------------------------------------

def test_database_initializes_with_seed_data(db_path):
    import database as db

    customers = db.find_customers(limit=20, db_path=db_path)
    assert len(customers) == 20

    with db.get_connection(db_path) as conn:
        total_interactions = conn.execute(
            "SELECT COUNT(*) AS n FROM interactions"
        ).fetchone()["n"]
    assert total_interactions == 40


def test_seeding_is_idempotent(db_path):
    import seed_database

    before = seed_database.seed(db_path)
    after = seed_database.seed(db_path)
    assert before == after


# ---------------------------------------------------------------------------
# 2. Tool discovery
# ---------------------------------------------------------------------------

async def test_tool_discovery(client):
    result = await client.list_tools()
    names = {tool.name for tool in result.tools}
    assert names == {
        "find_customers",
        "get_customer",
        "update_customer_status",
        "add_interaction",
        "get_interactions",
        "customer_pipeline_summary",
    }


# ---------------------------------------------------------------------------
# 3. find_customers
# ---------------------------------------------------------------------------

async def test_find_customers_by_query(client):
    result = await client.call_tool("find_customers", {"query": "Nimbus"})
    payload = _json(result)
    assert payload["count"] == 1
    assert payload["customers"][0]["company"] == "Nimbus Logix"


async def test_find_customers_by_status(client):
    result = await client.call_tool("find_customers", {"status": "lead", "limit": 20})
    payload = _json(result)
    assert payload["count"] >= 1
    assert all(c["status"] == "lead" for c in payload["customers"])


# ---------------------------------------------------------------------------
# 4. get_customer
# ---------------------------------------------------------------------------

async def test_get_customer(client):
    result = await client.call_tool("get_customer", {"customer_id": 1})
    payload = _json(result)
    assert payload["customer"]["id"] == 1
    assert payload["interaction_count"] >= 1
    assert isinstance(payload["recent_interactions"], list)


# ---------------------------------------------------------------------------
# 5. update_customer_status
# ---------------------------------------------------------------------------

async def test_update_customer_status(client):
    result = await client.call_tool(
        "update_customer_status", {"customer_id": 4, "status": "prospect"}
    )
    payload = _json(result)
    assert payload["customer"]["status"] == "prospect"
    assert payload["customer"]["last_contacted_at"] is not None


# ---------------------------------------------------------------------------
# 6. add_interaction
# ---------------------------------------------------------------------------

async def test_add_interaction(client):
    result = await client.call_tool(
        "add_interaction",
        {"customer_id": 1, "interaction_type": "call", "note": "Test call note."},
    )
    payload = _json(result)
    assert payload["interaction"]["customer_id"] == 1
    assert payload["interaction"]["interaction_type"] == "call"
    assert payload["interaction"]["note"] == "Test call note."


# ---------------------------------------------------------------------------
# 7. get_interactions
# ---------------------------------------------------------------------------

async def test_get_interactions(client):
    result = await client.call_tool("get_interactions", {"customer_id": 1, "limit": 5})
    payload = _json(result)
    assert payload["customer_id"] == 1
    assert len(payload["interactions"]) <= 5
    # newest first
    dates = [i["interaction_date"] for i in payload["interactions"]]
    assert dates == sorted(dates, reverse=True)


# ---------------------------------------------------------------------------
# 8. customer_pipeline_summary
# ---------------------------------------------------------------------------

async def test_customer_pipeline_summary(client):
    result = await client.call_tool("customer_pipeline_summary", {})
    payload = _json(result)
    assert payload["total_customers"] == 20
    assert (
        payload["lead_count"]
        + payload["prospect_count"]
        + payload["customer_count"]
        + payload["inactive_count"]
        == 20
    )
    assert 0.0 <= payload["conversion_rate"] <= 1.0


# ---------------------------------------------------------------------------
# 9. customer resource
# ---------------------------------------------------------------------------

async def test_customer_resource(client):
    result = await client.read_resource("crm://customer/1")
    text = result.contents[0].text
    assert "Customer:" in text
    assert "Nimbus Logix" in text


async def test_customer_resource_not_found(client):
    result = await client.read_resource("crm://customer/9999")
    text = result.contents[0].text
    assert "No customer found" in text


# ---------------------------------------------------------------------------
# 10. schema resource
# ---------------------------------------------------------------------------

async def test_schema_resource(client):
    result = await client.read_resource("crm://schema")
    text = result.contents[0].text
    assert "customers" in text
    assert "interactions" in text
    assert "lead, prospect, customer, inactive" in text


# ---------------------------------------------------------------------------
# 11. sales follow-up prompt
# ---------------------------------------------------------------------------

async def test_sales_followup_prompt(client):
    result = await client.get_prompt(
        "sales_followup_prompt",
        {"customer_id": "1", "goal": "Follow up after a product demo"},
    )
    text = result.messages[0].content.text
    assert "customer_id=1" in text
    assert "Follow up after a product demo" in text
    assert "Do not invent facts" in text


# ---------------------------------------------------------------------------
# 12. invalid customer
# ---------------------------------------------------------------------------

async def test_get_customer_invalid_id(client):
    result = await client.call_tool("get_customer", {"customer_id": 9999})
    payload = _json(result)
    assert "error" in payload


async def test_get_customer_non_positive_id(client):
    result = await client.call_tool("get_customer", {"customer_id": -1})
    payload = _json(result)
    assert "error" in payload


# ---------------------------------------------------------------------------
# 13. invalid status
# ---------------------------------------------------------------------------

async def test_update_customer_status_invalid_status(client):
    result = await client.call_tool(
        "update_customer_status", {"customer_id": 1, "status": "vip"}
    )
    payload = _json(result)
    assert "error" in payload


# ---------------------------------------------------------------------------
# 14. invalid interaction type
# ---------------------------------------------------------------------------

async def test_add_interaction_invalid_type(client):
    result = await client.call_tool(
        "add_interaction",
        {"customer_id": 1, "interaction_type": "carrier_pigeon", "note": "hi"},
    )
    payload = _json(result)
    assert "error" in payload


# ---------------------------------------------------------------------------
# 15. empty note
# ---------------------------------------------------------------------------

async def test_add_interaction_empty_note(client):
    result = await client.call_tool(
        "add_interaction",
        {"customer_id": 1, "interaction_type": "call", "note": "   "},
    )
    payload = _json(result)
    assert "error" in payload


# ---------------------------------------------------------------------------
# 16. excessive note
# ---------------------------------------------------------------------------

async def test_add_interaction_excessive_note(client):
    long_note = "x" * 2001
    result = await client.call_tool(
        "add_interaction",
        {"customer_id": 1, "interaction_type": "call", "note": long_note},
    )
    payload = _json(result)
    assert "error" in payload


# ---------------------------------------------------------------------------
# 17. invalid limit
# ---------------------------------------------------------------------------

async def test_find_customers_invalid_limit_too_high(client):
    result = await client.call_tool("find_customers", {"limit": 999})
    payload = _json(result)
    assert "error" in payload


async def test_find_customers_invalid_limit_too_low(client):
    result = await client.call_tool("find_customers", {"limit": 0})
    payload = _json(result)
    assert "error" in payload


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _json(call_tool_result):
    import json

    text = call_tool_result.content[0].text
    return json.loads(text)
