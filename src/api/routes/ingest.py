from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import IngestRunResponse
from core.database import get_db
from models.entities import IngestRun
from workers.ingest import IngestWorker

router = APIRouter(tags=["ingest"])


@router.post("/ingest/run", response_model=IngestRunResponse, status_code=202)
async def run_ingest(db: AsyncSession = Depends(get_db)) -> IngestRunResponse:
    worker = IngestWorker(db)
    run = await worker.run()
    return IngestRunResponse(ingest_run_id=run.id, status=run.status)



@router.get("/ingest/runs/{run_id}")
async def get_ingest_run(
    run_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    result = await db.execute(select(IngestRun).where(IngestRun.id == run_id))
    run = result.scalar_one_or_none()
    if run is None:
        raise HTTPException(status_code=404, detail="Ingest run not found")
    return {
        "id": str(run.id),
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "posts_fetched": run.posts_fetched,
        "comments_fetched": run.comments_fetched,
        "mentions_created": run.mentions_created,
        "errors": run.errors,
    }
