"""ExportSight — Module 2: Export Order Management (CRUD + import/export)."""

from __future__ import annotations

import sqlite3

import pandas as pd
import streamlit as st

from db.database import execute, fetch_df, fetch_one
from utils.finance import delayed_orders, get_rates, to_base
from utils.io_helpers import (import_orders, read_upload, sample_order_csv,
                              to_csv_bytes, to_excel_bytes)
from utils.validators import CURRENCIES, validate_order
from .shared import confirm_row, demo_banner, fmt_money, page_header


def _buyer_options(conn):
    df = fetch_df(conn, "SELECT buyer_id, name FROM buyers ORDER BY name")
    return df


def render(conn) -> None:
    page_header("Export Orders", "Create, track and fulfil export orders")
    demo_banner(conn)
    base, rates = get_rates(conn)

    tab_view, tab_add, tab_edit, tab_io = st.tabs(
        ["📋 Browse Orders", "➕ Add Order", "✏️ Edit / Delete", "🔄 Import / Export"])

    # ---------------------------------------------------------------- Browse
    with tab_view:
        col_s, col_f = st.columns([2, 1])
        with col_s:
            q = st.text_input("Search (ID, buyer, product, country)", key="ord_q")
        with col_f:
            fstat = st.selectbox("Shipment status",
                                 ["All", "Pending", "Shipped", "Delivered", "Cancelled"],
                                 key="ord_fstat")
        orders = fetch_df(conn, """
            SELECT o.order_id, o.order_date, b.name AS buyer, o.destination_country,
                   o.product, o.quantity, o.unit_price, o.currency, o.order_value,
                   o.production_status, o.shipment_status,
                   o.expected_delivery_date, o.actual_delivery_date, o.notes
            FROM orders o JOIN buyers b ON b.buyer_id = o.buyer_id
            ORDER BY o.order_date DESC""")
        if q:
            ql = q.lower()
            orders = orders[orders.apply(
                lambda r: ql in str(r["order_id"]).lower()
                or ql in str(r["buyer"]).lower() or ql in str(r["product"]).lower()
                or ql in str(r["destination_country"]).lower(), axis=1)]
        if fstat != "All":
            orders = orders[orders["shipment_status"] == fstat]
        if orders.empty:
            st.info("No orders match. Add your first order in the ➕ tab.")
        else:
            show = orders.copy()
            show[f"value_{base}"] = [to_base(v, c, rates)
                                     for v, c in zip(show["order_value"], show["currency"])]
            st.dataframe(show, width="stretch", hide_index=True)
            st.caption(f"{len(show)} order(s) · values also shown in {base}")

        alerts = delayed_orders(conn)
        if not alerts.empty:
            st.markdown('<div class="warn-card">⚠️ <b>Delivery alerts</b></div>',
                        unsafe_allow_html=True)
            st.dataframe(alerts[["order_id", "buyer_name", "product", "alert", "days",
                                 "expected_delivery_date"]],
                         width="stretch", hide_index=True)

    # ---------------------------------------------------------------- Add
    with tab_add:
        buyers = _buyer_options(conn)
        if buyers.empty:
            st.warning("Add a buyer first (Settings → Buyers).")
        else:
            with st.form("add_order", clear_on_submit=True):
                c1, c2, c3 = st.columns(3)
                with c1:
                    oid = st.text_input("Order ID *", placeholder="ORD-1020")
                    odate = st.date_input("Order date *")
                    buyer = st.selectbox("Buyer *", buyers["buyer_id"],
                                         format_func=lambda x: buyers.set_index("buyer_id").loc[x, "name"])
                with c2:
                    country = st.text_input("Destination country *")
                    product = st.text_input("Product *")
                    qty = st.number_input("Quantity *", min_value=0.0, step=1.0)
                with c3:
                    price = st.number_input("Unit price *", min_value=0.0, step=0.01)
                    ccy = st.selectbox("Currency *", sorted(CURRENCIES))
                    pstat = st.selectbox("Production status",
                                         ["Pending", "In Production", "Completed"])
                    sstat = st.selectbox("Shipment status",
                                         ["Pending", "Shipped", "Delivered", "Cancelled"])
                c4, c5 = st.columns(2)
                with c4:
                    expd = st.date_input("Expected delivery", value=None, key="add_expd")
                with c5:
                    actd = st.date_input("Actual delivery", value=None, key="add_actd")
                notes = st.text_area("Notes")
                if st.form_submit_button("Create order", type="primary"):
                    data = {
                        "order_id": oid.strip(), "order_date": odate.isoformat(),
                        "buyer_id": buyer, "destination_country": country.strip(),
                        "product": product.strip(), "quantity": qty, "unit_price": price,
                        "currency": ccy, "production_status": pstat,
                        "shipment_status": sstat,
                        "expected_delivery_date": expd.isoformat() if expd else "",
                        "actual_delivery_date": actd.isoformat() if actd else "",
                    }
                    existing = set(fetch_df(conn, "SELECT order_id FROM orders")["order_id"])
                    errors = validate_order(data, existing)
                    if errors:
                        for msg in errors:
                            st.error(msg)
                    else:
                        execute(conn, """
                            INSERT INTO orders (order_id, order_date, buyer_id,
                                destination_country, product, quantity, unit_price,
                                currency, order_value, production_status, shipment_status,
                                expected_delivery_date, actual_delivery_date, notes, created_at)
                            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,date('now'))""",
                            (data["order_id"], data["order_date"], buyer,
                             data["destination_country"], data["product"], qty, price, ccy,
                             round(qty * price, 2), pstat, sstat,
                             data["expected_delivery_date"] or None,
                             data["actual_delivery_date"] or None, notes))
                        st.success(f"Order {data['order_id']} created "
                                   f"({fmt_money(round(qty*price,2), ccy)}).")
                        st.rerun()

    # ---------------------------------------------------------------- Edit/Delete
    with tab_edit:
        ids = fetch_df(conn, "SELECT order_id FROM orders ORDER BY order_id")["order_id"].tolist()
        if not ids:
            st.info("No orders to edit yet.")
        else:
            sel = st.selectbox("Select order", ids, key="edit_sel")
            row = fetch_one(conn, "SELECT * FROM orders WHERE order_id = ?", (sel,))
            buyers = _buyer_options(conn)
            with st.form("edit_order"):
                c1, c2, c3 = st.columns(3)
                with c1:
                    odate = st.text_input("Order date", row["order_date"])
                    buyer = st.selectbox("Buyer", buyers["buyer_id"],
                                         index=list(buyers["buyer_id"]).index(row["buyer_id"]),
                                         format_func=lambda x: buyers.set_index("buyer_id").loc[x, "name"])
                    country = st.text_input("Destination country", row["destination_country"])
                with c2:
                    product = st.text_input("Product", row["product"])
                    qty = st.number_input("Quantity", value=float(row["quantity"]), min_value=0.0)
                    price = st.number_input("Unit price", value=float(row["unit_price"]), min_value=0.0)
                with c3:
                    ccy = st.selectbox("Currency", sorted(CURRENCIES),
                                       index=sorted(CURRENCIES).index(row["currency"]))
                    pstat = st.selectbox("Production status",
                                         ["Pending", "In Production", "Completed"],
                                         index=["Pending", "In Production", "Completed"].index(row["production_status"]))
                    sstat = st.selectbox("Shipment status",
                                         ["Pending", "Shipped", "Delivered", "Cancelled"],
                                         index=["Pending", "Shipped", "Delivered", "Cancelled"].index(row["shipment_status"]))
                c4, c5 = st.columns(2)
                with c4:
                    expd = st.text_input("Expected delivery (YYYY-MM-DD)",
                                         row["expected_delivery_date"] or "")
                with c5:
                    actd = st.text_input("Actual delivery (YYYY-MM-DD)",
                                         row["actual_delivery_date"] or "")
                notes = st.text_area("Notes", row["notes"] or "")
                if st.form_submit_button("Save changes", type="primary"):
                    data = {"order_id": sel, "order_date": odate, "buyer_id": buyer,
                            "destination_country": country, "product": product,
                            "quantity": qty, "unit_price": price, "currency": ccy,
                            "production_status": pstat, "shipment_status": sstat,
                            "expected_delivery_date": expd, "actual_delivery_date": actd}
                    errors = validate_order(data, set(ids) - {sel})
                    if errors:
                        for msg in errors:
                            st.error(msg)
                    else:
                        execute(conn, """
                            UPDATE orders SET order_date=?, buyer_id=?, destination_country=?,
                                product=?, quantity=?, unit_price=?, currency=?, order_value=?,
                                production_status=?, shipment_status=?,
                                expected_delivery_date=?, actual_delivery_date=?, notes=?
                            WHERE order_id=?""",
                            (odate, buyer, country.strip(), product.strip(), qty, price, ccy,
                             round(qty * price, 2), pstat, sstat, expd or None, actd or None,
                             notes, sel))
                        st.success(f"Order {sel} updated.")
                        st.rerun()
            st.divider()
            st.subheader("Delete order")
            st.caption("Orders linked to invoices cannot be deleted (referential integrity).")
            if confirm_row(f"Delete {sel}", key=f"del_{sel}"):
                try:
                    n = execute(conn, "DELETE FROM orders WHERE order_id = ?", (sel,))
                    if n:
                        st.success(f"Order {sel} deleted.")
                        st.rerun()
                    else:
                        st.error("Order not found.")
                except sqlite3.IntegrityError:
                    st.error("Cannot delete: this order has invoices linked to it. "
                             "Delete the invoices first.")

    # ---------------------------------------------------------------- Import/Export
    with tab_io:
        st.subheader("Import orders")
        st.download_button("⬇️ Download sample CSV template", sample_order_csv(),
                           file_name="orders_template.csv", mime="text/csv")
        up = st.file_uploader("Upload CSV or Excel", type=["csv", "xlsx", "xls"], key="ord_up")
        if up:
            df, err = read_upload(up)
            if err:
                st.error(err)
            else:
                st.write("Preview:", df.head())
                if st.button("Validate & import", type="primary", key="ord_import"):
                    report = import_orders(conn, df)
                    st.success(f"Inserted {report['inserted']} row(s), "
                               f"skipped {report['skipped']}.")
                    for row_no, msgs in report["errors"]:
                        st.error(f"Row {row_no}: " + "; ".join(msgs))
                    if report["inserted"]:
                        st.rerun()
        st.divider()
        st.subheader("Export orders")
        orders = fetch_df(conn, "SELECT * FROM orders ORDER BY order_date")
        c1, c2 = st.columns(2)
        with c1:
            st.download_button("⬇️ Export CSV", to_csv_bytes(orders),
                               file_name="orders_export.csv", mime="text/csv")
        with c2:
            st.download_button("⬇️ Export Excel", to_excel_bytes(orders, "Orders"),
                               file_name="orders_export.xlsx",
                               mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
