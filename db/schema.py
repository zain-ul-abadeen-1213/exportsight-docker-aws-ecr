"""ExportSight — SQLite schema (normalized, with PKs, FKs, and indexes)."""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS buyers (
    buyer_id   TEXT PRIMARY KEY,
    name       TEXT NOT NULL,
    country    TEXT NOT NULL,
    email      TEXT,
    phone      TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id               TEXT PRIMARY KEY,
    order_date             TEXT NOT NULL,   -- ISO YYYY-MM-DD
    buyer_id               TEXT NOT NULL REFERENCES buyers(buyer_id) ON DELETE RESTRICT,
    destination_country    TEXT NOT NULL,
    product                TEXT NOT NULL,
    quantity               REAL NOT NULL CHECK (quantity > 0),
    unit_price             REAL NOT NULL CHECK (unit_price >= 0),
    currency               TEXT NOT NULL,   -- ISO 4217 code, e.g. USD, PKR, EUR
    order_value            REAL NOT NULL,   -- quantity * unit_price, in order currency
    production_status      TEXT NOT NULL,   -- Pending | In Production | Completed
    shipment_status        TEXT NOT NULL,   -- Pending | Shipped | Delivered | Cancelled
    expected_delivery_date TEXT,            -- ISO YYYY-MM-DD, nullable
    actual_delivery_date   TEXT,            -- ISO YYYY-MM-DD, nullable
    notes                  TEXT,
    created_at             TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invoices (
    invoice_id   TEXT PRIMARY KEY,
    order_id     TEXT NOT NULL REFERENCES orders(order_id) ON DELETE RESTRICT,
    buyer_id     TEXT NOT NULL REFERENCES buyers(buyer_id) ON DELETE RESTRICT,
    invoice_date TEXT NOT NULL,   -- ISO YYYY-MM-DD
    due_date     TEXT NOT NULL,   -- ISO YYYY-MM-DD
    amount       REAL NOT NULL CHECK (amount >= 0),
    currency     TEXT NOT NULL,
    notes        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS payments (
    payment_id   TEXT PRIMARY KEY,
    invoice_id   TEXT NOT NULL REFERENCES invoices(invoice_id) ON DELETE RESTRICT,
    payment_date TEXT NOT NULL,   -- ISO YYYY-MM-DD
    amount       REAL NOT NULL CHECK (amount > 0),
    currency     TEXT NOT NULL,
    reference    TEXT UNIQUE,     -- bank / transfer reference; duplicates rejected
    notes        TEXT,
    created_at   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS order_costs (
    cost_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    order_id      TEXT NOT NULL REFERENCES orders(order_id) ON DELETE CASCADE,
    cost_category TEXT NOT NULL,  -- Raw Materials | Labour/Manufacturing | Packaging
                                  -- Inland Transportation | Freight | Insurance | Other Direct Costs
    amount        REAL NOT NULL CHECK (amount >= 0),
    currency      TEXT NOT NULL,
    notes         TEXT,
    created_at    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS settings (
    key        TEXT PRIMARY KEY,
    value      TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

-- Indexes for join / filter performance
CREATE INDEX IF NOT EXISTS idx_orders_buyer      ON orders(buyer_id);
CREATE INDEX IF NOT EXISTS idx_orders_date       ON orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_shipstatus ON orders(shipment_status);
CREATE INDEX IF NOT EXISTS idx_invoices_order    ON invoices(order_id);
CREATE INDEX IF NOT EXISTS idx_invoices_buyer    ON invoices(buyer_id);
CREATE INDEX IF NOT EXISTS idx_invoices_duedate  ON invoices(due_date);
CREATE INDEX IF NOT EXISTS idx_payments_invoice  ON payments(invoice_id);
CREATE INDEX IF NOT EXISTS idx_costs_order       ON order_costs(order_id);
"""
