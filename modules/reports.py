"""ExportSight — Module 5: Management Reports & Business Insights."""

from __future__ import annotations

from datetime import date, timedelta

import pandas as pd
import streamlit as st

from db.database import fetch_df
from utils.finance import (delayed_orders, get_rates, invoice_summary,
                           kpi_overview, order_profitability, to_base)
from utils.io_helpers import to_csv_bytes, to_excel_bytes
from utils.pdf_reports import build_pdf
from .shared import demo_banner, fmt_money, is_demo, page_header


def _period_bounds(kind: str, ref: date):
    if kind == "Weekly":
        start = ref - timedelta(days=6)
        return start.isoformat(), ref.isoformat(), f"Week of {start.isoformat()} – {ref.isoformat()}"
    start = ref.replace(day=1)
    return start.isoformat(), ref.isoformat(), f"Month of {start.strftime('%B %Y')}"


def _sales_df(conn, start: str, end: str) -> pd.DataFrame:
    base, rates = get_rates(conn)
    df = fetch_df(conn, """
        SELECT o.order_id, o.order_date, b.name AS buyer, o.destination_country,
               o.product, o.quantity, o.unit_price, o.currency, o.order_value,
               o.shipment_status
        FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
        WHERE o.order_date BETWEEN ? AND ? ORDER BY o.order_date""", (start, end))
    if not df.empty:
        df[f"value_{base}"] = [to_base(v, c, rates)
                               for v, c in zip(df["order_value"], df["currency"])]
    return df


def _build_report(conn, kind: str, start: str, end: str, label: str):
    """Return (title, kpis, sections) for the chosen report."""
    base, rates = get_rates(conn)
    k = kpi_overview(conn, start_date=start, end_date=end)
    inv = invoice_summary(conn)
    inv_p = inv[(inv["invoice_date"] >= start) & (inv["invoice_date"] <= end)]
    bal, paid = f"balance_{base}", f"paid_{base}"

    money = lambda v: fmt_money(v, base)  # noqa: E731
    kpis = [("Total Export Sales", money(k["total_export_sales"])),
            ("Total Orders", str(k["total_orders"])),
            ("Payments Received", money(k["payments_received"])),
            ("Outstanding Receivables", money(k["outstanding_receivables"])),
            ("Overdue Invoices", money(k["overdue_invoices"])),
            ("Est. Gross Profit", money(k["estimated_gross_profit"]))]

    if kind == "Weekly Management Report" or kind == "Monthly Management Report":
        sales = _sales_df(conn, start, end)
        sections = [
            ("Orders in period", sales[["order_id", "order_date", "buyer",
                                        "destination_country", "product",
                                        f"value_{base}", "shipment_status"]]
             if not sales.empty else sales),
            ("Overdue invoices", inv_p[inv_p["status"] == "Overdue"]
             [["invoice_id", "buyer_name", "due_date", bal, "days_overdue"]]
             if not inv_p.empty else inv_p),
        ]
    elif kind == "Sales Performance Report":
        sales = _sales_df(conn, start, end)
        by_buyer = (sales.groupby("buyer", as_index=False)[f"value_{base}"].sum()
                    .sort_values(f"value_{base}", ascending=False)) if not sales.empty else sales
        by_country = (sales.groupby("destination_country", as_index=False)[f"value_{base}"]
                      .sum().sort_values(f"value_{base}", ascending=False)) if not sales.empty else sales
        sections = [("Orders", sales), ("Sales by buyer", by_buyer),
                    ("Sales by country", by_country)]
    elif kind == "Outstanding Payments Report":
        open_inv = inv[inv["status"] != "Paid"]
        aging = (open_inv[open_inv["status"] == "Overdue"]
                 .groupby("aging_bucket", as_index=False)[bal].sum()
                 if not open_inv.empty else open_inv)
        buyer_out = (open_inv.groupby("buyer_name", as_index=False)[bal].sum()
                     .sort_values(bal, ascending=False)) if not open_inv.empty else open_inv
        sections = [("Open invoices", open_inv[["invoice_id", "buyer_name", "due_date",
                                                "status", bal, "days_overdue"]]
                     if not open_inv.empty else open_inv),
                    ("Aging summary", aging), ("Buyer-wise outstanding", buyer_out)]
    elif kind == "Delayed Orders Report":
        alerts = delayed_orders(conn)
        sections = [("Delayed & approaching orders", alerts)]
    elif kind == "Order Profitability Report":
        prof = order_profitability(conn)
        sections = [("Per-order profitability",
                     prof[["order_id", "buyer_name", "product", "revenue_base",
                           "costs_base", "gross_profit_base", "gross_margin_pct",
                           "costs_complete"]] if not prof.empty else prof)]
    else:  # Buyer Performance Report
        sales = _sales_df(conn, start, end)
        prof = order_profitability(conn)
        buyers = fetch_df(conn, "SELECT buyer_id, name FROM buyers")
        rows = []
        for _, b in buyers.iterrows():
            bs = sales[sales["buyer"] == b["name"]] if not sales.empty else sales
            bp = prof[prof["buyer_name"] == b["name"]] if not prof.empty else prof
            bi = inv[inv["buyer_name"] == b["name"]] if not inv.empty else inv
            rows.append({
                "buyer": b["name"],
                f"sales_{base}": round(float(bs[f"value_{base}"].sum()) if not bs.empty else 0, 2),
                "orders": int(len(bs)),
                f"paid_{base}": round(float(bi[paid].sum()) if not bi.empty else 0, 2),
                f"outstanding_{base}": round(float(bi[bal].sum()) if not bi.empty else 0, 2),
                f"gross_profit_{base}": round(float(bp["gross_profit_base"].sum())
                                             if not bp.empty else 0, 2),
            })
        sections = [("Buyer performance", pd.DataFrame(rows))]
    return f"{kind} — {label}", kpis, sections


