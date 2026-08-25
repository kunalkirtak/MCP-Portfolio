"""
database.py

Reusable SQLite database module for the Database MCP Server.

Responsibilities:
    * database file path
    * connection creation (with foreign keys enabled)
    * schema creation
    * small, safe, parameterized query helpers

This module has NO knowledge of MCP. The MCP server layer (server.py)
calls into these functions. Keeping the two layers separate makes the
database logic independently testable and reusable.

All SQL in this module uses parameterized queries (`?` placeholders).
User-supplied values are NEVER concatenated into SQL strings.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

# Default database file lives next to this module.
DB_PATH = Path(__file__).resolve().parent / "ecommerce.db"

# Business rules enforced at the application layer (and mirrored with
# SQL CHECK constraints at the schema layer).
ALLOWED_SEGMENTS = ("Standard", "Premium", "Enterprise")
ALLOWED_STATUSES = ("pending", "processing", "shipped", "delivered", "cancelled")


# ---------------------------------------------------------------------------
# Connections
# ---------------------------------------------------------------------------

def get_connection(db_path: str | Path = DB_PATH) -> sqlite3.Connection:
    """Create a new SQLite connection with foreign keys enabled.

    Each call returns a fresh connection. Callers are responsible for
    closing it (the `connection()` context manager below does this
    automatically).
    """
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def connection(db_path: str | Path = DB_PATH) -> Iterator[sqlite3.Connection]:
    """Context manager that yields a connection and always closes it.

    Commits on success, rolls back on exception.
    """
    conn = get_connection(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    email       TEXT    NOT NULL UNIQUE,
    country     TEXT    NOT NULL,
    segment     TEXT    NOT NULL CHECK (segment IN ('Standard', 'Premium', 'Enterprise')),
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    category    TEXT    NOT NULL,
    price       REAL    NOT NULL CHECK (price >= 0),
    stock       INTEGER NOT NULL CHECK (stock >= 0)
);

CREATE TABLE IF NOT EXISTS orders (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL,
    order_date    TEXT    NOT NULL,
    status        TEXT    NOT NULL CHECK (
                      status IN ('pending', 'processing', 'shipped', 'delivered', 'cancelled')
                  ),
    total_amount  REAL    NOT NULL CHECK (total_amount >= 0),
    FOREIGN KEY (customer_id) REFERENCES customers (id)
);

CREATE TABLE IF NOT EXISTS order_items (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id    INTEGER NOT NULL,
    product_id  INTEGER NOT NULL,
    quantity    INTEGER NOT NULL CHECK (quantity > 0),
    unit_price  REAL    NOT NULL CHECK (unit_price >= 0),
    FOREIGN KEY (order_id)   REFERENCES orders (id),
    FOREIGN KEY (product_id) REFERENCES products (id)
);

CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders (customer_id);
CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items (order_id);
CREATE INDEX IF NOT EXISTS idx_order_items_product_id ON order_items (product_id);
"""


def init_schema(db_path: str | Path = DB_PATH) -> None:
    """Create all tables (and indexes) if they do not already exist."""
    with connection(db_path) as conn:
        conn.executescript(SCHEMA_SQL)


def reset_schema(db_path: str | Path = DB_PATH) -> None:
    """Drop and recreate all tables. Used to make seeding idempotent."""
    with connection(db_path) as conn:
        conn.executescript(
            """
            DROP TABLE IF EXISTS order_items;
            DROP TABLE IF EXISTS orders;
            DROP TABLE IF EXISTS products;
            DROP TABLE IF EXISTS customers;
            """
        )
        conn.executescript(SCHEMA_SQL)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert a list of sqlite3.Row objects into plain dicts."""
    return [dict(row) for row in rows]


def table_counts(db_path: str | Path = DB_PATH) -> dict[str, int]:
    """Return row counts for every table. Useful for seeding summaries/tests."""
    counts: dict[str, int] = {}
    with connection(db_path) as conn:
        for table in ("customers", "products", "orders", "order_items"):
            cur = conn.execute(f"SELECT COUNT(*) AS n FROM {table}")
            counts[table] = cur.fetchone()["n"]
    return counts


# ---------------------------------------------------------------------------
# Insert helpers (used by seed_database.py)
# ---------------------------------------------------------------------------

def insert_customer(
    conn: sqlite3.Connection,
    name: str,
    email: str,
    country: str,
    segment: str,
    created_at: str,
) -> int:
    """Insert a customer row using a parameterized query. Returns new id."""
    if segment not in ALLOWED_SEGMENTS:
        raise ValueError(f"Invalid segment: {segment!r}")
    cur = conn.execute(
        """
        INSERT INTO customers (name, email, country, segment, created_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (name, email, country, segment, created_at),
    )
    return int(cur.lastrowid)


