"""FastAPI application factory (spec §44, §74)."""

from __future__ import annotations

import hashlib
import time
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable
from contextlib import asynccontextmanager
from typing import Any, Protocol

from fastapi import FastAPI, Request, status
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
    notifications,
    players,
    portfolio,
    progress,
    scout,
    simulation_aggregates,
    simulations,
    tactics,
    traces,
    trainings,
    transfers,
    video,
    world,
)
from app.core.cache import _response_cache, response_cache_key
from app.core.config import settings
from app.core.db import SessionLocal, init_db
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging, get_logger, request_id_var, request_started_var
from app.core.redis_cache import close_redis_cache, get_redis_cache
from app.core.request_metrics import record
from app.core.response_headers import dress_response
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


def caller_identity(credential: str) -> str:
    """A short, stable name for the caller a credential belongs to — never the credential.

    A cache key has to name the caller when the answer belongs to one, and the credential
    itself must not go into the key: keys are printed in metrics, written to logs, and
    readable by anyone with access to the shared store. A truncated SHA-256 of the whole
    `Authorization` header is stable for the life of the token, different for every caller,
    and useless to anyone who does not already hold the token.
    """
    if not credential:
        return ""
    return hashlib.sha256(credential.encode("utf-8")).hexdigest()[:32]


PER_REQUEST_HEADERS = frozenset({"x-request-id", "x-request-duration-ms"})
"""Headers that describe one request and are therefore not part of its answer.

`request_context` sets these while `response_cache` is still collecting the response,
so they are present at store time and would otherwise be replayed on every hit — two
different callers receiving the same `X-Request-ID`, and a hit reporting the duration
of the miss it was copied from. They are filtered on the way in and again on the way
out, because a shared tier may already hold entries written before this existed.
"""


