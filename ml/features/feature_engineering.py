from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd


DATA_DIR = Path(__file__).resolve().parents[2] / "backend" / "data" / "sample-data"
CURRENT_YEAR = pd.Timestamp.now().year
ONLINE_MCC_KEYWORDS = {
    "digital",
    "online",
    "software",
    "computer",
    "telecom",
    "cable",
    "network",
    "internet",
    "stream",
    "mail",
}


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _clean_money(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .replace({"nan": np.nan, "None": np.nan, "": np.nan})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _find_transaction_id_column(frame: pd.DataFrame) -> str:
    for candidate in ("id", "transaction_id"):
        if candidate in frame.columns:
            return candidate
    raise KeyError("Transaction data must contain an id or transaction_id column.")


def _resolve_user_join_column(transactions: pd.DataFrame, users: pd.DataFrame) -> str:
    if "client_id" in transactions.columns and "id" in users.columns:
        return "client_id"
    if "user_id" in transactions.columns and "id" in users.columns:
        return "user_id"
    raise KeyError("Unable to determine a join key between transactions and users.")


def _build_online_mcc_set(mcc_lookup: dict) -> set[int]:
    online_codes: set[int] = set()
    for code, description in mcc_lookup.items():
        text = str(description).lower()
        if any(keyword in text for keyword in ONLINE_MCC_KEYWORDS):
            try:
                online_codes.add(int(code))
            except ValueError:
                continue
    return online_codes


def _ensure_exists(path: Path) -> Path:
    if not path.exists():
        raise FileNotFoundError(f"Required dataset file not found: {path}")
    return path


def build_feature_matrix() -> tuple[pd.DataFrame, pd.Series]:
    transactions_path = _ensure_exists(DATA_DIR / "transactions_data.csv")
    cards_path = _ensure_exists(DATA_DIR / "cards_data.csv")
    users_path = _ensure_exists(DATA_DIR / "users_data.csv")
    mcc_path = _ensure_exists(DATA_DIR / "mcc_codes.json")
    labels_path = _ensure_exists(DATA_DIR / "train_fraud_labels.json")

    transactions = pd.read_csv(transactions_path, nrows=500_000)
    cards = pd.read_csv(cards_path)
    users = pd.read_csv(users_path)
    mcc_lookup = _load_json(mcc_path)
    raw_labels = _load_json(labels_path)

    transaction_id_col = _find_transaction_id_column(transactions)
    transactions = transactions.drop_duplicates(subset=[transaction_id_col]).copy()

    money_columns = []
    for frame in (transactions, cards, users):
        for column in frame.columns:
            if frame[column].dtype == object:
                sample = frame[column].dropna().astype(str).head(20)
                if sample.str.contains(r"[$,]").any():
                    money_columns.append((frame, column))

    for frame, column in money_columns:
        frame[column] = _clean_money(frame[column])

    if "expires" in cards.columns:
        cards["expires"] = pd.to_datetime(cards["expires"], format="%m/%Y", errors="coerce")
    if "acct_open_date" in cards.columns:
        cards["acct_open_date"] = pd.to_datetime(
            cards["acct_open_date"], format="%m/%Y", errors="coerce"
        )

    transaction_time_col = "timestamp" if "timestamp" in transactions.columns else "date"
    if transaction_time_col in transactions.columns:
        transactions[transaction_time_col] = pd.to_datetime(
            transactions[transaction_time_col], errors="coerce"
        )
        transactions["hour_of_day"] = transactions[transaction_time_col].dt.hour.fillna(12).astype(int)
    else:
        transactions["hour_of_day"] = 12

    online_mcc_codes = _build_online_mcc_set(mcc_lookup)
    transactions["amount"] = _clean_money(transactions["amount"])
    transactions["mcc_code"] = pd.to_numeric(
        transactions["mcc"] if "mcc" in transactions.columns else transactions.get("mcc_code"),
        errors="coerce",
    )
    transactions["is_online"] = transactions["mcc_code"].isin(online_mcc_codes).astype(int)

    card_columns = {
        "id": "card_id_lookup",
        "client_id": "card_client_id",
        "credit_limit": "credit_limit",
        "has_chip": "has_chip",
        "acct_open_date": "acct_open_date",
        "year_pin_last_changed": "year_pin_last_changed",
        "card_type": "card_type",
    }
    cards_for_id = cards[list(card_columns.keys())].rename(columns=card_columns)
    merged = transactions.merge(
        cards_for_id,
        how="left",
        left_on="card_id",
        right_on="card_id_lookup",
    )

    cards_by_client = (
        cards.assign(
            has_chip_binary=cards["has_chip"].astype(str).str.upper().eq("YES").astype(float),
            is_prepaid_binary=cards["card_type"].astype(str).str.contains("prepaid", case=False, na=False).astype(float),
            acct_open_year=cards["acct_open_date"].dt.year,
        )
        .groupby("client_id", as_index=False)
        .agg(
            credit_limit_client=("credit_limit", "median"),
            has_chip_client=("has_chip_binary", "max"),
            acct_open_year_client=("acct_open_year", "min"),
            year_pin_last_changed_client=("year_pin_last_changed", "median"),
            is_prepaid_client=("is_prepaid_binary", "max"),
        )
    )
    merged = merged.merge(cards_by_client, how="left", on="client_id")

    merged["credit_limit"] = merged["credit_limit"].fillna(merged["credit_limit_client"])
    merged["has_chip"] = (
        merged["has_chip"].astype(str).str.upper().eq("YES").astype(float).where(merged["has_chip"].notna())
    )
    merged["has_chip"] = merged["has_chip"].fillna(merged["has_chip_client"]).fillna(0).astype(int)
    merged["card_age_years"] = (
        CURRENT_YEAR - merged["acct_open_date"].dt.year.fillna(merged["acct_open_year_client"])
    ).clip(lower=0)
    merged["pin_staleness"] = (
        CURRENT_YEAR - merged["year_pin_last_changed"].fillna(merged["year_pin_last_changed_client"])
    ).clip(lower=0)
    merged["is_prepaid"] = (
        merged["card_type"].astype(str).str.contains("prepaid", case=False, na=False).astype(float)
    )
    merged["is_prepaid"] = merged["is_prepaid"].fillna(merged["is_prepaid_client"]).fillna(0).astype(int)
    merged["amount_to_limit_ratio"] = (
        merged["amount"] / merged["credit_limit"].replace({0: np.nan})
    ).clip(upper=5.0)

    user_join_col = _resolve_user_join_column(transactions, users)
    users_for_join = users.rename(columns={"id": user_join_col})
    merged = merged.merge(
        users_for_join[[user_join_col, "credit_score", "total_debt", "yearly_income", "current_age"]],
        how="left",
        on=user_join_col,
    )
    merged["debt_to_income"] = (
        merged["total_debt"] / merged["yearly_income"].replace({0: np.nan})
    ).clip(upper=10.0)
    merged["age"] = pd.to_numeric(merged["current_age"], errors="coerce")

    labels = raw_labels.get("target", raw_labels) if isinstance(raw_labels, dict) else {}
    labels = pd.Series(labels, name="fraud_label")
    labels.index = pd.to_numeric(labels.index, errors="coerce")
    labels = labels[labels.index.notna()]
    labels.index = labels.index.astype(np.int64)
    labels = (labels.astype(str).str.strip() == "Yes").astype(int)

    merged["fraud_label"] = merged[transaction_id_col].map(labels)
    merged = merged[merged["fraud_label"].notna()].copy()

    feature_columns = [
        "amount",
        "hour_of_day",
        "is_online",
        "mcc_code",
        "credit_limit",
        "amount_to_limit_ratio",
        "has_chip",
        "card_age_years",
        "pin_staleness",
        "is_prepaid",
        "credit_score",
        "debt_to_income",
        "age",
    ]

    X = merged[feature_columns].copy()
    numeric_columns = X.select_dtypes(include=["number"]).columns
    X[numeric_columns] = X[numeric_columns].apply(pd.to_numeric, errors="coerce")
    X[numeric_columns] = X[numeric_columns].fillna(X[numeric_columns].median())

    X["hour_of_day"] = X["hour_of_day"].round().astype(int)
    X["is_online"] = X["is_online"].round().astype(int)
    X["mcc_code"] = X["mcc_code"].round().astype(int)
    X["has_chip"] = X["has_chip"].round().astype(int)
    X["is_prepaid"] = X["is_prepaid"].round().astype(int)
    X["credit_score"] = X["credit_score"].round().astype(int)
    X["age"] = X["age"].round().astype(int)

    y = merged["fraud_label"].astype(int).reset_index(drop=True)
    X = X.reset_index(drop=True)

    if X.isnull().any().any():
        raise ValueError("Feature matrix still contains null values after cleaning.")

    return X, y


if __name__ == "__main__":
    X, y = build_feature_matrix()
    print(f"X shape: {X.shape}")
    print(f"y shape: {y.shape}")
    print(f"Fraud rate: {y.mean():.4f}")
    print(X.dtypes)