def insert_product(
    conn: sqlite3.Connection,
    name: str,
    category: str,
    price: float,
    stock: int,
) -> int:
    """Insert a product row using a parameterized query. Returns new id."""
    cur = conn.execute(
        "INSERT INTO products (name, category, price, stock) VALUES (?, ?, ?, ?)",
        (name, category, price, stock),
    )
    return int(cur.lastrowid)


def insert_order(
    conn: sqlite3.Connection,
    customer_id: int,
    order_date: str,
    status: str,
    total_amount: float,
) -> int:
    """Insert an order row using a parameterized query. Returns new id."""
    if status not in ALLOWED_STATUSES:
        raise ValueError(f"Invalid status: {status!r}")
    cur = conn.execute(
        """
        INSERT INTO orders (customer_id, order_date, status, total_amount)
        VALUES (?, ?, ?, ?)
        """,
        (customer_id, order_date, status, total_amount),
    )
    return int(cur.lastrowid)


def insert_order_item(
    conn: sqlite3.Connection,
    order_id: int,
    product_id: int,
    quantity: int,
    unit_price: float,
) -> int:
    """Insert an order_item row using a parameterized query. Returns new id."""
    cur = conn.execute(
        """
        INSERT INTO order_items (order_id, product_id, quantity, unit_price)
        VALUES (?, ?, ?, ?)
        """,
        (order_id, product_id, quantity, unit_price),
    )
    return int(cur.lastrowid)


# ---------------------------------------------------------------------------
# Read helpers (used by server.py tools/resources)
# ---------------------------------------------------------------------------

def query_customers(
    db_path: str | Path,
    name: str | None = None,
    country: str | None = None,
    segment: str | None = None,
    limit: int = 10,
) -> list[dict[str, Any]]:
    """Search customers with optional, safely-parameterized filters."""
    clauses: list[str] = []
    params: list[Any] = []

    if name:
        clauses.append("name LIKE ?")
        params.append(f"%{name}%")
    if country:
        clauses.append("country = ?")
        params.append(country)
    if segment:
        clauses.append("segment = ?")
        params.append(segment)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT id, name, email, country, segment, created_at
        FROM customers
        {where_sql}
        ORDER BY id
        LIMIT ?
    """
    params.append(limit)

    with connection(db_path) as conn:
        cur = conn.execute(sql, params)
        return rows_to_dicts(cur.fetchall())


def get_customer_by_id(db_path: str | Path, customer_id: int) -> dict[str, Any] | None:
    """Fetch a single customer row by id, or None if not found."""
    with connection(db_path) as conn:
        cur = conn.execute(
            "SELECT id, name, email, country, segment, created_at "
            "FROM customers WHERE id = ?",
            (customer_id,),
        )
        row = cur.fetchone()
        return dict(row) if row else None


def customer_order_summary(db_path: str | Path, customer_id: int) -> dict[str, Any] | None:
    """Return order analytics for a single customer, or None if the
    customer does not exist."""
    customer = get_customer_by_id(db_path, customer_id)
    if customer is None:
        return None

    with connection(db_path) as conn:
        agg = conn.execute(
            """
            SELECT
                COUNT(*)                AS order_count,
                COALESCE(SUM(total_amount), 0.0)  AS total_spent,
                COALESCE(AVG(total_amount), 0.0)  AS average_order_value,
                MAX(order_date)         AS last_order_date
            FROM orders
            WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()

        status_rows = conn.execute(
            """
            SELECT status, COUNT(*) AS n
            FROM orders
            WHERE customer_id = ?
            GROUP BY status
            """,
            (customer_id,),
        ).fetchall()

    status_breakdown = {row["status"]: row["n"] for row in status_rows}

    return {
        "customer": customer,
        "order_count": agg["order_count"],
        "total_spent": round(agg["total_spent"], 2),
        "average_order_value": round(agg["average_order_value"], 2),
        "last_order_date": agg["last_order_date"],
        "status_breakdown": status_breakdown,
    }


