"""ExportSight — financial calculations (single source of truth).

Every module (overview, payments, profitability, reports) uses these
functions so KPIs stay consistent. Multi-currency amounts are converted
to the configured base currency using the documented exchange rates in
the settings table — currencies are NEVER mixed without conversion.
"""

from __future__ import annotations

import sqlite3
from datetime import date

import pandas as pd

from db.database import fetch_df, get_setting

# Invoice lifecycle states
UNPAID = "Unpaid"
PARTIALLY_PAID = "Partially Paid"
PAID = "Paid"
OVERDUE = "Overdue"

EPS = 1e-6


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------

def get_rates(conn: sqlite3.Connection) -> tuple[str, dict[str, float]]:
    """Return (base_currency, {currency_code: units_of_base_per_unit})."""
    base = get_setting(conn, "base_currency", "PKR") or "PKR"
    rates: dict[str, float] = {}
    for row in conn.execute(
        "SELECT key, value FROM settings WHERE key LIKE 'fx\\_%' ESCAPE '\\'"
    ):
        code = row[0].split("_")[1]  # fx_USD_PKR -> USD
        try:
            rates[code] = float(row[1])
        except (ValueError, TypeError):
            continue
    rates.setdefault(base, 1.0)
    return base, rates


def to_base(amount: float, currency: str, rates: dict[str, float]) -> float:
    """Convert an amount to base currency. Raises on unknown currency."""
    if currency not in rates:
        raise ValueError(f"No exchange rate configured for currency '{currency}'.")
    return round(float(amount) * rates[currency], 2)


def convert(amount: float, from_ccy: str, to_ccy: str, rates: dict[str, float]) -> float:
    """Convert between any two configured currencies via the base currency."""
    if from_ccy == to_ccy:
        return round(float(amount), 2)
    base_amount = to_base(amount, from_ccy, rates)
    if to_ccy not in rates or rates[to_ccy] == 0:
        raise ValueError(f"No exchange rate configured for currency '{to_ccy}'.")
    return round(base_amount / rates[to_ccy], 2)


# ---------------------------------------------------------------------------
# Invoices: status, balances, aging
# ---------------------------------------------------------------------------

def classify_invoice(amount: float, paid: float, due_date: str | None,
                     today: str | None = None) -> str:
    """Classify one invoice. Never 'Paid' without full payment recorded."""
    today = today or date.today().isoformat()
    balance = amount - paid
    if balance <= EPS:
        return PAID
    if paid > EPS:
        # Partially paid: overdue only matters for the remaining balance.
        if due_date and due_date < today:
            return OVERDUE
        return PARTIALLY_PAID
    if due_date and due_date < today:
        return OVERDUE
    return UNPAID


def aging_bucket(days_overdue: int) -> str:
    if days_overdue <= 30:
        return "0–30 days"
    if days_overdue <= 60:
        return "31–60 days"
    if days_overdue <= 90:
        return "61–90 days"
    return "Over 90 days"


