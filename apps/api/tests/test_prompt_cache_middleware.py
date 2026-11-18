"""The middleware shards every request: anon stays out of band with authenticated sessions."""

from __future__ import annotations

import json
import urllib.request

import app.services.manual_ask as manual_ask
import app.providers as providers
from app.providers import OpenAIChatProvider


class _Resp:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def read(self):
        return self._body


def _capture(monkeypatch) -> list[dict]:
    seen: list[dict] = []

    def fake_urlopen(request, *args, **kwargs):
        seen.append(json.loads(request.data.decode("utf-8")))
        return _Resp(
            b'{"choices":[{"message":{"content":"manual answers"}}],'
            b' "usage":{"prompt_tokens":5,"completion_tokens":2,"prompt_tokens_details":{"cached_tokens":4}}}'
        )

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    return seen


def test_anonymous_requests_shard_the_cache_as_anon(client, monkeypatch) -> None:
    seen = _capture(monkeypatch)
    provider = OpenAIChatProvider("k", "gpt-6.1-terra", base_url="https://api.aizzz.xyz/v1", stream=False)
    monkeypatch.setattr(manual_ask, "get_llm_provider", lambda: provider)

    response = client.post("/api/v1/manual/ask", json={"question": "how do i use the manual door", "locale": "en"})
    assert response.status_code == 200, response.text
    assert seen, "the model was never called"
    key = seen[-1]["prompt_cache_key"]
    assert key.startswith("football-os/manual-ask#")
    assert key.endswith("#anon")


def test_authenticated_requests_shard_per_user(client, monkeypatch) -> None:
    seen = _capture(monkeypatch)

    register = client.post(
        "/api/v1/auth/register",
        json={
            "email": "shard-per-user@example.test",
            "password": "strong-pass-1234",
            "display_name": "Shard",
            "role": "player",
            "accepts_data_policy": True,
        },
    )
    assert register.status_code == 201
    token = register.json()["access_token"]

    provider = OpenAIChatProvider("k", "gpt-6.1-terra", base_url="https://api.aizzz.xyz/v1", stream=False)
    monkeypatch.setattr(manual_ask, "get_llm_provider", lambda: provider)

    response = client.post(
        "/api/v1/manual/ask",
        json={"question": "how do i open the manual door", "locale": "en"},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200, response.text
    key = seen[-1]["prompt_cache_key"]
    assert key.startswith("football-os/manual-ask#")
    assert key.startswith("football-os/manual-ask#u-")
