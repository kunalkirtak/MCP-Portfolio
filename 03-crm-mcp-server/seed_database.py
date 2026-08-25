"""
seed_database.py

Creates the CRM SQLite database (if needed) and populates it with a fixed,
deterministic set of sample customers and interactions.

Running this script multiple times is safe: it checks whether data already
exists before inserting, so it will not create duplicate records.

Usage:
    python seed_database.py
"""

from __future__ import annotations

import database as db

# ---------------------------------------------------------------------------
# Deterministic seed data
# ---------------------------------------------------------------------------
# Fixed timestamps (no datetime.now()) so the seeded data — and therefore
# any tests that depend on it — is identical on every run.

CUSTOMERS = [
    # (name, email, company, country, industry, status, created_at, last_contacted_at)
    ("Aarav Sharma", "aarav.sharma@nimbuslogix.com", "Nimbus Logix", "India", "Logistics", "customer", "2025-01-05T09:00:00+00:00", "2025-06-10T11:30:00+00:00"),
    ("Meera Iyer", "meera.iyer@brightfin.com", "BrightFin", "India", "Fintech", "customer", "2025-01-08T09:00:00+00:00", "2025-06-02T14:00:00+00:00"),
    ("Rohan Verma", "rohan.verma@cropsense.io", "CropSense", "India", "AgriTech", "prospect", "2025-01-12T09:00:00+00:00", "2025-05-20T10:00:00+00:00"),
    ("Ananya Rao", "ananya.rao@healwell.com", "HealWell", "India", "Healthcare", "lead", "2025-01-15T09:00:00+00:00", None),
    ("Kabir Malhotra", "kabir.malhotra@edulaunch.com", "EduLaunch", "India", "EdTech", "prospect", "2025-01-18T09:00:00+00:00", "2025-05-28T09:15:00+00:00"),
    ("Diya Patel", "diya.patel@greenwatt.com", "GreenWatt Energy", "India", "Renewable Energy", "customer", "2025-01-20T09:00:00+00:00", "2025-06-15T16:00:00+00:00"),
    ("Vivaan Nair", "vivaan.nair@stackforge.dev", "StackForge", "India", "Software", "customer", "2025-01-22T09:00:00+00:00", "2025-06-01T12:00:00+00:00"),
    ("Ishita Desai", "ishita.desai@retailyze.com", "Retailyze", "India", "Retail Tech", "inactive", "2025-01-25T09:00:00+00:00", "2025-03-02T09:00:00+00:00"),
    ("Arjun Kapoor", "arjun.kapoor@medicore.com", "MediCore", "India", "Healthcare", "lead", "2025-01-28T09:00:00+00:00", None),
    ("Sanya Chatterjee", "sanya.chatterjee@fleetwise.io", "FleetWise", "India", "Logistics", "prospect", "2025-02-01T09:00:00+00:00", "2025-05-18T13:00:00+00:00"),
    ("Dev Joshi", "dev.joshi@quantifyhr.com", "QuantifyHR", "India", "HR Tech", "customer", "2025-02-04T09:00:00+00:00", "2025-06-05T10:30:00+00:00"),
    ("Priya Menon", "priya.menon@sunrisecapital.com", "Sunrise Capital", "India", "Financial Services", "inactive", "2025-02-07T09:00:00+00:00", "2025-02-20T09:00:00+00:00"),
    ("Karan Bhatt", "karan.bhatt@urbanfresh.com", "UrbanFresh", "India", "FoodTech", "lead", "2025-02-10T09:00:00+00:00", None),
    ("Neha Gupta", "neha.gupta@cloudscribe.io", "CloudScribe", "India", "SaaS", "prospect", "2025-02-13T09:00:00+00:00", "2025-05-25T15:00:00+00:00"),
    ("Aditya Singh", "aditya.singh@voltrix.com", "Voltrix Motors", "India", "Electric Vehicles", "customer", "2025-02-16T09:00:00+00:00", "2025-06-12T11:00:00+00:00"),
    ("Tanvi Reddy", "tanvi.reddy@pixelcraft.studio", "PixelCraft Studio", "India", "Design", "lead", "2025-02-19T09:00:00+00:00", None),
    ("Yash Trivedi", "yash.trivedi@securenet.io", "SecureNet", "India", "Cybersecurity", "prospect", "2025-02-22T09:00:00+00:00", "2025-05-30T10:00:00+00:00"),
    ("Riya Kulkarni", "riya.kulkarni@wanderloop.com", "WanderLoop", "India", "Travel Tech", "inactive", "2025-02-25T09:00:00+00:00", "2025-03-15T09:00:00+00:00"),
    ("Om Prakash", "om.prakash@buildright.com", "BuildRight", "India", "Construction Tech", "customer", "2025-02-28T09:00:00+00:00", "2025-06-08T14:30:00+00:00"),
    ("Zara Khan", "zara.khan@artisanloom.com", "Artisan Loom", "India", "E-commerce", "lead", "2025-03-03T09:00:00+00:00", None),
]

