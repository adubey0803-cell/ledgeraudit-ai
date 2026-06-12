import streamlit as st
import pandas as pd
import io, json, os
from itertools import combinations
from datetime import datetime, timedelta, timezone, date

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    _HAS_REQUESTS = False

st.set_page_config(page_title="LedgerAudit AI", layout="wide", page_icon="📊")
st.markdown(
    "<h1 style='margin-bottom:0'>📊 LedgerAudit AI</h1>"
    "<p style='color:#666; font-size:16px; margin-top:4px;'>"
    "Automated Shopify &times; Stripe &times; Bank reconciliation — "
    "AI-powered audit findings in seconds.</p>",
    unsafe_allow_html=True,
)

# ════════════════════════════════════════════════════════════════════════════════
# SIDEBAR — two independent data paths: CSV upload OR live Stripe API
# ════════════════════════════════════════════════════════════════════════════════
st.sidebar.header("Data Source")

# ── Quick action buttons (always visible at top) ──────────────────────────────
st.sidebar.markdown("**Quick Actions**")
_qa1, _qa2 = st.sidebar.columns(2)
_run_csv_top    = _qa1.button("Reconcile CSV", type="primary",  use_container_width=True)
_run_stripe_top = _qa2.button("Fetch Stripe",  type="secondary", use_container_width=True)
st.sidebar.caption("Configure inputs in the sections below, then click above.")
st.sidebar.divider()

# ── Sample data generator ──────────────────────────────────────────────────────
with st.sidebar.expander("Generate Sample Data", expanded=False):
    st.caption("No real data? Generate random test CSVs instantly.")
    num_orders   = st.slider("Number of orders", 3, 10, 5)
    missing_pct  = st.slider("% missing bank deposits", 0, 50, 20,
                             help="Simulates orders Stripe collected but bank never received")
    gen_btn      = st.button("Generate & Download CSVs")
    if gen_btn:
        import random, io as _io
        random.seed()
        items = ["Rain Jacket","Backpack","Headlamp","Down Jacket","Sleeping Bag",
                 "Hiking Boots","Trail Shoes","Fleece Vest","Trekking Poles","Base Layer"]
        stripe_rate = 0.029
        stripe_flat = 0.30
        shopify_rows, stripe_rows, bank_rows = [], [], []
        batch, batch_net = 1, 0.0
        batch_orders = []
        today_str = date.today().isoformat()
        for i in range(num_orders):
            ref   = f"#500{i+1}"
            item  = items[i % len(items)]
            gross = round(random.uniform(20, 250), 2)
            fee   = round(gross * stripe_rate + stripe_flat, 2)
            net   = round(gross - fee, 2)
            shopify_rows.append([ref, today_str, item, f"{gross:.2f}"])
            stripe_rows.append([f"ch_demo{i+1}", today_str, f"{gross:.2f}",
                                 f"{fee:.2f}", f"{net:.2f}", f"Payment for {ref} {item}"])
            missing = random.random() < (missing_pct / 100)
            if not missing:
                batch_net += net
                batch_orders.append(ref)
            # flush batch every 3 orders or on last order
            if (i + 1) % 3 == 0 or i == num_orders - 1:
                if batch_net > 0:
                    bank_rows.append([today_str,
                                      f"STRIPE PAYOUT BATCH{batch}",
                                      f"{batch_net:.2f}"])
                    batch += 1
                    batch_net = 0.0
                    batch_orders = []

        def _to_csv(headers, rows):
            buf = _io.StringIO()
            buf.write(",".join(headers) + "\n")
            for r in rows:
                buf.write(",".join(r) + "\n")
            return buf.getvalue().encode("utf-8")

        shopify_csv = _to_csv(["Name","Created at","Lineitem name","Total"], shopify_rows)
        stripe_csv  = _to_csv(["id","Created","Amount","Fee","Net","Description"], stripe_rows)
        bank_csv    = _to_csv(["Date","Description","Amount"], bank_rows)

        st.download_button("Download shopify_orders.csv", shopify_csv,
                           "shopify_orders.csv", "text/csv", key="dl_shop")
        st.download_button("Download stripe_payouts.csv", stripe_csv,
                           "stripe_payouts.csv", "text/csv", key="dl_stripe")
        st.download_button("Download bank_statement.csv", bank_csv,
                           "bank_statement.csv", "text/csv", key="dl_bank")
        st.caption(f"Generated {num_orders} orders across {batch-1} bank batch(es). "
                   "Upload all three above under 'Upload CSV files' to reconcile.")

# ── Path B: Live Stripe API (shown first — primary path) ─────────────────────
with st.sidebar.expander("Fetch from Stripe API", expanded=True):
    if not _HAS_REQUESTS:
        st.warning("`requests` library not found. Run `pip install requests` to enable live fetch.")
        run_stripe = False
        api_key    = ""
        fetch_days = 30
    else:
        _default_stripe = st.secrets.get("stripe_key", "") if hasattr(st, "secrets") else ""
        api_key    = st.text_input("Stripe API key", type="password",
                                   value=_default_stripe)
        fetch_days  = st.slider("Days to fetch", min_value=1, max_value=90, value=7)
        dedup_refs  = st.checkbox(
            "Deduplicate by order ref (keep latest charge per order)",
            value=True,
            help="Turn on if your test account has duplicate charges from multiple "
                 "seeder runs. In production, leave off so genuine duplicate charges "
                 "are still flagged."
        )
        st.markdown("**Shopify** (CSV or API):")
        shopify_file_stripe = st.file_uploader("Shopify Orders CSV",
                                               type="csv", key="shopify_stripe")
        shopify_store       = st.text_input("…or Shopify store domain",
                                            placeholder="mystore.myshopify.com",
                                            key="shop_store")
        shopify_token       = st.text_input("Shopify Admin API token", type="password",
                                            placeholder="shpat_...",
                                            key="shop_token")
        bank_file_stripe    = st.file_uploader("Bank Statement CSV (still needed)",
                                               type="csv", key="bank_stripe")
        shop_ready          = shopify_file_stripe or (shopify_store and shopify_token)
        stripe_api_ready    = bool(api_key) and shop_ready and bank_file_stripe
        run_stripe          = st.button("Fetch & Reconcile", type="primary",
                                        disabled=not stripe_api_ready) or (_run_stripe_top and stripe_api_ready)

st.sidebar.divider()

# ── Path A: CSV upload ─────────────────────────────────────────────────────────
with st.sidebar.expander("Upload CSV files (manual)", expanded=False):
    shopify_file = st.file_uploader("Shopify Orders CSV", type="csv")
    stripe_file  = st.file_uploader("Stripe Payouts CSV", type="csv")
    bank_file    = st.file_uploader("Bank Statement CSV", type="csv")
    csv_ready    = shopify_file and stripe_file and bank_file
    run_csv      = st.button("Reconcile (CSV)", type="primary", disabled=not csv_ready) or (_run_csv_top and csv_ready)

