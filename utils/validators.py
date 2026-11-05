"""ExportSight — input validation. Returns a list of error strings (empty = valid)."""

from __future__ import annotations

import re
from datetime import date

ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
CURRENCIES = {"USD", "EUR", "GBP", "PKR", "AED", "SAR", "CAD", "AUD"}
PROD_STATUSES = {"Pending", "In Production", "Completed"}
SHIP_STATUSES = {"Pending", "Shipped", "Delivered", "Cancelled"}
COST_CATEGORIES = {
    "Raw Materials", "Labour/Manufacturing", "Packaging",
    "Inland Transportation", "Freight", "Insurance", "Other Direct Costs",
}


def _valid_date(value: str | None, field: str, errors: list, required: bool = True) -> None:
    if not value:
        if required:
            errors.append(f"{field} is required.")
        return
    if not ISO_DATE.match(str(value)):
        errors.append(f"{field} must be a valid date (YYYY-MM-DD).")
        return
    try:
        date.fromisoformat(str(value))
    except ValueError:
        errors.append(f"{field} is not a real calendar date.")


def _positive_number(value, field: str, errors: list, allow_zero: bool = False) -> None:
    try:
        num = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field} must be a number.")
        return
    if allow_zero:
        if num < 0:
            errors.append(f"{field} cannot be negative.")
    elif num <= 0:
        errors.append(f"{field} must be greater than zero.")


def validate_order(data: dict, existing_ids: set) -> list[str]:
    e: list[str] = []
    oid = (data.get("order_id") or "").strip()
    if not oid:
        e.append("Order ID is required.")
    elif oid in existing_ids:
        e.append(f"Order ID '{oid}' already exists (duplicate IDs are not allowed).")
    _valid_date(data.get("order_date"), "Order date", e)
    if not (data.get("buyer_id") or "").strip():
        e.append("Buyer is required.")
    if not (data.get("destination_country") or "").strip():
        e.append("Destination country is required.")
    if not (data.get("product") or "").strip():
        e.append("Product is required.")
    _positive_number(data.get("quantity"), "Quantity", e)
    _positive_number(data.get("unit_price"), "Unit price", e, allow_zero=True)
    if (data.get("currency") or "").upper() not in CURRENCIES:
        e.append(f"Currency must be one of: {', '.join(sorted(CURRENCIES))}.")
    if (data.get("production_status") or "") not in PROD_STATUSES:
        e.append(f"Production status must be one of: {', '.join(sorted(PROD_STATUSES))}.")
    if (data.get("shipment_status") or "") not in SHIP_STATUSES:
        e.append(f"Shipment status must be one of: {', '.join(sorted(SHIP_STATUSES))}.")
    _valid_date(data.get("expected_delivery_date"), "Expected delivery date", e, required=False)
    _valid_date(data.get("actual_delivery_date"), "Actual delivery date", e, required=False)
    exp, act, od = (data.get("expected_delivery_date"), data.get("actual_delivery_date"),
                    data.get("order_date"))
    if exp and act and ISO_DATE.match(exp) and ISO_DATE.match(act) and act < exp:
        e.append("Actual delivery date cannot be earlier than expected delivery date.")
    if od and exp and ISO_DATE.match(od) and ISO_DATE.match(exp) and exp < od:
        e.append("Expected delivery date cannot be earlier than order date.")
    return e


def validate_invoice(data: dict, existing_ids: set, order_ids: set,
                     order_buyer: dict) -> list[str]:
    e: list[str] = []
    iid = (data.get("invoice_id") or "").strip()
    if not iid:
        e.append("Invoice ID is required.")
    elif iid in existing_ids:
        e.append(f"Invoice ID '{iid}' already exists.")
    oid = (data.get("order_id") or "").strip()
    if not oid:
        e.append("Related order is required.")
    elif oid not in order_ids:
        e.append(f"Order '{oid}' does not exist (invalid invoice reference).")
    elif data.get("buyer_id") and order_buyer.get(oid) != data["buyer_id"]:
        e.append("Invoice buyer does not match the order's buyer.")
    _valid_date(data.get("invoice_date"), "Invoice date", e)
    _valid_date(data.get("due_date"), "Due date", e)
    inv_d, due_d = data.get("invoice_date"), data.get("due_date")
    if inv_d and due_d and ISO_DATE.match(inv_d) and ISO_DATE.match(due_d) and due_d < inv_d:
        e.append("Due date cannot be earlier than invoice date.")
    _positive_number(data.get("amount"), "Invoice amount", e, allow_zero=True)
    if (data.get("currency") or "").upper() not in CURRENCIES:
        e.append(f"Currency must be one of: {', '.join(sorted(CURRENCIES))}.")
    return e


def validate_payment(data: dict, existing_ids: set, existing_refs: set,
                     invoice_ids: set, invoice_balance_base: dict | None = None,
                     rates: dict | None = None) -> list[str]:
    e: list[str] = []
    pid = (data.get("payment_id") or "").strip()
    if not pid:
        e.append("Payment ID is required.")
    elif pid in existing_ids:
        e.append(f"Payment ID '{pid}' already exists.")
    iid = (data.get("invoice_id") or "").strip()
    if not iid:
        e.append("Invoice is required.")
    elif iid not in invoice_ids:
        e.append(f"Invoice '{iid}' does not exist (invalid payment reference).")
    _valid_date(data.get("payment_date"), "Payment date", e)
    _positive_number(data.get("amount"), "Payment amount", e)
    if (data.get("currency") or "").upper() not in CURRENCIES:
        e.append(f"Currency must be one of: {', '.join(sorted(CURRENCIES))}.")
    ref = (data.get("reference") or "").strip()
    if ref and ref in existing_refs:
        e.append(f"Payment reference '{ref}' is already used (duplicate payment blocked).")
    if (invoice_balance_base and rates and iid in invoice_balance_base
            and not e):
        try:
            from .finance import to_base
            amt_base = to_base(float(data["amount"]), data["currency"].upper(), rates)
            if amt_base - invoice_balance_base[iid] > 0.01:
                e.append("Payment exceeds the invoice's outstanding balance "
                         "(overpayment is blocked unless explicitly configured).")
        except (ValueError, KeyError):
            pass
    return e


def validate_cost(data: dict, order_ids: set) -> list[str]:
    e: list[str] = []
    if (data.get("order_id") or "").strip() not in order_ids:
        e.append("Order does not exist.")
    if (data.get("cost_category") or "") not in COST_CATEGORIES:
        e.append(f"Cost category must be one of: {', '.join(sorted(COST_CATEGORIES))}.")
    _positive_number(data.get("amount"), "Cost amount", e, allow_zero=True)
    if (data.get("currency") or "").upper() not in CURRENCIES:
        e.append(f"Currency must be one of: {', '.join(sorted(CURRENCIES))}.")
    return e


def validate_buyer(data: dict, existing_ids: set) -> list[str]:
    e: list[str] = []
    bid = (data.get("buyer_id") or "").strip()
    if not bid:
        e.append("Buyer ID is required.")
    elif bid in existing_ids:
        e.append(f"Buyer ID '{bid}' already exists.")
    if not (data.get("name") or "").strip():
        e.append("Buyer name is required.")
    if not (data.get("country") or "").strip():
        e.append("Country is required.")
    return e
