import os
from datetime import datetime, timezone
from uuid import UUID, uuid5, NAMESPACE_URL

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db
from backend.api.models.db import AuditFinding
from backend.api.schemas.schemas import FindingCreate, FindingListResponse, FindingResponse


router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


DEMO_FINDING_IDS = {
    "transaction_monitoring": uuid5(NAMESPACE_URL, "aria-demo-transaction-monitoring"),
    "card_controls": uuid5(NAMESPACE_URL, "aria-demo-card-controls"),
    "fraud_queue": uuid5(NAMESPACE_URL, "aria-demo-fraud-queue"),
}


def _to_finding_response(finding: AuditFinding) -> FindingResponse:
    return FindingResponse(
        id=str(finding.id),
        title=finding.title,
        criteria=finding.criteria,
        condition=finding.condition,
        cause=finding.cause,
        consequence=finding.consequence,
        corrective_action=finding.corrective_action,
        risk_level=finding.risk_level,
        created_at=finding.created_at,
        created_by=finding.created_by,
    )


async def _count_table(db: AsyncSession, table_name: str) -> int:
    result = await db.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
    return int(result.scalar() or 0)


async def _demo_findings(db: AsyncSession) -> list[FindingResponse]:
    try:
        transactions = await _count_table(db, "aria_transactions")
        fraud_labels = await _count_table(db, "aria_fraud_labels")
        fraud_cases = await _count_table(db, "aria_fraud_labels WHERE is_fraud IS TRUE")
        cards = await _count_table(db, "aria_cards")
    except Exception:
        transactions = 0
        fraud_labels = 0
        fraud_cases = 0
        cards = 0

    now = datetime.now(timezone.utc)
    fraud_rate = (fraud_cases / fraud_labels * 100) if fraud_labels else 0.0
    return [
        FindingResponse(
            id=str(DEMO_FINDING_IDS["transaction_monitoring"]),
            title="Representative transaction monitoring sample requires risk-based review",
            criteria="Fraud monitoring controls should evaluate representative transaction populations and escalate anomalies for timely review.",
            condition=(
                f"ARIA has loaded {transactions:,} representative transactions and "
                f"{fraud_cases:,} fraud-positive labels into Railway for demo analytics."
            ),
            cause="The production demo is operating on a storage-safe representative sample rather than the full raw dataset.",
            consequence="Audit users can validate workflow behavior and fraud-risk logic, but full-population assurance requires a larger database tier.",
            corrective_action="Keep the representative seed for demo use and provision expanded Postgres storage before loading the complete transaction population.",
            risk_level="MEDIUM",
            created_at=now,
            created_by="ARIA",
        ),
        FindingResponse(
            id=str(DEMO_FINDING_IDS["fraud_queue"]),
            title="Fraud-positive cases available for prioritization",
            criteria="Known fraud-positive transactions should be available for prioritized model validation and audit triage.",
            condition=(
                f"The seeded Railway dataset contains {fraud_cases:,} fraud-positive cases "
                f"across {fraud_labels:,} labeled transactions, a label fraud rate of {fraud_rate:.2f}%."
            ),
            cause="Representative seeding intentionally preserves all positive fraud labels while sampling non-fraud context.",
            consequence="The demo can exercise high-risk alerting scenarios without exhausting Railway database storage.",
            corrective_action="Use the fraud-only sample endpoint during demonstrations and migrate full labels when production storage is increased.",
            risk_level="HIGH",
            created_at=now,
            created_by="ARIA",
        ),
        FindingResponse(
            id=str(DEMO_FINDING_IDS["card_controls"]),
            title="Card portfolio control attributes loaded for contextual risk scoring",
            criteria="Transaction risk scoring should include card-level control attributes such as chip status, credit limit, and PIN freshness.",
            condition=f"ARIA has loaded {cards:,} card records that can support contextual fraud and control-risk scoring.",
            cause="Card controls are available in the seeded dataset but are not yet fully exposed in the dashboard drill-down workflow.",
            consequence="The current demo supports aggregate portfolio context while detailed card-control evidence remains a Phase 2 enhancement.",
            corrective_action="Add card-level drill-down views and connect transaction analysis results to persisted audit findings.",
            risk_level="LOW",
            created_at=now,
            created_by="ARIA",
        ),
    ]


@router.post("", response_model=FindingResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=FindingResponse, status_code=status.HTTP_201_CREATED)
async def create_finding(
    body: FindingCreate,
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    try:
        session_id = UUID(body.session_id) if body.session_id else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID.") from exc

    try:
        finding = AuditFinding(
            session_id=session_id,
            title=body.title,
            criteria=body.criteria,
            condition=body.condition,
            cause=body.cause,
            consequence=body.consequence,
            corrective_action=body.corrective_action,
            risk_level=body.risk_level,
        )
        db.add(finding)
        await db.commit()
        await db.refresh(finding)
        return _to_finding_response(finding)
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create finding: {exc}") from exc


@router.get("", response_model=FindingListResponse, include_in_schema=False)
@router.get("/", response_model=FindingListResponse)
async def list_findings(
    session_id: str | None = None,
    risk_level: str | None = None,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> FindingListResponse:
    try:
        parsed_session_id = UUID(session_id) if session_id else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID.") from exc

    try:
        stmt = select(AuditFinding).order_by(AuditFinding.created_at.desc()).limit(limit).offset(offset)
        if parsed_session_id:
            stmt = stmt.where(AuditFinding.session_id == parsed_session_id)
        if risk_level:
            stmt = stmt.where(AuditFinding.risk_level == risk_level)

        result = await db.execute(stmt)
        findings = result.scalars().all()
        if (
            not findings
            and not parsed_session_id
            and not risk_level
            and offset == 0
            and os.getenv("ARIA_ENV") != "test"
        ):
            demo_findings = await _demo_findings(db)
            return FindingListResponse(
                findings=demo_findings[:limit],
                total=len(demo_findings),
            )
        return FindingListResponse(
            findings=[_to_finding_response(finding) for finding in findings],
            total=len(findings),
        )
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to list findings: {exc}") from exc


@router.get("/{finding_id}", response_model=FindingResponse)
async def get_finding(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> FindingResponse:
    try:
        result = await db.execute(select(AuditFinding).where(AuditFinding.id == UUID(finding_id)))
        finding = result.scalar_one_or_none()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid finding ID.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load finding: {exc}") from exc

    if finding is None:
        if os.getenv("ARIA_ENV") != "test":
            demo_findings = await _demo_findings(db)
            for demo_finding in demo_findings:
                if demo_finding.id == finding_id:
                    return demo_finding
        raise HTTPException(status_code=404, detail="Finding not found.")

    return _to_finding_response(finding)


@router.delete("/{finding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_finding(
    finding_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        result = await db.execute(select(AuditFinding).where(AuditFinding.id == UUID(finding_id)))
        finding = result.scalar_one_or_none()
        if finding is None:
            raise HTTPException(status_code=404, detail="Finding not found.")

        await db.delete(finding)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid finding ID.") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to delete finding: {exc}") from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