# ── AI explanations (optional) ────────────────────────────────────────────────
with st.sidebar.expander("AI explanations (optional)", expanded=False):
    _default_anthropic = st.secrets.get("anthropic_key", "") if hasattr(st, "secrets") else ""
    anthropic_key = st.text_input(
        "Anthropic API key", type="password",
        value=_default_anthropic,
        help="Adds a plain-English explanation under each audit finding. "
             "Get a key at console.anthropic.com. Explanations are cached "
             "so each unique finding is only called once per session."
    )

# ── Period filter (applies to all paths) ──────────────────────────────────────
with st.sidebar.expander("Period filter (optional)", expanded=False):
    period_mode = st.selectbox("Scope", ["All data", "Specific month"], index=0)
    if period_mode == "Specific month":
        period_year  = st.number_input("Year",  min_value=2020, max_value=2030, value=2026)
        period_month = st.selectbox("Month", list(range(1, 13)), index=5)
    else:
        period_year = period_month = None

# Guard: nothing to do yet
if not run_csv and not run_stripe:
    if csv_ready:
        st.success("Files ready. Click Reconcile (CSV).")
    elif _HAS_REQUESTS and api_key:
        st.success("API key set. Upload Shopify + Bank CSVs, then click Fetch & Reconcile.")
    else:
        st.info("Upload CSV files or enter a Stripe API key in the sidebar to begin.")
    st.stop()

# ════════════════════════════════════════════════════════════════════════════════
# STRIPE API FETCH (only when Path B was chosen)
# ════════════════════════════════════════════════════════════════════════════════

def _stripe_get(api_key, endpoint, params):
    """Single authenticated GET to Stripe. Raises on HTTP error."""
    resp = requests.get(
        "https://api.stripe.com/v1" + endpoint,
        headers={"Authorization": "Bearer " + api_key},
        params=params,
        timeout=15,
    )
    resp.raise_for_status()
    return resp.json()

def _paginate(api_key, endpoint, base_params):
    """Cursor-paginate through all pages of a Stripe list endpoint."""
    items  = []
    params = dict(base_params, limit=100)
    while True:
        page = _stripe_get(api_key, endpoint, params)
        items.extend(page["data"])
        if not page.get("has_more"):
            break
        params["starting_after"] = page["data"][-1]["id"]
    return items

def fetch_stripe_as_df(api_key, days, dedup=False):
    """
    Fetch charges + refunds from Stripe for the last `days` days.
    Uses /v1/charges (with expanded balance_transaction) rather than
    /v1/balance/history — charge objects carry description reliably.

    Returns a DataFrame with the same columns as the Stripe CSV:
        id, Created, Amount, Fee, Net, Description
    """
    since = int((datetime.now(tz=timezone.utc) - timedelta(days=days)).timestamp())

    # Fetch charges with balance_transaction expanded so we get fee/net in one call
    charges = _paginate(api_key, "/charges", {
        "created[gte]": since,
        "expand[]":     "data.balance_transaction",
    })

    # Build a lookup: charge_id -> description (for matching refunds later)
    charge_desc = {}
    rows = []
    for c in charges:
        bt = c.get("balance_transaction")
        if not isinstance(bt, dict):
            continue   # uncaptured or failed charge — no balance impact

        desc   = c.get("description") or c.get("statement_descriptor") or ""
        amount =  c["amount"] / 100
        fee    =  bt["fee"]   / 100
        net    =  bt["net"]   / 100
        charge_desc[c["id"]] = desc

        rows.append({
            "id":          c["id"],
            "Created":     datetime.fromtimestamp(c["created"],
                                                   tz=timezone.utc).strftime("%Y-%m-%d"),
            "Amount":      amount,
            "Fee":         fee,
            "Net":         net,
            "Description": desc,
        })

    # Fetch refunds separately — Stripe's newer API versions removed the inline
    # refunds list from charge objects; /v1/refunds is the reliable source.
    refunds_raw = _paginate(api_key, "/refunds", {"created[gte]": since})
    for rf in refunds_raw:
        parent_desc = charge_desc.get(rf.get("charge"), "")
        rf_amount   = -(rf["amount"] / 100)
        rows.append({
            "id":          rf["id"],
            "Created":     datetime.fromtimestamp(rf["created"],
                                                   tz=timezone.utc).strftime("%Y-%m-%d"),
            "Amount":      rf_amount,
            "Fee":         0.0,
            "Net":         rf_amount,
            "Description": parent_desc,  # same description → same order_ref
        })

    df_out = pd.DataFrame(rows, columns=["id", "Created", "Amount", "Fee", "Net", "Description"])

    # ── Diagnostics (always render, auto-expand when empty) ───────────────────
    n_charges = sum(1 for r in rows if r["Amount"] > 0)
    n_refunds = sum(1 for r in rows if r["Amount"] < 0)
    since_str = datetime.fromtimestamp(since, tz=timezone.utc).strftime("%Y-%m-%d")

    with st.expander("Stripe API diagnostics", expanded=df_out.empty):
        st.write(f"**Date window:** last {days} day(s) — since {since_str}")
        st.write(f"**Charges fetched:** {n_charges}  |  **Refunds:** {n_refunds}")
        if df_out.empty:
            st.warning("No charges found in this window. "
                       "Increase 'Days to fetch' and try again.")
        else:
            # Show a sample so you can verify descriptions look right
            sample = df_out[["id","Created","Amount","Net","Description"]].head(5)
            st.write("**Sample rows (first 5):**")
            st.dataframe(sample, hide_index=True, use_container_width=True)
            no_ref = df_out[df_out["Description"].str.extract(r"(#\d+)")[0].isna()]
            if not no_ref.empty:
                st.warning(
                    f"{len(no_ref)} row(s) have no order ref (#NNNN) in their description "
                    "and will not match any Shopify order. Check that your charges were "
                    "created with descriptions like 'Payment for #1234'."
                )

    # ── Deduplicate by order ref (keep latest charge per ref) ─────────────────
    if dedup and not df_out.empty:
        df_out["_ref"] = df_out["Description"].str.extract(r"(#\d+)")
        positives = df_out[df_out["Amount"] > 0].copy()
        negatives = df_out[df_out["Amount"] < 0].copy()

        has_ref   = positives["_ref"].notna()
        deduped_p = pd.concat([
            positives[has_ref].sort_values("Created").groupby("_ref").last().reset_index().drop(columns=["_ref"]),
            positives[~has_ref],
        ], ignore_index=True)

        removed = len(positives) - len(deduped_p)
        if removed > 0:
            st.info(
                f"Deduplicated: removed {removed} older charge(s), kept only the most "
                "recent per order ref. Turn off 'Deduplicate' to see all charges."
            )
        df_out = pd.concat([deduped_p, negatives], ignore_index=True).drop(columns=["_ref"])

    return df_out

