from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from ml.features.feature_engineering import build_feature_matrix
from ml.models.fraud_classifier import load_fraud_classifier


ARTIFACTS_DIR = Path(__file__).resolve().parents[1] / "artifacts"
METADATA_PATH = ARTIFACTS_DIR / "risk_scorer_metadata.json"


def _clean_money(series: pd.Series) -> pd.Series:
    cleaned = (
        series.astype(str)
        .str.replace("$", "", regex=False)
        .str.replace(",", "", regex=False)
        .replace({"nan": np.nan, "None": np.nan, "": np.nan})
    )
    return pd.to_numeric(cleaned, errors="coerce")


def _categorize_risk(score: pd.Series) -> pd.Series:
    return pd.Series(
        np.where(score >= 65, "HIGH", np.where(score >= 35, "MEDIUM", "LOW")),
        index=score.index,
    )


def _get_fraud_probabilities(X: pd.DataFrame) -> pd.Series:
    if "fraud_probability" in X.columns:
        return pd.to_numeric(X["fraud_probability"], errors="coerce").fillna(0.0).clip(0.0, 1.0)

    try:
        model, _ = load_fraud_classifier()
    except FileNotFoundError:
        return pd.Series(np.zeros(len(X), dtype=float), index=X.index)

    feature_frame = X.copy()
    if hasattr(model, "feature_names_in_"):
        missing = [name for name in model.feature_names_in_ if name not in feature_frame.columns]
        if missing:
            return pd.Series(np.zeros(len(X), dtype=float), index=X.index)
        feature_frame = feature_frame.loc[:, model.feature_names_in_]

    probabilities = model.predict_proba(feature_frame)[:, 1]
    return pd.Series(probabilities, index=X.index).clip(0.0, 1.0)


def compute_transaction_risk_score(X: pd.DataFrame) -> pd.Series:
    X = X.copy()
    fraud_probability = _get_fraud_probabilities(X)
    amount = pd.to_numeric(X["amount"], errors="coerce").fillna(0.0)
    amount_percentile = amount.rank(method="average", pct=True).fillna(0.0)
    amount_to_limit_ratio = pd.to_numeric(X["amount_to_limit_ratio"], errors="coerce").fillna(0.0)
    pin_staleness = pd.to_numeric(X["pin_staleness"], errors="coerce").fillna(0.0)
    has_chip = pd.to_numeric(X["has_chip"], errors="coerce").fillna(1)
    credit_score = pd.to_numeric(X["credit_score"], errors="coerce").fillna(700.0)

    score = (
        fraud_probability * 40.0
        + amount_percentile * 20.0
        + np.minimum(amount_to_limit_ratio / 5.0, 1.0) * 15.0
        + np.minimum(pin_staleness / 10.0, 1.0) * 10.0
        + np.where(has_chip == 0, 10.0, 0.0)
        + np.maximum(0.0, (700.0 - credit_score) / 700.0) * 5.0
    )

    return pd.Series(score, index=X.index, name="risk_score").clip(0.0, 100.0).astype(float)


def compute_customer_risk_score(users_df: pd.DataFrame) -> pd.DataFrame:
    frame = users_df.copy()
    for column in ("total_debt", "yearly_income", "per_capita_income"):
        if column in frame.columns:
            frame[column] = _clean_money(frame[column])

    frame["credit_score"] = pd.to_numeric(frame["credit_score"], errors="coerce").fillna(750.0)
    frame["current_age"] = pd.to_numeric(frame["current_age"], errors="coerce").fillna(0.0)
    frame["retirement_age"] = pd.to_numeric(frame["retirement_age"], errors="coerce").fillna(65.0)
    frame["total_debt"] = pd.to_numeric(frame["total_debt"], errors="coerce").fillna(0.0)
    frame["yearly_income"] = pd.to_numeric(frame["yearly_income"], errors="coerce").replace({0: np.nan})

    debt_to_income = (frame["total_debt"] / frame["yearly_income"]).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    debt_to_income_score = np.minimum(debt_to_income / 2.0, 1.0) * 35.0
    credit_score_component = np.maximum(0.0, (750.0 - frame["credit_score"]) / 750.0) * 30.0
    age_proximity_to_retirement = (
        np.maximum(0.0, 1.0 - (frame["retirement_age"] - frame["current_age"]) / 30.0) * 20.0
    )
    high_debt_flag = np.where(frame["total_debt"] > 100000, 15.0, 0.0)

    risk_score = (
        debt_to_income_score
        + credit_score_component
        + age_proximity_to_retirement
        + high_debt_flag
    ).clip(0.0, 100.0)

    component_frame = pd.DataFrame(
        {
            "Elevated debt-to-income ratio": debt_to_income_score,
            "Lower credit score": credit_score_component,
            "Approaching retirement age": age_proximity_to_retirement,
            "High total debt balance": high_debt_flag,
        },
        index=frame.index,
    )

    def _top_drivers(row: pd.Series) -> str:
        top = row.sort_values(ascending=False)
        top = top[top > 0].head(2)
        if top.empty:
            return "No significant risk drivers identified"
        return "; ".join(top.index.tolist())

    result = pd.DataFrame(
        {
            "user_id": frame["id"] if "id" in frame.columns else frame["user_id"],
            "risk_score": risk_score.astype(float),
            "risk_level": _categorize_risk(pd.Series(risk_score, index=frame.index)).values,
            "risk_drivers": component_frame.apply(_top_drivers, axis=1),
        }
    )
    return result


def save_risk_scorer_metadata(stats: dict):
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    with METADATA_PATH.open("w", encoding="utf-8") as handle:
        json.dump(stats, handle, indent=2)


if __name__ == "__main__":
    X, _ = build_feature_matrix()
    transaction_scores = compute_transaction_risk_score(X)
    risk_levels = _categorize_risk(transaction_scores)

    print(f"Mean risk score: {transaction_scores.mean():.2f}")
    print(f"Min risk score: {transaction_scores.min():.2f}")
    print(f"Max risk score: {transaction_scores.max():.2f}")
    print(f"HIGH risk transactions: {(risk_levels.eq('HIGH').mean() * 100):.2f}%")
    print(f"MEDIUM risk transactions: {(risk_levels.eq('MEDIUM').mean() * 100):.2f}%")
    print(f"LOW risk transactions: {(risk_levels.eq('LOW').mean() * 100):.2f}%")

    save_risk_scorer_metadata(
        {
            "computed_at": datetime.now(timezone.utc).isoformat(),
            "total_scored": int(len(transaction_scores)),
            "mean_score": float(transaction_scores.mean()),
            "pct_high_risk": float(risk_levels.eq("HIGH").mean() * 100),
            "pct_medium_risk": float(risk_levels.eq("MEDIUM").mean() * 100),
            "pct_low_risk": float(risk_levels.eq("LOW").mean() * 100),
        }
    )
