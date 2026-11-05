"""ExportSight — professional PDF report generation (ReportLab).

Every report carries the ExportSight brand header, generation timestamp,
and a demo-data notice when the database holds seeded demo data.
"""

from __future__ import annotations

import io
from datetime import date

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (Paragraph, SimpleDocTemplate, Spacer, Table,
                                TableStyle)

NAVY = colors.HexColor("#0F2A44")
TEAL = colors.HexColor("#0E7C7B")
LIGHT = colors.HexColor("#F1F5F9")
GREY = colors.HexColor("#64748B")

BRAND_LINE = "ExportSight — by Zain Tech Automation Solutions"


def _footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(GREY)
    canvas.drawString(15 * mm, 12 * mm, BRAND_LINE)
    canvas.drawRightString(A4[0] - 15 * mm, 12 * mm, f"Page {doc.page}")
    canvas.restoreState()


def _styled_table(df: pd.DataFrame, col_widths=None) -> Table:
    """DataFrame -> ReportLab table with branded header row."""
    if df.empty:
        return Paragraph("<i>No data available for this section.</i>",
                         getSampleStyleSheet()["Normal"])
    headers = [str(c).replace("_", " ").title() for c in df.columns]
    data = [headers]
    for _, row in df.iterrows():
        data.append([_fmt(v) for v in row.tolist()])
    tbl = Table(data, repeatRows=1, colWidths=col_widths)
    style = [
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 6),
    ]
    tbl.setStyle(TableStyle(style))
    return tbl


def _fmt(value) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "—"
    if isinstance(value, float):
        return f"{value:,.2f}"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    text = str(value)
    return text[:60]


def build_pdf(title: str,
              kpis: list[tuple[str, str]] | None = None,
              sections: list[tuple[str, pd.DataFrame]] | None = None,
              subtitle: str = "",
              demo_notice: bool = False) -> bytes:
    """Build a complete PDF report and return it as bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            leftMargin=15 * mm, rightMargin=15 * mm,
                            topMargin=18 * mm, bottomMargin=16 * mm,
                            title=f"ExportSight — {title}")
    styles = getSampleStyleSheet()
    h1 = ParagraphStyle("H1", parent=styles["Heading1"], textColor=NAVY, fontSize=20,
                        spaceAfter=2 * mm)
    h2 = ParagraphStyle("H2", parent=styles["Heading2"], textColor=TEAL, fontSize=13,
                        spaceBefore=6 * mm, spaceAfter=3 * mm)
    brand = ParagraphStyle("Brand", parent=styles["Normal"], textColor=TEAL,
                           fontSize=10, spaceAfter=1 * mm)
    meta = ParagraphStyle("Meta", parent=styles["Normal"], textColor=GREY, fontSize=9,
                          spaceAfter=4 * mm)

    story = [
        Paragraph(BRAND_LINE, brand),
        Paragraph(title, h1),
    ]
    if subtitle:
        story.append(Paragraph(subtitle, meta))
    story.append(Paragraph(f"Generated on {date.today().isoformat()}", meta))
    if demo_notice:
        story.append(Paragraph(
            "<i>Note: figures below are calculated from fictional demo data "
            "(textile exporter sample dataset).</i>", meta))

    if kpis:
        kpi_data = [[Paragraph(f"<b>{label}</b>", styles["Normal"]),
                     Paragraph(f"<b>{value}</b>", styles["Normal"])]
                    for label, value in kpis]
        kpi_tbl = Table(kpi_data, colWidths=[85 * mm, 85 * mm])
        kpi_tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), LIGHT),
            ("BOX", (0, 0), (-1, -1), 0.6, NAVY),
            ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#CBD5E1")),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ]))
        story += [kpi_tbl, Spacer(1, 4 * mm)]

    for heading, df in (sections or []):
        story.append(Paragraph(heading, h2))
        story.append(_styled_table(df))

    doc.build(story, onFirstPage=_footer, onLaterPages=_footer)
    buf.seek(0)
    return buf.read()