# ── Load stripe_df from whichever path was activated ──────────────────────────
stripe_source_label = ""

def fetch_shopify_as_df(store, token, days):
    """Fetch orders from Shopify Admin API. Returns DataFrame matching CSV format."""
    since   = (datetime.now(tz=timezone.utc) - timedelta(days=days)).isoformat()
    url     = f"https://{store}/admin/api/2024-01/orders.json"
    headers = {"X-Shopify-Access-Token": token}
    rows    = []
    params  = {"status": "any", "created_at_min": since, "limit": 250}
    while True:
        r = requests.get(url, headers=headers, params=params, timeout=15)
        r.raise_for_status()
        for o in r.json().get("orders", []):
            items = o.get("line_items", [{}])
            rows.append({
                "Name": o.get("name", ""),
                "Created at": o.get("created_at", ""),
                "Lineitem name": items[0].get("title", "") if items else "",
                "Total": float(o.get("total_price", 0)),
            })
        link = r.headers.get("Link", "")
        if 'rel="next"' not in link:
            break
        url = link.split("<")[1].split(">")[0]
        params = {}
    return pd.DataFrame(rows, columns=["Name", "Created at", "Lineitem name", "Total"])

if run_stripe:
    with st.spinner("Fetching from Stripe API..."):
        try:
            stripe_df_raw   = fetch_stripe_as_df(api_key, fetch_days, dedup=dedup_refs)
            if shopify_file_stripe:
                shopify_file = shopify_file_stripe
            else:
                shop_df      = fetch_shopify_as_df(shopify_store, shopify_token, fetch_days)
                shop_buf     = io.BytesIO()
                shop_df.to_csv(shop_buf, index=False)
                shop_buf.seek(0)
                shopify_file = shop_buf
                st.info(f"Shopify API: fetched {len(shop_df)} orders")
            bank_file       = bank_file_stripe
            stripe_file     = None            # not used in this path
            stripe_source_label = (
                "Live Stripe API — last " + str(fetch_days) + " days  "
                "(" + str(len(stripe_df_raw)) + " transactions fetched)"
            )
            st.success(stripe_source_label)
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else "?"
            body   = ""
            if e.response is not None:
                try:
                    body = e.response.json().get("error", {}).get("message", "")
                except Exception:
                    pass
            st.error(
                "Stripe API error " + str(status) + ": " + body + "\n\n"
                "Check your API key and try again, or upload a CSV instead."
            )
            st.stop()
        except requests.exceptions.ConnectionError:
            st.error("Could not reach Stripe (no internet connection). "
                     "Upload a CSV instead.")
            st.stop()
        except Exception as e:
            st.error("Unexpected error fetching from Stripe: " + str(e))
            st.stop()
else:
    stripe_df_raw       = pd.read_csv(stripe_file)
    stripe_source_label = "CSV upload"

# ════════════════════════════════════════════════════════════════════════════════
# DATA LOADING — identical path from here regardless of source
# ════════════════════════════════════════════════════════════════════════════════
shopify = pd.read_csv(shopify_file)
stripe  = stripe_df_raw.copy()
bank    = pd.read_csv(bank_file)

stripe["order_ref"] = stripe["Description"].str.extract(r"(#\d+)")
stripe["Created"]   = pd.to_datetime(stripe["Created"])
shopify["Created"]  = pd.to_datetime(shopify["Created at"])
bank["Date"]        = pd.to_datetime(bank["Date"])

# Apply period filter if set
if period_year and period_month:
    def _in_period(s):
        return (s.dt.year == period_year) & (s.dt.month == period_month)
    stripe  = stripe[_in_period(stripe["Created"])].copy()
    shopify = shopify[_in_period(shopify["Created"])].copy()
    bank    = bank[_in_period(bank["Date"])].copy()
    st.info(f"Period filter active: **{period_year}-{period_month:02d}**  "
            f"({len(stripe)} stripe rows, {len(shopify)} orders, {len(bank)} bank entries)")

# ── Data integrity check — shown before reconciliation so problems are obvious ─
with st.expander("Data loaded — click to verify before reconciling", expanded=True):
    col_a, col_b, col_c = st.columns(3)

    with col_a:
        st.write("**Stripe rows**", len(stripe))
        st.dataframe(
            stripe[["id", "Description", "order_ref", "Amount", "Net"]].head(10),
            hide_index=True, use_container_width=True
        )
        n_missing_ref = stripe["order_ref"].isna().sum()
        if n_missing_ref:
            st.warning(f"{n_missing_ref} row(s) have no order ref — "
                       "descriptions don't contain #NNNN. "
                       "Those rows won't match any Shopify order.")

    with col_b:
        st.write("**Shopify orders**", len(shopify))
        st.dataframe(
            shopify[["Name", "Lineitem name", "Total"]].head(10),
            hide_index=True, use_container_width=True
        )

    with col_c:
        st.write("**Bank deposits**", len(bank))
        st.dataframe(bank[["Date", "Description", "Amount"]],
                     hide_index=True, use_container_width=True)

    # Cross-check: which Shopify order names appear in the Stripe order refs?
    shopify_orders  = set(shopify["Name"].str.strip())
    stripe_refs     = set(stripe["order_ref"].dropna())
    matched_refs    = shopify_orders & stripe_refs
    unmatched_shop  = shopify_orders - stripe_refs
    st.write(f"**Order ref overlap:** {len(matched_refs)} of {len(shopify_orders)} "
             f"Shopify orders found in Stripe descriptions")
    if unmatched_shop:
        st.warning("Shopify orders NOT found in Stripe: " + ", ".join(sorted(unmatched_shop)))

def cents(x):
    return round(float(x) * 100)

# ── Classify stripe negatives ──────────────────────────────────────────────────
negatives   = stripe[stripe["Amount"] < 0].copy()
chargebacks = negatives[negatives["Description"].str.contains("Chargeback", case=False, na=False)].copy()
refunds     = negatives[~negatives["Description"].str.contains("Chargeback", case=False, na=False)].copy()

payouts = stripe[stripe["Amount"] > 0].copy().set_index("order_ref")
for order, grp in refunds.groupby("order_ref"):
    if order in payouts.index:
        payouts.loc[order, "Net"] += grp["Net"].sum()
payouts = payouts.reset_index()

is_stripe  = bank["Description"].str.contains("STRIPE", case=False, na=False)
stripe_pos = bank[is_stripe & (bank["Amount"] > 0)].copy()
stripe_neg = bank[is_stripe & (bank["Amount"] < 0)].copy()

