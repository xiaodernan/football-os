"""The response cache must never replay one account's answer to another.

Measured 2026-10-20 against a live server, with the cache engaged (`ENV=development`):
account A created a player and asked for `/api/v1/players`; account B asked for the same
path with its own token and was **served A's player row**. The cache key was path + query
+ origin and named no caller, so the second account's request matched the first account's
stored answer, and the answer was a 200 with somebody else's football identity in it.

The same finding is the reason the shared tier could not be landed before this file: a
second tier that is shared across workers and across hosts would have spread one
account's private answer to every worker on the box.

The rule the cases below hold has two halves, and the halves are not the same rule:

* **The near tier names the caller.** A credentialed request is keyed by a hash of its
  credential, so its answer is stored under its own name and no other caller's request
  can match it. The near tier is one process's memory, and it is where a private answer
  lived before this change.
* **The shared tier never sees a private answer.** RFC 9111 §3.5: a shared cache must not
  store a response to a request that carries an `Authorization` header, because that
  response is not one every user may see. So a credentialed request is neither read from
  nor written to the shared tier, and the shared store holds public answers only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from uuid import uuid4

from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.cache import TTLCache
from app.main import cached_response_for, caller_identity, response_cache_key

Origin = Callable[[Request], Awaitable[Response]]

PASSWORD = "TestPass1234!"


def _request(path: str = "/api/v1/players", headers: list[tuple[bytes, bytes]] | None = None) -> Request:
    return Request(
        {
            "type": "http",
            "method": "GET",
            "scheme": "http",
            "path": path,
            "query_string": b"",
            "headers": headers or [],
            "client": ("127.0.0.1", 1),
            "server": ("testserver", 80),
        }
    )


def _origin_answering_the_caller() -> Origin:
    """An origin that answers with the body the request's own credential asked for.

    The point is to make two callers' answers differ, so that a replay is visible in the
    body rather than only in a header.
    """

    async def call_next(request: Request) -> Response:
        credential = request.headers.get("authorization", "")
        return JSONResponse(content={"served_to": credential})

    return call_next


class _CountingTier:
    """A shared tier that counts what it is asked and what it is given."""

    def __init__(self) -> None:
        self.store: dict[str, object] = {}
        self.gets = 0
        self.sets = 0

    @property
    def available(self) -> bool:
        return True

    def get(self, key: str, default: object = None) -> object:
        self.gets += 1
        return self.store.get(key, default)

    def set(self, key: str, value: object, ttl: float | None = None) -> bool:
        self.sets += 1
        self.store[key] = value
        return True


class TestTheKeyNamesTheCaller:
    def test_the_identity_is_a_hash_and_not_the_credential(self) -> None:
        identity = caller_identity("Bearer super-secret-token")
        assert "super-secret-token" not in identity, f"the credential survived into the key: {identity!r}"
        assert len(identity) >= 16, f"the identity is too short to be a hash: {identity!r}"
        assert identity == caller_identity("Bearer super-secret-token"), "the identity must be stable for a token"
        assert identity != caller_identity("Bearer another-token"), "two callers must not share an identity"
        assert caller_identity("") == "", "a request with no credential has no identity"

    def test_two_callers_have_two_keys(self) -> None:
        first = response_cache_key("/api/v1/players", "", "", caller_identity("Bearer a"))
        second = response_cache_key("/api/v1/players", "", "", caller_identity("Bearer b"))
        public = response_cache_key("/api/v1/players", "", "")
        assert first != second, "two callers must not share a cache key"
        assert first != public, "a private answer must not sit under the public key"
        assert public == response_cache_key("/api/v1/players", "", ""), "the public key is stable"


class TestTheNearTier:
    def test_a_credentialed_request_is_never_served_from_the_cache(self) -> None:
        """Two callers, one path, and the second must not get the first's body."""
        cache: TTLCache = TTLCache()
        origin = _origin_answering_the_caller()

        async def run() -> tuple[str, str]:
            first = await cached_response_for(
                cache,
                _request(headers=[(b"authorization", b"Bearer token-a")]),
                origin,
            )
            second = await cached_response_for(
                cache,
                _request(headers=[(b"authorization", b"Bearer token-b")]),
                origin,
            )
            return first.body.decode(), second.body.decode()

        first_body, second_body = asyncio.run(run())
        assert "token-a" in first_body, first_body
        assert "token-b" in second_body, f"the second caller was served the first caller's answer: {second_body!r}"
        assert first_body != second_body

    def test_the_same_caller_is_served_from_the_near_tier(self) -> None:
        """The other half: the fix must not simply disable the cache."""
        cache: TTLCache = TTLCache()
        origin = _origin_answering_the_caller()

        async def run() -> tuple[str, str]:
            first = await cached_response_for(
                cache,
                _request(headers=[(b"authorization", b"Bearer token-a")]),
                origin,
            )
            second = await cached_response_for(
                cache,
                _request(headers=[(b"authorization", b"Bearer token-a")]),
                origin,
            )
            return first.headers["X-Cache"], second.headers["X-Cache"]

        assert asyncio.run(run()) == ("MISS", "HIT")


