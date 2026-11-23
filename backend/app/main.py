"""FastAPI app factory. Run: uv run uvicorn app.main:app --reload (from backend/)."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.api.routes import router
from app.core.config import load_settings
from app.core.logging_setup import configure_logging
from app.service import Service, ServiceError

log = logging.getLogger(__name__)


def create_app(service: Service | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if service is None:
            configure_logging()
        app.state.service = service or Service(load_settings())
        app.state.service.bootstrap()
        log.info("ready mode=%s", app.state.service.mode()["label"])
        yield

    app = FastAPI(title="Stargo RevOps", version="0.1.0", lifespan=lifespan)

    @app.exception_handler(ServiceError)
    async def service_error(_: Request, exc: ServiceError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content={"detail": exc.reasons})

    @app.exception_handler(Exception)
    async def unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Never echo internals or request content; the log carries the type only.
        log.error("unhandled error type=%s", type(exc).__name__)
        return JSONResponse(status_code=500, content={"detail": ["internal error"]})

    app.include_router(router)
    return app


app = create_app()
