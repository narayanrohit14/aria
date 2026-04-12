from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class SessionCreate(BaseModel):
    room_name: str
    participant_identity: str = "aria-user"


class SessionResponse(BaseModel):
    session_id: str
    room_name: str
    livekit_token: str
    livekit_url: str
    risk_level: str

    model_config = ConfigDict(from_attributes=True)


class FindingCreate(BaseModel):
    session_id: Optional[str] = None
    title: str
    criteria: str
    condition: str
    cause: str
    consequence: str
    corrective_action: str
    risk_level: Literal["HIGH", "MEDIUM", "LOW"]


class FindingResponse(BaseModel):
    id: str
    title: str
    criteria: str
    condition: str
    cause: str
    consequence: str
    corrective_action: str
    risk_level: str
    created_at: datetime
    created_by: str

    model_config = ConfigDict(from_attributes=True)


class FindingListResponse(BaseModel):
    findings: list[FindingResponse]
    total: int


class TransactionFeatures(BaseModel):
    amount: float
    hour_of_day: int = 12
    is_online: int = 0
    mcc_code: int = 5812
    credit_limit: float = 10000.0
    amount_to_limit_ratio: float = 0.1
    has_chip: int = 1
    card_age_years: float = 3.0
    pin_staleness: int = 3
    is_prepaid: int = 0
    credit_score: int = 700
    debt_to_income: float = 1.0
    age: int = 40


class AnalysisResponse(BaseModel):
    fraud_probability: float
    fraud_predicted: bool
    confidence: str
    threshold_used: float
    risk_score: float
    risk_level: str
    audit_flags: list[str]


class ModelMetrics(BaseModel):
    cv_f1_mean: float
    cv_precision_mean: float
    cv_recall_mean: float
    cv_roc_auc_mean: float
    n_samples: int
    n_fraud_cases: int
    optimal_threshold: float


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
    model_loaded: bool
    database_connected: bool
    model_metrics: Optional[ModelMetrics] = None


class SubtitleMessage(BaseModel):
    type: Literal["subtitle", "clear", "risk_update"]
    text: Optional[str] = None
    risk_level: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