# (customer_email, interaction_type, note, interaction_date)
INTERACTIONS = [
    ("aarav.sharma@nimbuslogix.com", "call", "Discussed renewal terms for the logistics tracking module.", "2025-06-10T11:30:00+00:00"),
    ("aarav.sharma@nimbuslogix.com", "email", "Sent updated pricing sheet after the renewal call.", "2025-06-05T09:00:00+00:00"),
    ("aarav.sharma@nimbuslogix.com", "meeting", "Quarterly business review with the ops team.", "2025-04-14T10:00:00+00:00"),

    ("meera.iyer@brightfin.com", "demo", "Walked through the fraud-detection dashboard with the compliance lead.", "2025-06-02T14:00:00+00:00"),
    ("meera.iyer@brightfin.com", "call", "Follow-up call to answer questions about API rate limits.", "2025-05-20T11:00:00+00:00"),

    ("rohan.verma@cropsense.io", "meeting", "In-person meeting to scope a pilot for soil-sensor integration.", "2025-05-20T10:00:00+00:00"),
    ("rohan.verma@cropsense.io", "email", "Sent pilot proposal document for review.", "2025-05-10T09:00:00+00:00"),

    ("kabir.malhotra@edulaunch.com", "demo", "Product demo focused on the course-authoring tools.", "2025-05-28T09:15:00+00:00"),
    ("kabir.malhotra@edulaunch.com", "note", "Prospect mentioned budget approval expected next quarter.", "2025-05-29T09:00:00+00:00"),

    ("diya.patel@greenwatt.com", "call", "Annual contract review, confirmed continued usage.", "2025-06-15T16:00:00+00:00"),
    ("diya.patel@greenwatt.com", "email", "Sent updated SLA documentation.", "2025-06-16T09:00:00+00:00"),
    ("diya.patel@greenwatt.com", "meeting", "Onsite visit to review energy-monitoring dashboard usage.", "2025-03-10T10:00:00+00:00"),

    ("vivaan.nair@stackforge.dev", "email", "Shared new API documentation for the webhook integration.", "2025-06-01T12:00:00+00:00"),
    ("vivaan.nair@stackforge.dev", "call", "Support call regarding webhook delivery delays.", "2025-05-15T13:00:00+00:00"),

    ("ishita.desai@retailyze.com", "note", "Account marked inactive after contract lapsed.", "2025-03-02T09:00:00+00:00"),

    ("sanya.chatterjee@fleetwise.io", "meeting", "Discovery meeting covering fleet-tracking requirements.", "2025-05-18T13:00:00+00:00"),
    ("sanya.chatterjee@fleetwise.io", "email", "Sent case study from a similar logistics customer.", "2025-05-08T09:00:00+00:00"),

    ("dev.joshi@quantifyhr.com", "call", "Renewal call, customer requested an additional seat license.", "2025-06-05T10:30:00+00:00"),
    ("dev.joshi@quantifyhr.com", "email", "Sent invoice for the additional seat license.", "2025-06-06T09:00:00+00:00"),
    ("dev.joshi@quantifyhr.com", "demo", "Demoed the new performance-review module.", "2025-04-02T11:00:00+00:00"),

    ("priya.menon@sunrisecapital.com", "note", "Account marked inactive after budget was cut.", "2025-02-20T09:00:00+00:00"),

    ("neha.gupta@cloudscribe.io", "demo", "Demo of the collaborative editing features.", "2025-05-25T15:00:00+00:00"),
    ("neha.gupta@cloudscribe.io", "email", "Sent trial extension confirmation.", "2025-05-26T09:00:00+00:00"),

    ("aditya.singh@voltrix.com", "meeting", "Strategic review of the fleet-charging analytics rollout.", "2025-06-12T11:00:00+00:00"),
    ("aditya.singh@voltrix.com", "call", "Technical call about telemetry data export.", "2025-05-29T14:00:00+00:00"),
    ("aditya.singh@voltrix.com", "email", "Sent Q2 usage report.", "2025-04-20T09:00:00+00:00"),

    ("yash.trivedi@securenet.io", "call", "Discussed findings from the security audit.", "2025-05-30T10:00:00+00:00"),
    ("yash.trivedi@securenet.io", "note", "Prospect asked for a reference customer in the same industry.", "2025-05-31T09:00:00+00:00"),

    ("riya.kulkarni@wanderloop.com", "note", "Account marked inactive; team paused the project internally.", "2025-03-15T09:00:00+00:00"),

    ("om.prakash@buildright.com", "call", "Renewal confirmed for the site-inspection module.", "2025-06-08T14:30:00+00:00"),
    ("om.prakash@buildright.com", "meeting", "Onsite training session for the field team.", "2025-04-25T10:00:00+00:00"),
    ("om.prakash@buildright.com", "email", "Sent training materials follow-up.", "2025-04-26T09:00:00+00:00"),

    ("meera.iyer@brightfin.com", "note", "Compliance lead asked for an updated SOC 2 report.", "2025-06-18T09:00:00+00:00"),
    ("vivaan.nair@stackforge.dev", "meeting", "Roadmap review for the next integration milestone.", "2025-06-20T10:00:00+00:00"),
    ("sanya.chatterjee@fleetwise.io", "demo", "Second demo focused on real-time GPS tracking.", "2025-06-01T11:00:00+00:00"),
    ("yash.trivedi@securenet.io", "email", "Sent the requested reference customer contact.", "2025-06-02T09:00:00+00:00"),
    ("neha.gupta@cloudscribe.io", "call", "Check-in call ahead of trial expiration.", "2025-06-10T09:00:00+00:00"),
    ("kabir.malhotra@edulaunch.com", "call", "Budget check-in call ahead of next quarter.", "2025-06-15T09:00:00+00:00"),
    ("rohan.verma@cropsense.io", "note", "Pilot proposal under internal review at CropSense.", "2025-06-01T09:00:00+00:00"),
    ("dev.joshi@quantifyhr.com", "note", "Customer flagged interest in the analytics add-on.", "2025-06-07T09:00:00+00:00"),
]


