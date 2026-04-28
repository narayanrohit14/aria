import os
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from livekit.api import AccessToken, VideoGrants
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db
from backend.api.models.db import AuditSession
from backend.api.schemas.schemas import SessionCreate, SessionResponse


router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


@router.post("", response_model=SessionResponse, status_code=status.HTTP_201_CREATED, include_in_schema=False)
@router.post("/", response_model=SessionResponse, status_code=status.HTTP_201_CREATED)
async def create_session(
    body: SessionCreate,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL", "")
    if not api_key or not api_secret or not livekit_url:
        raise HTTPException(status_code=500, detail="LiveKit credentials are not configured.")

    token = (
        AccessToken(api_key, api_secret)
        .with_identity(body.participant_identity)
        .with_grants(VideoGrants(room_join=True, room=body.room_name))
        .to_jwt()
    )

    session = AuditSession(
        room_name=body.room_name,
        livekit_token=token,
        risk_level="UNKNOWN",
    )
    try:
        db.add(session)
        await db.commit()
        await db.refresh(session)
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to create session: {exc}") from exc

    return SessionResponse(
        session_id=str(session.id),
        room_name=session.room_name,
        livekit_token=token,
        livekit_url=livekit_url,
        risk_level=session.risk_level,
    )


@router.get("/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> SessionResponse:
    try:
        result = await db.execute(select(AuditSession).where(AuditSession.id == UUID(session_id)))
        session = result.scalar_one_or_none()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID.") from exc
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=500, detail=f"Failed to load session: {exc}") from exc

    if session is None:
        raise HTTPException(status_code=404, detail="Session not found.")

    return SessionResponse(
        session_id=str(session.id),
        room_name=session.room_name,
        livekit_token=session.livekit_token or "",
        livekit_url=os.getenv("LIVEKIT_URL", ""),
        risk_level=session.risk_level,
    )


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def end_session(
    session_id: str,
    db: AsyncSession = Depends(get_db),
) -> Response:
    try:
        result = await db.execute(select(AuditSession).where(AuditSession.id == UUID(session_id)))
        session = result.scalar_one_or_none()
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found.")

        session.ended_at = datetime.now(timezone.utc)
        await db.commit()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID.") from exc
    except SQLAlchemyError as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to update session: {exc}") from exc

    return Response(status_code=status.HTTP_204_NO_CONTENT)
