"""
database.py

SQLite persistence layer for the CRM MCP Server.

This module owns all direct database access:
- connection management
- schema creation
- customer queries and updates
- interaction queries and inserts

No MCP-specific code lives here. Keeping this module independent of the
MCP server makes the business logic easy to unit test and easy to reuse
in other contexts (CLI scripts, other services, etc).

All SQL is parameterized. User-provided values are NEVER concatenated
directly into SQL strings.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Tests override this via the CRM_DB_PATH environment variable so that each
# test run gets an isolated, temporary database file.
DEFAULT_DB_PATH = "crm.db"


def get_db_path() -> str:
    """Return the configured SQLite database path."""
    return os.environ.get("CRM_DB_PATH", DEFAULT_DB_PATH)


# ---------------------------------------------------------------------------
# Domain constants
# ---------------------------------------------------------------------------

ALLOWED_CUSTOMER_STATUSES = ("lead", "prospect", "customer", "inactive")
ALLOWED_INTERACTION_TYPES = ("email", "call", "meeting", "demo", "note")

MAX_NOTE_LENGTH = 2000
MAX_LIMIT = 20
MIN_LIMIT = 1


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------

class CRMValidationError(ValueError):
    """Raised when caller-supplied input fails validation."""


class CustomerNotFoundError(LookupError):
    """Raised when a customer_id does not exist."""


# ---------------------------------------------------------------------------
# Connection management
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@contextmanager
def get_connection(db_path: Optional[str] = None) -> Iterator[sqlite3.Connection]:
    """Yield a SQLite connection with foreign keys enabled and row access by name."""
    path = db_path or get_db_path()
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema creation
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    email TEXT NOT NULL UNIQUE,
    company TEXT NOT NULL,
    country TEXT NOT NULL,
    industry TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('lead', 'prospect', 'customer', 'inactive')),
    created_at TEXT NOT NULL,
    last_contacted_at TEXT
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id INTEGER NOT NULL,
    interaction_type TEXT NOT NULL CHECK (
        interaction_type IN ('email', 'call', 'meeting', 'demo', 'note')
    ),
    note TEXT NOT NULL,
    interaction_date TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (customer_id) REFERENCES customers (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_interactions_customer_id
    ON interactions (customer_id);
"""


def init_db(db_path: Optional[str] = None) -> None:
    """Create the customers/interactions tables if they do not already exist."""
    with get_connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


# ---------------------------------------------------------------------------
# Row -> dict helpers
# ---------------------------------------------------------------------------

def _customer_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "name": row["name"],
        "email": row["email"],
        "company": row["company"],
        "country": row["country"],
        "industry": row["industry"],
        "status": row["status"],
        "created_at": row["created_at"],
        "last_contacted_at": row["last_contacted_at"],
    }


def _interaction_row_to_dict(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "customer_id": row["customer_id"],
        "interaction_type": row["interaction_type"],
        "note": row["note"],
        "interaction_date": row["interaction_date"],
        "created_at": row["created_at"],
    }


# ---------------------------------------------------------------------------
# Customer queries
# ---------------------------------------------------------------------------

