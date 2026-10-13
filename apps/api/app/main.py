"""FastAPI application factory (spec §44, §74)."""

from __future__ import annotations

import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response

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
from app.core.cache import TTLCache, _response_cache
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger, request_id_var
from app.core.redis_cache import close_redis_cache
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


async def _read_body(response: Response) -> bytes:
    """Read a response body whichever shape it arrived in.

    Inside a middleware stack `call_next` hands back a streaming response, whose body
    is an async iterator and has to be drained to be read. A response built directly —
    a stub origin in a test, or any ordinary `JSONResponse` — already has its body in
    `response.body` and no iterator at all. Draining the iterator unconditionally worked
    in production and raised `AttributeError` the moment the function was called
    anywhere else, which is the difference between code that has been exercised and
    code that has only been reached.
    """
    iterator = getattr(response, "body_iterator", None)
    if iterator is None:
        return response.body
    body = b""
    async for chunk in iterator:
        body += chunk
    return body


def response_cache_key(path: str, query: str) -> str:
    """The cache identity of a request: path plus query, prefixed by kind.

    The prefix matters less than it looks — nothing else writes into this cache
    today — but it keeps an HTTP entry from colliding with any future key space
    sharing the same store.
    """
    return f"http:{path}:{query}"


async def cached_response_for(
    cache: TTLCache,
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    *,
    ttl: float = 60.0,
) -> Response:
    """Serve a GET from `cache`, or fetch it from `call_next` and store the answer.

    The cache holds a serialisable payload rather than a response object, which is what
    lets a second tier sit behind the same operations later: an in-memory cache can hold
    a `Response` and a Redis one cannot, so the value here is a plain dict in both.

    A response is cached only when it is a 2xx whose content type is JSON. Anything else
    is passed through untouched and marked MISS — caching a 500 would replay a failure
    for the whole TTL, and caching a non-JSON body would break the contract the payload
    is built on. `no-cache` from the caller defeats a warm entry, because a caller who
    asks for a fresh answer is entitled to one.
    """
    if request.method != "GET":
        return await call_next(request)

    if "no-cache" in request.headers.get("Cache-Control", "").lower():
        return await call_next(request)

    key = response_cache_key(request.url.path, request.url.query)
    cached = cache.get(key)
    if cached is not None:
        replay = Response(
            content=cached["body"],
            status_code=cached["status_code"],
            headers=dict(cached["headers"]),
            media_type=cached["media_type"],
        )
        replay.headers["X-Cache"] = "HIT"
        return replay

    response = await call_next(request)

    if not (200 <= response.status_code < 300) or "application/json" not in response.headers.get("content-type", ""):
        response.headers["X-Cache"] = "MISS"
        return response

    body = await _read_body(response)

    cache.set(
        key,
        {
            "body": body.decode("utf-8"),
            "status_code": response.status_code,
            "headers": [tuple(pair) for pair in response.headers.items()],
            "media_type": response.media_type,
        },
        ttl=ttl,
    )

    replay = Response(content=body, status_code=response.status_code, headers=dict(response.headers), media_type=response.media_type)
    replay.headers["X-Cache"] = "MISS"
    return replay


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
        # The Redis singleton is built on first use, which may be never, and closing an
        # unconstructed one is a no-op — so shutdown does not have to know whether the
        # metrics door was ever called.
        close_redis_cache()

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
        """Cache GET responses for 60 seconds.

        Only the environment decision lives here. It is configuration — the test
        database persists from case to case, so a cached response would make one case
        read another's — and it is the reason this middleware had no test. Everything
        else is in `cached_response_for`, which takes the cache as an argument and can
        therefore be driven directly.
        """
        if settings.env == "test":
            return await call_next(request)
        return await cached_response_for(_response_cache, request, call_next)

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
