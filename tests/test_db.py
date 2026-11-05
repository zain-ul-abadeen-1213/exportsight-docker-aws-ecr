"""ExportSight tests — schema, settings, transactions, seed integrity."""

import sqlite3

import pytest

from db.database import (execute, fetch_df, get_connection, get_setting,
                         init_database, set_setting, transaction)
from db.seed import seed_demo_data


def test_tables_and_indexes_exist(conn):
    tables = {r[0] for r in
              conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert {"buyers", "orders", "invoices", "payments",
            "order_costs", "settings"} <= tables
    idx = {r[0] for r in
           conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert "idx_orders_buyer" in idx and "idx_payments_invoice" in idx


def test_foreign_keys_enforced(conn):
    with pytest.raises(sqlite3.IntegrityError):
        execute(conn, """INSERT INTO orders
                         (order_id, order_date, buyer_id, destination_country, product,
                          quantity, unit_price, currency, order_value,
                          production_status, shipment_status, created_at)
                         VALUES ('OX','2026-01-01','GHOST','X','Y',1,1,'USD',1,
                                 'Pending','Pending',date('now'))""")


def test_transaction_rolls_back(conn):
    with pytest.raises(RuntimeError):
        with transaction(conn):
            conn.execute("INSERT INTO buyers VALUES ('BT','T','X',NULL,NULL,date('now'))")
            raise RuntimeError("boom")
    assert conn.execute("SELECT COUNT(*) FROM buyers WHERE buyer_id='BT'").fetchone()[0] == 0


def test_settings_roundtrip(conn):
    set_setting(conn, "fx_USD_PKR", "280.0", "2026-10-13")
    assert get_setting(conn, "fx_USD_PKR") == "280.0"
    assert get_setting(conn, "missing_key", "dflt") == "dflt"


def test_demo_seed_marks_and_counts(conn):
    counts = seed_demo_data(conn)
    assert counts["buyers"] == 5
    assert counts["orders"] == 14
    assert counts["invoices"] == 9
    assert get_setting(conn, "demo_data") == "true"
    # every order value equals qty * price
    df = fetch_df(conn, "SELECT quantity, unit_price, order_value FROM orders")
    assert ((df["quantity"] * df["unit_price"]).round(2)
            == df["order_value"].round(2)).all()


def test_demo_seed_has_live_aging_buckets():
    """Seeded dates are relative to today, so some invoices are overdue."""
    import tempfile
    from utils.finance import invoice_summary
    with tempfile.TemporaryDirectory() as td:
        p = f"{td}/demo.db"
        init_database(p)
        c = get_connection(p)
        try:
            seed_demo_data(c)
            inv = invoice_summary(c)
            assert (inv["status"] == "Overdue").sum() >= 1
            assert (inv["status"] == "Paid").sum() >= 1
        finally:
            c.close()
