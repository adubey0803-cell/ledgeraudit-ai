# Product Requirements Document
## LedgerAudit AI — Automated Financial Reconciliation

**Author:** Ashutosh Dubey  
**Date:** June 2026  
**Version:** 1.0

---

## Problem

Small and mid-sized e-commerce businesses using Shopify + Stripe spend 4–8 hours per
month manually reconciling three separate systems: their Shopify order records, Stripe
payout reports, and bank statements. Errors — missing deposits, duplicate charges,
split payouts, chargebacks — are caught late or not at all, leading to cash flow
surprises, incorrect tax filings, and unresolved disputes.

No affordable tool connects all three systems automatically and explains discrepancies
in plain English without requiring accounting knowledge.

---

## Target Users

| User | Pain Point |
|------|-----------|
| **Shopify store owner** (SMB) | Spends hours cross-checking CSV exports every month-end |
| **Freelance bookkeeper** | Manages 10+ clients, each with slightly different Stripe setups |
| **Finance manager at a DTC brand** | Needs audit trail for investors/auditors without hiring a full-time accountant |

---

## Key Features

### 1. Three-way Reconciliation Engine
Matches Shopify orders ↔ Stripe charges ↔ bank deposits automatically.
Handles exact batches, split payouts (one order split across two deposits),
partial refunds, and chargebacks. Uses integer-cent arithmetic to eliminate
all floating-point errors.

### 2. Live Stripe API Integration
Fetches real charge and refund data directly from Stripe — no CSV export needed.
Configurable date range (1–90 days). Deduplication logic handles merchants who
re-run imports.

### 3. AI-Powered Audit Findings
7 automated checks (sum mismatch, orphan payouts, fee anomalies, duplicate charges,
high refund ratios, chargebacks, deposit remainders). Each finding is explained in
one plain-English sentence via Claude AI — no accounting jargon.

### 4. Health Score (0–100)
A single number summarising reconciliation quality. Deductions applied per issue
type and severity. Colour-coded (green / amber / orange / red) for instant status
at a glance.

### 5. Run History & Snapshots
Each reconciliation run can be saved as a JSON snapshot. A trend table shows health
score, gross sales, and flagged orders across previous runs — enabling month-over-month
tracking.

### 6. Export
One-click export to Excel (4 sheets: Orders, QA Audit, Duplicates, Summary) or
Markdown for inclusion in reports or handoff to accountants.

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Time to reconcile 100 orders | < 30 seconds (vs. 4–8 hrs manual) |
| Reconciliation accuracy | 100% match to the cent |
| User setup time | < 5 minutes (no install, browser-based) |
| Audit finding false-positive rate | < 5% |

---

## Current Limitations (v1)

- **Shopify data** is uploaded as a CSV export — Shopify OAuth API integration is not yet
  implemented. In a production build this would connect directly via the Shopify Admin API.
- **Bank statement** is uploaded as a CSV export — Plaid or Open Banking integration is
  not yet implemented. In a production build this would pull transactions automatically.
- **Stripe** is connected live via API (real test-mode charges). Shopify and bank remain
  manual CSV uploads due to API access constraints during development.

---

## Out of Scope (v1)

- Multi-currency support
- QuickBooks / Xero direct sync
- Plaid bank integration (bank CSV upload used instead)
- Multi-tenant / team login
- Mobile app

---

## Tech Stack

Python · Streamlit · Pandas · Stripe API · Anthropic Claude Haiku · Streamlit Cloud

---

## Deployment

Live at: **https://ledgeraudit-ai-gvqra3grdsbeep5wy9a8sp.streamlit.app/**  
Source: **https://github.com/adubey0803-cell/ledgeraudit-ai**