def cacheable_headers(headers: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    """The response headers that belong to the answer rather than to one request."""
    return [pair for pair in headers if pair[0].lower() not in PER_REQUEST_HEADERS]


class CacheTier(Protocol):
    """The operations a response-cache tier must offer.

    Both tiers implement it: `TTLCache` returns `None` from `set`, `RedisCache`
    returns a bool. Declared as a protocol rather than a union so the middleware
    can name the shape it depends on instead of the classes it happens to use.

    `available` is what distinguishes a tier that is serving from one that is merely
    configured. It is the flag that keeps a degraded second tier from quietly becoming
    a second *process-local* tier. Declared as a property because neither tier should
    let a caller set it: only the tier knows whether it is serving.
    """

    @property
    def available(self) -> bool: ...

    def get(self, key: str, default: Any = None) -> Any: ...

    def set(self, key: str, value: Any, ttl: float | None = None) -> Any: ...

    def drop_identity(self, identity: str) -> int: ...


async def cached_response_for(
    cache: CacheTier,
    request: Request,
    call_next: Callable[[Request], Awaitable[Response]],
    *,
    ttl: float = 60.0,
    shared: CacheTier | None = None,
) -> Response:
    """Serve a GET from `cache`, or fetch it from `call_next` and store the answer.

    `cache` is the process-local tier; `shared` is an optional second tier other
    processes can see. Reads check the near tier first because it is the cheapest,
    and a hit found only in the shared tier is written back into the near one so the
    next request from this process does not pay for it again. Writes go to both.

    Four uvicorn workers otherwise run four independent caches, which is part of why
    the measured gain from extra workers fell away at higher concurrency: a response
    one process paid for cannot be served by another. With `shared` absent — as it is
    today, and on any host where the second tier cannot serve — every code path here
    is the single-tier behaviour it replaced.

    The cache holds a serialisable payload rather than a response object, which is what
    lets the two tiers share a value: an in-memory cache can hold a `Response` and a
    Redis one cannot, so the value here is a plain dict in both.

    A response is cached only when it is a 2xx whose content type is JSON. Anything else
    is passed through and marked MISS — caching a 500 would replay a failure for the
    whole TTL, and caching a non-JSON body would break the contract the payload is built
    on. `no-cache` from the caller defeats a warm entry, because a caller who asks for a
    fresh answer is entitled to one. So is a caller whose own write just succeeded: the
    write drops every entry keyed to that caller, so the next GET cannot serve the answer
    the write made false.

    **A private answer belongs to the caller who asked for it, so the key names the
    caller.** Measured 2026-10-20 against a live server: the key was path + query +
    origin and named no caller, so `GET /api/v1/players` — the caller's own player row —
    was stored under a key that any other account's request for the same path matched,
    and the second account was served the first account's player. The cached payload was
    the leak, not the header, and the replay was invisible: the second caller got a 200
    with someone else's football identity in it.

    The `Authorization` header is the only credential this API honours (`current_user`
    reads a bearer token and nothing else), so it is the only one the cache has to
    consider. A request that carries one is keyed by `caller_identity(credential)` — a
    hash of the header, never the header — so its answer is stored under its own name
    and no other caller's request can match it.

    **The shared tier follows RFC 9111 §3.5: a shared cache must not store a response
    to a request that carries an `Authorization` header**, because that response is not
    one every user may see. So a credentialed request is answered from the near tier
    only, and the shared store holds public answers and nothing else. The near tier is
    one process's memory and it is already where a private answer lived before; the
    change is that the answer is now under the caller's name.

    The cost is that a private answer is not shared between workers — the price of never
    sharing one account's answer with another. The benefit is that the shared tier still
    does the work it is for, on the public content every caller asks the same question
    about, and that no user data is written to a store another process can read.
    """
    if request.method != "GET":
        response = await call_next(request)
        # Read-your-writes: a caller whose write succeeded must not be served their own
        # pre-write answers for the rest of the TTL. Measured 2026-10-27 on a live server:
        # after a career's `POST /play`, five consecutive plain GETs returned the pre-play
        # career view — the cache held the answer the write had just made false. The drop
        # is scoped to the caller because the key already is: every private answer sits
        # under that caller's identity, and no other caller's answer may be dropped for
        # this one's write. An anonymous write drops nothing — an anonymous caller holds no
        # identity their future reads could be keyed under, and their next read after
        # registering or signing in runs under a fresh identity with no entries at all.
        if 200 <= response.status_code < 300 and caller_identity(request.headers.get("authorization", "")):
            cache.drop_identity(caller_identity(request.headers["authorization"]))
        return response

    if "no-cache" in request.headers.get("Cache-Control", "").lower():
        return await call_next(request)

    credential = request.headers.get("authorization", "")
    identity = caller_identity(credential)
    key = response_cache_key(request.url.path, request.url.query, request.headers.get("origin", ""), identity)
    cached = cache.get(key)
    if cached is None and not identity and shared is not None and shared.available:
        cached = shared.get(key)
        if cached is not None:
            cache.set(key, cached, ttl=ttl)
    if cached is not None:
        replay = Response(
            content=cached["body"],
            status_code=cached["status_code"],
            headers=dict(cacheable_headers(cached["headers"])),
            media_type=cached["media_type"],
        )
        replay.headers["X-Cache"] = "HIT"
        return replay

    response = await call_next(request)

    if not (200 <= response.status_code < 300) or "application/json" not in response.headers.get("content-type", ""):
        response.headers["X-Cache"] = "MISS"
        return response

    body = await _read_body(response)

    payload = {
        "body": body.decode("utf-8"),
        "status_code": response.status_code,
        "headers": cacheable_headers(response.headers.items()),
        "media_type": response.media_type,
    }
    cache.set(key, payload, ttl=ttl)
    if not identity and shared is not None and shared.available:
        shared.set(key, payload, ttl=ttl)

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
        # The shared tier is fetched per request rather than captured at startup: the
        # singleton is built on first use, and building it at import would make every
        # process pay a Redis connect before it had served a single request. Once built,
        # this is a global lookup, and a tier that cannot serve is remembered as such.
        return await cached_response_for(_response_cache, request, call_next, shared=get_redis_cache())

    # Registered after `response_cache`, and therefore wrapped by it: this is the
    # outermost middleware. The order is load-bearing in both directions. Here it means
    # the request id is set before the cache layer runs, so a warning emitted while
    # looking the answer up still carries the id of the request that caused it. It also
    # means this runs on a HIT, where `response_cache` returns without calling anything
    # downstream — so a served-from-cache response gets this request's own id, duration
    # and security headers rather than none, or the previous caller's.
    #
    # The headers themselves are added by `dress_response`, which the 500 handler also calls: an
    # exception propagates out of this middleware before the lines below could run, so the crash
    # has to dress itself, and two definitions of the header set would drift apart.
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        started = time.perf_counter()
        # Generate or extract request ID
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(request_id)
        request_started_var.set(started)
        try:
            response = await call_next(request)
        except Exception:
            # An exception that reached here is a 500 `ServerErrorMiddleware` will render, because
            # everything shorter of one was already answered further in. Counting it needs this path:
            # that middleware sits outside every user middleware, so nothing downstream of here will
            # ever run for it, and an error the row cannot see is the error that hides.
            record(status.HTTP_500_INTERNAL_SERVER_ERROR, (time.perf_counter() - started) * 1000)
            raise
        record(response.status_code, (time.perf_counter() - started) * 1000)
        dress_response(response)
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
    app.include_router(notifications.router, prefix=api)
    app.include_router(metrics.router, prefix=api)
    app.include_router(jobs.router, prefix=api)
    app.include_router(traces.router, prefix=api)

    @app.get("/healthz", include_in_schema=False)
    def root_health() -> JSONResponse:
        return JSONResponse({"status": "ok", "demo_mode": settings.is_demo_mode})

    return app


app = create_app()
