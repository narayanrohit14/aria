import os
from datetime import datetime, timezone
from pathlib import Path

os.environ["POSTGRES_URL"] = "sqlite+aiosqlite:///./test.db"
os.environ["ARIA_ENV"] = "test"
os.environ["LIVEKIT_URL"] = "wss://test.livekit.cloud"
os.environ["LIVEKIT_API_KEY"] = "test-key"
os.environ["LIVEKIT_API_SECRET"] = "test-secret"

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from backend.api.database import Base, get_db
from backend.api.main import app
from backend.api.routers import analyze as analyze_router


TEST_DATABASE_URL = os.environ["POSTGRES_URL"]
TEST_DB_PATH = Path(__file__).resolve().parents[1] / "test.db"
test_engine = create_async_engine(TEST_DATABASE_URL, future=True)
TestSessionLocal = async_sessionmaker(bind=test_engine, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest.fixture(scope="session")
def test_app():
    app.dependency_overrides[get_db] = override_get_db
    app.state.started_at = datetime.now(timezone.utc)
    return app


@pytest_asyncio.fixture(autouse=True)
async def reset_database():
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client(test_app):
    transport = ASGITransport(app=test_app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture(autouse=True)
def mock_model(monkeypatch: pytest.MonkeyPatch):
    class DummyModel:
        pass

    def fake_load_fraud_classifier():
        return DummyModel(), 0.35

    def fake_predict_fraud(model, threshold, transaction_features: dict):
        ratio = float(transaction_features.get("amount_to_limit_ratio", 0.0))
        chip = int(transaction_features.get("has_chip", 1))
        pin = int(transaction_features.get("pin_staleness", 0))
        credit_score = int(transaction_features.get("credit_score", 700))

        probability = min(
            0.99,
            0.02
            + min(ratio / 4.0, 0.6)
            + (0.16 if chip == 0 else 0.0)
            + min(pin / 20.0, 0.15)
            + max(0.0, (650 - credit_score) / 1000.0),
        )
        return {
            "fraud_probability": probability,
            "fraud_predicted": probability >= threshold,
            "confidence": "high" if probability > 0.75 or probability < 0.15 else "medium" if 0.3 <= probability <= 0.75 else "low",
            "threshold_used": threshold,
        }

    monkeypatch.setattr(analyze_router, "load_fraud_classifier", fake_load_fraud_classifier)
    monkeypatch.setattr(analyze_router, "predict_fraud", fake_predict_fraud)


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
