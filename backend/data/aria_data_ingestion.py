"""
ARIA Data Ingestion Layer
Loads and preprocesses sample-data/ files into audit-ready summaries.

Verified schemas (from actual uploaded files):
  cards_data.csv  — id, client_id, card_brand, card_type, card_number,
                    expires, cvv, has_chip, num_cards_issued, credit_limit,
                    acct_open_date, year_pin_last_changed, card_on_dark_web
  users_data.csv  — id, current_age, retirement_age, birth_year, birth_month,
                    gender, address, latitude, longitude, per_capita_income,
                    yearly_income, total_debt, credit_score, num_credit_cards
  mcc_codes.json  — { "mcc_code": "description", ... }  (flat string values)
  transactions_data.csv — (schema inferred at runtime; common fields tried)
  train_fraud_labels.json — { "target": { "transaction_id": "Yes"|"No", ... } }
"""

import os
import json
import csv
from datetime import datetime
from collections import defaultdict, Counter

# ─────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────
BASE_DIR   = os.path.join(os.path.dirname(__file__), "sample-data")
TX_FILE    = os.path.join(BASE_DIR, "transactions_data.csv")
CARDS_FILE = os.path.join(BASE_DIR, "cards_data.csv")
MCC_FILE   = os.path.join(BASE_DIR, "mcc_codes.json")
FRAUD_FILE = os.path.join(BASE_DIR, "train_fraud_labels.json")
USERS_FILE = os.path.join(BASE_DIR, "users_data.csv")

MAX_TX_ROWS = 15_000   # cap for transactions only; cards/users loaded fully


# ─────────────────────────────────────────────
# LOADERS
# ─────────────────────────────────────────────

def _load_csv(path: str, max_rows: int = 999_999) -> list[dict]:
    rows = []
    try:
        with open(path, newline="", encoding="utf-8") as f:
            for i, row in enumerate(csv.DictReader(f)):
                if i >= max_rows:
                    break
                rows.append(row)
    except FileNotFoundError:
        print(f"[ARIA] ⚠️  Not found: {path}")
    return rows


def _load_json(path: str):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"[ARIA] ⚠️  Not found: {path}")
        return {}


# ─────────────────────────────────────────────
# CARD ANALYSIS  (verified schema)
# ─────────────────────────────────────────────

def analyze_cards(cards: list[dict]) -> dict:
    if not cards:
        return {"error": "No card data loaded"}

    total      = len(cards)
    brands     = Counter()
    card_types = Counter()
    limits     = []
    expired    = 0
    no_chip    = 0
    dark_web   = 0
    pin_old    = 0
    zero_limit = 0
    today      = datetime.today()

    for c in cards:
        brands[c.get("card_brand", "Unknown")] += 1
        card_types[c.get("card_type", "Unknown")] += 1

        # Credit limit — format: $24295
        raw = c.get("credit_limit", "0").replace("$", "").replace(",", "")
        try:
            lim = float(raw)
            limits.append(lim)
            if lim == 0:
                zero_limit += 1
        except ValueError:
            pass

        # Expiry — format: 12/2022
        exp = c.get("expires", "")
        if exp and "/" in exp:
            try:
                m, y = exp.split("/")
                if datetime(int(y), int(m), 1) < today:
                    expired += 1
            except Exception:
                pass

        # EMV chip — "YES" / "NO"
        if c.get("has_chip", "YES").upper() == "NO":
            no_chip += 1

        # Dark web — "No" / "Yes"
        if c.get("card_on_dark_web", "No").lower() in ("yes", "true", "1"):
            dark_web += 1

        # PIN staleness — flag if not changed in 5+ years
        try:
            if today.year - int(c.get("year_pin_last_changed", today.year)) >= 5:
                pin_old += 1
        except (ValueError, TypeError):
            pass

    avg_limit    = round(sum(limits) / len(limits), 2) if limits else 0
    max_limit    = round(max(limits), 2)                if limits else 0
    expired_pct  = round(expired  / total * 100, 1)
    no_chip_pct  = round(no_chip  / total * 100, 1)
    pin_old_pct  = round(pin_old  / total * 100, 1)

    findings = []
    if expired_pct > 50:
        findings.append(
            f"HIGH: {expired_pct}% of cards ({expired:,}) are past expiry — stale account "
            "management elevates fraud exposure and data integrity risk."
        )
    if no_chip_pct > 5:
        findings.append(
            f"MEDIUM: {no_chip_pct}% of cards ({no_chip:,}) lack EMV chip technology — "
            "legacy magstripe cards carry significantly higher counterfeit fraud risk."
        )
    if dark_web > 0:
        findings.append(
            f"HIGH: {dark_web:,} card(s) detected on dark web marketplaces — "
            "immediate investigation and proactive card replacement warranted."
        )
    if pin_old_pct > 30:
        findings.append(
            f"MEDIUM: {pin_old_pct}% of cards ({pin_old:,}) have PINs unchanged for 5+ years — "
            "weak credential hygiene increases account takeover risk."
        )
    if zero_limit > 0:
        findings.append(
            f"LOW: {zero_limit:,} card(s) carry a $0 credit limit — "
            "review for data integrity issues or misconfigured account settings."
        )

    return {
        "total_cards":             total,
        "card_brand_distribution": dict(brands),
        "card_type_distribution":  dict(card_types),
        "average_credit_limit":    avg_limit,
        "max_credit_limit":        max_limit,
        "expired_cards":           expired,
        "expired_pct":             expired_pct,
        "no_chip_cards":           no_chip,
        "no_chip_pct":             no_chip_pct,
        "dark_web_exposed":        dark_web,
        "pin_stale_cards":         pin_old,
        "pin_stale_pct":           pin_old_pct,
        "zero_limit_cards":        zero_limit,
        "audit_findings":          findings,
    }


