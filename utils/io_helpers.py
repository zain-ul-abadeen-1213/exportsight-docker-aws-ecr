"""ExportSight — CSV/Excel import & export helpers.

Imports validate every row and return a validation report:
  {"inserted": n, "skipped": m, "errors": [(row_no, [messages]), ...]}
so users always see what was accepted and what was rejected, and why.
"""

from __future__ import annotations

import io
import sqlite3

import pandas as pd

# Expected columns per importable entity (case-insensitive mapping).
ORDER_COLUMNS = ["order_id", "order_date", "buyer_id", "destination_country",
                 "product", "quantity", "unit_price", "currency",
                 "production_status", "shipment_status", "expected_delivery_date",
                 "actual_delivery_date", "notes"]
INVOICE_COLUMNS = ["invoice_id", "order_id", "buyer_id", "invoice_date",
                   "due_date", "amount", "currency", "notes"]
PAYMENT_COLUMNS = ["payment_id", "invoice_id", "payment_date", "amount",
                   "currency", "reference", "notes"]


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
    return df


def read_upload(uploaded_file) -> tuple[pd.DataFrame | None, str | None]:
    """Read an uploaded CSV or Excel file into a normalized DataFrame."""
    try:
        name = (uploaded_file.name or "").lower()
        if name.endswith(".csv"):
            df = pd.read_csv(uploaded_file)
        elif name.endswith((".xlsx", ".xls")):
            df = pd.read_excel(uploaded_file, engine="openpyxl")
        else:
            return None, "Unsupported file type. Please upload .csv or .xlsx."
        return _normalize_columns(df), None
    except Exception as exc:  # malformed uploads handled gracefully
        return None, f"Could not read file: {exc}"


def to_csv_bytes(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def to_excel_bytes(df: pd.DataFrame, sheet_name: str = "ExportSight") -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name[:31])
    buf.seek(0)
    return buf.read()


def import_orders(conn: sqlite3.Connection, df: pd.DataFrame) -> dict:
    """Validate + insert order rows. Returns a validation report dict."""
    from .validators import validate_order
    from db.database import execute, fetch_df

    df = _normalize_columns(df)
    existing = set(fetch_df(conn, "SELECT order_id FROM orders")["order_id"])
    buyer_ids = set(fetch_df(conn, "SELECT buyer_id FROM buyers")["buyer_id"])

    report = {"inserted": 0, "skipped": 0, "errors": []}
    seen_in_file: set[str] = set()
    for idx, row in df.iterrows():
        row_no = idx + 2  # +1 header, +1 for 1-based
        data = {c: ("" if pd.isna(row.get(c)) else str(row.get(c)).strip())
                for c in ORDER_COLUMNS if c in df.columns}
        # Buyer must exist; surface as a clear row error otherwise.
        if data.get("buyer_id") and data["buyer_id"] not in buyer_ids:
            report["skipped"] += 1
            report["errors"].append((row_no, [f"Buyer '{data['buyer_id']}' does not exist."]))
            continue
        errors = validate_order(data, existing | seen_in_file)
        if errors:
            report["skipped"] += 1
            report["errors"].append((row_no, errors))
            continue
        try:
            qty, price = float(data["quantity"]), float(data["unit_price"])
            execute(conn, """
                INSERT INTO orders (order_id, order_date, buyer_id, destination_country,
                    product, quantity, unit_price, currency, order_value,
                    production_status, shipment_status, expected_delivery_date,
                    actual_delivery_date, notes, created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,date('now'))""",
                (data["order_id"], data["order_date"], data["buyer_id"],
                 data["destination_country"], data["product"], qty, price,
                 data["currency"].upper(), round(qty * price, 2),
                 data["production_status"], data["shipment_status"],
                 data.get("expected_delivery_date") or None,
                 data.get("actual_delivery_date") or None,
                 data.get("notes", "")))
            seen_in_file.add(data["order_id"])
            report["inserted"] += 1
        except Exception as exc:
            report["skipped"] += 1
            report["errors"].append((row_no, [f"Database error: {exc}"]))
    return report


def sample_order_csv() -> bytes:
    sample = pd.DataFrame([{
        "order_id": "ORD-9001", "order_date": "2026-09-01", "buyer_id": "BYR-001",
        "destination_country": "Germany", "product": "Cotton Bed Sheet Set",
        "quantity": 1000, "unit_price": 12.5, "currency": "USD",
        "production_status": "Pending", "shipment_status": "Pending",
        "expected_delivery_date": "2026-11-15", "actual_delivery_date": "",
        "notes": "Sample row — replace with your data",
    }])
    return to_csv_bytes(sample)
