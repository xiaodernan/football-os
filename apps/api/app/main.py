"""FastAPI application factory (spec §44, §74)."""

from __future__ import annotations

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import auth, coach, knowledge, meta, players, progress, tactics, trainings, world
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import install_error_handlers
from app.services.knowledge import corpus_stats, sync_knowledge
from app.services.tactics import sync_tactics
from app.services.training_catalog import sync_catalog
from app.services.world import sync_world

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("football_os.api")

DESCRIPTION = """
**FOOTBALL OS** — The Operating System for Football.

M0 foundation + M1 vertical slice: My Football (player identity) → Training Academy →
explainable progression → AI Coach → progress → history.

Data provenance: the training catalogue and any world data are **synthetic demo data**
and are labelled as such. AI surfaces run in **DEMO MODE** unless a provider key is
configured, and always say so.
"""


def create_app() -> FastAPI:
    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        init_db()
        with SessionLocal() as session:
            sync_catalog(session)
        if settings.knowledge_auto_ingest:
            with SessionLocal() as session:
                report = sync_knowledge(session)
                if report.errors:
                    logger.error("knowledge ingestion problems: %s", "; ".join(report.errors[:8]))
                else:
                    stats = corpus_stats(session)
                    logger.info(
                        "knowledge base ready docs=%d chunks=%d written_now=%d backend=%s",
                        report.documents_seen,
                        stats["chunks"],
                        report.chunks_written,
                        report.embedding_model,
                    )
        if settings.world_auto_sync:
            with SessionLocal() as session:
                world_report = sync_world(session)
                if world_report.errors:
                    logger.error("football world sync problems: %s", "; ".join(world_report.errors[:8]))
                elif world_report.changed:
                    logger.info("football world synced %s", world_report.summary_line())
        if settings.tactics_auto_sync:
            with SessionLocal() as session:
                tactics_report = sync_tactics(session)
                if tactics_report.errors:
                    logger.error("tactical catalogue sync problems: %s", "; ".join(tactics_report.errors[:8]))
                elif tactics_report.changed:
                    logger.info("tactical systems synced %s", tactics_report.summary_line())
        logger.info("boot env=%s dialect=%s demo_mode=%s", settings.env, settings.database_url.split(":")[0], settings.is_demo_mode)
        yield

    app = FastAPI(
        title="FOOTBALL OS API",
        version="0.1.0",
        description=DESCRIPTION,
        lifespan=lifespan,
        openapi_url="/api/v1/openapi.json",
        docs_url="/api/v1/docs",
        redoc_url=None,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-Duration-Ms"] = str(int((time.perf_counter() - started) * 1000))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    install_error_handlers(app)
    api = "/api/v1"
    app.include_router(meta.router, prefix=api)
    app.include_router(auth.router, prefix=api)
    app.include_router(players.router, prefix=api)
    app.include_router(trainings.router, prefix=api)
    app.include_router(coach.router, prefix=api)
    app.include_router(progress.router, prefix=api)
    app.include_router(knowledge.router, prefix=api)
    app.include_router(world.router, prefix=api)
    app.include_router(tactics.router, prefix=api)

    @app.get("/healthz", include_in_schema=False)
    def root_health() -> JSONResponse:
        return JSONResponse({"status": "ok", "demo_mode": settings.is_demo_mode})

    return app


app = create_app()
