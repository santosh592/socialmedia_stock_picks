from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.deps import optional_basic_auth
from api.routes import (
    dashboard_router,
    digest_router,
    health_router,
    ingest_router,
    opportunities_router,
    settings_router,
    tickers_router,
)
from core.config import get_settings
from workers.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    scheduler = start_scheduler(settings)
    yield
    stop_scheduler(scheduler)


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app.name,
        version="0.1.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://127.0.0.1:3000", "http://localhost:3000"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    auth = [Depends(optional_basic_auth)]
    prefix = "/api/v1"
    app.include_router(health_router, prefix=prefix)
    app.include_router(dashboard_router, prefix=prefix, dependencies=auth)
    app.include_router(tickers_router, prefix=prefix, dependencies=auth)
    app.include_router(ingest_router, prefix=prefix, dependencies=auth)
    app.include_router(opportunities_router, prefix=prefix, dependencies=auth)
    app.include_router(settings_router, prefix=prefix, dependencies=auth)
    app.include_router(digest_router, prefix=prefix, dependencies=auth)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "api.main:app",
        host=settings.app.host,
        port=settings.app.port,
        reload=True,
    )


if __name__ == "__main__":
    run()
