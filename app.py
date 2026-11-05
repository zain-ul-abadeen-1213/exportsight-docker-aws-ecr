"""ExportSight — Business Intelligence & MIS Dashboard for export businesses.

Product: ExportSight · by Zain Tech Automation Solutions

Run with:
    streamlit run app.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent))

from db.database import DEFAULT_DB_PATH, get_connection, init_database  # noqa: E402
from db.seed import seed_demo_data  # noqa: E402
from modules import (orders, overview, payments, profitability,  # noqa: E402
                     reports, settings)
from modules.shared import BRAND_NAME, COMPANY_NAME, inject_css  # noqa: E402

st.set_page_config(page_title=f"{BRAND_NAME} — {COMPANY_NAME}",
                   page_icon="📊", layout="wide")

NAV_ITEMS = [
    ("Executive Overview", "📊", overview.render),
    ("Export Orders", "📦", orders.render),
    ("Payments & Receivables", "💰", payments.render),
    ("Profitability Analysis", "📈", profitability.render),
    ("Management Reports", "📑", reports.render),
    ("Settings", "⚙️", settings.render),
]


@st.cache_resource
def _connect():
    """Create schema on first run; seed demo data only on a fresh database."""
    fresh = not DEFAULT_DB_PATH.exists()
    init_database(DEFAULT_DB_PATH)
    conn = get_connection(DEFAULT_DB_PATH)
    if fresh:
        seed_demo_data(conn)
    return conn


def main() -> None:
    inject_css()
    conn = _connect()

    with st.sidebar:
        st.markdown(f"## 📊 {BRAND_NAME}")
        st.caption(f"by {COMPANY_NAME}")
        st.divider()
        labels = [f"{icon} {name}" for name, icon, _ in NAV_ITEMS]
        choice = st.radio("Navigate", labels, label_visibility="collapsed")
        st.divider()
        st.caption("Fictional demo data is clearly labeled wherever shown.")

    for name, icon, render_fn in NAV_ITEMS:
        if choice == f"{icon} {name}":
            render_fn(conn)
            break

    st.sidebar.divider()
    st.sidebar.caption(f"{BRAND_NAME} · by {COMPANY_NAME}")


if __name__ == "__main__":
    main()
