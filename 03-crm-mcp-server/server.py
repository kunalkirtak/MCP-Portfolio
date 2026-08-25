"""
server.py

CRM MCP Server.

Exposes a small, realistic CRM (customers + interactions, backed by SQLite)
to an AI agent through the Model Context Protocol.

Design principle — agent safety:
    This server deliberately does NOT expose raw SQL, a generic
    "update anything" tool, or delete operations. Every write path is a
    narrowly scoped, validated, explicit business operation:

        find_customers            (read)
        get_customer               (read)
        update_customer_status     (write — status only)
        add_interaction            (write — append-only)
        get_interactions           (read)
        customer_pipeline_summary  (read)

    An AI agent can only do what these six operations allow. It cannot run
    arbitrary queries or mutate arbitrary fields.

Data flow:

    AI Agent
       | structured MCP tool call
       v
    Validation
       |
       v
    Explicit CRM Operation (this file)
       |
       v
    Parameterized SQL (database.py)
       |
       v
    SQLite
"""

from __future__ import annotations

from typing import Optional

from mcp.server import MCPServer

import database as db

mcp_server = MCPServer(
    name="crm-mcp-server",
    instructions=(
        "Tools for interacting with a small CRM system: search and read "
        "customer records, update customer status, log interactions, and "
        "view a pipeline summary. Read the crm://schema resource first if "
        "you are unsure what data is available."
    ),
)


# ---------------------------------------------------------------------------
# Shared validation helpers
# ---------------------------------------------------------------------------

def _validate_customer_id(customer_id: int) -> str | None:
    if not isinstance(customer_id, int) or isinstance(customer_id, bool) or customer_id <= 0:
        return "customer_id must be a positive integer."
    return None


def _validate_status(status: str) -> str | None:
    if status not in db.ALLOWED_CUSTOMER_STATUSES:
        allowed = ", ".join(db.ALLOWED_CUSTOMER_STATUSES)
        return f"Invalid status '{status}'. Allowed values: {allowed}."
    return None


def _validate_interaction_type(interaction_type: str) -> str | None:
    if interaction_type not in db.ALLOWED_INTERACTION_TYPES:
        allowed = ", ".join(db.ALLOWED_INTERACTION_TYPES)
        return f"Invalid interaction_type '{interaction_type}'. Allowed values: {allowed}."
    return None


def _validate_note(note: str) -> str | None:
    if not note or not note.strip():
        return "note must not be empty."
    if len(note) > db.MAX_NOTE_LENGTH:
        return f"note is too long ({len(note)} characters). Maximum is {db.MAX_NOTE_LENGTH}."
    return None


def _validate_limit(limit: int) -> str | None:
    if not isinstance(limit, int) or isinstance(limit, bool):
        return "limit must be an integer."
    if not (db.MIN_LIMIT <= limit <= db.MAX_LIMIT):
        return f"limit must be between {db.MIN_LIMIT} and {db.MAX_LIMIT}."
    return None


# ---------------------------------------------------------------------------
# Tool 1 — find_customers
# ---------------------------------------------------------------------------

@mcp_server.tool()
def find_customers(
    query: Optional[str] = None,
    status: Optional[str] = None,
    company: Optional[str] = None,
    limit: int = 10,
) -> dict:
    """Search CRM customers by free-text query and/or filters.

    query searches across name, email, company, and industry.
    status must be one of: lead, prospect, customer, inactive (optional).
    company filters to customers whose company name contains this text (optional).
    limit must be between 1 and 20 (default 10).
    """
    error = _validate_limit(limit)
    if error:
        return {"error": error}

    if status:
        error = _validate_status(status)
        if error:
            return {"error": error}

    results = db.find_customers(
        query=query or None,
        status=status or None,
        company=company or None,
        limit=limit,
    )
    return {"count": len(results), "customers": results}


# ---------------------------------------------------------------------------
# Tool 2 — get_customer
# ---------------------------------------------------------------------------

