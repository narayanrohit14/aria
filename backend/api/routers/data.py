from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.database import get_db


router = APIRouter(prefix="/api/v1/data", tags=["data"])


async def _scalar_int(db: AsyncSession, query: str) -> int:
    result = await db.execute(text(query))
    return int(result.scalar() or 0)


@router.get("/summary")
async def dataset_summary(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        users = await _scalar_int(db, "SELECT COUNT(*) FROM aria_users")
        cards = await _scalar_int(db, "SELECT COUNT(*) FROM aria_cards")
        transactions = await _scalar_int(db, "SELECT COUNT(*) FROM aria_transactions")
        mcc_codes = await _scalar_int(db, "SELECT COUNT(*) FROM aria_mcc_codes")
        fraud_labels = await _scalar_int(db, "SELECT COUNT(*) FROM aria_fraud_labels")
        fraud_cases = await _scalar_int(
            db,
            "SELECT COUNT(*) FROM aria_fraud_labels WHERE is_fraud IS TRUE",
        )

        return {
            "status": "ok",
            "users": users,
            "cards": cards,
            "transactions": transactions,
            "mcc_codes": mcc_codes,
            "fraud_labels": fraud_labels,
            "fraud_cases": fraud_cases,
            "fraud_rate": fraud_cases / fraud_labels if fraud_labels else 0.0,
        }
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Seeded dataset is unavailable: {exc}",
        ) from exc


@router.get("/transactions/sample")
async def transaction_sample(
    limit: int = 10,
    fraud_only: bool = False,
    db: AsyncSession = Depends(get_db),
) -> dict:
    safe_limit = max(1, min(limit, 50))
    where_clause = "WHERE fl.is_fraud IS TRUE" if fraud_only else ""
    query = text(
        f"""
        SELECT
            tx.id,
            tx.transaction_date,
            tx.client_id,
            tx.card_id,
            tx.amount,
            tx.merchant_city,
            tx.merchant_state,
            tx.mcc,
            mcc.description AS mcc_description,
            COALESCE(fl.is_fraud, false) AS is_fraud
        FROM aria_transactions tx
        LEFT JOIN aria_fraud_labels fl ON fl.transaction_id = tx.id
        LEFT JOIN aria_mcc_codes mcc ON mcc.mcc_code = tx.mcc
        {where_clause}
        ORDER BY tx.amount DESC NULLS LAST
        LIMIT :limit
        """
    )

    try:
        result = await db.execute(query, {"limit": safe_limit})
        rows = [dict(row._mapping) for row in result]
        for row in rows:
            if row.get("transaction_date") is not None:
                row["transaction_date"] = row["transaction_date"].isoformat()
            if row.get("amount") is not None:
                row["amount"] = float(row["amount"])
        return {"transactions": rows, "total": len(rows)}
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail=f"Seeded transactions are unavailable: {exc}",
        ) from exc
