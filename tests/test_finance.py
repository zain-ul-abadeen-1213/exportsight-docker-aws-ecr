"""ExportSight tests — finance calculations (spec section 10)."""

import pytest

from utils.finance import (aging_bucket, classify_invoice, convert,
                           delayed_orders, invoice_summary, kpi_overview,
                           monthly_sales_trend, order_profitability, to_base)

TODAY = "2026-10-13"


# --- order values -----------------------------------------------------------
def test_order_value_is_quantity_times_price(conn):
    from db.database import fetch_one
    row = fetch_one(conn, "SELECT quantity, unit_price, order_value FROM orders WHERE order_id='O1'")
    assert row["order_value"] == pytest.approx(row["quantity"] * row["unit_price"])


# --- currency ----------------------------------------------------------------
def test_to_base_converts_with_documented_rate(conn):
    from utils.finance import get_rates
    _, rates = get_rates(conn)
    assert to_base(1000, "USD", rates) == pytest.approx(278000.0)
    assert to_base(1000, "EUR", rates) == pytest.approx(301500.0)


def test_to_base_unknown_currency_raises():
    with pytest.raises(ValueError, match="No exchange rate"):
        to_base(100, "XXX", {"USD": 278.0})


def test_convert_between_currencies():
    rates = {"USD": 278.0, "EUR": 301.5, "PKR": 1.0}
    assert convert(278.0, "USD", "PKR", rates) == pytest.approx(77284.0)
    assert convert(100, "USD", "USD", rates) == 100


def test_cross_currency_payment_converts_before_balance(conn):
    """A EUR payment against a USD invoice must convert, not mix."""
    from db.database import execute
    execute(conn, """INSERT INTO payments
                     (payment_id, invoice_id, payment_date, amount, currency,
                      reference, notes, created_at)
                     VALUES ('PX1','I3','2026-10-01',500.0,'USD','REF-X1','',?)""",
            (TODAY,))
    inv = invoice_summary(conn, TODAY).set_index("invoice_id").loc["I3"]
    # 1000 EUR invoice = 301500 PKR; 500 USD payment = 139000 PKR
    assert inv["paid_PKR"] == pytest.approx(139000.0)
    assert inv["balance_PKR"] == pytest.approx(301500.0 - 139000.0)
    assert inv["status"] == "Overdue"  # still partially unpaid & past due


# --- invoice classification ---------------------------------------------------
def test_never_paid_without_full_payment():
    assert classify_invoice(1000, 999.99, "2020-01-01", TODAY) != "Paid"
    assert classify_invoice(1000, 1000, "2020-01-01", TODAY) == "Paid"
    assert classify_invoice(1000, 0, "2020-01-01", TODAY) == "Overdue"
    assert classify_invoice(1000, 0, "2099-01-01", TODAY) == "Unpaid"
    assert classify_invoice(1000, 400, "2099-01-01", TODAY) == "Partially Paid"
    assert classify_invoice(1000, 400, "2020-01-01", TODAY) == "Overdue"


def test_invoice_summary_statuses(conn):
    inv = invoice_summary(conn, TODAY).set_index("invoice_id")
    assert inv.loc["I1", "status"] == "Overdue"          # partial + past due
    assert inv.loc["I2", "status"] == "Paid"             # 400 + 600 = full
    assert inv.loc["I3", "status"] == "Overdue"          # unpaid + past due
    assert inv.loc["I2", "balance_PKR"] == pytest.approx(0.0)
    assert inv.loc["I1", "balance_PKR"] == pytest.approx(700 * 278.0)


def test_aging_buckets():
    assert aging_bucket(0) == "0–30 days"
    assert aging_bucket(30) == "0–30 days"
    assert aging_bucket(31) == "31–60 days"
    assert aging_bucket(90) == "61–90 days"
    assert aging_bucket(91) == "Over 90 days"
    assert aging_bucket(400) == "Over 90 days"


# --- KPIs ----------------------------------------------------------------------
def test_kpi_totals(conn):
    k = kpi_overview(conn, today=TODAY)
    assert k["base_currency"] == "PKR"
    assert k["total_export_sales"] == pytest.approx(927000.0)
    assert k["total_orders"] == 4
    assert k["active_orders"] == 3  # O2 pending, O3 shipped, O4 pending
    # paid: I2 full (1000 USD) + I1 partial (300 USD)
    assert k["payments_received"] == pytest.approx(1300 * 278.0)
    # outstanding: I1 700 USD + I3 1000 EUR
    assert k["outstanding_receivables"] == pytest.approx(700 * 278.0 + 1000 * 301.5)
    assert k["overdue_count"] == 2
    assert k["collection_rate"] == pytest.approx(42.1, abs=0.05)


def test_kpi_filters_narrow_results(conn):
    k = kpi_overview(conn, buyer_id="B2", today=TODAY)
    assert k["total_orders"] == 2
    assert k["total_export_sales"] == pytest.approx(1000 * 301.5 + 250 * 278.0)


# --- profitability --------------------------------------------------------------
def test_gross_profit_and_margin(conn):
    prof = order_profitability(conn).set_index("order_id")
    o1 = prof.loc["O1"]
    assert o1["revenue_base"] == pytest.approx(278000.0)
    assert o1["costs_base"] == pytest.approx(600 * 278.0)
    assert o1["gross_profit_base"] == pytest.approx(400 * 278.0)
    assert o1["gross_margin_pct"] == pytest.approx(40.0)
    assert o1["costs_complete"]
    assert not o1["negative_margin"]


def test_missing_costs_flagged_not_invented(conn):
    prof = order_profitability(conn).set_index("order_id")
    o2 = prof.loc["O2"]
    assert not o2["costs_complete"]
    assert o2["costs_base"] == pytest.approx(0.0)
    # revenue still counted; profit equals revenue (flagged as estimate)
    assert o2["gross_profit_base"] == pytest.approx(278000.0)


def test_negative_margin_flagged(conn):
    from db.database import execute
    execute(conn, """INSERT INTO order_costs
                     (order_id, cost_category, amount, currency, notes, created_at)
                     VALUES ('O3','Freight',300.0,'EUR','',?)""", (TODAY,))
    prof = order_profitability(conn).set_index("order_id")
    o3 = prof.loc["O3"]
    assert o3["gross_profit_base"] == pytest.approx((1000 - 1200) * 301.5)
    assert o3["negative_margin"]


# --- alerts & trends ---------------------------------------------------------------
def test_delayed_orders_detected(conn):
    alerts = delayed_orders(conn, TODAY)
    by_id = {r.order_id: r.alert for r in alerts.itertuples()}
    assert by_id.get("O4") == "Delayed"          # expected 2026-05-01, still open
    assert by_id.get("O3") == "Delayed"          # shipped but past expected date
    assert "O1" not in by_id                      # delivered
    assert "O2" not in by_id                      # expected date far in future


def test_monthly_trend_sums_base_currency(conn):
    trend = monthly_sales_trend(conn)
    assert not trend.empty
    assert trend["sales_PKR"].sum() == pytest.approx(927000.0)
