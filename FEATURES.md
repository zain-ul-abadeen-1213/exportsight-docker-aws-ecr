# ExportSight — Implemented Features & Known Limitations

**Product:** ExportSight · **by Zain Tech Automation Solutions**

## Implemented ✅

**Module 1 — Executive Overview**
- 8 KPI cards: total export sales, total orders, active orders, payments
  received, outstanding receivables, overdue invoices (+count), estimated
  gross profit, collection rate — all respond to filters.
- Filters: date range, buyer, destination country, order (shipment) status.
- Plotly charts: monthly sales trend, order-status distribution, top-5
  buyers, country-wise export performance.

**Module 2 — Export Order Management**
- Create / view / edit / search / filter / delete orders with full
  validation (duplicate IDs, dates, quantities, prices, currency codes,
  date logic).
- Delivery alerts: delayed shipments and deadlines approaching within 7 days.
- CSV/Excel import with per-row validation report (inserted / skipped /
  reasons); CSV/Excel export; downloadable sample template.

**Module 3 — Payments & Receivables**
- Invoice lifecycle computed from real payments: Unpaid → Partially Paid →
  Paid, plus Overdue when past due with a balance. An invoice is never
  marked Paid without full payment records.
- Partial and multiple payments per invoice; cross-currency payments are
  converted with documented rates before balance comparison.
- Guards: duplicate payment references, unknown invoice references,
  overpayments (blocked unless the balance allows).
- KPIs: total receivables, overdue amount, collection rate; aging buckets
  0–30 / 31–60 / 61–90 / 90+ days; buyer-wise outstanding chart.

**Module 4 — Profitability Analysis**
- 7 direct-cost categories per order; per-order revenue, costs, **gross**
  profit and gross-margin % (strictly never called net profit).
- Missing-cost and negative-margin flags; buyer / product / country /
  monthly breakdowns; configurable revenue-recognition rule
  (order date vs shipment date).

**Module 5 — Management Reports**
- 7 reports: weekly, monthly, sales performance, outstanding payments,
  delayed orders, order profitability, buyer performance.
- Downloads in CSV, Excel and professionally formatted PDF (ReportLab).
- Rule-based insights: overdue invoices, at-risk shipments, top buyer,
  negative/incomplete margins, sales vs previous 30 days — every insight
  computed from live data; estimates clearly labeled.

**Settings** — base currency, editable FX rates, revenue rule, buyer
management, demo-data reload / full wipe (both with confirmation).

**Cross-cutting** — normalized SQLite schema (PKs, FKs, indexes),
parameterized queries everywhere, transactional writes, input validation,
delete confirmations, graceful empty states, demo-data labeling,
37 passing automated tests.

## Known limitations ⚠️

1. **No authentication.** There is deliberately no login screen; do not
   expose the app publicly with sensitive data unless you add auth.
2. **Single-user SQLite.** Fine for one business on one server; not built
   for concurrent multi-user writes.
3. **Fictional exchange rates.** Demo FX values are placeholders — set
   real rates in Settings before trusting converted totals.
4. **Demo data by default.** First launch loads the fictional textile-
   exporter dataset; replace it via Import or wipe it in Settings.
5. **PDF tables are static snapshots** (no interactive charts inside PDFs).
6. **Revenue recognition** supports order-date and shipment-date rules
   only (no percentage-of-completion).
7. Streamlit Community Cloud's ephemeral filesystem resets the SQLite
   file on redeploy — use the Docker volume setup for persistence.
