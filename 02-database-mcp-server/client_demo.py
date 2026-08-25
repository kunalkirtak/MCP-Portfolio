"""
client_demo.py

A standalone demo of an MCP client talking to the Database MCP Server.

This uses the current MCP Python SDK v2 `Client`, connected in-process
directly to the `MCPServer` instance defined in server.py (no subprocess,
no stdio transport needed — this keeps the demo simple and Colab-friendly).

Run it with:
    python client_demo.py

No API key or external service is required.
"""

from __future__ import annotations

import asyncio
import json

import seed_database
import server
from mcp import Client


def _print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


def _print_json(data) -> None:
    print(json.dumps(data, indent=2, default=str))


async def main() -> None:
    # Make sure the demo database exists and has deterministic data.
    seed_database.seed()

    async with Client(server.mcp) as client:
        # 1. Tool discovery ---------------------------------------------
        _print_header("1. TOOL DISCOVERY")
        tools = await client.list_tools()
        for tool in tools.tools:
            print(f"  - {tool.name}: {tool.description.splitlines()[0]}")

        # 2. Read schema resource -----------------------------------------
        _print_header("2. SCHEMA RESOURCE (db://schema)")
        schema = await client.read_resource("db://schema")
        print(schema.contents[0].text)

        # 3. Search Premium customers -------------------------------------
        _print_header("3. QUERY CUSTOMERS (segment=Premium)")
        result = await client.call_tool("query_customers", {"segment": "Premium", "limit": 5})
        _print_json(result.structured_content)

        # 4. Customer analytics --------------------------------------------
        _print_header("4. CUSTOMER ORDER SUMMARY (customer_id=1)")
        result = await client.call_tool("customer_order_summary", {"customer_id": 1})
        _print_json(result.structured_content)

        # 5. Product analytics ----------------------------------------------
        _print_header("5. TOP PRODUCTS (limit=5)")
        result = await client.call_tool("top_products", {"limit": 5})
        _print_json(result.structured_content)

        # 6. Sales analytics --------------------------------------------------
        _print_header("6. SALES SUMMARY")
        result = await client.call_tool("sales_summary", {})
        _print_json(result.structured_content)

        # 6b. Order status distribution ----------------------------------------
        _print_header("6b. ORDER STATUS SUMMARY")
        result = await client.call_tool("order_status_summary", {})
        _print_json(result.structured_content)

        # 7. Dynamic customer resource ------------------------------------------
        _print_header("7. DYNAMIC CUSTOMER RESOURCE (db://customer/1)")
        result = await client.read_resource("db://customer/1")
        print(result.contents[0].text)

        # 8. Analytics prompt -----------------------------------------------------
        _print_header("8. ANALYTICS PROMPT")
        prompt_result = await client.get_prompt(
            "analytics_prompt",
            {"question": "Which customer segment generates the most revenue?"},
        )
        print(prompt_result.messages[0].content.text)

    _print_header("DEMO COMPLETE")
    print("No API key or external AI service was used. All data came from SQLite.")


if __name__ == "__main__":
    asyncio.run(main())