payout_list  = [(r["order_ref"], r["id"], cents(r["Net"])) for _, r in payouts.iterrows()]
deposit_list = [(r["Description"], cents(r["Amount"])) for _, r in stripe_pos.iterrows()]

# ── Phase 1: subset-sum via DP (O(n*target) — handles 100s of payouts instantly) ──
def subset_sum_dp(items, target):
    """items: list of (key, value) in cents. Returns list of keys summing to target, or None."""
    if target <= 0:
        return None
    dp = {0: []}
    for key, val in items:
        if val <= 0 or val > target:
            continue
        new_dp = dict(dp)
        for s, keys in dp.items():
            ns = s + val
            if ns <= target and ns not in new_dp:
                new_dp[ns] = keys + [key]
        dp = new_dp
        if target in dp:
            return dp[target]
    return dp.get(target)

matched_pids    = set()
deposit_map     = {}
split_parts_map = {}
deposit_claimed = set()
pid_lookup      = {pid: (ref, net) for ref, pid, net in payout_list}

for dep_label, dep_amt in deposit_list:
    available = [(pid, net) for ref, pid, net in payout_list if pid not in matched_pids]
    pids      = subset_sum_dp(available, dep_amt)
    if pids:
        for pid in pids:
            matched_pids.add(pid)
            deposit_map[pid]     = dep_label
            split_parts_map[pid] = [(dep_label, pid_lookup[pid][1])]
        deposit_claimed.add(dep_label)

# ── Phase 2: split detection ──────────────────────────────────────────────────
unmatched_payouts  = [p for p in payout_list  if p[1] not in matched_pids]
unmatched_deposits = [(l, a) for l, a in deposit_list if l not in deposit_claimed]
matched_order_refs = {p[0] for p in payout_list if p[1] in matched_pids}

split_candidates = sorted(
    [p for p in unmatched_payouts if p[0] not in matched_order_refs],
    key=lambda p: p[2], reverse=True
)

def try_split(split_pid, split_net, dep1_label, dep1_amt, dep2_label, dep2_amt, others):
    for r1 in range(0, len(others) + 1):
        for idx1 in combinations(range(len(others)), r1):
            sel1 = [others[k] for k in idx1]
            sum1 = sum(p[2] for p in sel1)
            if sum1 >= dep1_amt:
                continue
            R1 = dep1_amt - sum1
            if R1 > split_net or R1 <= 0:
                continue
            R2       = split_net - R1
            leftover = [others[k] for k in range(len(others)) if k not in idx1]
            for r2 in range(0, len(leftover) + 1):
                for idx2 in combinations(range(len(leftover)), r2):
                    sel2 = [leftover[k] for k in idx2]
                    if sum(p[2] for p in sel2) + R2 == dep2_amt:
                        return {
                            "split_pid":   split_pid,
                            "split_parts": [(dep1_label, R1), (dep2_label, R2)],
                            "complete1":   [p[1] for p in sel1],
                            "complete2":   [p[1] for p in sel2],
                            "dep1_label":  dep1_label,
                            "dep2_label":  dep2_label,
                        }
    return None

def find_one_split(unmatched_p, unmatched_d, dup_refs):
    cands = sorted([p for p in unmatched_p if p[0] not in dup_refs],
                   key=lambda p: p[2], reverse=True)
    for split_ref, split_pid, split_net in cands:
        others = [p for p in unmatched_p if p[1] != split_pid]
        for i in range(len(unmatched_d)):
            for j in range(i + 1, len(unmatched_d)):
                d1l, d1a = unmatched_d[i]
                d2l, d2a = unmatched_d[j]
                r = try_split(split_pid, split_net, d1l, d1a, d2l, d2a, others)
                if r:
                    return r
    return None

# Loop until no more splits found (handles multiple split payouts)
splits_found = 0
while True:
    split_result = find_one_split(unmatched_payouts, unmatched_deposits, matched_order_refs)
    if not split_result:
        break
    splits_found += 1

    sp = split_result["split_pid"]
    matched_pids.add(sp)
    split_parts_map[sp] = split_result["split_parts"]
    deposit_map[sp]     = (split_result["dep1_label"] + " + " +
                           split_result["dep2_label"] + " (split)")
    deposit_claimed.update([split_result["dep1_label"], split_result["dep2_label"]])
    for pid in split_result["complete1"]:
        matched_pids.add(pid)
        net = next(p[2] for p in payout_list if p[1] == pid)
        deposit_map[pid]     = split_result["dep1_label"]
        split_parts_map[pid] = [(split_result["dep1_label"], net)]
    for pid in split_result["complete2"]:
        matched_pids.add(pid)
        net = next(p[2] for p in payout_list if p[1] == pid)
        deposit_map[pid]     = split_result["dep2_label"]
        split_parts_map[pid] = [(split_result["dep2_label"], net)]

    # Recompute remaining work for next iteration
    unmatched_payouts  = [p for p in payout_list  if p[1] not in matched_pids]
    unmatched_deposits = [(l, a) for l, a in deposit_list if l not in deposit_claimed]
    matched_order_refs = {p[0] for p in payout_list if p[1] in matched_pids}
    if not unmatched_payouts or len(unmatched_deposits) < 2:
        break

# ── Chargebacks ───────────────────────────────────────────────────────────────
chargeback_map = {}
for _, cb in chargebacks.iterrows():
    cb_c = cents(cb["Amount"])
    for _, dep in stripe_neg.iterrows():
        if cents(dep["Amount"]) == cb_c:
            chargeback_map[cb["id"]] = dep["Description"]
            break

# ── Duplicate payouts ─────────────────────────────────────────────────────────
payout_groups = {}
for _, pr in payouts.iterrows():
    payout_groups.setdefault(pr["order_ref"], []).append(pr)

duplicate_orders = {ref for ref, prs in payout_groups.items() if len(prs) > 1}
duplicate_detail = {
    ref: [{"payout_id": pr["id"], "net": float(pr["Net"]),
            "bank_deposit": deposit_map.get(pr["id"], "UNMATCHED")}
          for pr in prs]
    for ref, prs in payout_groups.items() if len(prs) > 1
}