# ─────────────────────────────────────────────
# USER / CUSTOMER ANALYSIS  (verified schema)
# ─────────────────────────────────────────────

def analyze_users(users: list[dict]) -> dict:
    if not users:
        return {"error": "No user data loaded"}

    total       = len(users)
    incomes     = []
    debts       = []
    scores      = []
    ages        = []
    genders     = Counter()
    high_debt   = 0
    low_score   = 0
    near_retire = 0

    for u in users:
        genders[u.get("gender", "Unknown")] += 1

        # Monetary fields — format: $59696
        for field, lst in [("yearly_income", incomes), ("total_debt", debts)]:
            raw = u.get(field, "0").replace("$", "").replace(",", "")
            try:
                lst.append(float(raw))
            except ValueError:
                pass

        try:
            score = int(u.get("credit_score", 0))
            scores.append(score)
            if score < 580:
                low_score += 1
        except ValueError:
            pass

        try:
            age = int(u.get("current_age", 0))
            ages.append(age)
        except ValueError:
            pass

        try:
            ret = int(u.get("retirement_age", 999))
            cur = int(u.get("current_age", 0))
            if 0 < ret - cur <= 5:
                near_retire += 1
        except (ValueError, TypeError):
            pass

        debt_raw = u.get("total_debt", "0").replace("$", "").replace(",", "")
        try:
            if float(debt_raw) > 100_000:
                high_debt += 1
        except ValueError:
            pass

    avg_income = round(sum(incomes) / len(incomes), 2) if incomes else 0
    avg_debt   = round(sum(debts)   / len(debts),   2) if debts   else 0
    avg_score  = round(sum(scores)  / len(scores),   0) if scores  else 0
    dti        = round(avg_debt / avg_income * 100,  1) if avg_income else 0

    score_bands = {
        "Poor (<580)":           sum(1 for s in scores if s < 580),
        "Fair (580-669)":        sum(1 for s in scores if 580 <= s < 670),
        "Good (670-739)":        sum(1 for s in scores if 670 <= s < 740),
        "Very Good (740-799)":   sum(1 for s in scores if 740 <= s < 800),
        "Exceptional (800+)":    sum(1 for s in scores if s >= 800),
    }

    findings = []
    if dti > 100:
        findings.append(
            f"HIGH: Portfolio average debt-to-income ratio is {dti}% — "
            "significantly elevated; indicates systemic credit risk across the customer base."
        )
    if low_score > total * 0.10:
        findings.append(
            f"MEDIUM: {low_score:,} customers ({round(low_score/total*100,1)}%) carry poor "
            "credit scores below 580 — elevated default and delinquency risk."
        )
    if high_debt > total * 0.15:
        findings.append(
            f"MEDIUM: {high_debt:,} customers ({round(high_debt/total*100,1)}%) carry debt "
            "exceeding $100,000 — concentration risk within high-debt segment."
        )

    return {
        "total_customers":           total,
        "gender_distribution":       dict(genders),
        "average_yearly_income":     avg_income,
        "average_total_debt":        avg_debt,
        "average_credit_score":      avg_score,
        "debt_to_income_ratio_pct":  dti,
        "credit_score_bands":        score_bands,
        "high_debt_customers":       high_debt,
        "high_debt_pct":             round(high_debt  / total * 100, 1),
        "poor_credit_customers":     low_score,
        "near_retirement_customers": near_retire,
        "age_range":                 f"{min(ages)} – {max(ages)}" if ages else "N/A",
        "average_age":               round(sum(ages) / len(ages), 0) if ages else 0,
        "audit_findings":            findings,
    }


