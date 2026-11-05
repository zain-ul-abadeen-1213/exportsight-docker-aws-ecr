"""ExportSight tests — validators & import validation (spec section 10)."""

import io

import pandas as pd

from utils.finance import get_rates
from utils.io_helpers import import_orders, read_upload, to_csv_bytes, to_excel_bytes
from utils.validators import (validate_buyer, validate_invoice, validate_order,
                              validate_payment)


def _order(**kw):
    base = {"order_id": "OX", "order_date": "2026-01-01", "buyer_id": "B1",
            "destination_country": "Testland", "product": "Fabric",
            "quantity": 10, "unit_price": 5, "currency": "USD",
            "production_status": "Pending", "shipment_status": "Pending",
            "expected_delivery_date": "", "actual_delivery_date": ""}
    base.update(kw)
    return base


def test_duplicate_order_id_rejected():
    errs = validate_order(_order(order_id="O1"), {"O1", "O2"})
    assert any("already exists" in e for e in errs)


def test_order_field_validation():
    errs = validate_order(_order(quantity=-5, unit_price="abc", currency="XYZ",
                                 order_date="01-01-2026"), set())
    assert any("Quantity" in e for e in errs)
    assert any("Unit price" in e for e in errs)
    assert any("Currency" in e for e in errs)
    assert any("Order date" in e for e in errs)


def test_order_date_logic():
    errs = validate_order(_order(expected_delivery_date="2025-12-01",
                                 actual_delivery_date="2025-11-01"), set())
    assert any("Actual delivery date cannot be earlier" in e for e in errs)


def test_invoice_rejects_unknown_order():
    errs = validate_invoice(
        {"invoice_id": "IX", "order_id": "NOPE", "buyer_id": "B1",
         "invoice_date": "2026-01-01", "due_date": "2026-02-01",
         "amount": 100, "currency": "USD"},
        set(), {"O1"}, {"O1": "B1"})
    assert any("does not exist" in e for e in errs)


def test_invoice_due_before_invoice_date_rejected():
    errs = validate_invoice(
        {"invoice_id": "IX", "order_id": "O1", "buyer_id": "B1",
         "invoice_date": "2026-02-01", "due_date": "2026-01-01",
         "amount": 100, "currency": "USD"},
        set(), {"O1"}, {"O1": "B1"})
    assert any("Due date cannot be earlier" in e for e in errs)


def test_payment_rejects_duplicate_reference(conn):
    errs = validate_payment(
        {"payment_id": "PX", "invoice_id": "I1", "payment_date": "2026-10-01",
         "amount": 10, "currency": "USD", "reference": "REF-001"},
        set(), {"REF-001", "REF-002"}, {"I1"})
    assert any("already used" in e for e in errs)


def test_payment_rejects_unknown_invoice(conn):
    errs = validate_payment(
        {"payment_id": "PX", "invoice_id": "NOPE", "payment_date": "2026-10-01",
         "amount": 10, "currency": "USD", "reference": ""},
        set(), set(), {"I1"})
    assert any("does not exist" in e for e in errs)


def test_overpayment_blocked(conn):
    from utils.finance import invoice_summary
    _, rates = get_rates(conn)
    inv = invoice_summary(conn, "2026-10-13").set_index("invoice_id")
    balances = {"I1": float(inv.loc["I1", "balance_PKR"])}  # 700 USD -> 194600 PKR
    errs = validate_payment(
        {"payment_id": "PX", "invoice_id": "I1", "payment_date": "2026-10-01",
         "amount": 1000, "currency": "USD", "reference": ""},
        set(), set(), {"I1"}, balances, rates)
    assert any("exceeds the invoice's outstanding balance" in e for e in errs)


def test_buyer_duplicate_id():
    errs = validate_buyer({"buyer_id": "B1", "name": "X", "country": "Y"}, {"B1"})
    assert any("already exists" in e for e in errs)


# --- CSV/Excel import validation ------------------------------------------------
def _upload_df(df: pd.DataFrame, name: str) -> io.BytesIO:
    """Build a real seekable upload stream (pandas/openpyxl compatible)."""
    buf = io.BytesIO()
    if name.endswith(".csv"):
        buf.write(df.to_csv(index=False).encode("utf-8"))
    else:
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, index=False)
    buf.seek(0)
    buf.name = name
    return buf


def test_import_mixed_rows_reports_errors(conn):
    df = pd.DataFrame([
        {"order_id": "O9", "order_date": "2026-06-01", "buyer_id": "B1",
         "destination_country": "Testland", "product": "Fabric", "quantity": 5,
         "unit_price": 10, "currency": "USD", "production_status": "Pending",
         "shipment_status": "Pending", "expected_delivery_date": "",
         "actual_delivery_date": "", "notes": ""},
        {"order_id": "O1", "order_date": "2026-06-01", "buyer_id": "B1",  # duplicate
         "destination_country": "Testland", "product": "Fabric", "quantity": 5,
         "unit_price": 10, "currency": "USD", "production_status": "Pending",
         "shipment_status": "Pending", "expected_delivery_date": "",
         "actual_delivery_date": "", "notes": ""},
        {"order_id": "O10", "order_date": "bad-date", "buyer_id": "GHOST",  # bad buyer+date
         "destination_country": "Testland", "product": "Fabric", "quantity": -2,
         "unit_price": 10, "currency": "USD", "production_status": "Pending",
         "shipment_status": "Pending", "expected_delivery_date": "",
         "actual_delivery_date": "", "notes": ""},
    ])
    report = import_orders(conn, df)
    assert report["inserted"] == 1
    assert report["skipped"] == 2
    assert len(report["errors"]) == 2
    # the valid row really landed
    from db.database import fetch_one
    assert fetch_one(conn, "SELECT order_id FROM orders WHERE order_id='O9'")


def test_read_upload_rejects_bad_type():
    df, err = read_upload(_upload_df(pd.DataFrame([{"a": 1}]), "data.txt"))
    assert df is None and "Unsupported file type" in err


def test_excel_bytes_roundtrip():
    df = pd.DataFrame([{"a": 1, "b": "x"}])
    blob = to_excel_bytes(df, "Sheet1")
    back = pd.read_excel(io.BytesIO(blob), engine="openpyxl")
    assert list(back.columns) == ["a", "b"]
    assert back.iloc[0]["a"] == 1


def test_csv_bytes_roundtrip():
    df = pd.DataFrame([{"a": 1}])
    text = to_csv_bytes(df).decode()
    assert text.splitlines() == ["a", "1"]
