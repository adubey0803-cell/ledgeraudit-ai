# LedgerAudit AI — CLAUDE.md

## Project Overview

LedgerAudit AI is a financial reconciliation SaaS tool built with Python and Streamlit.
It automatically matches Shopify orders, Stripe charges, and bank deposits — detecting
mismatches, duplicate charges, split payouts, missing deposits, chargebacks, and partial
refunds. An AI-powered audit layer explains each finding in plain English.

## How to Run Locally

```bash
pip install -r requirements.txt
streamlit run reconcile_app.py
```

## How to Run on the Web

Live app: https://ledgeraudit-ai-gvqra3grdsbeep5wy9a8sp.streamlit.app/

## Key Commands

```bash
# Install dependencies
pip install streamlit pandas requests openpyxl

# Run the app
streamlit run reconcile_app.py

# Syntax check
python -c "import ast; ast.parse(open('reconcile_app.py', encoding='utf-8').read()); print('OK')"
```

## Architecture

```
reconcile_app.py        # Single-file Streamlit app (all logic self-contained)
requirements.txt        # Python dependencies
shopify_orders_test.csv # 6 test Shopify orders (#3001-#3006)
bank_statement_test.csv # 2 bank deposits (BATCH1 + BATCH2)
snapshots/              # Auto-created at runtime — stores JSON run history
```

## Reconciliation Engine

Two-phase algorithm:

1. **Phase 1 — Exact batch matching (Dynamic Programming subset-sum)**
   - Converts all amounts to integer cents to avoid float precision errors
   - O(n × target) DP finds which Stripe payouts sum exactly to each bank deposit

2. **Phase 2 — Split payout detection**
   - Runs in a while-loop until no more splits found
   - Handles cases where one payout is split across two bank deposits
   - Uses deposit-remainder algorithm: `R1 + R2 = split_net`

## QA Auditor (7 checks)

| Check | Severity | Description |
|-------|----------|-------------|
| SUM MISMATCH | ERROR | Allocated payouts don't add up to bank deposit |
| DEPOSIT REMAINDER | WARNING | Unaccounted funds in a deposit after matching |
| ORPHAN PAYOUT | ERROR | Stripe payout not matched to any deposit |
| FEE ANOMALY | WARNING | Fee deviates >50% from expected 2.9% + $0.30 |
| HIGH REFUND RATIO | WARNING | Refunds exceed 15% of gross |
| ORPHAN CHARGE | WARNING | Stripe charge with no Shopify order |
| CHARGEBACK | WARNING | Chargeback detected — always flagged |

ERROR findings override order status to NEEDS REVIEW.

## Health Score (0–100)

Starts at 100 and deducts per issue:
- -15 per MISSING IN STRIPE (capped at 30)
- -10 per MISSING BANK DEPOSIT (capped at 25)
- -8 per DUPLICATE CHARGE (capped at 20)
- -5 per NEEDS REVIEW order (capped at 15)
- -5 per audit ERROR (capped at 15)
- -2 per audit WARNING (capped at 10)

## Stripe API Integration

- Endpoint: `GET /v1/charges?expand[]=data.balance_transaction`
- Refunds fetched separately: `GET /v1/refunds?created[gte]=since`
- Pagination: cursor-based via `starting_after`
- All amounts converted: `round(float(x) * 100)` → integer cents

## AI Explanations

- Model: `claude-haiku-4-5-20251001` (Anthropic)
- One plain-English sentence per audit finding
- Cached in `st.session_state["ai_cache"]` — API called once per unique finding
- API key loaded from Streamlit Secrets (`st.secrets["anthropic_key"]`)

## Environment / Secrets

Keys are stored in Streamlit Cloud Secrets (never in source code):

```toml
# .streamlit/secrets.toml (local only, gitignored)
stripe_key = "sk_test_..."
anthropic_key = "sk-ant-..."
```

## Test Data

6 orders designed to exercise all reconciliation paths:

| Order | Item | Scenario |
|-------|------|---------|
| #3001 | Fjell Rain Jacket | Normal reconcile → BATCH1 |
| #3002 | Ridge Backpack 32L | Normal reconcile → BATCH1 |
| #3003 | Summit Headlamp | Normal reconcile → BATCH1 |
| #3004 | Alpine Down Jacket | Partial refund (-$45) → BATCH2 |
| #3005 | Aurora Sleeping Bag | Normal reconcile → BATCH2 |
| #3006 | Tind Hiking Boots | Intentional MISSING BANK DEPOSIT |

## Tech Stack

- **Python 3.x** — core language
- **Streamlit** — web UI and hosting
- **Pandas** — data processing
- **Requests** — Stripe + Anthropic API calls
- **openpyxl** — Excel export
- **Anthropic Claude Haiku** — AI audit explanations
- **Stripe Test API** — real test-mode payment data
