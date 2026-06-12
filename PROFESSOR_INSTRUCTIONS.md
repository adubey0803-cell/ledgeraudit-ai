# LedgerAudit AI — Submission Notes
**Student:** Ashutosh Dubey  
**App URL:** https://ledgeraudit-ai-gvqra3grdsbeep5wy9a8sp.streamlit.app/  
**GitHub:** https://github.com/adubey0803-cell/ledgeraudit-ai  

---

## What This App Does

LedgerAudit AI is a financial reconciliation tool that automatically matches:
- **Shopify orders** (what was sold)
- **Stripe charges** (what was collected)
- **Bank deposits** (what actually landed in the account)

It detects mismatches, duplicate charges, split payouts, missing deposits, chargebacks,
and partial refunds — then produces an AI-powered audit report with plain-English explanations.

---

## How to Run the Demo (No Installation Required)

Simply open the app in any browser:

**https://ledgeraudit-ai-gvqra3grdsbeep5wy9a8sp.streamlit.app/**

Everything is pre-configured. No API keys or passwords need to be entered.

---

## Step-by-Step Test Run

### Option A — Live Stripe API (Recommended)

1. Open the app URL above
2. In the left sidebar, expand **"Fetch from Stripe API"**
3. The Stripe API key is **pre-filled** — do not change it
4. Set **Days to fetch: 7**
5. **Deduplicate by order ref** checkbox should be **ticked**
6. Upload the file **`shopify_orders_test.csv`** (attached to this submission)
7. Upload the file **`bank_statement_test.csv`** (attached to this submission)
8. Click **"Fetch & Reconcile"**

### Option B — CSV Only (Fallback)

If the Stripe API is unavailable:

1. Expand **"Upload CSV files"** in the sidebar
2. Upload all three files: `shopify_orders_test.csv`, `stripe_payouts_test.csv`, `bank_statement_test.csv`
3. Click **"Reconcile (CSV)"**

---

## Expected Results

| Order | Item | Expected Status |
|-------|------|----------------|
| #3001 | Fjell Rain Jacket | RECONCILED → STRIPE PAYOUT BATCH1 |
| #3002 | Ridge Backpack 32L | RECONCILED → STRIPE PAYOUT BATCH1 |
| #3003 | Summit Headlamp | RECONCILED → STRIPE PAYOUT BATCH1 |
| #3004 | Alpine Down Jacket | RECONCILED (partial refund) → BATCH2 |
| #3005 | Aurora Sleeping Bag | RECONCILED → STRIPE PAYOUT BATCH2 |
| #3006 | Tind Hiking Boots | MISSING BANK DEPOSIT (intentional) |

- **Health Score:** ~90/100 (one intentional missing deposit deducts points)
- **QA Audit:** 1 warning for the missing deposit on #3006
- **AI Explanations:** Each audit finding includes a plain-English explanation

---

## Key Features to Note

| Feature | Where to See It |
|---------|----------------|
| Health Score (0-100) | Top of results — large coloured banner |
| AI audit explanations | QA Audit section — grey text under each finding |
| Split payout detection | Automatically detected if one order spans two bank deposits |
| Duplicate charge detection | Flags if same order appears twice in Stripe |
| Export to Excel | "Export Excel" button — 4 sheets: Orders, QA Audit, Duplicates, Summary |
| Export to Markdown | "Export Markdown" button |
| Snapshot history | "Save Snapshot" → "Run History" table shows trend over time |

---

## Important: Data Source Clarification

- **Stripe:** Connected live via Stripe REST API using a test-mode account.
  All charges are simulated (test card `tok_visa`) — no real money involved.
- **Shopify:** Not connected via API. Shopify OAuth was outside scope for this build.
  Orders are provided as a manually created CSV (`shopify_orders_test.csv`) that
  matches the Stripe test charges exactly.
- **Bank statement:** Not connected via Plaid or Open Banking API. The bank CSV
  (`bank_statement_test.csv`) was manually generated with deposit amounts computed
  from actual Stripe net payouts. In a production build both would be automated.

---

## Special Notes

- **Test data is real Stripe test-mode data** — charges were created via the Stripe API
  using test card `tok_visa`. No real money is involved.
- **AI explanations** use Claude Haiku (Anthropic API). The key is pre-configured.
  Each explanation is cached so the API is only called once per unique finding.
- **The app is stateless between sessions** — snapshot history resets on each deployment.
  To see the history trend, click "Save Snapshot" after reconciling, then reconcile again.
- **No installation required** — the app runs entirely in the browser via Streamlit Cloud.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend / App | Python · Streamlit |
| Data processing | Pandas |
| Payment data | Stripe REST API |
| AI explanations | Anthropic Claude Haiku |
| Hosting | Streamlit Community Cloud |
| Export | openpyxl (Excel) · Markdown |

---

## File List (attached to submission)

| File | Description |
|------|-------------|
| `reconcile_app.py` | Full application source code |
| `requirements.txt` | Python dependencies |
| `shopify_orders_test.csv` | 6 test Shopify orders (#3001–#3006) |
| `bank_statement_test.csv` | 2 bank deposits (BATCH1 + BATCH2) |
| `PROFESSOR_INSTRUCTIONS.md` | This file |
