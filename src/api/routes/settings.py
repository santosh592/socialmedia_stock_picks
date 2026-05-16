from fastapi import APIRouter, Depends
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import SettingsResponse, SettingsUpdate
from core.config import get_settings, load_yaml_config
from core.database import get_db
from models.entities import AppConfigRow

router = APIRouter(tags=["settings"])

SECRET_KEYS = {"client_secret", "api_key", "app_password"}


def _redact(obj: object, parent_key: str = "") -> object:
    if isinstance(obj, dict):
        return {k: _redact(v, k) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_redact(v, parent_key) for v in obj]
    if parent_key in SECRET_KEYS and obj:
        return "***"
    return obj


@router.get("/settings", response_model=SettingsResponse)
async def get_app_settings(db: AsyncSession = Depends(get_db)) -> SettingsResponse:
    base = load_yaml_config()
    get_settings()  # warm cache
    merged = _redact(base)
    return SettingsResponse(config=merged)


@router.put("/settings", response_model=SettingsResponse)
async def update_settings(
    body: SettingsUpdate,
    db: AsyncSession = Depends(get_db),
) -> SettingsResponse:
    patches = body.model_dump(exclude_none=True)
    for key, value in patches.items():
        stmt = (
            insert(AppConfigRow)
            .values(key=key, value=value)
            .on_conflict_do_update(index_elements=["key"], set_={"value": value})
        )
        await db.execute(stmt)
    await db.commit()
    return await get_app_settings(db)
