# ExportSight — Business Intelligence & MIS Dashboard

**Product:** ExportSight · **by Zain Tech Automation Solutions**

A complete, working Business Intelligence and MIS dashboard for small
Pakistani export businesses that currently run on Excel and CSV files.
Upload your orders, track invoices and payments, analyse profitability,
and generate board-ready reports — all from one premium dashboard.

## Features (5 modules + Settings)

1. **Executive Overview** — KPI cards (sales, orders, receivables, overdue,
   gross profit, collection rate), date/buyer/country/status filters,
   monthly sales trend, order-status distribution, top-5 buyers,
   country-wise performance (Plotly).
2. **Export Orders** — full CRUD, search/filter, delivery-deadline alerts,
   CSV/Excel import with row-level validation reports, CSV/Excel export.
3. **Payments & Receivables** — invoice lifecycle (Unpaid → Partially Paid →
   Paid / Overdue), partial & multi-payments, overpayment & duplicate-
   reference guards, aging buckets (0–30 / 31–60 / 61–90 / 90+),
   buyer-wise outstanding.
4. **Profitability Analysis** — direct costs per order, gross profit and
   gross-margin % (never called net profit), buyer/product/country/monthly
   breakdowns, missing-cost and negative-margin flags.
5. **Management Reports** — weekly, monthly, sales, outstanding payments,
   delayed orders, profitability, buyer performance reports with
   CSV / Excel / PDF downloads, plus rule-based business insights.
6. **Settings** — base currency, documented exchange rates, revenue-
   recognition rule, buyer management, demo-data reload / wipe.

All figures are calculated from live application data; multi-currency
amounts convert via the documented rates in Settings.

## Installation

Requires Python 3.10+.

```bash
pip install -r requirements.txt
```

## Initialise the database

```bash
# schema only
python -m db.init_db

# schema + fictional textile-exporter demo data (clearly labeled in-app)
python -m db.init_db --seed
```

## Run the app

```bash
streamlit run app.py
```

Then open the URL shown (usually http://localhost:8501).
On first launch with a fresh database, the fictional demo dataset is
loaded automatically so you can explore every module immediately.

## Run the tests

```bash
python -m pytest tests/ -q
```

37 automated tests cover KPI math, order values, duplicate IDs, partial/full
payments, balances, overdue classification, margins, missing costs, currency
conversion/mismatches, CSV/Excel validation and PDF/Excel generation.

## Sample files

`data/samples/` contains fictional `sample_orders.csv`,
`sample_orders.xlsx`, `sample_invoices.csv` and `sample_payments.csv`
you can import via **Export Orders → Import / Export**.

## Project structure

```
exportsight/
├── app.py                 # Streamlit entry point + sidebar navigation
├── requirements.txt
├── README.md  DEPLOYMENT.md  FEATURES.md
├── .streamlit/config.toml # navy / white / teal theme
├── db/                    # schema.py, database.py, seed.py, init_db.py
├── modules/               # overview, orders, payments, profitability, reports, settings
├── utils/                 # finance.py (calc core), validators.py, io_helpers.py, pdf_reports.py
├── data/samples/          # fictional sample CSV/Excel files
└── tests/                 # pytest suite (37 tests)
```

## Data & honesty notes

- The bundled dataset is **fictional demo data** for a textile exporter
  and is labeled as such everywhere in the app. Never use real customer
  information without authorization.
- There is **no login screen**: authentication is not implemented, so none
  is claimed (per the security spec).
- Exchange rates are fictional demo values — update them in Settings to
  your bank's rates before relying on converted totals.