def invoice_summary(conn: sqlite3.Connection,
                    today: str | None = None) -> pd.DataFrame:
    """One row per invoice with paid/balance (base ccy), status, days overdue.

    Payments in a different currency than the invoice are converted with the
    documented rates before comparison.
    """
    today = today or date.today().isoformat()
    base, rates = get_rates(conn)

    invoices = fetch_df(conn, """
        SELECT i.invoice_id, i.order_id, i.buyer_id, b.name AS buyer_name,
               b.country AS buyer_country, i.invoice_date, i.due_date,
               i.amount, i.currency
        FROM invoices i JOIN buyers b ON b.buyer_id = i.buyer_id
        ORDER BY i.due_date
    """)
    payments = fetch_df(conn, """
        SELECT invoice_id, payment_date, amount, currency FROM payments
    """)

    rows = []
    for _, inv in invoices.iterrows():
        paid_base = 0.0
        inv_payments = payments[payments["invoice_id"] == inv["invoice_id"]] \
            if not payments.empty else payments
        for _, p in inv_payments.iterrows():
            paid_base += to_base(p["amount"], p["currency"], rates)
        amount_base = to_base(inv["amount"], inv["currency"], rates)
        balance_base = round(amount_base - paid_base, 2)
        status = classify_invoice(amount_base, paid_base, inv["due_date"], today)
        days_overdue = 0
        if status == OVERDUE and inv["due_date"]:
            days_overdue = (date.fromisoformat(today)
                            - date.fromisoformat(inv["due_date"])).days
        rows.append({
            "invoice_id": inv["invoice_id"],
            "order_id": inv["order_id"],
            "buyer_id": inv["buyer_id"],
            "buyer_name": inv["buyer_name"],
            "buyer_country": inv["buyer_country"],
            "invoice_date": inv["invoice_date"],
            "due_date": inv["due_date"],
            "currency": inv["currency"],
            "amount": inv["amount"],
            f"amount_{base}": amount_base,
            f"paid_{base}": round(paid_base, 2),
            f"balance_{base}": max(balance_base, 0.0),
            "status": status,
            "days_overdue": days_overdue,
            "aging_bucket": aging_bucket(days_overdue) if status == OVERDUE else "",
        })
    cols = ["invoice_id", "order_id", "buyer_id", "buyer_name", "buyer_country",
            "invoice_date", "due_date", "currency", "amount",
            f"amount_{base}", f"paid_{base}", f"balance_{base}",
            "status", "days_overdue", "aging_bucket"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Executive overview KPIs (all in base currency)
# ---------------------------------------------------------------------------

def kpi_overview(conn: sqlite3.Connection,
                 start_date: str | None = None,
                 end_date: str | None = None,
                 buyer_id: str | None = None,
                 country: str | None = None,
                 ship_status: str | None = None,
                 today: str | None = None) -> dict:
    """KPIs filtered by date range / buyer / country / shipment status."""
    today = today or date.today().isoformat()
    base, rates = get_rates(conn)

    conds, params = [], []
    if start_date:
        conds.append("o.order_date >= ?"); params.append(start_date)
    if end_date:
        conds.append("o.order_date <= ?"); params.append(end_date)
    if buyer_id:
        conds.append("o.buyer_id = ?"); params.append(buyer_id)
    if country:
        conds.append("o.destination_country = ?"); params.append(country)
    if ship_status:
        conds.append("o.shipment_status = ?"); params.append(ship_status)
    where = ("WHERE " + " AND ".join(conds)) if conds else ""

    orders = fetch_df(conn, f"""
        SELECT o.order_id, o.order_date, o.buyer_id, b.name AS buyer_name,
               o.destination_country, o.product, o.quantity, o.unit_price,
               o.currency, o.order_value, o.production_status, o.shipment_status,
               o.expected_delivery_date, o.actual_delivery_date
        FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
        {where} ORDER BY o.order_date
    """, params)

    total_sales = sum(to_base(r.order_value, r.currency, rates) for r in orders.itertuples())
    active = orders[~orders["shipment_status"].isin(["Delivered", "Cancelled"])]
    recognised = _recognised_revenue(conn, orders, rates)

    inv = invoice_summary(conn, today)
    # Restrict invoice KPIs to the filtered order set for consistency.
    inv = inv[inv["order_id"].isin(set(orders["order_id"]))] if not orders.empty \
        else inv.iloc[0:0]

    bal_col = f"balance_{base}"
    paid_col = f"paid_{base}"
    amt_col = f"amount_{base}"
    overdue = inv[inv["status"] == OVERDUE]

    gross_profit = _total_gross_profit(conn, set(orders["order_id"]), rates)

    return {
        "base_currency": base,
        "total_export_sales": round(total_sales, 2),
        "total_orders": int(len(orders)),
        "active_orders": int(len(active)),
        "payments_received": round(float(inv[paid_col].sum()) if not inv.empty else 0.0, 2),
        "outstanding_receivables": round(float(inv[bal_col].sum()) if not inv.empty else 0.0, 2),
        "overdue_invoices": round(float(overdue[bal_col].sum()) if not overdue.empty else 0.0, 2),
        "overdue_count": int(len(overdue)),
        "recognised_revenue": round(recognised, 2),
        "estimated_gross_profit": round(gross_profit, 2),
        "collection_rate": round(
            float(inv[paid_col].sum()) / float(inv[amt_col].sum()) * 100, 1
        ) if not inv.empty and float(inv[amt_col].sum()) > 0 else 0.0,
    }


def _recognised_revenue(conn: sqlite3.Connection, orders: pd.DataFrame,
                        rates: dict[str, float]) -> float:
    """Revenue under the configured recognition rule."""
    rule = get_setting(conn, "revenue_recognition", "order_date") or "order_date"
    total = 0.0
    for r in orders.itertuples():
        if rule == "shipment_date" and r.shipment_status not in ("Shipped", "Delivered"):
            continue
        total += to_base(r.order_value, r.currency, rates)
    return total


def _total_gross_profit(conn: sqlite3.Connection, order_ids: set,
                        rates: dict[str, float]) -> float:
    prof = order_profitability(conn)
    if not order_ids:
        return 0.0
    prof = prof[prof["order_id"].isin(order_ids)]
    return float(prof["gross_profit_base"].sum()) if not prof.empty else 0.0


# ---------------------------------------------------------------------------
# Profitability (per order — always called GROSS profit, never net)
# ---------------------------------------------------------------------------

def order_profitability(conn: sqlite3.Connection) -> pd.DataFrame:
    """Per-order revenue, direct costs, gross profit and margin (base ccy).

    Flags rows with missing cost records or negative gross profit.
    """
    base, rates = get_rates(conn)
    orders = fetch_df(conn, """
        SELECT o.order_id, o.order_date, o.buyer_id, b.name AS buyer_name,
               o.destination_country, o.product, o.order_value, o.currency,
               o.shipment_status
        FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
    """)
    costs = fetch_df(conn, "SELECT order_id, cost_category, amount, currency FROM order_costs")

    rows = []
    for _, o in orders.iterrows():
        oc = costs[costs["order_id"] == o["order_id"]] if not costs.empty else costs
        total_cost_base = sum(to_base(r.amount, r.currency, rates) for r in oc.itertuples())
        revenue_base = to_base(o["order_value"], o["currency"], rates)
        gross_profit = round(revenue_base - total_cost_base, 2)
        margin = round(gross_profit / revenue_base * 100, 1) if revenue_base > EPS else 0.0
        rows.append({
            "order_id": o["order_id"],
            "order_date": o["order_date"],
            "buyer_name": o["buyer_name"],
            "destination_country": o["destination_country"],
            "product": o["product"],
            "currency": o["currency"],
            "revenue": o["order_value"],
            "revenue_base": revenue_base,
            "costs_base": round(total_cost_base, 2),
            "gross_profit_base": gross_profit,
            "gross_margin_pct": margin,
            "costs_complete": bool(len(oc) > 0),
            "negative_margin": gross_profit < 0,
        })
    cols = ["order_id", "order_date", "buyer_name", "destination_country", "product",
            "currency", "revenue", "revenue_base", "costs_base",
            "gross_profit_base", "gross_margin_pct", "costs_complete", "negative_margin"]
    return pd.DataFrame(rows, columns=cols)


# ---------------------------------------------------------------------------
# Order alerts
# ---------------------------------------------------------------------------

def delayed_orders(conn: sqlite3.Connection, today: str | None = None,
                   approaching_days: int = 7) -> pd.DataFrame:
    """Orders past their expected delivery (delayed) or due soon (approaching)."""
    today = today or date.today().isoformat()
    orders = fetch_df(conn, """
        SELECT o.order_id, o.order_date, b.name AS buyer_name,
               o.destination_country, o.product, o.shipment_status,
               o.expected_delivery_date, o.actual_delivery_date
        FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
        WHERE o.actual_delivery_date IS NULL
          AND o.shipment_status NOT IN ('Delivered', 'Cancelled')
          AND o.expected_delivery_date IS NOT NULL
    """)
    rows = []
    for _, r in orders.iterrows():
        delta = (date.fromisoformat(r["expected_delivery_date"])
                 - date.fromisoformat(today)).days
        if delta < 0:
            alert, days = "Delayed", -delta
        elif delta <= approaching_days:
            alert, days = "Approaching deadline", delta
        else:
            continue
        rows.append({**r.to_dict(), "alert": alert, "days": days})
    return pd.DataFrame(rows)


def monthly_sales_trend(conn: sqlite3.Connection) -> pd.DataFrame:
    """Monthly recognised sales totals in base currency."""
    base, rates = get_rates(conn)
    orders = fetch_df(conn, "SELECT order_date, order_value, currency FROM orders")
    if orders.empty:
        return pd.DataFrame(columns=["month", f"sales_{base}"])
    orders["month"] = pd.to_datetime(orders["order_date"]).dt.strftime("%Y-%m")
    orders[f"sales_{base}"] = [
        to_base(v, c, rates) for v, c in zip(orders["order_value"], orders["currency"])
    ]
    trend = orders.groupby("month", as_index=False)[f"sales_{base}"].sum()
    return trend.sort_values("month")