def _insights(conn) -> list[tuple[str, str]]:
    """Rule-based insights, every one computed from live data."""
    base, rates = get_rates(conn)
    today = date.today().isoformat()
    out: list[tuple[str, str]] = []

    inv = invoice_summary(conn, today)
    overdue = inv[inv["status"] == "Overdue"].sort_values("days_overdue", ascending=False)
    if overdue.empty:
        out.append(("✅ Collections", "No overdue invoices right now."))
    else:
        top = overdue.iloc[0]
        out.append(("⚠️ Overdue invoices",
                    f"{len(overdue)} overdue, totalling "
                    f"{fmt_money(float(overdue[f'balance_{base}'].sum()), base)}. "
                    f"Oldest: {top['invoice_id']} ({top['buyer_name']}, "
                    f"{int(top['days_overdue'])} days overdue)."))

    alerts = delayed_orders(conn, today)
    delayed = alerts[alerts["alert"] == "Delayed"]
    approaching = alerts[alerts["alert"] == "Approaching deadline"]
    if not delayed.empty:
        out.append(("🔻 Delayed shipments",
                    f"{len(delayed)} order(s) past expected delivery: "
                    + ", ".join(delayed["order_id"].head(5))))
    if not approaching.empty:
        out.append(("⏰ Approaching deadlines",
                    f"{len(approaching)} order(s) due within 7 days: "
                    + ", ".join(approaching["order_id"].head(5))))
    if delayed.empty and approaching.empty:
        out.append(("✅ Deliveries", "No delayed or at-risk shipments."))

    sales = _sales_df(conn, (date.today() - timedelta(days=365)).isoformat(), today)
    if not sales.empty:
        top_buyer = sales.groupby("buyer", as_index=False)[f"value_{base}"].sum() \
            .sort_values(f"value_{base}", ascending=False).iloc[0]
        out.append(("🏆 Top buyer",
                    f"{top_buyer['buyer']} leads with "
                    f"{fmt_money(float(top_buyer[f'value_{base}']), base)} in the last 12 months."))

    prof = order_profitability(conn)
    if not prof.empty:
        neg = prof[prof["negative_margin"]]
        inc = prof[~prof["costs_complete"]]
        if not neg.empty:
            out.append(("🔻 Negative margins",
                        "Costs exceed recorded revenue on: " + ", ".join(neg["order_id"])))
        if not inc.empty:
            out.append(("⚠️ Incomplete cost records",
                        f"{len(inc)} order(s) have no recorded costs — margins are estimates: "
                        + ", ".join(inc["order_id"].head(5))))

    # Sales vs previous 30-day period.
    cur = _sales_df(conn, (date.today() - timedelta(days=30)).isoformat(), today)
    prev = _sales_df(conn, (date.today() - timedelta(days=60)).isoformat(),
                     (date.today() - timedelta(days=31)).isoformat())
    cur_v = float(cur[f"value_{base}"].sum()) if not cur.empty else 0.0
    prev_v = float(prev[f"value_{base}"].sum()) if not prev.empty else 0.0
    if prev_v > 0:
        chg = (cur_v - prev_v) / prev_v * 100
        arrow = "📈" if chg >= 0 else "📉"
        out.append((f"{arrow} Sales vs previous 30 days",
                    f"{chg:+.1f}% ({fmt_money(cur_v, base)} vs {fmt_money(prev_v, base)})."))
    return out


def render(conn) -> None:
    page_header("Management Reports", "Board-ready reports & insights")
    demo_banner(conn)

    st.subheader("🧠 Business Insights")
    for title, text in _insights(conn):
        st.markdown(f"**{title}** — {text}")
    st.divider()

    st.subheader("Generate a report")
    kind = st.selectbox("Report type", [
        "Weekly Management Report", "Monthly Management Report",
        "Sales Performance Report", "Outstanding Payments Report",
        "Delayed Orders Report", "Order Profitability Report",
        "Buyer Performance Report"], key="rep_kind")
    c1, c2 = st.columns(2)
    with c1:
        start = st.date_input("From", value=date.today() - timedelta(days=30), key="rep_start")
    with c2:
        end = st.date_input("To", value=date.today(), key="rep_end")
    label = f"{start.isoformat()} to {end.isoformat()}"

    if st.button("Generate report", type="primary", key="rep_gen"):
        st.session_state["report_cache"] = _build_report(
            conn, kind, start.isoformat(), end.isoformat(), label)
        st.session_state["report_label"] = label

    cached = st.session_state.get("report_cache")
    if cached:
        title, kpis, sections = cached
        st.markdown(f"### {title}")
        for label_, value in kpis:
            st.markdown(f"- **{label_}:** {value}")
        for heading, df in sections:
            st.markdown(f"#### {heading}")
            st.dataframe(df, width="stretch", hide_index=True)

        # Downloads
        c1, c2, c3 = st.columns(3)
        combined = pd.concat(
            [d.assign(_section=h) for h, d in sections if not d.empty],
            ignore_index=True) if any(not d.empty for _, d in sections) \
            else pd.DataFrame()
        with c1:
            st.download_button("⬇️ CSV", to_csv_bytes(combined),
                               file_name="exportsight_report.csv", mime="text/csv")
        with c2:
            st.download_button("⬇️ Excel", to_excel_bytes(combined, "Report"),
                               file_name="exportsight_report.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        with c3:
            pdf = build_pdf(title, kpis=kpis, sections=sections,
                            subtitle=f"Period: {st.session_state.get('report_label', '')}",
                            demo_notice=is_demo(conn))
            st.download_button("⬇️ PDF", pdf, file_name="exportsight_report.pdf",
                               mime="application/pdf")
