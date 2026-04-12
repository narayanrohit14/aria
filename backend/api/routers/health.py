import json
import os
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db
from backend.api.schemas.schemas import HealthResponse, ModelMetrics


router = APIRouter(prefix="")
ARTIFACTS_DIR = Path(__file__).resolve().parents[3] / "ml" / "artifacts"
EVALUATION_REPORT_PATH = ARTIFACTS_DIR / "evaluation_report.json"
THRESHOLD_PATH = ARTIFACTS_DIR / "optimal_threshold.json"
MODEL_PATH = ARTIFACTS_DIR / "fraud_classifier.pkl"


def _load_model_metrics() -> ModelMetrics | None:
    if not EVALUATION_REPORT_PATH.exists():
        return None

    try:
        metrics = json.loads(EVALUATION_REPORT_PATH.read_text(encoding="utf-8"))
        threshold = 0.35
        if THRESHOLD_PATH.exists():
            threshold = float(json.loads(THRESHOLD_PATH.read_text(encoding="utf-8"))["threshold"])

        return ModelMetrics(
            cv_f1_mean=float(metrics["cv_f1_mean"]),
            cv_precision_mean=float(metrics["cv_precision_mean"]),
            cv_recall_mean=float(metrics["cv_recall_mean"]),
            cv_roc_auc_mean=float(metrics["cv_roc_auc_mean"]),
            n_samples=int(metrics["n_samples"]),
            n_fraud_cases=int(metrics["n_fraud_cases"]),
            optimal_threshold=threshold,
        )
    except Exception:
        return None


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    database_connected = False
    try:
        await db.execute(text("SELECT 1"))
        database_connected = True
    except Exception:
        database_connected = False

    model_metrics = _load_model_metrics()
    model_loaded = MODEL_PATH.exists()
    status = "ok" if database_connected and model_loaded else "degraded"

    return HealthResponse(
        status=status,
        version="0.1.0",
        environment=os.getenv("ARIA_ENV", "development"),
        model_loaded=model_loaded,
        database_connected=database_connected,
        model_metrics=model_metrics,
    )


@router.get("/api/v1/status")
async def status(request: Request) -> dict:
    started_at = getattr(request.app.state, "started_at", datetime.utcnow())
    now = datetime.utcnow()
    uptime_seconds = int((now - started_at).total_seconds())
    return {
        "status": "ok",
        "environment": os.getenv("ARIA_ENV", "development"),
        "started_at": started_at.isoformat(),
        "uptime_seconds": uptime_seconds,
    }
