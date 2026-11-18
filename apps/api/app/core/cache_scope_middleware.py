"""Pure-ASGI edge for prompt-cache sharding (see app.core.prompt_cache_scope).

Sets the shard for the lifetime of an HTTP request so any LLM call — auth or no auth —
sees the same shard. Pure ASGI on purpose: FastAPI's BaseHTTPMiddleware does not
promise contextvars propagate downstream, and `anyio.to_thread` copies the context for
sync endpoints, so one door at the edge covers both.

The bearer is read, signature-checked with the same helper the API uses everywhere
else, and dropped. No claim about identity reaches the model; only the public id
prefix (`u0123abc…`) shards the cache.
"""

from __future__ import annotations

from typing import Any

from app.core.prompt_cache_scope import reset_prompt_cache_scope, set_prompt_cache_scope


class PromptCacheScopeMiddleware:
    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return
        shard = ""
        for name, value in scope.get("headers") or []:
            if name.lower() != b"authorization":
                continue
            auth = value.decode("latin-1").strip()
            scheme, _, token = auth.partition(" ")
            if scheme.lower() == "bearer" and token:
                try:
                    from app.core.security import decode_token

                    payload = decode_token(token, "access")
                    sub = str(payload.get("sub") or "").strip()
                    if sub:
                        shard = f"u-{sub[:16]}"
                except Exception:  # noqa: BLE001 — a broken token shards nothing; it never fails the request
                    shard = ""
            break
        if not shard:
            shard = "anon"
        token = set_prompt_cache_scope(shard)
        try:
            await self.app(scope, receive, send)
        finally:
            reset_prompt_cache_scope(token)