def seed(db_path: str | None = None) -> tuple[int, int]:
    """Seed the database if it is empty. Returns (customer_count, interaction_count)."""
    db.init_db(db_path)

    existing_customers = db.find_customers(limit=db.MAX_LIMIT, db_path=db_path)
    if existing_customers:
        # Already seeded — avoid inserting duplicates on repeated runs.
        customer_count = len(db.find_customers(limit=db.MAX_LIMIT, db_path=db_path))
        with db.get_connection(db_path) as conn:
            total_customers = conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
            total_interactions = conn.execute("SELECT COUNT(*) AS n FROM interactions").fetchone()["n"]
        return total_customers, total_interactions

    email_to_id: dict[str, int] = {}
    for (name, email, company, country, industry, status, created_at, last_contacted_at) in CUSTOMERS:
        customer_id = db.insert_customer(
            name=name,
            email=email,
            company=company,
            country=country,
            industry=industry,
            status=status,
            created_at=created_at,
            last_contacted_at=last_contacted_at,
            db_path=db_path,
        )
        email_to_id[email] = customer_id

    for (email, interaction_type, note, interaction_date) in INTERACTIONS:
        customer_id = email_to_id[email]
        # Insert directly rather than via insert_interaction() so that seeding
        # does not overwrite the deterministic last_contacted_at values above
        # with a fresh timestamp.
        with db.get_connection(db_path) as conn:
            conn.execute(
                """
                INSERT INTO interactions
                    (customer_id, interaction_type, note, interaction_date, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (customer_id, interaction_type, note, interaction_date, interaction_date),
            )

    with db.get_connection(db_path) as conn:
        total_customers = conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
        total_interactions = conn.execute("SELECT COUNT(*) AS n FROM interactions").fetchone()["n"]

    return total_customers, total_interactions


def main() -> None:
    customer_count, interaction_count = seed()
    print("CRM database initialized.")
    print()
    print(f"Customers: {customer_count}")
    print(f"Interactions: {interaction_count}")


if __name__ == "__main__":
    main()