@mcp_server.tool()
def get_customer(customer_id: int) -> dict:
    """Retrieve full CRM information for one customer: profile, interaction
    count, and recent interaction history."""
    error = _validate_customer_id(customer_id)
    if error:
        return {"error": error}

    customer = db.get_customer_by_id(customer_id)
    if customer is None:
        return {"error": f"No customer found with id {customer_id}."}

    interaction_count = db.count_interactions_for_customer(customer_id)
    recent_interactions = db.get_interactions_for_customer(customer_id, limit=5)

    return {
        "customer": customer,
        "interaction_count": interaction_count,
        "recent_interactions": recent_interactions,
    }


# ---------------------------------------------------------------------------
# Tool 3 — update_customer_status
# ---------------------------------------------------------------------------

@mcp_server.tool()
def update_customer_status(customer_id: int, status: str) -> dict:
    """Change a customer's CRM status.

    This is the ONLY way to modify a customer record through this server —
    there is intentionally no generic "update customer fields" tool.

    status must be one of: lead, prospect, customer, inactive.
    """
    error = _validate_customer_id(customer_id)
    if error:
        return {"error": error}

    error = _validate_status(status)
    if error:
        return {"error": error}

    if not db.customer_exists(customer_id):
        return {"error": f"No customer found with id {customer_id}."}

    updated = db.update_customer_status(customer_id, status, touch_last_contacted=True)
    return {"customer": updated}


# ---------------------------------------------------------------------------
# Tool 4 — add_interaction
# ---------------------------------------------------------------------------

@mcp_server.tool()
def add_interaction(customer_id: int, interaction_type: str, note: str) -> dict:
    """Record a CRM interaction (email, call, meeting, demo, or note) for a
    customer. Automatically updates the customer's last_contacted_at.

    interaction_type must be one of: email, call, meeting, demo, note.
    note must be non-empty and no longer than 2000 characters.
    """
    error = _validate_customer_id(customer_id)
    if error:
        return {"error": error}

    error = _validate_interaction_type(interaction_type)
    if error:
        return {"error": error}

    error = _validate_note(note)
    if error:
        return {"error": error}

    if not db.customer_exists(customer_id):
        return {"error": f"No customer found with id {customer_id}."}

    interaction = db.insert_interaction(
        customer_id=customer_id,
        interaction_type=interaction_type,
        note=note,
    )
    if interaction is None:
        return {"error": f"No customer found with id {customer_id}."}

    return {"interaction": interaction}


# ---------------------------------------------------------------------------
# Tool 5 — get_interactions
# ---------------------------------------------------------------------------

@mcp_server.tool()
def get_interactions(customer_id: int, limit: int = 10) -> dict:
    """Retrieve a customer's interaction history, newest first.

    limit must be between 1 and 20 (default 10).
    """
    error = _validate_customer_id(customer_id)
    if error:
        return {"error": error}

    error = _validate_limit(limit)
    if error:
        return {"error": error}

    if not db.customer_exists(customer_id):
        return {"error": f"No customer found with id {customer_id}."}

    interactions = db.get_interactions_for_customer(customer_id, limit=limit)
    return {"customer_id": customer_id, "count": len(interactions), "interactions": interactions}


# ---------------------------------------------------------------------------
# Tool 6 — customer_pipeline_summary
# ---------------------------------------------------------------------------

@mcp_server.tool()
def customer_pipeline_summary() -> dict:
    """Provide a high-level summary of the CRM pipeline: counts by status
    and a simple lead-to-customer conversion rate."""
    counts = db.count_customers_by_status()
    total = sum(counts.values())

    lead_count = counts.get("lead", 0)
    prospect_count = counts.get("prospect", 0)
    customer_count = counts.get("customer", 0)
    inactive_count = counts.get("inactive", 0)

    if total == 0:
        conversion_rate = None
        conversion_note = "No customers in the CRM yet; conversion rate is undefined."
    else:
        conversion_rate = round(customer_count / total, 4)
        conversion_note = (
            "conversion_rate = customer_count / total_customers. This is a simple "
            "overall snapshot, not a cohort-based or time-windowed conversion metric."
        )

    return {
        "lead_count": lead_count,
        "prospect_count": prospect_count,
        "customer_count": customer_count,
        "inactive_count": inactive_count,
        "total_customers": total,
        "conversion_rate": conversion_rate,
        "conversion_rate_explanation": conversion_note,
    }