# ─────────────────────────────────────────────
# TRANSACTION ANALYSIS
# ─────────────────────────────────────────────

def _get(row: dict, *keys) -> str:
    for k in keys:
        if k in row and str(row[k]).strip():
            return str(row[k]).strip()
    return ""


def analyze_transactions(transactions: list[dict], fraud_labels: dict) -> dict:
    if not transactions:
        return {
            "total_transactions": 0,
            "note": "transactions_data.csv not found — card and user analysis still available.",
            "risk_level":   "UNKNOWN",
            "risk_score":   0,
            "audit_findings": [],
            "top_mcc_codes":  [],
            "top_error_types": [],
        }

    total       = len(transactions)
    amounts     = []
    failed      = 0
    fraud_count = 0
    mcc_freq    = defaultdict(int)
    error_types = defaultdict(int)

    for tx in transactions:
        tx_id  = _get(tx, "id", "transaction_id", "ID")
        amount = _get(tx, "amount", "Amount", "transaction_amount")
        errors = _get(tx, "errors", "Errors", "error", "Error")

        try:
            amounts.append(abs(float(amount.replace("$", "").replace(",", ""))))
        except ValueError:
            pass

        if errors and errors.lower() not in ("none", "nan", ""):
            failed += 1
            error_types[errors] += 1

        if str(tx_id) in fraud_labels:
            if str(fraud_labels[str(tx_id)]).strip() == "Yes":
                fraud_count += 1

        mcc = _get(tx, "mcc", "MCC", "merchant_category_code")
        if mcc:
            mcc_freq[mcc] += 1

    avg_amount   = round(sum(amounts) / len(amounts), 2) if amounts else 0
    max_amount   = round(max(amounts), 2)                if amounts else 0
    failure_rate = round(failed      / total * 100, 2)
    fraud_rate   = round(fraud_count / total * 100, 2)

    top_mccs   = sorted(mcc_freq.items(),    key=lambda x: x[1], reverse=True)[:6]
    top_errors = sorted(error_types.items(), key=lambda x: x[1], reverse=True)[:5]

    score = 0
    if fraud_rate   > 5:   score += 45
    elif fraud_rate > 2:   score += 25
    if failure_rate > 10:  score += 30
    elif failure_rate > 5: score += 15
    if avg_amount   > 5000: score += 15

    risk_level = "HIGH" if score >= 55 else "MEDIUM" if score >= 25 else "LOW"

    findings = []
    if fraud_rate > 2:
        findings.append(
            f"HIGH: {fraud_count:,} transactions ({fraud_rate}%) flagged as fraudulent — "
            "transaction monitoring controls require immediate review."
        )
    if failure_rate > 5:
        findings.append(
            f"MEDIUM: {failed:,} transactions ({failure_rate}%) contain processing errors — "
            "review exception handling and upstream data validation controls."
        )
    for err, cnt in top_errors[:3]:
        findings.append(
            f"OBSERVATION: '{err}' error type recorded {cnt:,} times in the transaction population."
        )

    return {
        "total_transactions":         total,
        "average_transaction_amount": avg_amount,
        "max_transaction_amount":     max_amount,
        "failed_transactions":        failed,
        "failure_rate_pct":           failure_rate,
        "flagged_fraud_count":        fraud_count,
        "fraud_rate_pct":             fraud_rate,
        "top_mcc_codes":              top_mccs,
        "top_error_types":            top_errors,
        "risk_score":                 score,
        "risk_level":                 risk_level,
        "audit_findings":             findings,
    }


