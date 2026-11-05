"""ExportSight — Module 6: Settings (currency, FX rates, buyers, data)."""

from __future__ import annotations

import streamlit as st

from db.database import execute, fetch_df, get_setting, set_setting
from db.seed import DEMO_FX, seed_demo_data
from utils.validators import validate_buyer
from .shared import confirm_row, demo_banner, page_header


def render(conn) -> None:
    page_header("Settings", "Currency, exchange rates, buyers and data")
    demo_banner(conn)
    today = __import__("datetime").date.today().isoformat()

    st.subheader("💱 Currency & exchange rates")
    st.caption("All multi-currency figures are converted to the base currency using "
               "these documented rates. Rates are fictional demo values — update them "
               "to your bank's rates before relying on converted totals.")
    base = st.text_input("Base currency (ISO code)",
                         value=get_setting(conn, "base_currency", "PKR") or "PKR",
                         max_chars=3, key="set_base").upper().strip()
    fx_rows = fetch_df(conn, "SELECT key, value FROM settings WHERE key LIKE 'fx\\_%' ESCAPE '\\'")
    new_rates = {}
    cols = st.columns(4)
    for i, row in enumerate(fx_rows.itertuples()):
        code = row.key.split("_")[1]
        with cols[i % 4]:
            new_rates[code] = st.number_input(f"1 {code} → {base}", min_value=0.0,
                                              value=float(row.value), step=0.01,
                                              key=f"fx_{code}")
    rule = st.selectbox(
        "Revenue recognition rule",
        ["order_date", "shipment_date"],
        index=0 if (get_setting(conn, "revenue_recognition", "order_date")
                    or "order_date") == "order_date" else 1,
        help="order_date: revenue counts on the order date. shipment_date: revenue "
             "counts only once the order is Shipped/Delivered.",
        key="set_rule")
    if st.button("Save settings", type="primary", key="set_save"):
        set_setting(conn, "base_currency", base or "PKR", today)
        for code, rate in new_rates.items():
            set_setting(conn, f"fx_{code}_{base}", str(rate), today)
        set_setting(conn, "revenue_recognition", rule, today)
        st.success("Settings saved.")
        st.rerun()

    st.divider()
    st.subheader("🏢 Buyers")
    buyers = fetch_df(conn, "SELECT buyer_id, name, country, email, phone FROM buyers ORDER BY name")
    if buyers.empty:
        st.info("No buyers yet.")
    else:
        st.dataframe(buyers, width="stretch", hide_index=True)
    with st.form("add_buyer", clear_on_submit=True):
        c1, c2, c3 = st.columns(3)
        with c1:
            bid = st.text_input("Buyer ID *", placeholder="BYR-006")
            name = st.text_input("Name *")
        with c2:
            country = st.text_input("Country *")
            email = st.text_input("Email")
        with c3:
            phone = st.text_input("Phone")
        if st.form_submit_button("Add buyer", type="primary"):
            data = {"buyer_id": bid.strip(), "name": name.strip(),
                    "country": country.strip()}
            errors = validate_buyer(data, set(buyers["buyer_id"]) if not buyers.empty else set())
            if errors:
                for m in errors:
                    st.error(m)
            else:
                execute(conn, """INSERT INTO buyers (buyer_id, name, country, email, phone, created_at)
                                 VALUES (?,?,?,?,?,date('now'))""",
                        (data["buyer_id"], data["name"], data["country"],
                         email.strip(), phone.strip()))
                st.success(f"Buyer {data['buyer_id']} added.")
                st.rerun()

    st.divider()
    st.subheader("🗄️ Data management")
    st.caption("Reloading demo data replaces ALL current data with the fictional "
               "textile-exporter sample dataset. Clearing removes everything.")
    if confirm_row("Reload fictional demo data", key="reseed"):
        counts = seed_demo_data(conn)
        st.success("Demo data reloaded: " + ", ".join(f"{k}={v}" for k, v in counts.items()))
        st.rerun()
    if confirm_row("⚠️ Clear ALL data", key="wipe"):
        for tbl in ("order_costs", "payments", "invoices", "orders", "buyers"):
            execute(conn, f"DELETE FROM {tbl}")
        # keep FX defaults so the app still converts correctly
        for key, value in DEMO_FX.items():
            if key != "demo_data":
                set_setting(conn, key, value, today)
        set_setting(conn, "demo_data", "false", today)
        st.success("All data cleared.")
        st.rerun()
