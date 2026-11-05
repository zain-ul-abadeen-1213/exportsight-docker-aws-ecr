"""ExportSight — fictional demo data seeder.

ALL data in this file is FICTIONAL and for demonstration only. Names,
companies, figures and dates are invented. No real customer information
is used. The app labels this dataset as "Demo data" wherever it appears.
"""

from __future__ import annotations

import sqlite3
from datetime import date, timedelta

from .database import execute_many, get_setting, set_setting

# Documented demo exchange rates (fictional, editable in Settings).
DEMO_FX = {
    "base_currency": "PKR",
    "fx_USD_PKR": "278.0",
    "fx_EUR_PKR": "301.5",
    "fx_GBP_PKR": "352.0",
    "fx_PKR_PKR": "1.0",
    "revenue_recognition": "order_date",  # or: shipment_date
}

COST_CATEGORIES = [
    "Raw Materials",
    "Labour/Manufacturing",
    "Packaging",
    "Inland Transportation",
    "Freight",
    "Insurance",
    "Other Direct Costs",
]


def _d(days_ago: int) -> str:
    """ISO date string `days_ago` days before today (negative = future)."""
    return (date.today() - timedelta(days=days_ago)).isoformat()


def _now() -> str:
    return date.today().isoformat()


def seed_demo_data(conn: sqlite3.Connection) -> dict:
    """Clear demo tables and insert the fictional textile-exporter dataset.

    Returns a dict of counts per table.
    """
    # --- wipe (demo only) -------------------------------------------------
    for tbl in ("order_costs", "payments", "invoices", "orders", "buyers"):
        conn.execute(f"DELETE FROM {tbl};")
    conn.commit()

    now = _now()

    buyers = [
        ("BYR-001", "NordTextil GmbH", "Germany", "orders@nordtextil.example.de", "+49-170-000101", now),
        ("BYR-002", "Gulf Apparel LLC", "UAE", "buying@gulfapparel.example.ae", "+971-50-000202", now),
        ("BYR-003", "Maple Home Textiles Inc", "Canada", "sales@maplehome.example.ca", "+1-416-000303", now),
        ("BYR-004", "Sahara Linens SARL", "France", "contact@saharalinens.example.fr", "+33-6-000404", now),
        ("BYR-005", "Pacific Traders Pty", "Australia", "info@pacifictraders.example.au", "+61-4-000505", now),
    ]
    execute_many(
        conn,
        "INSERT INTO buyers (buyer_id, name, country, email, phone, created_at) VALUES (?,?,?,?,?,?)",
        buyers,
    )

    # order_id, days_ago, buyer, country, product, qty, unit_price, ccy,
    # prod_status, ship_status, expected_in_days_ago (neg=future), actual_in_days_ago|None
    orders_raw = [
        ("ORD-1001", 210, "BYR-001", "Germany",  "Cotton Bed Sheet Set", 5000, 12.50, "USD", "Completed", "Delivered", 180, 182),
        ("ORD-1002", 190, "BYR-002", "UAE",      "Denim Fabric Roll",    2000, 8.75,  "USD", "Completed", "Delivered", 160, 159),
        ("ORD-1003", 170, "BYR-003", "Canada",   "Bath Towel Bundle",    8000, 4.20,  "USD", "Completed", "Shipped",   140, None),
        ("ORD-1004", 150, "BYR-001", "Germany",  "Table Linen Set",      3000, 15.00, "EUR", "Completed", "Delivered", 120, 121),
        ("ORD-1005", 130, "BYR-004", "France",   "Canvas Fabric Roll",   1500, 9.80,  "EUR", "Completed", "Delivered", 100, 104),
        ("ORD-1006", 110, "BYR-002", "UAE",      "Cotton Bed Sheet Set", 6000, 12.00, "USD", "In Production", "Pending", 5, None),  # delayed
        ("ORD-1007", 95,  "BYR-005", "Australia","Bath Towel Bundle",   10000, 4.00,  "USD", "Completed", "Shipped",    65, None),
        ("ORD-1008", 80,  "BYR-003", "Canada",   "Denim Fabric Roll",    2500, 8.50,  "USD", "In Production", "Pending", -3, None),  # approaching
        ("ORD-1009", 65,  "BYR-001", "Germany",  "Cotton Bed Sheet Set", 4000, 13.00, "USD", "Pending", "Pending",      -30, None),
        ("ORD-1010", 50,  "BYR-004", "France",   "Table Linen Set",      3500, 14.50, "EUR", "In Production", "Pending", -5, None),
        ("ORD-1011", 35,  "BYR-002", "UAE",      "Canvas Fabric Roll",   1200, 10.20, "USD", "Pending", "Pending",      -45, None),
        ("ORD-1012", 20,  "BYR-005", "Australia","Cotton Bed Sheet Set", 5500, 12.80, "USD", "Pending", "Pending",      -60, None),
        ("ORD-1013", 120, "BYR-002", "UAE",      "Cotton Bed Sheet Set", 3000, 3500.0,"PKR", "Completed", "Delivered",  90, 88),
        ("ORD-1014", 8,   "BYR-001", "Germany",  "Denim Fabric Roll",    1800, 9.00,  "USD", "Pending", "Pending",      -75, None),
    ]
    orders = []
    for (oid, ago, buyer, country, product, qty, price, ccy,
         pstat, sstat, exp_ago, act_ago) in orders_raw:
        orders.append((
            oid, _d(ago), buyer, country, product, qty, price, ccy,
            round(qty * price, 2), pstat, sstat,
            _d(exp_ago) if exp_ago is not None else None,
            _d(act_ago) if act_ago is not None else None,
            "", now,
        ))
    execute_many(
        conn,
        """INSERT INTO orders (order_id, order_date, buyer_id, destination_country,
               product, quantity, unit_price, currency, order_value,
               production_status, shipment_status, expected_delivery_date,
               actual_delivery_date, notes, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        orders,
    )

    # invoice_id, order_id, buyer, inv_days_ago, due_days_ago, amount, ccy
    invoices = [
        ("INV-2001", "ORD-1001", "BYR-001", 195, 150, 62500.0, "USD"),
        ("INV-2002", "ORD-1002", "BYR-002", 175, 130, 17500.0, "USD"),
        ("INV-2003", "ORD-1003", "BYR-003", 155, 110, 33600.0, "USD"),
        ("INV-2004", "ORD-1004", "BYR-001", 135, 90, 45000.0, "EUR"),
        ("INV-2005", "ORD-1005", "BYR-004", 115, 70, 14700.0, "EUR"),
        ("INV-2006", "ORD-1007", "BYR-005", 80, 35, 40000.0, "USD"),
        ("INV-2007", "ORD-1013", "BYR-002", 105, 60, 10500000.0, "PKR"),
        ("INV-2008", "ORD-1008", "BYR-003", 65, -20, 21250.0, "USD"),
        ("INV-2009", "ORD-1010", "BYR-004", 55, 12, 50750.0, "EUR"),
    ]
    execute_many(
        conn,
        """INSERT INTO invoices (invoice_id, order_id, buyer_id, invoice_date,
               due_date, amount, currency, notes, created_at)
           VALUES (?,?,?,?,?,?,?,'',?)""",
        [(i, o, b, _d(inv), _d(due), a, c, now) for (i, o, b, inv, due, a, c) in invoices],
    )

    # payment_id, invoice_id, pay_days_ago, amount, ccy, reference
    payments = [
        ("PAY-3001", "INV-2001", 160, 62500.0, "USD", "TT-884102"),
        ("PAY-3002", "INV-2002", 140, 10000.0, "USD", "TT-884109"),
        ("PAY-3003", "INV-2004", 100, 20000.0, "EUR", "SEPA-551201"),
        ("PAY-3004", "INV-2004", 95, 25000.0, "EUR", "SEPA-551233"),
        ("PAY-3005", "INV-2005", 80, 5000.0, "EUR", "SEPA-551240"),
        ("PAY-3006", "INV-2007", 70, 10500000.0, "PKR", "IBFT-990211"),
        ("PAY-3007", "INV-2009", 20, 20000.0, "EUR", "SEPA-551298"),
    ]
    execute_many(
        conn,
        """INSERT INTO payments (payment_id, invoice_id, payment_date, amount,
               currency, reference, notes, created_at)
           VALUES (?,?,?,?,?,?,'',?)""",
        [(p, i, _d(ago), a, c, r, now) for (p, i, ago, a, c, r) in payments],
    )

    # Direct costs per order: order_id -> total cost as fraction of order value.
    # ORD-1005 is deliberately over-cost (negative margin example).
    # ORD-1009/1011/1012/1014 have NO costs (incomplete-record example).
    cost_plan = {
        "ORD-1001": 0.66, "ORD-1002": 0.70, "ORD-1003": 0.68, "ORD-1004": 0.64,
        "ORD-1005": 1.10, "ORD-1006": 0.62, "ORD-1007": 0.71, "ORD-1008": 0.66,
        "ORD-1010": 0.69, "ORD-1013": 0.63,
    }
    # Split of total cost across the 7 categories (sums to 1.0).
    split = [0.42, 0.22, 0.06, 0.05, 0.16, 0.04, 0.05]
    order_ccy = {o[0]: o[7] for o in orders_raw}
    order_val = {o[0]: round(o[5] * o[6], 2) for o in orders_raw}
    cost_rows = []
    for oid, ratio in cost_plan.items():
        total = round(order_val[oid] * ratio, 2)
        for cat, frac in zip(COST_CATEGORIES, split):
            cost_rows.append((oid, cat, round(total * frac, 2), order_ccy[oid], "", now))
    execute_many(
        conn,
        """INSERT INTO order_costs (order_id, cost_category, amount, currency, notes, created_at)
           VALUES (?,?,?,?,?,?)""",
        cost_rows,
    )

    # Settings (documented demo FX rates + revenue rule)
    for key, value in DEMO_FX.items():
        if get_setting(conn, key) is None:
            set_setting(conn, key, value, now)
    # Marker so the UI can label this dataset as demo data.
    set_setting(conn, "demo_data", "true", now)

    counts = {}
    for tbl in ("buyers", "orders", "invoices", "payments", "order_costs"):
        row = conn.execute(f"SELECT COUNT(*) AS n FROM {tbl}").fetchone()
        counts[tbl] = row["n"]
    return counts
