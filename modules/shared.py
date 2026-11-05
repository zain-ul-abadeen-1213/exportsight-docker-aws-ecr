"""ExportSight — shared Streamlit UI helpers (branding, KPI cards, banners)."""

from __future__ import annotations

import streamlit as st

from db.database import get_setting

BRAND_NAME = "ExportSight"
COMPANY_NAME = "Zain Tech Automation Solutions"

CUSTOM_CSS = """
<style>
  .brand-title { color:#0F2A44; font-weight:800; font-size:1.6rem; margin-bottom:0; }
  .brand-sub { color:#0E7C7B; font-size:0.95rem; margin-top:0; }
  .kpi-card { background:#F8FAFC; border:1px solid #E2E8F0; border-left:4px solid #0E7C7B;
              border-radius:10px; padding:12px 14px; margin-bottom:8px; }
  .kpi-label { color:#64748B; font-size:0.78rem; text-transform:uppercase; letter-spacing:0.04em; }
  .kpi-value { color:#0F2A44; font-size:1.35rem; font-weight:700; }
  .demo-banner { background:#FFFBEB; border:1px solid #F59E0B; border-radius:8px;
                 padding:8px 12px; color:#92400E; font-size:0.85rem; margin-bottom:12px; }
  .warn-card { background:#FEF2F2; border:1px solid #FCA5A5; border-radius:8px;
               padding:8px 12px; color:#991B1B; font-size:0.85rem; margin:8px 0; }
</style>
"""


def inject_css() -> None:
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


def page_header(title: str, subtitle: str = "") -> None:
    st.markdown(f'<p class="brand-title">{BRAND_NAME}</p>', unsafe_allow_html=True)
    st.markdown(
        f'<p class="brand-sub">by {COMPANY_NAME}'
        + (f" &nbsp;·&nbsp; {subtitle}" if subtitle else "") + "</p>",
        unsafe_allow_html=True,
    )
    st.markdown(f"### {title}")
    st.divider()


def is_demo(conn) -> bool:
    return (get_setting(conn, "demo_data", "false") or "false").lower() == "true"


def demo_banner(conn) -> None:
    if is_demo(conn):
        st.markdown(
            '<div class="demo-banner">📊 <b>Demo data</b> — you are viewing the '
            "fictional textile-exporter sample dataset. Replace it with your own "
            "data via Import, or clear it in Settings.</div>",
            unsafe_allow_html=True,
        )


def kpi_cards(kpis: list[tuple[str, str]]) -> None:
    """Render KPI cards in responsive columns (4 per row)."""
    for i in range(0, len(kpis), 4):
        cols = st.columns(4)
        for col, (label, value) in zip(cols, kpis[i:i + 4]):
            with col:
                st.markdown(
                    f'<div class="kpi-card"><div class="kpi-label">{label}</div>'
                    f'<div class="kpi-value">{value}</div></div>',
                    unsafe_allow_html=True,
                )


def fmt_money(amount: float, currency: str = "PKR") -> str:
    return f"{currency} {amount:,.0f}"


def confirm_row(label: str, key: str) -> bool:
    """Two-step delete confirmation pattern."""
    if f"confirm_{key}" not in st.session_state:
        st.session_state[f"confirm_{key}"] = False
    if st.button(label, key=f"btn_{key}", type="secondary"):
        st.session_state[f"confirm_{key}"] = True
    if st.session_state[f"confirm_{key}"]:
        c1, c2 = st.columns(2)
        with c1:
            if st.button("✅ Yes, delete", key=f"yes_{key}", type="primary"):
                st.session_state[f"confirm_{key}"] = False
                return True
        with c2:
            if st.button("❌ Cancel", key=f"no_{key}"):
                st.session_state[f"confirm_{key}"] = False
                st.rerun()
    return False