def insert_customer(
    name: str,
    email: str,
    company: str,
    country: str,
    industry: str,
    status: str,
    created_at: Optional[str] = None,
    last_contacted_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> int:
    """Insert a customer and return the new customer id."""
    created_at = created_at or _utc_now_iso()
    with get_connection(db_path) as conn:
        cursor = conn.execute(
            """
            INSERT INTO customers
                (name, email, company, country, industry, status, created_at, last_contacted_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (name, email, company, country, industry, status, created_at, last_contacted_at),
        )
        return int(cursor.lastrowid)


def get_customer_by_id(customer_id: int, db_path: Optional[str] = None) -> Optional[dict]:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return _customer_row_to_dict(row) if row else None


def find_customers(
    query: Optional[str] = None,
    status: Optional[str] = None,
    company: Optional[str] = None,
    limit: int = 10,
    db_path: Optional[str] = None,
) -> list[dict]:
    """Search customers by free-text query across name/email/company/industry,
    optionally filtered by exact status and/or company."""
    sql = "SELECT * FROM customers WHERE 1 = 1"
    params: list = []

    if query:
        like = f"%{query}%"
        sql += (
            " AND (name LIKE ? OR email LIKE ? OR company LIKE ? OR industry LIKE ?)"
        )
        params.extend([like, like, like, like])

    if status:
        sql += " AND status = ?"
        params.append(status)

    if company:
        sql += " AND company LIKE ?"
        params.append(f"%{company}%")

    sql += " ORDER BY id ASC LIMIT ?"
    params.append(limit)

    with get_connection(db_path) as conn:
        rows = conn.execute(sql, params).fetchall()
        return [_customer_row_to_dict(row) for row in rows]


def update_customer_status(
    customer_id: int,
    status: str,
    touch_last_contacted: bool = True,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Update a customer's status. Returns the updated customer dict, or None
    if the customer does not exist."""
    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if existing is None:
            return None

        if touch_last_contacted:
            conn.execute(
                "UPDATE customers SET status = ?, last_contacted_at = ? WHERE id = ?",
                (status, _utc_now_iso(), customer_id),
            )
        else:
            conn.execute(
                "UPDATE customers SET status = ? WHERE id = ?",
                (status, customer_id),
            )

        row = conn.execute(
            "SELECT * FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return _customer_row_to_dict(row)


def touch_last_contacted(customer_id: int, when: Optional[str] = None, db_path: Optional[str] = None) -> None:
    with get_connection(db_path) as conn:
        conn.execute(
            "UPDATE customers SET last_contacted_at = ? WHERE id = ?",
            (when or _utc_now_iso(), customer_id),
        )


def count_customers_by_status(db_path: Optional[str] = None) -> dict:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM customers GROUP BY status"
        ).fetchall()
        counts = {status: 0 for status in ALLOWED_CUSTOMER_STATUSES}
        for row in rows:
            counts[row["status"]] = row["n"]
        return counts


# ---------------------------------------------------------------------------
# Interaction queries
# ---------------------------------------------------------------------------

def insert_interaction(
    customer_id: int,
    interaction_type: str,
    note: str,
    interaction_date: Optional[str] = None,
    created_at: Optional[str] = None,
    db_path: Optional[str] = None,
) -> Optional[dict]:
    """Insert an interaction for a customer and bump last_contacted_at.

    Returns the created interaction dict, or None if the customer does not
    exist (caller is responsible for validating first in most call paths,
    but this guards against races)."""
    interaction_date = interaction_date or _utc_now_iso()
    created_at = created_at or _utc_now_iso()

    with get_connection(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        if existing is None:
            return None

        cursor = conn.execute(
            """
            INSERT INTO interactions
                (customer_id, interaction_type, note, interaction_date, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (customer_id, interaction_type, note, interaction_date, created_at),
        )
        interaction_id = int(cursor.lastrowid)

        conn.execute(
            "UPDATE customers SET last_contacted_at = ? WHERE id = ?",
            (interaction_date, customer_id),
        )

        row = conn.execute(
            "SELECT * FROM interactions WHERE id = ?", (interaction_id,)
        ).fetchone()
        return _interaction_row_to_dict(row)


def get_interactions_for_customer(
    customer_id: int, limit: int = 10, db_path: Optional[str] = None
) -> list[dict]:
    with get_connection(db_path) as conn:
        rows = conn.execute(
            """
            SELECT * FROM interactions
            WHERE customer_id = ?
            ORDER BY interaction_date DESC, id DESC
            LIMIT ?
            """,
            (customer_id, limit),
        ).fetchall()
        return [_interaction_row_to_dict(row) for row in rows]


def count_interactions_for_customer(customer_id: int, db_path: Optional[str] = None) -> int:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n FROM interactions WHERE customer_id = ?",
            (customer_id,),
        ).fetchone()
        return int(row["n"])


def customer_exists(customer_id: int, db_path: Optional[str] = None) -> bool:
    with get_connection(db_path) as conn:
        row = conn.execute(
            "SELECT 1 FROM customers WHERE id = ?", (customer_id,)
        ).fetchone()
        return row is not None
