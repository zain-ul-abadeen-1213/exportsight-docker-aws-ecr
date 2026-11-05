"""ExportSight tests — PDF report generation (spec section 10)."""

import pandas as pd

from utils.pdf_reports import BRAND_LINE, build_pdf


def test_pdf_is_valid_and_branded():
    df = pd.DataFrame([{"order": "O1", "revenue": 1000.5},
                       {"order": "O2", "revenue": 250.0}])
    blob = build_pdf("Test Report",
                     kpis=[("Total Sales", "PKR 1,251")],
                     sections=[("Orders", df)],
                     subtitle="Period: 2026-01-01 to 2026-01-31",
                     demo_notice=True)
    assert blob[:5] == b"%PDF-"
    assert len(blob) > 2000
    # brand + title embedded as text
    assert b"ExportSight" in blob
    assert BRAND_LINE.split(" — ")[0].encode() in blob


def test_pdf_handles_empty_sections():
    blob = build_pdf("Empty Report",
                     sections=[("Nothing here", pd.DataFrame())])
    assert blob[:5] == b"%PDF-"


def test_pdf_kpis_only():
    blob = build_pdf("KPI Report", kpis=[("Orders", "4")])
    assert blob[:5] == b"%PDF-"
