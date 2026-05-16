from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.schemas import DigestResponse
from core.config import get_settings

router = APIRouter(tags=["digest"])


@router.get("/digest/latest", response_model=DigestResponse)
async def latest_digest() -> DigestResponse:
    settings = get_settings()
    output_dir = Path(settings.digest.get("output_path", "data/digests"))
    if not output_dir.is_absolute():
        output_dir = Path(__file__).resolve().parents[3] / output_dir
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="No digests generated yet")
    files = sorted(output_dir.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise HTTPException(status_code=404, detail="No digests generated yet")
    latest = files[0]
    return DigestResponse(
        path=str(latest),
        markdown=latest.read_text(encoding="utf-8"),
        generated_at=None,
    )
