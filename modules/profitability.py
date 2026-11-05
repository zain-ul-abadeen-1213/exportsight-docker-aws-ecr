"""ExportSight — Module 4: Order Profitability Analysis.

Terminology is strict: we report GROSS profit (revenue minus recorded
DIRECT costs) — never net profit. Missing costs are flagged, never invented.
"""

from __future__ import annotations

import plotly.express as px
import streamlit as st

from db.database import execute, fetch_df, get_setting
from utils.finance import get_rates, order_profitability
from utils.validators import CURRENCIES, validate_cost
from .shared import demo_banner, fmt_money, kpi_cards, page_header

NAVY, TEAL = "#0F2A44", "#0E7C7B"


def render(conn) -> None:
    page_header("Profitability Analysis", "Gross profit per order — direct costs only")
    demo_banner(conn)
    base, rates = get_rates(conn)
    rule = get_setting(conn, "revenue_recognition", "order_date")
    st.caption(f"Revenue recognition rule: **{rule}** (configurable in Settings). "
               "Gross profit = recorded revenue − recorded direct costs.")

    prof = order_profitability(conn)
    if prof.empty:
        st.info("No orders yet.")
        return

    total_rev = float(prof["revenue_base"].sum())
    total_cost = float(prof["costs_base"].sum())
    total_gp = float(prof["gross_profit_base"].sum())
    avg_margin = round(total_gp / total_rev * 100, 1) if total_rev > 0 else 0.0
    incomplete = int((~prof["costs_complete"]).sum())
    neg = int(prof["negative_margin"].sum())

    kpi_cards([
        ("Recorded Revenue", fmt_money(total_rev, base)),
        ("Recorded Direct Costs", fmt_money(total_cost, base)),
        ("Estimated Gross Profit", fmt_money(total_gp, base)),
        ("Avg. Gross Margin", f"{avg_margin}%"),
    ])
    if incomplete:
        st.markdown(f'<div class="warn-card">⚠️ {incomplete} order(s) have '
                    "no recorded costs — margins shown as estimates.</div>",
                    unsafe_allow_html=True)
    if neg:
        st.markdown(f'<div class="warn-card">🔻 {neg} order(s) show negative '
                    "gross profit (costs exceed recorded revenue).</div>",
                    unsafe_allow_html=True)

    tab_table, tab_charts, tab_costs = st.tabs(
        ["📋 Per-Order Table", "📊 Breakdowns", "➕ Record Costs"])

    with tab_table:
        show = prof[["order_id", "order_date", "buyer_name", "product",
                     "revenue_base", "costs_base", "gross_profit_base",
                     "gross_margin_pct", "costs_complete", "negative_margin"]].copy()
        show.columns = ["Order", "Date", "Buyer", "Product", f"Revenue ({base})",
                        f"Direct costs ({base})", f"Gross profit ({base})",
                        "Margin %", "Costs recorded", "Negative margin"]
        st.dataframe(show, width="stretch", hide_index=True)
        st.caption("Margin % = gross profit ÷ revenue. 'Costs recorded = No' means "
                   "the profit figure is incomplete, not final.")

    with tab_charts:
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Buyer-Wise Profitability")
            b = prof.groupby("buyer_name", as_index=False)["gross_profit_base"].sum()
            b = b.sort_values("gross_profit_base", ascending=False)
            fig = px.bar(b, x="buyer_name", y="gross_profit_base",
                         color_discrete_sequence=[TEAL])
            fig.update_layout(xaxis_title="", yaxis_title=f"Gross profit ({base})",
                              plot_bgcolor="white")
            st.plotly_chart(fig, width="stretch")
        with c2:
            st.subheader("Product-Wise Profitability")
            p = prof.groupby("product", as_index=False)["gross_profit_base"].sum()
            p = p.sort_values("gross_profit_base", ascending=False)
            fig = px.bar(p, x="product", y="gross_profit_base",
                         color_discrete_sequence=[NAVY])
            fig.update_layout(xaxis_title="", yaxis_title=f"Gross profit ({base})",
                              plot_bgcolor="white")
            st.plotly_chart(fig, width="stretch")
        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Country-Wise Profitability")
            co = prof.groupby("destination_country", as_index=False)["gross_profit_base"].sum()
            co = co.sort_values("gross_profit_base", ascending=False)
            fig = px.bar(co, x="destination_country", y="gross_profit_base",
                         color_discrete_sequence=[TEAL])
            fig.update_layout(xaxis_title="", yaxis_title=f"Gross profit ({base})",
                              plot_bgcolor="white")
            st.plotly_chart(fig, width="stretch")
        with c2:
            st.subheader("Monthly Profitability Trend")
            m = prof.copy()
            m["month"] = m["order_date"].str[:7]
            mt = m.groupby("month", as_index=False)["gross_profit_base"].sum().sort_values("month")
            if mt.empty:
                st.info("No data.")
            else:
                fig = px.line(mt, x="month", y="gross_profit_base", markers=True,
                              color_discrete_sequence=[NAVY])
                fig.update_layout(xaxis_title="", yaxis_title=f"Gross profit ({base})",
                                  plot_bgcolor="white")
                st.plotly_chart(fig, width="stretch")

    with tab_costs:
        st.subheader("Record a direct cost")
        order_ids = fetch_df(conn, "SELECT order_id FROM orders ORDER BY order_id")["order_id"].tolist()
        if not order_ids:
            st.info("Create an order first.")
        else:
            from utils.validators import COST_CATEGORIES
            with st.form("add_cost", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    oid = st.selectbox("Order *", order_ids)
                    cat = st.selectbox("Cost category *", sorted(COST_CATEGORIES))
                with c2:
                    amount = st.number_input("Amount *", min_value=0.0, step=0.01)
                    ccy = st.selectbox("Currency *", sorted(CURRENCIES))
                with c3:
                    notes = st.text_area("Notes")
                if st.form_submit_button("Save cost", type="primary"):
                    data = {"order_id": oid, "cost_category": cat,
                            "amount": amount, "currency": ccy}
                    errors = validate_cost(data, set(order_ids))
                    if errors:
                        for m in errors:
                            st.error(m)
                    else:
                        execute(conn, """
                            INSERT INTO order_costs (order_id, cost_category, amount,
                                currency, notes, created_at)
                            VALUES (?,?,?,?,?,date('now'))""",
                            (oid, cat, amount, ccy, notes))
                        st.success("Cost recorded.")
                        st.rerun()
        st.divider()
        st.subheader("Recorded costs")
        costs = fetch_df(conn, """
            SELECT c.cost_id, c.order_id, c.cost_category, c.amount, c.currency, c.notes
            FROM order_costs c ORDER BY c.order_id, c.cost_category""")
        if costs.empty:
            st.info("No costs recorded yet.")
        else:
            st.dataframe(costs, width="stretch", hide_index=True)
