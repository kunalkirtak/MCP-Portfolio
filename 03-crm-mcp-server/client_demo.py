"""
client_demo.py

Demonstrates a full MCP client workflow against the CRM MCP Server:
tool discovery, calling every tool, reading both resources, and rendering
the sales follow-up prompt.

This does NOT call any AI/LLM API — it is a plain MCP client walking
through the server's capabilities so you can see exactly what an agent
would see.

Usage:
    python client_demo.py

(Run seed_database.py first so there is data to query.)
"""

from __future__ import annotations

import asyncio
import json

from mcp import Client

from server import mcp_server


def _print_header(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def _print_tool_result(result) -> None:
    if result.is_error:
        print("ERROR:", result.content[0].text if result.content else "(no message)")
        return
    for block in result.content:
        text = getattr(block, "text", None)
        if text is None:
            continue
        try:
            parsed = json.loads(text)
            print(json.dumps(parsed, indent=2))
        except (json.JSONDecodeError, TypeError):
            print(text)


async def main() -> None:
    async with Client(mcp_server) as client:

        # 1. Tool discovery ---------------------------------------------------
        _print_header("1. Tool discovery")
        tools = await client.list_tools()
        for tool in tools.tools:
            print(f"- {tool.name}")

        # 2. Find customer -----------------------------------------------------
        _print_header("2. find_customers(query='Nimbus')")
        result = await client.call_tool("find_customers", {"query": "Nimbus"})
        _print_tool_result(result)

        # 3. Get customer --------------------------------------------------------
        _print_header("3. get_customer(customer_id=1)")
        result = await client.call_tool("get_customer", {"customer_id": 1})
        _print_tool_result(result)

        # 4. Update status ----------------------------------------------------
        _print_header("4. update_customer_status(customer_id=4, status='prospect')")
        result = await client.call_tool(
            "update_customer_status", {"customer_id": 4, "status": "prospect"}
        )
        _print_tool_result(result)

        # 5. Add interaction ----------------------------------------------------
        _print_header("5. add_interaction(customer_id=1, interaction_type='call', note=...)")
        result = await client.call_tool(
            "add_interaction",
            {
                "customer_id": 1,
                "interaction_type": "call",
                "note": "Client demo call: confirmed interest in expanding the contract.",
            },
        )
        _print_tool_result(result)

        # 6. Get interactions -----------------------------------------------------
        _print_header("6. get_interactions(customer_id=1, limit=5)")
        result = await client.call_tool("get_interactions", {"customer_id": 1, "limit": 5})
        _print_tool_result(result)

        # 7. Pipeline summary -------------------------------------------------
        _print_header("7. customer_pipeline_summary()")
        result = await client.call_tool("customer_pipeline_summary", {})
        _print_tool_result(result)

        # 8. Customer resource --------------------------------------------------
        _print_header("8. Read resource crm://customer/1")
        resource_result = await client.read_resource("crm://customer/1")
        for content in resource_result.contents:
            print(content.text)

        # 9. Schema resource ------------------------------------------------------
        _print_header("9. Read resource crm://schema")
        resource_result = await client.read_resource("crm://schema")
        for content in resource_result.contents:
            print(content.text)

        # 10. Sales follow-up prompt --------------------------------------------
        _print_header("10. sales_followup_prompt(customer_id=1, goal=...)")
        prompt_result = await client.get_prompt(
            "sales_followup_prompt",
            {"customer_id": "1", "goal": "Follow up after a product demo"},
        )
        for message in prompt_result.messages:
            print(f"[{message.role}]")
            print(message.content.text)


if __name__ == "__main__":
    asyncio.run(main())
