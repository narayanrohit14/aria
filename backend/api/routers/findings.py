from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db
from backend.api.models.db import AuditFinding
from backend.api.schemas.schemas import FindingCreate, FindingListResponse, FindingResponse


router = APIRouter(prefix="/api/v1/findings", tags=["findings"])


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
