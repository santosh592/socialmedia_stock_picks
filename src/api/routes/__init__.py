from api.routes.dashboard import router as dashboard_router
from api.routes.digest import router as digest_router
from api.routes.health import router as health_router
from api.routes.ingest import router as ingest_router
from api.routes.opportunities import router as opportunities_router
from api.routes.settings import router as settings_router
from api.routes.tickers import router as tickers_router

__all__ = [
    "dashboard_router",
    "digest_router",
    "health_router",
    "ingest_router",
    "opportunities_router",
    "settings_router",
    "tickers_router",
]