# ── Per-order status ──────────────────────────────────────────────────────────
rows = []
for _, o in shopify.iterrows():
    order = o["Name"].strip()
    item  = o["Lineitem name"]
    gross = float(o["Total"])

    order_payouts = payouts[payouts["order_ref"] == order]
    if order_payouts.empty:
        rows.append(dict(order=order, item=item, gross=gross,
                         fee=None, net=None, chargeback=None,
                         bank_deposit=None, status="MISSING IN STRIPE"))
        continue

    if order in duplicate_orders:
        all_nets = sum(float(pr["Net"]) for pr in payout_groups[order])
        all_deps = ", ".join(deposit_map.get(pr["id"], "UNMATCHED")
                             for pr in payout_groups[order])
        rows.append(dict(order=order, item=item, gross=gross,
                         fee=None, net=all_nets, chargeback=None,
                         bank_deposit=all_deps, status="DUPLICATE CHARGE"))
        continue

    matched_row = next(
        (pr for _, pr in order_payouts.iterrows() if pr["id"] in matched_pids), None
    )
    if matched_row is None:
        pr = order_payouts.iloc[0]
        rows.append(dict(order=order, item=item, gross=gross,
                         fee=float(pr["Fee"]), net=float(pr["Net"]),
                         chargeback=None, bank_deposit=None,
                         status="MISSING BANK DEPOSIT"))
        continue

    pid      = matched_row["id"]
    fee      = float(matched_row["Fee"])
    net      = float(matched_row["Net"])
    deposit  = deposit_map.get(pid)
    is_split = len(split_parts_map.get(pid, [])) > 1

    cb_rows  = chargebacks[chargebacks["order_ref"] == order]
    cb_amt   = float(cb_rows["Amount"].sum()) if not cb_rows.empty else 0.0
    ref_rows = refunds[refunds["order_ref"] == order]
    ref_amt  = float(ref_rows["Amount"].sum()) if not ref_rows.empty else 0.0

    if is_split:
        status = "SPLIT RECONCILED"
    elif ref_amt < 0:
        status = "RECONCILED (partial refund)"
    elif cb_amt < 0:
        status = "RECONCILED (chargeback issued)"
    else:
        status = "RECONCILED"

    rows.append(dict(order=order, item=item, gross=gross, fee=fee, net=net,
                     chargeback=cb_amt if cb_amt < 0 else None,
                     bank_deposit=deposit, status=status))

df = pd.DataFrame(rows)

# ════════════════════════════════════════════════════════════════════════════════
# QA AUDITOR
# ════════════════════════════════════════════════════════════════════════════════
pid_to_cents       = {pid: net for _, pid, net in payout_list}
deposit_allocated  = {label: 0 for label, _ in deposit_list}
for pid, parts in split_parts_map.items():
    for dep_label, portion in parts:
        if dep_label in deposit_allocated:
            deposit_allocated[dep_label] += portion
deposit_amount_map = {label: amt for label, amt in deposit_list}

audit_findings = []

# Check 1: sum mismatch
for dep_label in deposit_claimed:
    dep_amt   = deposit_amount_map.get(dep_label, 0)
    allocated = deposit_allocated.get(dep_label, 0)
    diff      = dep_amt - allocated
    if diff != 0:
        affected = [row["order"] for _, row in df.iterrows()
                    if dep_label in str(row.get("bank_deposit", ""))]
        audit_findings.append({
            "check": "SUM MISMATCH", "severity": "ERROR", "orders": affected,
            "message": (
                "Deposit " + dep_label + ": bank shows $" + f"{dep_amt/100:.2f}" +
                " but allocated payouts total $" + f"{allocated/100:.2f}" +
                " — off by $" + f"{abs(diff)/100:.2f}" +
                (" short" if diff > 0 else " over") + "."
            ),
        })

# Check 2: deposit remainder
for dep_label in deposit_claimed:
    dep_amt   = deposit_amount_map.get(dep_label, 0)
    allocated = deposit_allocated.get(dep_label, 0)
    remainder = dep_amt - allocated
    if remainder > 0:
        audit_findings.append({
            "check": "DEPOSIT REMAINDER", "severity": "WARNING", "orders": [],
            "message": (
                "Deposit " + dep_label + " has $" + f"{remainder/100:.2f}" +
                " unaccounted for after all matched payouts are applied."
            ),
        })

# Check 3: orphan payouts
flagged_orders = set(
    row["order"] for _, row in df.iterrows()
    if row["status"] in ("MISSING BANK DEPOSIT", "DUPLICATE CHARGE", "MISSING IN STRIPE")
)
all_flagged_pids = {
    pid for _, pid, _ in payout_list
    if next((r["order_ref"] for _, r in payouts.iterrows() if r["id"] == pid), None)
       in flagged_orders
}
for order_ref, pid, net in payout_list:
    if pid in matched_pids or pid in all_flagged_pids:
        continue
    audit_findings.append({
        "check": "ORPHAN PAYOUT", "severity": "ERROR", "orders": [order_ref],
        "message": (
            "Payout " + pid + " for order " + str(order_ref) +
            " (net $" + f"{net/100:.2f}" + ") is not matched to any bank deposit "
            "and is not flagged as missing."
        ),
    })

# ── Business-rule checks (warnings, no status override) ──────────────────────
# Check 4: fee % outside Stripe's typical 2.9% + $0.30 band
for _, pr in payouts.iterrows():
    gross = float(pr["Amount"])
    fee   = float(pr["Fee"])
    if gross <= 0:
        continue
    expected_fee = gross * 0.029 + 0.30
    deviation    = abs(fee - expected_fee)
    if deviation > 0.50 and abs(deviation / expected_fee) > 0.50:
        audit_findings.append({
            "check": "FEE ANOMALY", "severity": "WARNING",
            "orders": [pr["order_ref"]],
            "message": (
                f"Payout {pr['id']} for {pr['order_ref']}: fee ${fee:.2f} "
                f"deviates {deviation/expected_fee*100:.1f}% from expected "
                f"${expected_fee:.2f} (2.9% + $0.30). Possible fee tier change "
                "or international/Amex surcharge."
            ),
        })

# Check 5: refund-to-gross ratio
_gross_for_check  = df["gross"].sum() if not df.empty else 0.0
_refund_for_check = abs(float(refunds["Amount"].sum())) if not refunds.empty else 0.0
if _gross_for_check > 0:
    ratio = _refund_for_check / _gross_for_check
    if ratio > 0.15:
        audit_findings.append({
            "check": "HIGH REFUND RATIO", "severity": "WARNING", "orders": [],
            "message": (
                f"Refunds are {ratio*100:.1f}% of gross sales "
                f"(${_refund_for_check:.2f} / ${_gross_for_check:.2f}). "
                "Industry benchmark is 5-10%."
            ),
        })

# Check 6: Stripe charges with no matching Shopify order (potential fraud / wrong channel)
shopify_order_set = set(shopify["Name"].str.strip())
for _, pr in payouts.iterrows():
    ref = pr["order_ref"]
    if pd.isna(ref) or ref not in shopify_order_set:
        audit_findings.append({
            "check": "ORPHAN CHARGE", "severity": "WARNING",
            "orders": [ref if pd.notna(ref) else "?"],
            "message": (
                f"Stripe charge {pr['id']} (${float(pr['Amount']):.2f}) "
                f"references {'order ' + str(ref) if pd.notna(ref) else 'NO order'} "
                "which is not in Shopify. Possible fraud, manual charge, "
                "or wrong sales channel."
            ),
        })

