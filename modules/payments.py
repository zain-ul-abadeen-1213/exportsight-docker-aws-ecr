"""ExportSight — Module 3: Payment & Receivables Management."""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import streamlit as st

from db.database import execute, fetch_df
from utils.finance import get_rates, invoice_summary
from utils.validators import CURRENCIES, validate_invoice, validate_payment
from .shared import confirm_row, demo_banner, fmt_money, kpi_cards, page_header

NAVY, TEAL = "#0F2A44", "#0E7C7B"


def render(conn) -> None:
    page_header("Payments & Receivables", "Invoices, collections and aging")
    demo_banner(conn)
    base, rates = get_rates(conn)
    inv = invoice_summary(conn)

    bal, paid, amt = f"balance_{base}", f"paid_{base}", f"amount_{base}"
    total_recv = float(inv[bal].sum()) if not inv.empty else 0.0
    overdue_amt = float(inv[inv["status"] == "Overdue"][bal].sum()) if not inv.empty else 0.0
    coll = (float(inv[paid].sum()) / float(inv[amt].sum()) * 100
            if not inv.empty and float(inv[amt].sum()) > 0 else 0.0)

    kpi_cards([
        ("Total Receivables", fmt_money(total_recv, base)),
        ("Overdue Amount", fmt_money(overdue_amt, base)),
        ("Collection Rate", f"{coll:.1f}%"),
        ("Open Invoices", str(int((inv["status"] != "Paid").sum()) if not inv.empty else 0)),
    ])

    tab_inv, tab_add_inv, tab_pay = st.tabs(
        ["📋 Invoices", "➕ New Invoice", "💰 Record Payment"])

    # ---------------------------------------------------------------- Invoices
    with tab_inv:
        fstat = st.selectbox("Status filter",
                             ["All", "Unpaid", "Partially Paid", "Paid", "Overdue"],
                             key="inv_f")
        show = inv if fstat == "All" else inv[inv["status"] == fstat]
        if show.empty:
            st.info("No invoices in this view.")
        else:
            st.dataframe(show[["invoice_id", "order_id", "buyer_name", "invoice_date",
                                "due_date", "currency", "amount", amt, paid, bal,
                                "status", "days_overdue"]],
                         width="stretch", hide_index=True)

        c1, c2 = st.columns(2)
        with c1:
            st.subheader("Receivables Aging")
            aging = inv[inv["status"] == "Overdue"]
            if aging.empty:
                st.success("Nothing overdue. 🎉")
            else:
                ag = aging.groupby("aging_bucket", as_index=False)[bal].sum()
                order = ["0–30 days", "31–60 days", "61–90 days", "Over 90 days"]
                ag["aging_bucket"] = pd.Categorical(ag["aging_bucket"], categories=order,
                                                    ordered=True)
                ag = ag.sort_values("aging_bucket")
                fig = px.bar(ag, x="aging_bucket", y=bal, color_discrete_sequence=[TEAL])
                fig.update_layout(xaxis_title="", yaxis_title=f"Overdue ({base})",
                                  plot_bgcolor="white")
                st.plotly_chart(fig, width="stretch")
                st.dataframe(ag, width="stretch", hide_index=True)
        with c2:
            st.subheader("Buyer-Wise Outstanding")
            bo = inv[inv[bal] > 0]
            if bo.empty:
                st.info("No outstanding balances.")
            else:
                grp = bo.groupby("buyer_name", as_index=False)[bal].sum().sort_values(
                    bal, ascending=False)
                fig = px.bar(grp, x="buyer_name", y=bal, color_discrete_sequence=[NAVY])
                fig.update_layout(xaxis_title="", yaxis_title=f"Outstanding ({base})",
                                  plot_bgcolor="white")
                st.plotly_chart(fig, width="stretch")
                st.dataframe(grp, width="stretch", hide_index=True)

    # ---------------------------------------------------------------- New invoice
    with tab_add_inv:
        orders = fetch_df(conn, """
            SELECT o.order_id, o.order_value, o.currency, o.buyer_id, b.name AS buyer_name
            FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
            WHERE o.order_id NOT IN (SELECT order_id FROM invoices)
            ORDER BY o.order_id""")
        if orders.empty:
            st.info("Every order already has an invoice, or there are no orders yet.")
        else:
            with st.form("add_invoice", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    iid = st.text_input("Invoice ID *", placeholder="INV-2010")
                    oid = st.selectbox("Related order *", orders["order_id"])
                    orow = orders.set_index("order_id").loc[oid]
                with c2:
                    idate = st.date_input("Invoice date *")
                    ddate = st.date_input("Due date *")
                    amount = st.number_input("Invoice amount *", min_value=0.0, step=0.01,
                                             value=float(orow["order_value"]))
                    ccy = st.selectbox("Currency *", sorted(CURRENCIES),
                                       index=sorted(CURRENCIES).index(orow["currency"]))
                notes = st.text_area("Notes")
                if st.form_submit_button("Create invoice", type="primary"):
                    data = {"invoice_id": iid.strip(), "order_id": oid,
                            "buyer_id": str(orow["buyer_id"]),
                            "invoice_date": idate.isoformat(), "due_date": ddate.isoformat(),
                            "amount": amount, "currency": ccy}
                    order_ids = set(fetch_df(conn, "SELECT order_id FROM orders")["order_id"])
                    ex_ids = set(inv["invoice_id"]) if not inv.empty else set()
                    order_buyer = dict(fetch_df(conn,
                        "SELECT order_id, buyer_id FROM orders").itertuples(index=False, name=None))
                    errors = validate_invoice(data, ex_ids, order_ids, order_buyer)
                    if errors:
                        for m in errors:
                            st.error(m)
                    else:
                        execute(conn, """
                            INSERT INTO invoices (invoice_id, order_id, buyer_id, invoice_date,
                                due_date, amount, currency, notes, created_at)
                            VALUES (?,?,?,?,?,?,?,?,date('now'))""",
                            (data["invoice_id"], oid, data["buyer_id"],
                             data["invoice_date"], data["due_date"], amount, ccy, notes))
                        st.success(f"Invoice {data['invoice_id']} created.")
                        st.rerun()

    # ---------------------------------------------------------------- Record payment
    with tab_pay:
        open_inv = inv[inv["status"] != "Paid"]
        if open_inv.empty:
            st.info("No open invoices — everything is paid. 🎉")
        else:
            with st.form("add_payment", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    pid = st.text_input("Payment ID *", placeholder="PAY-3010")
                    iid = st.selectbox("Invoice *", open_inv["invoice_id"],
                                       format_func=lambda x: f"{x} — balance "
                                       f"{open_inv.set_index('invoice_id').loc[x, bal]:,.0f} {base}")
                    pdate = st.date_input("Payment date *")
                with c2:
                    amount = st.number_input("Payment amount *", min_value=0.0, step=0.01)
                    ccy = st.selectbox("Currency *", sorted(CURRENCIES))
                    ref = st.text_input("Payment reference",
                                        placeholder="Bank transfer ref (must be unique)")
                notes = st.text_area("Notes")
                if st.form_submit_button("Record payment", type="primary"):
                    data = {"payment_id": pid.strip(), "invoice_id": iid,
                            "payment_date": pdate.isoformat(), "amount": amount,
                            "currency": ccy, "reference": ref.strip()}
                    ex_pids = set(fetch_df(conn, "SELECT payment_id FROM payments")["payment_id"])
                    ex_refs = set(r for r in
                                  fetch_df(conn, "SELECT reference FROM payments")["reference"]
                                  if r)
                    balances = dict(zip(open_inv["invoice_id"], open_inv[bal]))
                    errors = validate_payment(data, ex_pids, ex_refs,
                                              set(open_inv["invoice_id"]), balances, rates)
                    if errors:
                        for m in errors:
                            st.error(m)
                    else:
                        execute(conn, """
                            INSERT INTO payments (payment_id, invoice_id, payment_date,
                                amount, currency, reference, notes, created_at)
                            VALUES (?,?,?,?,?,?,?,date('now'))""",
                            (data["payment_id"], iid, data["payment_date"], amount, ccy,
                             ref.strip() or None, notes))
                        st.success(f"Payment {data['payment_id']} recorded.")
                        st.rerun()

            st.divider()
            st.subheader("Payment history")
            hist = fetch_df(conn, """
                SELECT p.payment_id, p.invoice_id, b.name AS buyer, p.payment_date,
                       p.amount, p.currency, p.reference
                FROM payments p JOIN invoices i ON i.invoice_id = p.invoice_id
                JOIN buyers b ON b.buyer_id = i.buyer_id
                ORDER BY p.payment_date DESC""")
            if hist.empty:
                st.info("No payments recorded yet.")
            else:
                st.dataframe(hist, width="stretch", hide_index=True)
                del_id = st.selectbox("Delete a payment (correct mistakes)",
                                      ["—"] + hist["payment_id"].tolist(), key="pay_del")
                if del_id != "—" and confirm_row(f"Delete payment {del_id}", key=f"pdel_{del_id}"):
                    execute(conn, "DELETE FROM payments WHERE payment_id = ?", (del_id,))
                    st.success(f"Payment {del_id} deleted.")
                    st.rerun()