class TestTheSharedTier:
    def test_a_credentialed_answer_never_reaches_the_shared_tier(self) -> None:
        """RFC 9111 §3.5: a shared cache must not store a credentialed response."""
        near: TTLCache = TTLCache()
        shared = _CountingTier()
        origin = _origin_answering_the_caller()

        async def run() -> None:
            await cached_response_for(
                near,
                _request(headers=[(b"authorization", b"Bearer token-a")]),
                origin,
                shared=shared,
            )

        asyncio.run(run())
        assert shared.sets == 0, "a private answer was written to the shared tier"
        assert shared.gets == 0, "the shared tier was consulted for a private answer"

    def test_a_public_answer_still_reaches_the_shared_tier(self) -> None:
        near: TTLCache = TTLCache()
        shared = _CountingTier()
        origin = _origin_answering_the_caller()

        async def run() -> None:
            await cached_response_for(near, _request(), origin, shared=shared)

        asyncio.run(run())
        assert shared.sets == 1, "a public answer never reached the shared tier"
        assert shared.gets == 1, "the shared tier was written to but never read from"

    def test_a_public_answer_is_read_back_from_the_shared_tier(self) -> None:
        """The sharing itself: the second reader has an empty near tier."""
        near: TTLCache = TTLCache()
        shared = _CountingTier()
        origin = _origin_answering_the_caller()

        async def run() -> str:
            await cached_response_for(near, _request(), origin, shared=shared)
            other_near: TTLCache = TTLCache()
            replayed = await cached_response_for(other_near, _request(), origin, shared=shared)
            return replayed.headers["X-Cache"]

        assert asyncio.run(run()) == "HIT", "a second process's answer was not served from the shared tier"


class TestAgainstTheRealStack:
    """The middleware, the two tiers and two real accounts."""

    def test_a_second_account_is_not_served_the_first_ones_player(self) -> None:
        from starlette.testclient import TestClient

        from app.core.cache import _response_cache
        from app.core.config import settings
        from app.main import app as fastapi_app

        was_env = settings.env
        object.__setattr__(settings, "env", "development")
        _response_cache.clear()
        try:
            with TestClient(fastapi_app) as client:
                first = client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": f"cache-owner-{uuid4().hex[:8]}@example.test",
                        "password": PASSWORD,
                        "display_name": "Cache Owner",
                        "role": "player",
                        "accepts_data_policy": True,
                    },
                )
                assert first.status_code == 201, first.text
                owner_token = first.json()["access_token"]
                created = client.post(
                    "/api/v1/players",
                    headers={"Authorization": f"Bearer {owner_token}"},
                    json={
                        "name": "The Only Player Of This Account",
                        "position": "ST",
                        "age": 24,
                        "level": "advanced",
                        "preferred_foot": "left",
                        "goal": "become_box_to_box",
                    },
                )
                assert created.status_code == 201, created.text

                owner_view = client.get("/api/v1/players", headers={"Authorization": f"Bearer {owner_token}"})
                assert owner_view.status_code == 200, owner_view.text
                assert "The Only Player Of This Account" in owner_view.text

                second = client.post(
                    "/api/v1/auth/register",
                    json={
                        "email": f"cache-stranger-{uuid4().hex[:8]}@example.test",
                        "password": PASSWORD,
                        "display_name": "Cache Stranger",
                        "role": "player",
                        "accepts_data_policy": True,
                    },
                )
                assert second.status_code == 201, second.text
                stranger_token = second.json()["access_token"]

                stranger_view = client.get("/api/v1/players", headers={"Authorization": f"Bearer {stranger_token}"})
                assert stranger_view.status_code == 200, stranger_view.text
                assert "The Only Player Of This Account" not in stranger_view.text, (
                    "a second account was served the first account's player: "
                    f"{stranger_view.text[:300]!r}"
                )
        finally:
            object.__setattr__(settings, "env", was_env)
            _response_cache.clear()