# ─────────────────────────────────────────────
# MCC ENRICHMENT  (exact format: flat string values)
# ─────────────────────────────────────────────

def enrich_mcc(mcc_codes: dict, top_mccs: list[tuple]) -> list[dict]:
    enriched = []
    for code, count in top_mccs:
        desc = mcc_codes.get(str(code), f"MCC {code}")
        enriched.append({"mcc": code, "description": desc, "count": count})
    return enriched


# ─────────────────────────────────────────────
# MASTER LOADER
# ─────────────────────────────────────────────

_cache: dict = {}


def load_audit_context() -> dict:
    global _cache
    if _cache:
        return _cache

    print("[ARIA] Loading audit datasets…")

    transactions = _load_csv(TX_FILE, MAX_TX_ROWS)
    cards        = _load_csv(CARDS_FILE)
    users        = _load_csv(USERS_FILE)
    mcc_codes    = _load_json(MCC_FILE)
    raw = _load_json(FRAUD_FILE)
    fraud_labels = raw.get("target", raw) if isinstance(raw, dict) else {}

    tx_summary   = analyze_transactions(transactions, fraud_labels)
    card_summary = analyze_cards(cards)
    user_summary = analyze_users(users)
    enriched_mcc = enrich_mcc(mcc_codes, tx_summary.get("top_mcc_codes", []))

    # Composite risk across all three data dimensions
    risk_inputs = [tx_summary.get("risk_score", 0)]
    if card_summary.get("dark_web_exposed", 0) > 0:
        risk_inputs.append(60)
    if card_summary.get("expired_pct", 0) > 80:
        risk_inputs.append(40)
    if user_summary.get("debt_to_income_ratio_pct", 0) > 100:
        risk_inputs.append(35)

    composite    = round(sum(risk_inputs) / len(risk_inputs))
    overall_risk = "HIGH" if composite >= 55 else "MEDIUM" if composite >= 25 else "LOW"

    _cache = {
        "loaded_at":               datetime.now().isoformat(),
        "transaction_summary":     tx_summary,
        "card_summary":            card_summary,
        "customer_summary":        user_summary,
        "top_merchant_categories": enriched_mcc,
        "overall_risk_level":      overall_risk,
        "composite_risk_score":    composite,
        "data_coverage": {
            "transactions_loaded": len(transactions),
            "cards_loaded":        len(cards),
            "users_loaded":        len(users),
            "fraud_labels_loaded": len(fraud_labels) if isinstance(fraud_labels, dict) else 0,
            "mcc_codes_loaded":    len(mcc_codes),
        },
    }

    print(
        f"[ARIA] ✅ Ready — {len(cards):,} cards | {len(users):,} customers | "
        f"{len(transactions):,} transactions | Overall Risk: {overall_risk}"
    )
    return _cache


# ─────────────────────────────────────────────
# LLM CONTEXT STRING
# ─────────────────────────────────────────────

