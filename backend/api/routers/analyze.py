import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db
from backend.api.models.db import TransactionAnalysis
from backend.api.routers.data import derive_risk_level
from backend.api.schemas.schemas import AnalysisResponse, TransactionFeatures
import sys
from pathlib import Path

# Add ml/ to path relative to container working directory /app
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "ml"))

from models.fraud_classifier import load_fraud_classifier, predict_fraud

router = APIRouter(prefix="/api/v1/analyze", tags=["analyze"])


def _fallback_predict_fraud(features: TransactionFeatures) -> dict:
    probability = min(
        0.99,
        0.02
        + min(features.amount_to_limit_ratio / 4.0, 0.6)
        + (0.16 if features.has_chip == 0 else 0.0)
        + min(features.pin_staleness / 20.0, 0.15)
        + max(0.0, (650 - features.credit_score) / 1000.0)
        + (0.06 if features.is_online else 0.0),
    )
    threshold = 0.35
    return {
        "fraud_probability": probability,
        "fraud_predicted": probability >= threshold,
        "confidence": "high"
        if probability > 0.75 or probability < 0.15
        else "medium"
        if 0.3 <= probability <= 0.75
        else "low",
        "threshold_used": threshold,
    }


@router.post("/transaction", response_model=AnalysisResponse)
async def analyze_transaction(
    features: TransactionFeatures,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        model, threshold = load_fraud_classifier()
        result = predict_fraud(model, threshold, features.model_dump())
    except FileNotFoundError:
        result = _fallback_predict_fraud(features)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to run fraud model: {exc}") from exc

    fraud_prob = result["fraud_probability"]
    risk_score = min(
        100.0,
        fraud_prob * 40.0
        + min(features.amount_to_limit_ratio / 5.0, 1.0) * 20.0
        + (10.0 if features.has_chip == 0 else 0.0)
        + min(features.pin_staleness / 10.0, 1.0) * 10.0
        + max(0.0, (700.0 - features.credit_score) / 700.0) * 10.0,
    )

    audit_flags: list[str] = []
    if fraud_prob > 0.7:
        audit_flags.append("HIGH FRAUD PROBABILITY")
    if features.amount_to_limit_ratio > 2.0:
        audit_flags.append("EXCEEDS CREDIT LIMIT")
    if features.has_chip == 0:
        audit_flags.append("NO EMV CHIP")
    if features.pin_staleness > 5:
        audit_flags.append("STALE PIN")
    if features.credit_score < 580:
        audit_flags.append("POOR CREDIT SCORE")

    risk_level = "HIGH" if risk_score >= 65 else "MEDIUM" if risk_score >= 35 else "LOW"

    try:
        analysis = TransactionAnalysis(
            fraud_probability=fraud_prob,
            fraud_predicted=result["fraud_predicted"],
            risk_score=risk_score,
            confidence=result["confidence"],
            features_json=json.dumps(features.model_dump()),
        )
        db.add(analysis)
        await db.commit()
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to persist analysis: {exc}") from exc

    return AnalysisResponse(
        fraud_probability=fraud_prob,
        fraud_predicted=result["fraud_predicted"],
        confidence=result["confidence"],
        threshold_used=result["threshold_used"],
        risk_score=risk_score,
        risk_level=risk_level,
        audit_flags=audit_flags,
    )


async def _count(db: AsyncSession, query: str) -> int:
    result = await db.execute(text(query))
    return int(result.scalar() or 0)


@router.get("/portfolio/summary")
async def portfolio_summary(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        users = await _count(db, "SELECT COUNT(*) FROM aria_users")
        cards = await _count(db, "SELECT COUNT(*) FROM aria_cards")
        transactions = await _count(db, "SELECT COUNT(*) FROM aria_transactions")
        mcc_codes = await _count(db, "SELECT COUNT(*) FROM aria_mcc_codes")
        fraud_labels = await _count(db, "SELECT COUNT(*) FROM aria_fraud_labels")
        fraud_cases = await _count(db, "SELECT COUNT(*) FROM aria_fraud_labels WHERE is_fraud IS TRUE")
        fraud_rate = fraud_cases / fraud_labels if fraud_labels else 0.0
        risk_level = derive_risk_level(fraud_rate, fraud_cases, transactions)

        return {
            "overall_risk_level": risk_level,
            "composite_risk_score": 75 if risk_level == "HIGH" else 40 if risk_level == "MEDIUM" else 0,
            "transaction_summary": {
                "total_transactions": transactions,
                "flagged_fraud_count": fraud_cases,
                "fraud_rate_pct": round(fraud_rate * 100, 3),
                "risk_level": risk_level,
            },
            "data_coverage": {
                "transactions_loaded": transactions,
                "cards_loaded": cards,
                "users_loaded": users,
                "fraud_labels_loaded": fraud_labels,
                "mcc_codes_loaded": mcc_codes,
            },
            "seeded_dataset": {
                "users": users,
                "cards": cards,
                "transactions": transactions,
                "mcc_codes": mcc_codes,
                "fraud_labels": fraud_labels,
                "fraud_cases": fraud_cases,
                "fraud_rate": fraud_rate,
                "risk_level": risk_level,
            },
        }
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load portfolio summary: {exc}") from exc
