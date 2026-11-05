"""ExportSight tests — fixtures. Controlled (non-demo) dataset for assertions."""

import sqlite3
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from db.database import execute, get_connection, init_database, set_setting  # noqa: E402


@pytest.fixture()
def conn(tmp_path):
    """Temp SQLite DB with a small deterministic dataset."""
    db_path = tmp_path / "test.db"
    init_database(db_path)
    c = get_connection(db_path)
    today = "2026-10-13"
    for key, val in {"base_currency": "PKR", "fx_USD_PKR": "278.0",
                     "fx_EUR_PKR": "301.5", "fx_PKR_PKR": "1.0",
                     "revenue_recognition": "order_date",
                     "demo_data": "false"}.items():
        set_setting(c, key, val, today)

    execute(c, "INSERT INTO buyers VALUES ('B1','Test Buyer One','Testland',NULL,NULL,?)", (today,))
    execute(c, "INSERT INTO buyers VALUES ('B2','Test Buyer Two','Examplestan',NULL,NULL,?)", (today,))

    orders = [
        # oid, date, buyer, country, product, qty, price, ccy, value, pstat, sstat, exp, act
        ("O1", "2026-01-10", "B1", "Testland", "Fabric", 100, 10.0, "USD",
         1000.0, "Completed", "Delivered", "2026-02-10", "2026-02-09"),
        ("O2", "2026-02-15", "B1", "Testland", "Towels", 50, 20.0, "USD",
         1000.0, "In Production", "Pending", "2026-12-01", None),
        ("O3", "2026-03-01", "B2", "Examplestan", "Sheets", 10, 100.0, "EUR",
         1000.0, "Completed", "Shipped", "2026-04-01", None),
        ("O4", "2026-04-01", "B2", "Examplestan", "Fabric", 5, 50.0, "USD",
         250.0, "Pending", "Pending", "2026-05-01", None),  # delayed (past expected)
    ]
    for o in orders:
        execute(c, """INSERT INTO orders VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                o + ("", today))

    invoices = [
        # iid, oid, buyer, inv_date, due, amount, ccy
        ("I1", "O1", "B1", "2026-01-20", "2026-02-20", 1000.0, "USD"),  # overdue, partial
        ("I2", "O2", "B1", "2026-02-20", "2027-02-20", 1000.0, "USD"),  # fully paid
        ("I3", "O3", "B2", "2026-03-10", "2026-04-10", 1000.0, "EUR"),  # overdue, unpaid
    ]
    for i in invoices:
        execute(c, """INSERT INTO invoices
                      (invoice_id, order_id, buyer_id, invoice_date, due_date,
                       amount, currency, notes, created_at)
                      VALUES (?,?,?,?,?,?,?,'',?)""", i + (today,))

    payments = [
        # pid, iid, date, amount, ccy, ref
        ("P1", "I2", "2026-03-01", 400.0, "USD", "REF-001"),
        ("P2", "I2", "2026-04-01", 600.0, "USD", "REF-002"),
        ("P3", "I1", "2026-03-15", 300.0, "USD", "REF-003"),
    ]
    for p in payments:
        execute(c, """INSERT INTO payments
                      (payment_id, invoice_id, payment_date, amount, currency,
                       reference, notes, created_at)
                      VALUES (?,?,?,?,?,?,'',?)""", p + (today,))

    costs = [
        # oid, category, amount, ccy
        ("O1", "Raw Materials", 500.0, "USD"),
        ("O1", "Freight", 100.0, "USD"),
        ("O3", "Raw Materials", 900.0, "EUR"),
    ]
    for co in costs:
        execute(c, """INSERT INTO order_costs
                      (order_id, cost_category, amount, currency, notes, created_at)
                      VALUES (?,?,?,?,'',?)""", co + (today,))
    yield c
    c.close()