def format_context_for_llm(ctx: dict) -> str:
    tx   = ctx.get("transaction_summary",  {})
    cd   = ctx.get("card_summary",         {})
    usr  = ctx.get("customer_summary",     {})
    cov  = ctx.get("data_coverage",        {})
    risk = ctx.get("overall_risk_level",   "UNKNOWN")
    comp = ctx.get("composite_risk_score", 0)

    mcc_lines = "\n".join(
        f"  [{m['mcc']}] {m['description']}: {m['count']:,} transactions"
        for m in ctx.get("top_merchant_categories", [])
    ) or "  N/A"

    all_findings = (
        tx.get("audit_findings",  []) +
        cd.get("audit_findings",  []) +
        usr.get("audit_findings", [])
    )
    findings_str = "\n".join(f"  • {f}" for f in all_findings) or "  None identified"

    brands    = cd.get("card_brand_distribution", {})
    card_types = cd.get("card_type_distribution", {})
    bands      = usr.get("credit_score_bands", {})

    tx_note = ""
    if tx.get("total_transactions", 0) == 0:
        tx_note = "\n  ⚠️  transactions_data.csv not found — card and customer analysis available."

    return f"""
╔══════════════════════════════════════════════════════════════
║  ARIA AUDIT DATA CONTEXT
║  {cov.get('transactions_loaded',0):,} transactions | {cov.get('cards_loaded',0):,} cards | {cov.get('users_loaded',0):,} customers
║  Overall Portfolio Risk: {risk}  (composite score: {comp}/100)
╠══════════════════════════════════════════════════════════════

── TRANSACTION POPULATION ──────────────────────────────────{tx_note}
  Total transactions:          {tx.get('total_transactions', 'N/A'):,}
  Avg transaction amount:      ${tx.get('average_transaction_amount', 0):,.2f}
  Max single transaction:      ${tx.get('max_transaction_amount', 0):,.2f}
  Failed / error transactions: {tx.get('failed_transactions', 0):,}  ({tx.get('failure_rate_pct', 0)}%)
  Flagged as fraudulent:       {tx.get('flagged_fraud_count', 0):,}  ({tx.get('fraud_rate_pct', 0)}%)
  Transaction risk score:      {tx.get('risk_score', 0)}/100  →  {tx.get('risk_level', 'N/A')}

  Top Merchant Categories:
{mcc_lines}

── CARD PORTFOLIO  ({cov.get('cards_loaded',0):,} cards total) ───────────────────
  Card brands:      Visa {brands.get('Visa',0):,} | Mastercard {brands.get('Mastercard',0):,} | Amex {brands.get('Amex',0):,} | Discover {brands.get('Discover',0):,}
  Card types:       Credit {card_types.get('Credit',0):,} | Debit {card_types.get('Debit',0):,} | Prepaid {card_types.get('Debit (Prepaid)',0):,}
  Avg credit limit: ${cd.get('average_credit_limit', 0):,.2f}
  Max credit limit: ${cd.get('max_credit_limit', 0):,.2f}
  Expired cards:    {cd.get('expired_cards', 0):,}  ({cd.get('expired_pct', 0)}%)  ← CONTROL RISK
  No EMV chip:      {cd.get('no_chip_cards', 0):,}  ({cd.get('no_chip_pct', 0)}%)  ← FRAUD EXPOSURE
  Dark web exposed: {cd.get('dark_web_exposed', 0):,}
  Stale PINs (5y+): {cd.get('pin_stale_cards', 0):,}  ({cd.get('pin_stale_pct', 0)}%)

── CUSTOMER BASE  ({cov.get('users_loaded',0):,} customers) ──────────────────────
  Avg yearly income:      ${usr.get('average_yearly_income', 0):,.2f}
  Avg total debt:         ${usr.get('average_total_debt', 0):,.2f}
  Debt-to-income ratio:   {usr.get('debt_to_income_ratio_pct', 0)}%  ← CREDIT RISK
  Avg credit score:       {usr.get('average_credit_score', 0):.0f}
  High-debt (>$100K):     {usr.get('high_debt_customers', 0):,}  ({usr.get('high_debt_pct', 0)}%)
  Poor credit (<580):     {usr.get('poor_credit_customers', 0):,}
  Age range:              {usr.get('age_range', 'N/A')}  (avg {usr.get('average_age', 0):.0f})
  Credit score bands:
    Poor (<580):          {bands.get('Poor (<580)', 0):,}
    Fair (580-669):       {bands.get('Fair (580-669)', 0):,}
    Good (670-739):       {bands.get('Good (670-739)', 0):,}
    Very Good (740-799):  {bands.get('Very Good (740-799)', 0):,}
    Exceptional (800+):   {bands.get('Exceptional (800+)', 0):,}

── PRE-COMPUTED AUDIT FINDINGS ─────────────────────────────
{findings_str}

╚══════════════════════════════════════════════════════════════
""".strip()
