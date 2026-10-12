"""FastAPI application factory (spec §44, §74)."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.v1 import (
    agent_memory,
    agents,
    auth,
    boards,
    careers,
    challenges,
    club,
    club_academy,
    coach,
    community,
    creator,
    entitlements,
    graph,
    jobs,
    knowledge,
    meta,
    metrics,
    model_router,
    players,
    portfolio,
    progress,
    scout,
    simulation_aggregates,
    simulations,
    tactics,
    trainings,
    transfers,
    video,
    world,
)
from app.core.cache import _response_cache
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger, request_id_var
from app.core.tracing import init_tracing, instrument_fastapi
from app.services.knowledge import corpus_stats, sync_knowledge
from app.services.tactics import sync_tactics
from app.services.training_catalog import sync_catalog
from app.services.world import sync_world

# Configure structured logging
configure_logging()
logger = get_logger("football_os.api")

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
        init_tracing()
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
    instrument_fastapi(app)
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
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Request-Duration-Ms"] = str(int((time.perf_counter() - started) * 1000))
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    @app.middleware("http")
    async def response_cache(request: Request, call_next):
        """Cache GET responses for 60 seconds."""
        # Only cache GET requests
        if request.method != "GET":
            return await call_next(request)

        # Skip if no-cache header
        if request.headers.get("Cache-Control", "").lower().find("no-cache") >= 0:
            return await call_next(request)

        # Skip caching in test environment
        if settings.env == "test":
            return await call_next(request)

        # Build cache key
        cache_key = f"http:{request.url.path}:{request.url.query}"
        cached = _response_cache.get(cache_key)
        if cached is not None:
            # Return cached response with cache hit header
            from fastapi.responses import Response

            response = Response(
                content=cached.body,
                status_code=cached.status_code,
                headers=dict(cached.headers),
                media_type=cached.media_type,
            )
            response.headers["X-Cache"] = "HIT"
            return response

        response = await call_next(request)

        # Cache successful GET responses
        if 200 <= response.status_code < 300:
            # Only cache JSON responses
            content_type = response.headers.get("content-type", "")
            if "application/json" in content_type:
                # Read body for caching
                body = b""
                async for chunk in response.body_iterator:
                    body += chunk
                # Reconstruct response with same body
                from starlette.responses import Response as StarletteResponse

                cached_response = StarletteResponse(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
                _response_cache.set(f"http:{request.url.path}:{request.url.query}", cached_response, ttl=60.0)
                # Return new response with cache miss header
                new_response = StarletteResponse(
                    content=body,
                    status_code=response.status_code,
                    headers=dict(response.headers),
                    media_type=response.media_type,
                )
                new_response.headers["X-Cache"] = "MISS"
                return new_response

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
    app.include_router(boards.router, prefix=api)
    app.include_router(video.router, prefix=api)
    app.include_router(careers.router, prefix=api)
    app.include_router(challenges.router, prefix=api)
    app.include_router(simulations.router, prefix=api)
    app.include_router(simulation_aggregates.router, prefix=api)
    app.include_router(transfers.router, prefix=api)
    # The academy router is mounted before §39's own `/club/{ident}` door. Neither can actually shadow the
    # other — every academy path is two segments below `/club` and the tenant door is one — but the order
    # keeps the promise checkable by eye: no slug, `academy` included, can be read as a path segment.
    app.include_router(club_academy.router, prefix=api)
    app.include_router(entitlements.router, prefix=api)
    app.include_router(club.router, prefix=api)
    app.include_router(scout.router, prefix=api)
    app.include_router(community.router, prefix=api)
    app.include_router(creator.router, prefix=api)
    app.include_router(portfolio.router, prefix=api)
    app.include_router(graph.router, prefix=api)
    app.include_router(agent_memory.router, prefix=api)
    app.include_router(agents.router, prefix=api)
    app.include_router(model_router.router, prefix=api)
    app.include_router(metrics.router, prefix=api)
    app.include_router(jobs.router, prefix=api)

    @app.get("/healthz", include_in_schema=False)
    def root_health() -> JSONResponse:
        return JSONResponse({"status": "ok", "demo_mode": settings.is_demo_mode})

    return app


app = create_app()
