import json
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db
from backend.api.models.db import TransactionAnalysis
from backend.api.schemas.schemas import AnalysisResponse, TransactionFeatures
from backend.data.aria_data_ingestion import load_audit_context
from ml.models.fraud_classifier import load_fraud_classifier, predict_fraud


router = APIRouter(prefix="/api/v1/analyze", tags=["analyze"])


@lru_cache(maxsize=1)
def _cached_audit_context():
    return load_audit_context()


@router.post("/transaction", response_model=AnalysisResponse)
async def analyze_transaction(
    features: TransactionFeatures,
    db: AsyncSession = Depends(get_db),
) -> AnalysisResponse:
    try:
        model, threshold = load_fraud_classifier()
        result = predict_fraud(model, threshold, features.model_dump())
    except FileNotFoundError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
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


@router.get("/portfolio/summary")
async def portfolio_summary() -> dict:
    try:
        return _cached_audit_context()
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load portfolio summary: {exc}") from exc