# ---------------------------------------------------------------------------
# Resource 1 — customer context
# ---------------------------------------------------------------------------

@mcp_server.resource("crm://customer/{customer_id}")
def customer_context(customer_id: str) -> str:
    """Human-readable customer profile and recent activity, for an agent to
    read as context before taking an action."""
    try:
        cid = int(customer_id)
    except (TypeError, ValueError):
        return f"Invalid customer id: {customer_id!r}"

    customer = db.get_customer_by_id(cid)
    if customer is None:
        return f"No customer found with id {cid}."

    interaction_count = db.count_interactions_for_customer(cid)
    recent = db.get_interactions_for_customer(cid, limit=5)

    lines = [
        f"Customer: {customer['name']} ({customer['email']})",
        f"Company: {customer['company']}",
        f"Industry: {customer['industry']}",
        f"Country: {customer['country']}",
        f"Status: {customer['status']}",
        f"Last contacted: {customer['last_contacted_at'] or 'Never'}",
        f"Interaction count: {interaction_count}",
        "",
        "Recent interactions:",
    ]
    if recent:
        for interaction in recent:
            lines.append(
                f"  - [{interaction['interaction_date']}] "
                f"{interaction['interaction_type']}: {interaction['note']}"
            )
    else:
        lines.append("  (none recorded)")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Resource 2 — CRM schema
# ---------------------------------------------------------------------------

@mcp_server.resource("crm://schema")
def crm_schema() -> str:
    """Static description of the CRM database schema and business rules."""
    return f"""CRM Database Schema
====================

customers
---------
  id                  INTEGER, primary key
  name                TEXT
  email               TEXT, unique
  company             TEXT
  country             TEXT
  industry            TEXT
  status              TEXT, one of: {", ".join(db.ALLOWED_CUSTOMER_STATUSES)}
  created_at          TEXT (ISO 8601 timestamp)
  last_contacted_at   TEXT (ISO 8601 timestamp, nullable)

interactions
------------
  id                  INTEGER, primary key
  customer_id         INTEGER, foreign key -> customers.id
  interaction_type    TEXT, one of: {", ".join(db.ALLOWED_INTERACTION_TYPES)}
  note                TEXT (max {db.MAX_NOTE_LENGTH} characters)
  interaction_date    TEXT (ISO 8601 timestamp)
  created_at          TEXT (ISO 8601 timestamp)

Relationship
------------
  One customer has many interactions (interactions.customer_id -> customers.id).
  Deleting a customer cascades to their interactions.

Allowed customer statuses
--------------------------
  {", ".join(db.ALLOWED_CUSTOMER_STATUSES)}

Allowed interaction types
--------------------------
  {", ".join(db.ALLOWED_INTERACTION_TYPES)}
"""


# ---------------------------------------------------------------------------
# Prompt — sales_followup_prompt
# ---------------------------------------------------------------------------

@mcp_server.prompt()
def sales_followup_prompt(customer_id: str, goal: str) -> str:
    """Generate a structured instruction for an AI agent to prepare a sales
    follow-up for a specific customer and goal. Does not call an LLM itself —
    it only produces the instruction text for the agent to act on."""
    return f"""You are preparing a sales follow-up for customer_id={customer_id}.

Goal: {goal}

Follow these steps:
1. Retrieve the customer's context using the get_customer tool or the
   crm://customer/{customer_id} resource.
2. Inspect their recent interactions to understand what has already been
   discussed or promised.
3. Re-read the stated goal above and identify what outcome is wanted from
   this follow-up.
4. Decide which pieces of the customer's context are actually relevant to
   this goal — do not include unrelated details.
5. Draft a follow-up message (email or call notes) that is concise,
   specific to this customer's situation, and moves toward the stated goal.
6. Do not invent facts about the customer, their company, or prior
   conversations that are not present in the retrieved CRM data.
"""
