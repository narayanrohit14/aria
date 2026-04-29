import sys
from pathlib import Path

# Make ml/ importable from the container's /app working directory
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "ml"))

import logging
import os
from datetime import datetime, timezone
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from backend.api.database import engine
from backend.api.routers.analyze import router as analyze_router
from backend.api.routers.data import router as data_router
from backend.api.routers.findings import router as findings_router
from backend.api.routers.health import router as health_router
from backend.api.routers.sessions import router as sessions_router
from backend.api.routers.ws import router as ws_router


ARTIFACTS_MODEL_PATH = (
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))) + "/ml/artifacts/fraud_classifier.pkl"
)


def configure_logging() -> logging.Logger:
    log_level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    log_level = getattr(logging, log_level_name, logging.INFO)

    logging.basicConfig(
        level=log_level,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    return logging.getLogger("aria-api")


logger = configure_logging()


@asynccontextmanager
async def lifespan(app: FastAPI):
    environment = os.getenv("ARIA_ENV", "development")
    logger.info("ARIA API starting...")
    logger.info("╔══════════════════════════════════════╗")
    logger.info("║  A.R.I.A. API — v0.1.0             ║")
    logger.info("║  Environment: %-22s║", environment)
    logger.info("║  Docs: http://localhost:8000/docs   ║")
    logger.info("╚══════════════════════════════════════╝")

    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        logger.info("Database connection check passed")
    except Exception as exc:
        logger.warning("Database connection check failed: %s", exc)

    model_exists = os.path.exists(ARTIFACTS_MODEL_PATH)
    logger.info("Fraud model artifact %s", "found" if model_exists else "not found")

    app.state.started_at = datetime.now(timezone.utc)
    logger.info("ARIA API ready")
    try:
        yield
    finally:
        logger.info("ARIA API shutting down")


app = FastAPI(title="ARIA API", version="0.1.0", lifespan=lifespan, redirect_slashes=False)

frontend_url = os.getenv("FRONTEND_URL")
allowed_origins = ["http://localhost:3000"]
if frontend_url:
    allowed_origins.append(frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.up\.railway\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root() -> dict:
    return {
        "service": "aria-api",
        "version": "0.1.0",
        "status": "ok",
        "docs": "/docs",
        "health": "/health",
        "data_summary": "/api/v1/data/summary",
    }


app.include_router(health_router)
app.include_router(sessions_router)
app.include_router(findings_router)
app.include_router(analyze_router)
app.include_router(data_router)
app.include_router(ws_router)