# Check 7: chargebacks (always flag for review even if reconciled)
for _, cb in chargebacks.iterrows():
    audit_findings.append({
        "check": "CHARGEBACK", "severity": "WARNING",
        "orders": [cb.get("order_ref", "?")],
        "message": (
            f"Chargeback {cb['id']} for ${abs(float(cb['Amount'])):.2f} on "
            f"{cb.get('order_ref', 'unknown')}. Review dispute evidence "
            "and Stripe response deadline."
        ),
    })

# Drop the placeholder dummy finding from check 5
audit_findings = [f for f in audit_findings if f.get("message")]

# Override status for ERROR findings
overrideable        = {"RECONCILED", "RECONCILED (partial refund)",
                       "RECONCILED (chargeback issued)", "SPLIT RECONCILED"}
needs_review_orders = {o for f in audit_findings if f["severity"] == "ERROR"
                         for o in f["orders"]}
for idx, row in df.iterrows():
    if row["order"] in needs_review_orders and row["status"] in overrideable:
        df.at[idx, "status"] = "NEEDS REVIEW"

# ── Health Score ─────────────────────────────────────────────────────────────
def compute_health_score(df, audit_findings):
    n = len(df)
    if n == 0:
        return 100, []

    deductions = []

    # -15 per MISSING IN STRIPE
    mis_stripe = (df["status"] == "MISSING IN STRIPE").sum()
    if mis_stripe:
        d = min(15 * mis_stripe, 30)
        deductions.append((-d, f"{mis_stripe} order(s) missing in Stripe (-{d} pts)"))

    # -10 per MISSING BANK DEPOSIT
    mis_bank = (df["status"] == "MISSING BANK DEPOSIT").sum()
    if mis_bank:
        d = min(10 * mis_bank, 25)
        deductions.append((-d, f"{mis_bank} missing bank deposit(s) (-{d} pts)"))

    # -8 per DUPLICATE CHARGE
    dupes = (df["status"] == "DUPLICATE CHARGE").sum()
    if dupes:
        d = min(8 * dupes, 20)
        deductions.append((-d, f"{dupes} duplicate charge(s) (-{d} pts)"))

    # -5 per NEEDS REVIEW
    needs_review = (df["status"] == "NEEDS REVIEW").sum()
    if needs_review:
        d = min(5 * needs_review, 15)
        deductions.append((-d, f"{needs_review} order(s) need review (-{d} pts)"))

    # -5 per ERROR audit finding
    audit_errors = sum(1 for f in audit_findings if f["severity"] == "ERROR")
    if audit_errors:
        d = min(5 * audit_errors, 15)
        deductions.append((-d, f"{audit_errors} audit error(s) (-{d} pts)"))

    # -2 per WARNING audit finding
    audit_warns = sum(1 for f in audit_findings if f["severity"] == "WARNING")
    if audit_warns:
        d = min(2 * audit_warns, 10)
        deductions.append((-d, f"{audit_warns} audit warning(s) (-{d} pts)"))

    score = max(0, 100 + sum(p for p, _ in deductions))
    return score, deductions

health_score, health_deductions = compute_health_score(df, audit_findings)

# Summary counts
total_gross    = df["gross"].sum()
total_fee      = df["fee"].dropna().sum()
total_refund   = abs(float(refunds["Amount"].sum())) if not refunds.empty else 0.0
total_net_pre  = total_gross - total_fee
total_net_post = total_net_pre - total_refund
missing_amt    = df[df["status"] == "MISSING BANK DEPOSIT"]["net"].sum()
total_in_bank  = stripe_pos["Amount"].sum()
reconciled_n   = df[df["status"].str.startswith("RECONCILED")].shape[0]
flagged_n      = df[~df["status"].str.startswith("RECONCILED")].shape[0]
unexplained    = [(l, a / 100) for l, a in deposit_list if l not in deposit_claimed]

# ════════════════════════════════════════════════════════════════════════════════
# DISPLAY
# ════════════════════════════════════════════════════════════════════════════════
# Show data source badge
source_icon = "API" if run_stripe else "CSV"
st.caption("Data source: **" + source_icon + "** — " + stripe_source_label +
           (f"  |  Split payouts detected: **{splits_found}**" if splits_found else ""))

# ── Export & persistence ──────────────────────────────────────────────────────
def build_excel():
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as w:
        df.to_excel(w, sheet_name="Orders", index=False)
        pd.DataFrame(audit_findings).to_excel(w, sheet_name="QA Audit", index=False)
        if duplicate_detail:
            pd.DataFrame([{"order": k, **d} for k, v in duplicate_detail.items() for d in v]
                         ).to_excel(w, sheet_name="Duplicates", index=False)
        pd.DataFrame([
            {"Metric": "Gross sales",     "Value": total_gross},
            {"Metric": "Stripe fees",     "Value": total_fee},
            {"Metric": "Refunds",         "Value": total_refund},
            {"Metric": "Net expected",    "Value": total_net_post},
            {"Metric": "Received in bank","Value": total_in_bank},
            {"Metric": "Missing payouts", "Value": missing_amt},
        ]).to_excel(w, sheet_name="Summary", index=False)
    return buf.getvalue()

def build_markdown():
    lines = ["# Reconciliation Report", f"\n_Generated {date.today().isoformat()}_\n",
             f"\n**Source:** {stripe_source_label}\n",
             "\n## Summary\n",
             f"- Reconciled: **{reconciled_n} / {len(df)}**",
             f"- Flagged: **{flagged_n}**",
             f"- Gross: **${total_gross:,.2f}**",
             f"- Fees: ${total_fee:,.2f}  |  Refunds: ${total_refund:,.2f}",
             f"- Received in bank: **${total_in_bank:,.2f}**",
             f"- Missing payouts: ${missing_amt:,.2f}",
             "\n## Orders\n",
             "| " + " | ".join(df.columns) + " |",
             "|" + "|".join(["---"] * len(df.columns)) + "|",
             *("| " + " | ".join(str(v) for v in row) + " |" for row in df.values),
             f"\n## QA Audit ({len(audit_findings)} finding(s))\n"]
    for f in audit_findings:
        lines.append(f"- **[{f['severity']}] {f['check']}** — {f['message']}")
    return "\n".join(lines).encode("utf-8")

# Persistence: save / load snapshots
SNAPSHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "snapshots")
os.makedirs(SNAPSHOT_DIR, exist_ok=True)

