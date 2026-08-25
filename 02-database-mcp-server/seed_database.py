"""
seed_database.py

Creates the SQLite database (if needed), (re)creates the schema, and
inserts a deterministic set of sample e-commerce data:

    * 20 customers  (multiple countries, multiple segments)
    * 10 products   (multiple categories)
    * 40 orders     (multiple statuses, spread across dates)
    * order_items for every order

Running this script is always safe: it resets the schema first, so
re-running it never creates duplicate data.

Usage:
    python seed_database.py
"""

from __future__ import annotations

import database as db


# ---------------------------------------------------------------------------
# Deterministic seed data
# ---------------------------------------------------------------------------
# Everything below is hard-coded (not randomly generated) so that the
# database — and therefore the tests and the demo output — is identical
# on every run.

CUSTOMERS = [
    # (name, email, country, segment, created_at)
    ("Alice Johnson", "alice.johnson@example.com", "USA", "Premium", "2023-01-05"),
    ("Bruno Silva", "bruno.silva@example.com", "Brazil", "Standard", "2023-01-12"),
    ("Chen Wei", "chen.wei@example.com", "China", "Enterprise", "2023-01-20"),
    ("Diana Kovacs", "diana.kovacs@example.com", "Hungary", "Standard", "2023-02-02"),
    ("Ethan Brown", "ethan.brown@example.com", "USA", "Standard", "2023-02-10"),
    ("Fatima Al-Sayed", "fatima.alsayed@example.com", "UAE", "Premium", "2023-02-18"),
    ("George Papadopoulos", "george.p@example.com", "Greece", "Standard", "2023-03-01"),
    ("Hannah Schmidt", "hannah.schmidt@example.com", "Germany", "Premium", "2023-03-09"),
    ("Ivan Petrov", "ivan.petrov@example.com", "Russia", "Standard", "2023-03-15"),
    ("Julia Nowak", "julia.nowak@example.com", "Poland", "Standard", "2023-03-22"),
    ("Kenji Yamamoto", "kenji.yamamoto@example.com", "Japan", "Enterprise", "2023-04-01"),
    ("Laura Martinez", "laura.martinez@example.com", "Mexico", "Standard", "2023-04-08"),
    ("Mohammed Khan", "mohammed.khan@example.com", "Pakistan", "Standard", "2023-04-16"),
    ("Nora Andersen", "nora.andersen@example.com", "Denmark", "Premium", "2023-04-25"),
    ("Oliver Smith", "oliver.smith@example.com", "UK", "Standard", "2023-05-03"),
    ("Priya Sharma", "priya.sharma@example.com", "India", "Enterprise", "2023-05-11"),
    ("Quinn O'Brien", "quinn.obrien@example.com", "Ireland", "Standard", "2023-05-19"),
    ("Rosa Fernandez", "rosa.fernandez@example.com", "Spain", "Premium", "2023-05-27"),
    ("Samuel Osei", "samuel.osei@example.com", "Ghana", "Standard", "2023-06-04"),
    ("Tina Nguyen", "tina.nguyen@example.com", "Vietnam", "Standard", "2023-06-12"),
]

PRODUCTS = [
    # (name, category, price, stock)
    ("Wireless Mouse", "Electronics", 24.99, 150),
    ("Mechanical Keyboard", "Electronics", 79.99, 90),
    ("USB-C Hub", "Electronics", 34.50, 120),
    ("Noise Cancelling Headphones", "Electronics", 159.99, 60),
    ("Standing Desk", "Furniture", 349.00, 25),
    ("Ergonomic Office Chair", "Furniture", 219.00, 40),
    ("Stainless Steel Water Bottle", "Home & Kitchen", 18.75, 200),
    ("Ceramic Coffee Mug Set", "Home & Kitchen", 22.00, 180),
    ("Running Shoes", "Apparel", 89.99, 75),
    ("Fleece Jacket", "Apparel", 64.50, 100),
]

