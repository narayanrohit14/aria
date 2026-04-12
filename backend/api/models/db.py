import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

try:
    from backend.api.database import Base
except ModuleNotFoundError:  # Support Alembic when run from backend/api/.
    from database import Base


class AuditSession(Base):
    __tablename__ = "audit_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    room_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    livekit_token: Mapped[str | None] = mapped_column(Text, nullable=True)
    risk_level: Mapped[str] = mapped_column(String(10), default="UNKNOWN", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)


class AuditFinding(Base):
    __tablename__ = "audit_findings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("audit_sessions.id"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    criteria: Mapped[str] = mapped_column(Text, nullable=False)
    condition: Mapped[str] = mapped_column(Text, nullable=False)
    cause: Mapped[str] = mapped_column(Text, nullable=False)
    consequence: Mapped[str] = mapped_column(Text, nullable=False)
    corrective_action: Mapped[str] = mapped_column(Text, nullable=False)
    risk_level: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    created_by: Mapped[str] = mapped_column(String(100), default="ARIA", nullable=False)


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(100), nullable=False)
    metric_value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    run_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class TransactionAnalysis(Base):
    __tablename__ = "transaction_analyses"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    fraud_probability: Mapped[float] = mapped_column(Float, nullable=False)
    fraud_predicted: Mapped[bool] = mapped_column(Boolean, nullable=False)
    risk_score: Mapped[float] = mapped_column(Float, nullable=False)
    confidence: Mapped[str] = mapped_column(String(10), nullable=False)
    analyzed_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    features_json: Mapped[str | None] = mapped_column(Text, nullable=True)
