from fastapi import APIRouter, Depends
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import HealthResponse
from core.database import get_db
from models.entities import IngestRun

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
async def health(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    db_status = "ok"
    last_ingest = None
    try:
        await db.execute(text("SELECT 1"))
        result = await db.execute(
            select(IngestRun).where(IngestRun.status == "success").order_by(IngestRun.finished_at.desc()).limit(1)
        )
        run = result.scalar_one_or_none()
        if run and run.finished_at:
            last_ingest = run.finished_at
    except Exception:
        db_status = "error"
    return HealthResponse(status="ok", db=db_status, last_ingest=last_ingest)