def top_products(
    db_path: str | Path,
    limit: int = 5,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """Return the highest-revenue products, optionally filtered by category."""
    clauses: list[str] = []
    params: list[Any] = []

    if category:
        clauses.append("p.category = ?")
        params.append(category)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT
            p.id                                   AS product_id,
            p.name                                  AS product_name,
            p.category                              AS category,
            COALESCE(SUM(oi.quantity), 0)           AS units_sold,
            COALESCE(SUM(oi.quantity * oi.unit_price), 0.0) AS revenue
        FROM products p
        LEFT JOIN order_items oi ON oi.product_id = p.id
        LEFT JOIN orders o ON o.id = oi.order_id AND o.status != 'cancelled'
        {where_sql}
        GROUP BY p.id
        ORDER BY revenue DESC, units_sold DESC
        LIMIT ?
    """
    params.append(limit)

    with connection(db_path) as conn:
        cur = conn.execute(sql, params)
        rows = rows_to_dicts(cur.fetchall())

    for row in rows:
        row["revenue"] = round(row["revenue"], 2)
    return rows


def sales_summary(
    db_path: str | Path,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    """Return overall business analytics, optionally scoped to a date range."""
    clauses: list[str] = []
    params: list[Any] = []

    if start_date:
        clauses.append("order_date >= ?")
        params.append(start_date)
    if end_date:
        clauses.append("order_date <= ?")
        params.append(end_date)

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""

    with connection(db_path) as conn:
        agg = conn.execute(
            f"""
            SELECT
                COUNT(*)                                            AS total_orders,
                COALESCE(SUM(total_amount), 0.0)                    AS total_revenue,
                COALESCE(AVG(total_amount), 0.0)                    AS average_order_value,
                COUNT(DISTINCT customer_id)                         AS unique_customers,
                SUM(CASE WHEN status = 'cancelled' THEN 1 ELSE 0 END) AS cancelled_orders
            FROM orders
            {where_sql}
            """,
            params,
        ).fetchone()

        top_category_row = conn.execute(
            f"""
            SELECT p.category AS category, SUM(oi.quantity * oi.unit_price) AS revenue
            FROM order_items oi
            JOIN orders o ON o.id = oi.order_id
            JOIN products p ON p.id = oi.product_id
            {where_sql.replace("order_date", "o.order_date") if where_sql else ""}
            GROUP BY p.category
            ORDER BY revenue DESC
            LIMIT 1
            """,
            params,
        ).fetchone()

    return {
        "total_orders": agg["total_orders"],
        "total_revenue": round(agg["total_revenue"], 2),
        "average_order_value": round(agg["average_order_value"], 2),
        "unique_customers": agg["unique_customers"],
        "cancelled_orders": agg["cancelled_orders"] or 0,
        "top_category": top_category_row["category"] if top_category_row else None,
    }


def order_status_summary(db_path: str | Path) -> dict[str, int]:
    """Return a count of orders grouped by status.

    All known statuses are always present in the result (defaulting to 0)
    so downstream consumers get a predictable, complete shape.
    """
    counts = {status: 0 for status in ALLOWED_STATUSES}
    with connection(db_path) as conn:
        rows = conn.execute(
            "SELECT status, COUNT(*) AS n FROM orders GROUP BY status"
        ).fetchall()
    for row in rows:
        counts[row["status"]] = row["n"]
    return counts


def customer_context(db_path: str | Path, customer_id: int) -> dict[str, Any] | None:
    """Return a readable context bundle for a single customer: profile,
    order stats, and recent orders. Used by the dynamic MCP resource."""
    customer = get_customer_by_id(db_path, customer_id)
    if customer is None:
        return None

    with connection(db_path) as conn:
        agg = conn.execute(
            """
            SELECT COUNT(*) AS order_count, COALESCE(SUM(total_amount), 0.0) AS total_spent
            FROM orders WHERE customer_id = ?
            """,
            (customer_id,),
        ).fetchone()

        recent_orders = conn.execute(
            """
            SELECT id, order_date, status, total_amount
            FROM orders
            WHERE customer_id = ?
            ORDER BY order_date DESC
            LIMIT 5
            """,
            (customer_id,),
        ).fetchall()

    return {
        "customer": customer,
        "order_count": agg["order_count"],
        "total_spent": round(agg["total_spent"], 2),
        "recent_orders": rows_to_dicts(recent_orders),
    }
