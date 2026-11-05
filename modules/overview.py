"""ExportSight — Module 1: Executive Overview."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from db.database import fetch_df
from utils.finance import (get_rates, kpi_overview, monthly_sales_trend,
                           to_base)
from .shared import demo_banner, fmt_money, kpi_cards, page_header

NAVY, TEAL = "#0F2A44", "#0E7C7B"


def render(conn) -> None:
    page_header("Executive Overview", "Command centre for your export business")
    demo_banner(conn)
    base, rates = get_rates(conn)

    # ---- Filters ---------------------------------------------------------
    buyers = fetch_df(conn, "SELECT buyer_id, name FROM buyers ORDER BY name")
    countries = fetch_df(conn, "SELECT DISTINCT destination_country FROM orders ORDER BY 1")
    with st.expander("🔎 Filters", expanded=True):
        c1, c2, c3, c4, c5 = st.columns(5)
        with c1:
            start = st.date_input("From", value=None, key="ov_start")
        with c2:
            end = st.date_input("To", value=None, key="ov_end")
        with c3:
            buyer = st.selectbox("Buyer", ["All"] + buyers["buyer_id"].tolist(),
                                 format_func=lambda x: "All" if x == "All"
                                 else buyers.set_index("buyer_id").loc[x, "name"],
                                 key="ov_buyer")
        with c4:
            country = st.selectbox("Country", ["All"] + countries["destination_country"].tolist(),
                                   key="ov_country")
        with c5:
            ship = st.selectbox("Order status",
                                ["All", "Pending", "Shipped", "Delivered", "Cancelled"],
                                key="ov_ship")

    kpis = kpi_overview(
        conn,
        start_date=start.isoformat() if start else None,
        end_date=end.isoformat() if end else None,
        buyer_id=None if buyer == "All" else buyer,
        country=None if country == "All" else country,
        ship_status=None if ship == "All" else ship,
    )

    kpi_cards([
        ("Total Export Sales", fmt_money(kpis["total_export_sales"], base)),
        ("Total Orders", str(kpis["total_orders"])),
        ("Active Orders", str(kpis["active_orders"])),
        ("Payments Received", fmt_money(kpis["payments_received"], base)),
        ("Outstanding Receivables", fmt_money(kpis["outstanding_receivables"], base)),
        (f"Overdue Invoices ({kpis['overdue_count']})",
         fmt_money(kpis["overdue_invoices"], base)),
        ("Est. Gross Profit", fmt_money(kpis["estimated_gross_profit"], base)),
        ("Collection Rate", f"{kpis['collection_rate']}%"),
    ])

    # ---- Charts ----------------------------------------------------------
    trend = monthly_sales_trend(conn)
    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Monthly Sales Trend")
        if trend.empty:
            st.info("No sales data yet.")
        else:
            fig = px.bar(trend, x="month", y=f"sales_{base}", color_discrete_sequence=[TEAL])
            fig.update_layout(xaxis_title="", yaxis_title=f"Sales ({base})",
                              plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Order Status Distribution")
        dist = fetch_df(conn, "SELECT shipment_status, COUNT(*) AS n FROM orders GROUP BY 1")
        if dist.empty:
            st.info("No orders yet.")
        else:
            fig = px.pie(dist, names="shipment_status", values="n",
                         color_discrete_sequence=px.colors.sequential.Teal)
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

    c1, c2 = st.columns(2)
    with c1:
        st.subheader("Top 5 Buyers")
        top = fetch_df(conn, """
            SELECT b.name AS buyer, SUM(o.order_value) AS total, o.currency
            FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
            GROUP BY b.buyer_id""")
        if top.empty:
            st.info("No orders yet.")
        else:
            top[f"total_{base}"] = [to_base(v, c, rates)
                                    for v, c in zip(top["total"], top["currency"])]
            top = (top.groupby("buyer", as_index=False)[f"total_{base}"].sum()
                      .sort_values(f"total_{base}", ascending=False).head(5))
            fig = px.bar(top, x=f"total_{base}", y="buyer", orientation="h",
                         color_discrete_sequence=[NAVY])
            fig.update_layout(xaxis_title=f"Sales ({base})", yaxis_title="",
                              plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")
    with c2:
        st.subheader("Country-Wise Export Performance")
        ctry = fetch_df(conn, """
            SELECT destination_country AS country, SUM(order_value) AS total, currency
            FROM orders GROUP BY destination_country, currency""")
        if ctry.empty:
            st.info("No orders yet.")
        else:
            ctry[f"total_{base}"] = [to_base(v, c, rates)
                                     for v, c in zip(ctry["total"], ctry["currency"])]
            ctry = (ctry.groupby("country", as_index=False)[f"total_{base}"].sum()
                       .sort_values(f"total_{base}", ascending=False))
            fig = px.bar(ctry, x="country", y=f"total_{base}",
                         color_discrete_sequence=[TEAL])
            fig.update_layout(xaxis_title="", yaxis_title=f"Sales ({base})",
                              plot_bgcolor="white", margin=dict(l=10, r=10, t=10, b=10))
            st.plotly_chart(fig, width="stretch")

    st.caption(f"All figures converted to {base} using the documented rates in Settings. "
               "KPIs respond to the filters above.")