ec1, ec2, ec3, ec4 = st.columns([1, 1, 1, 2])
ec1.download_button("Export Excel", build_excel(),
                    file_name=f"reconciliation_{date.today().isoformat()}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
ec2.download_button("Export Markdown", build_markdown(),
                    file_name=f"reconciliation_{date.today().isoformat()}.md",
                    mime="text/markdown")
if ec3.button("Save Snapshot"):
    snap = {"date": date.today().isoformat(), "source": stripe_source_label,
            "health_score": health_score,
            "orders": df.to_dict("records"), "audit": audit_findings,
            "summary": {"gross": total_gross, "fees": total_fee,
                        "refunds": total_refund, "in_bank": total_in_bank,
                        "missing": missing_amt}}
    path = os.path.join(SNAPSHOT_DIR, f"snap_{date.today().isoformat()}_{len(os.listdir(SNAPSHOT_DIR))}.json")
    with open(path, "w") as fp:
        json.dump(snap, fp, default=str, indent=2)
    ec3.success(f"Saved: {os.path.basename(path)}")
ec4.caption(f"Snapshots: {len(os.listdir(SNAPSHOT_DIR))} in `{SNAPSHOT_DIR}`")

# ── Health Score display ──────────────────────────────────────────────────────
if health_score >= 90:
    score_color = "#1a7a1a"
    score_bg    = "#e6f4e6"
    score_label = "Excellent"
    score_icon  = "[A]"
elif health_score >= 70:
    score_color = "#856404"
    score_bg    = "#fff8e1"
    score_label = "Needs Attention"
    score_icon  = "[B]"
elif health_score >= 50:
    score_color = "#cc5500"
    score_bg    = "#fff0e0"
    score_label = "Poor"
    score_icon  = "[C]"
else:
    score_color = "#900000"
    score_bg    = "#ffe0e0"
    score_label = "Critical"
    score_icon  = "[F]"

st.markdown(
    f"""
    <div style="background:{score_bg}; border-left:6px solid {score_color};
                border-radius:8px; padding:20px 28px; margin-bottom:20px;">
      <div style="display:flex; align-items:center; gap:24px; flex-wrap:wrap;">
        <div>
          <div style="font-size:14px; color:{score_color}; font-weight:600;
                      letter-spacing:1px; text-transform:uppercase;">
            Reconciliation Health Score
          </div>
          <div style="font-size:64px; font-weight:800; color:{score_color};
                      line-height:1.0; margin:4px 0;">
            {health_score}
            <span style="font-size:24px; font-weight:500;">/ 100</span>
          </div>
          <div style="font-size:18px; font-weight:600; color:{score_color};">
            {score_icon} {score_label}
          </div>
        </div>
        <div style="flex:1; min-width:220px;">
          <div style="background:#e0e0e0; border-radius:6px; height:16px; margin:8px 0 12px;">
            <div style="background:{score_color}; width:{health_score}%;
                         height:16px; border-radius:6px; transition:width 0.5s;"></div>
          </div>
          {"".join(
              f'<div style="font-size:13px; color:{score_color}; margin:2px 0;">{label}</div>'
              for _, label in health_deductions
          ) if health_deductions else
          '<div style="font-size:13px; color:#1a7a1a;">No issues found — perfect score!</div>'}
        </div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

st.header("Summary")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Orders Reconciled", str(reconciled_n) + " / " + str(len(df)))
c2.metric("Flagged",           str(flagged_n))
c3.metric("Received in Bank",  "$" + f"{total_in_bank:,.2f}")
audit_errors = sum(1 for f in audit_findings if f["severity"] == "ERROR")
audit_label  = str(len(audit_findings)) + " finding" + ("s" if len(audit_findings) != 1 else "")
c4.metric("QA Audit", audit_label,
          delta=(str(audit_errors) + " error" + ("s" if audit_errors != 1 else ""))
                if audit_errors else "Clean",
          delta_color="inverse" if audit_errors else "normal")

st.subheader("Money Flow")
st.table(pd.DataFrame([
    {"Step": "Gross sales (Shopify)",                "Amount": "$"  + f"{total_gross:,.2f}"},
    {"Step": "Less: Stripe fees",                    "Amount": "($" + f"{total_fee:,.2f}" + ")"},
    {"Step": "Less: Refunds",                        "Amount": "($" + f"{total_refund:,.2f}" + ")"},
    {"Step": "Net expected in bank",                 "Amount": "$"  + f"{total_net_post:,.2f}"},
    {"Step": "Less: Missing payouts (not received)", "Amount": "($" + f"{missing_amt:,.2f}" + ")"},
    {"Step": "Actually received in bank",            "Amount": "$"  + f"{total_in_bank:,.2f}"},
]))

# ── AI explanation helper (cached per session) ────────────────────────────────
if "ai_cache" not in st.session_state:
    st.session_state["ai_cache"] = {}

def ai_explain(finding):
    """Return a 1-sentence plain-English explanation. Cached by (check, message)."""
    if not anthropic_key or not _HAS_REQUESTS:
        return None
    key = finding["check"] + "||" + finding["message"]
    cache = st.session_state["ai_cache"]
    if key in cache:
        return cache[key]
    try:
        r = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key":         anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type":      "application/json",
            },
            json={
                "model":      "claude-haiku-4-5-20251001",
                "max_tokens": 120,
                "messages":   [{
                    "role": "user",
                    "content": (
                        "Explain this Stripe/Shopify reconciliation audit finding in "
                        "ONE plain-English sentence a small business owner (no accounting "
                        "background) can act on. No jargon, no preamble.\n\n"
                        f"Finding type: {finding['check']}\n"
                        f"Detail: {finding['message']}"
                    ),
                }],
            },
            timeout=15,
        )
        r.raise_for_status()
        text = r.json()["content"][0]["text"].strip()
        cache[key] = text
        return text
    except Exception as e:
        return f"(AI explanation unavailable: {e})"

# ── QA Audit ──────────────────────────────────────────────────────────────────
st.header("QA Audit")
if anthropic_key:
    st.caption("AI explanations enabled — one plain-English sentence per finding.")
if not audit_findings:
    st.success("All checks passed. Every reconciled match verified to the cent. "
               "No orphan payouts. No deposit remainders.")
else:
    errors   = [f for f in audit_findings if f["severity"] == "ERROR"]
    warnings = [f for f in audit_findings if f["severity"] == "WARNING"]
    if errors:
        st.subheader(str(len(errors)) + " Error" + ("s" if len(errors) != 1 else ""))
        for f in errors:
            orders_str  = ", ".join(f["orders"]) if f["orders"] else "N/A"
            explanation = ai_explain(f)
            body = ("[" + f["check"] + "]  " + f["message"] + "\n\n"
                    "Affected orders: " + orders_str + "\nStatus overridden to NEEDS REVIEW.")
            if explanation:
                body += "\n\n💡 " + explanation
            st.error(body)
    if warnings:
        st.subheader(str(len(warnings)) + " Warning" + ("s" if len(warnings) != 1 else ""))
        for f in warnings:
            orders_str  = ", ".join(f["orders"]) if f["orders"] else ""
            explanation = ai_explain(f)
            body = "[" + f["check"] + "]  " + f["message"]
            if orders_str:
                body += "\n\nAffected orders: " + orders_str
            if explanation:
                body += "\n\n💡 " + explanation
            st.warning(body)
    passed = [c for c in ["SUM MISMATCH", "DEPOSIT REMAINDER", "ORPHAN PAYOUT"]
              if not any(f["check"] == c for f in audit_findings)]
    if passed:
        st.success("Passed: " + ", ".join(passed))

# ── Requires Attention ────────────────────────────────────────────────────────
st.header("Requires Attention")

for _, row in df[df["status"] == "NEEDS REVIEW"].iterrows():
    st.error("NEEDS REVIEW: " + row["order"] + " (" + row["item"] + ")\n\n"
             "QA Auditor flagged an arithmetic error. See QA Audit section above.")

for _, row in df[df["status"] == "MISSING BANK DEPOSIT"].iterrows():
    st.error("URGENT - Missing Bank Deposit: " + row["order"] + " (" + row["item"] + ")\n\n"
             "Net payout of $" + f"{row['net']:.2f}" + " was collected by Stripe but "
             "does NOT appear in any bank deposit.")

for _, row in df[df["status"] == "MISSING IN STRIPE"].iterrows():
    st.error("No Stripe Payout: " + row["order"] + " (" + row["item"] + ")\n\n"
             "Shopify shows $" + f"{row['gross']:.2f}" + " paid but no Stripe payout found.")

for _, row in df[df["status"] == "DUPLICATE CHARGE"].iterrows():
    detail = duplicate_detail.get(row["order"], [])
    lines  = "\n".join("  - " + d["payout_id"] + "  net=$" + f"{d['net']:.2f}" +
                       "  bank=" + d["bank_deposit"]
                       for d in detail)
    st.warning("DUPLICATE CHARGE: " + row["order"] + " (" + row["item"] + ")\n\n"
               "Stripe has " + str(len(detail)) + " separate payouts for this order. "
               "The customer may have been billed twice.\n\n" + lines)

for _, row in df[df["status"] == "SPLIT RECONCILED"].iterrows():
    st.info("Split Payout: " + row["order"] + " (" + row["item"] + ")\n\n"
            "Net of $" + f"{row['net']:.2f}" + " split across: " +
            str(row["bank_deposit"]) + ". Totals match to the cent.")

for _, row in df[df["status"] == "RECONCILED (chargeback issued)"].iterrows():
    cb = row.get("chargeback")
    st.warning("Chargeback: " + row["order"] + " (" + row["item"] + ") - $" +
               (f"{abs(cb):.2f}" if pd.notna(cb) else "?") +
               " chargeback issued. Confirm dispute resolution.")

for label, amt in unexplained:
    st.error("UNEXPLAINED DEPOSIT: " + label + " $" + f"{amt:.2f}" +
             " — no matching payout combination found. Investigate manually.")

st.info("Stripe fees $" + f"{total_fee:.2f}" + " across " + str(len(df)) +
        " orders. Normal and expected.")

# ── All Orders ────────────────────────────────────────────────────────────────
st.header("All Orders")
display = df[["order", "item", "gross", "fee", "net", "bank_deposit", "status"]].copy()
display.columns = ["Order", "Item", "Gross", "Fee", "Net", "Bank Deposit", "Status"]
for col in ["Gross", "Fee", "Net"]:
    display[col] = display[col].apply(lambda x: "$" + f"{x:.2f}" if pd.notna(x) else "-")
display["Bank Deposit"] = display["Bank Deposit"].fillna("-")

def highlight(row):
    s = str(row["Status"])
    if "NEEDS REVIEW" in s:
        return ["background-color:#e8d5f5; color:#5a0080; font-weight:bold"] * len(row)
    if "MISSING" in s:
        return ["background-color:#ffcccc; color:#900; font-weight:bold"] * len(row)
    if "DUPLICATE" in s:
        return ["background-color:#ffe0b2; color:#7a3800; font-weight:bold"] * len(row)
    if "SPLIT" in s:
        return ["background-color:#fff3cd"] * len(row)
    return [""] * len(row)

st.dataframe(display.style.apply(highlight, axis=1),
             use_container_width=True, hide_index=True)

# ── Snapshot History ──────────────────────────────────────────────────────────
st.header("Run History")
snap_files = sorted(
    [f for f in os.listdir(SNAPSHOT_DIR) if f.endswith(".json")],
    reverse=True,
)
if not snap_files:
    st.caption("No snapshots saved yet. Click 'Save Snapshot' above to start tracking history.")
else:
    history_rows = []
    for fname in snap_files:
        try:
            with open(os.path.join(SNAPSHOT_DIR, fname)) as fp:
                s = json.load(fp)
            orders      = s.get("orders", [])
            rec_n       = sum(1 for o in orders if str(o.get("status","")).startswith("RECONCILED"))
            flag_n      = len(orders) - rec_n
            hs          = s.get("health_score", "-")
            hs_display  = str(hs) + "/100" if isinstance(hs, int) else hs
            history_rows.append({
                "Date":        s.get("date", fname),
                "Source":      s.get("source", "-"),
                "Health":      hs_display,
                "Reconciled":  str(rec_n) + "/" + str(len(orders)),
                "Flagged":     flag_n,
                "Gross":       "$" + f"{s.get('summary',{}).get('gross', 0):,.2f}",
                "In Bank":     "$" + f"{s.get('summary',{}).get('in_bank', 0):,.2f}",
            })
        except Exception:
            pass

    def highlight_history(row):
        hs_raw = str(row.get("Health", "")).replace("/100", "")
        try:
            hs = int(hs_raw)
        except ValueError:
            return [""] * len(row)
        if hs >= 90:
            color = "background-color:#e6f4e6"
        elif hs >= 70:
            color = "background-color:#fff8e1"
        elif hs >= 50:
            color = "background-color:#fff0e0"
        else:
            color = "background-color:#ffe0e0"
        return [color] * len(row)

    hist_df = pd.DataFrame(history_rows)
    st.dataframe(hist_df.style.apply(highlight_history, axis=1),
                 use_container_width=True, hide_index=True)
    st.caption(f"{len(snap_files)} snapshot(s) stored in `{SNAPSHOT_DIR}`")
