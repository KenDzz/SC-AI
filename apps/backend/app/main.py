import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.logging_utils import configure_logging
from app.redis_client import get_redis
from app.routers import auth, catalog, incidents, internal, system
from app.seed import seed
from app.storage import ensure_bucket

configure_logging()
log = logging.getLogger("api")


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    if settings.testing:
        Base.metadata.create_all(bind=engine)
    else:
        try:
            ensure_bucket()
        except Exception:
            log.warning("object storage is not ready yet")
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            seed(db)
        finally:
            db.close()
    get_redis()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="AI Safety & Compliance Monitoring", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router)
    app.include_router(catalog.router)
    app.include_router(incidents.router)
    app.include_router(system.router)
    app.include_router(internal.router)

    @app.exception_handler(ValueError)
    async def value_error(_: Request, exc: ValueError):
        return JSONResponse(status_code=400, content={"detail": str(exc)})

    return app


app = create_app()