# (customer_index[1-based], order_date, status, item list)
# item list entries: (product_index[1-based], quantity)
ORDERS: list[tuple[int, str, str, list[tuple[int, int]]]] = [
    (1, "2023-06-01", "delivered", [(1, 2), (3, 1)]),
    (2, "2023-06-02", "delivered", [(7, 3)]),
    (3, "2023-06-03", "delivered", [(5, 1), (6, 1)]),
    (4, "2023-06-04", "cancelled", [(9, 1)]),
    (5, "2023-06-05", "delivered", [(2, 1)]),
    (6, "2023-06-06", "shipped", [(4, 1), (1, 1)]),
    (7, "2023-06-07", "delivered", [(8, 2)]),
    (8, "2023-06-08", "delivered", [(6, 1), (5, 1)]),
    (9, "2023-06-09", "pending", [(10, 1)]),
    (10, "2023-06-10", "delivered", [(7, 1), (8, 1)]),
    (1, "2023-06-12", "delivered", [(4, 1)]),
    (11, "2023-06-13", "delivered", [(5, 2), (6, 2)]),
    (12, "2023-06-14", "processing", [(9, 1), (10, 1)]),
    (13, "2023-06-15", "delivered", [(2, 1), (3, 1)]),
    (14, "2023-06-16", "delivered", [(4, 1)]),
    (15, "2023-06-17", "shipped", [(1, 3)]),
    (16, "2023-06-18", "delivered", [(6, 1)]),
    (17, "2023-06-19", "delivered", [(7, 2), (8, 2)]),
    (18, "2023-06-20", "delivered", [(4, 1), (2, 1)]),
    (19, "2023-06-21", "cancelled", [(9, 1)]),
    (20, "2023-06-22", "delivered", [(10, 1), (9, 1)]),
    (2, "2023-06-24", "delivered", [(3, 2)]),
    (3, "2023-06-25", "delivered", [(5, 1)]),
    (6, "2023-06-26", "pending", [(1, 1), (2, 1)]),
    (8, "2023-06-27", "delivered", [(4, 2)]),
    (11, "2023-06-28", "delivered", [(6, 1), (7, 1)]),
    (14, "2023-06-29", "shipped", [(8, 1)]),
    (16, "2023-06-30", "delivered", [(9, 2)]),
    (1, "2023-07-01", "delivered", [(10, 1)]),
    (5, "2023-07-02", "delivered", [(1, 1), (4, 1)]),
    (7, "2023-07-03", "processing", [(2, 2)]),
    (9, "2023-07-04", "delivered", [(3, 1), (5, 1)]),
    (10, "2023-07-05", "delivered", [(6, 2)]),
    (12, "2023-07-06", "delivered", [(7, 1)]),
    (13, "2023-07-07", "cancelled", [(8, 1)]),
    (15, "2023-07-08", "delivered", [(9, 1), (10, 1)]),
    (17, "2023-07-09", "delivered", [(1, 2)]),
    (18, "2023-07-10", "pending", [(2, 1)]),
    (19, "2023-07-11", "delivered", [(3, 1), (4, 1)]),
    (20, "2023-07-12", "delivered", [(5, 1), (6, 1)]),
]


def seed(db_path=db.DB_PATH) -> dict[str, int]:
    """Reset the schema and insert deterministic sample data.

    Returns the resulting table row counts.
    """
    db.reset_schema(db_path)

    with db.connection(db_path) as conn:
        customer_ids: list[int] = []
        for name, email, country, segment, created_at in CUSTOMERS:
            cid = db.insert_customer(conn, name, email, country, segment, created_at)
            customer_ids.append(cid)

        product_ids: list[int] = []
        for name, category, price, stock in PRODUCTS:
            pid = db.insert_product(conn, name, category, price, stock)
            product_ids.append(pid)

        product_price_by_id = dict(zip(product_ids, (p[2] for p in PRODUCTS)))

        for customer_idx, order_date, status, items in ORDERS:
            customer_id = customer_ids[customer_idx - 1]

            total_amount = 0.0
            for product_idx, quantity in items:
                unit_price = PRODUCTS[product_idx - 1][2]
                total_amount += unit_price * quantity
            total_amount = round(total_amount, 2)

            order_id = db.insert_order(conn, customer_id, order_date, status, total_amount)

            for product_idx, quantity in items:
                product_id = product_ids[product_idx - 1]
                unit_price = product_price_by_id[product_id]
                db.insert_order_item(conn, order_id, product_id, quantity, unit_price)

    return db.table_counts(db_path)


def main() -> None:
    counts = seed()
    print("Database initialized successfully.\n")
    print(f"Customers:    {counts['customers']}")
    print(f"Products:     {counts['products']}")
    print(f"Orders:       {counts['orders']}")
    print(f"Order Items:  {counts['order_items']}")
    print(f"\nDatabase file: {db.DB_PATH}")


if __name__ == "__main__":
    main()
