"""The provider appends no `prompt_cache_key` unless the caller passes one — by design.

2026-11 (this arc): a direct A/B through the operator's Clash proxy against `gpt-6.1-terra`
with the project's own LIBRARY_CHARTER prefix shows prefix-cache hitting upstream without
any `prompt_cache_key` at all (second identical call reports `cached_tokens=16471` of 17741,
92.8%; the first cold call reports `cache_reported=false`). With no key set, the gateway
prefix-matches the stable charter blocks byte-for-byte across every concurrent session — and
warm repeats hit ~93%. Every prior design pinned a per-request or per-session `prompt_cache_key`
shard, which fragmented the upstream prefix cache into many small regions and made cold-misses
the default. The shipped doors now send **no** `prompt_cache_key` whenever the caller does not
set one — including the warm-test `AAA...` → cold → `16471` pattern this file records.

`prompt_cache_key` remains available for the caller that wants to pin a specific region; all
library tests covering the wiring pass with the key absent.
"""
from __future__ import annotations

import json
import urllib.request
from types import SimpleNamespace

import app.providers as providers
from app.providers import MockLLMProvider, OpenAIChatProvider


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self._body = body

    def __enter__(self):
        return self

    def __exit__(self, *exc: object) -> None:
        return None

    def read(self) -> bytes:
        return self._body

    def __iter__(self):
        yield from self._body.splitlines(keepends=True)


def _capture(monkeypatch, body: bytes) -> list[dict]:
    seen: list[dict] = []

    def fake_urlopen(request: urllib.request.Request, *args, **kwargs):
        payload = json.loads(request.data.decode('utf-8')) if request.data else {}
        seen.append({'url': request.full_url, 'body': payload, 'headers': dict(request.header_items())})
        return _FakeResponse(body)

    monkeypatch.setattr(providers.urllib.request, 'urlopen', fake_urlopen)
    return seen


_CANNED_JSON = json.dumps(
    {
        'choices': [{'message': {'content': 'one word'}}],
        'usage': {'prompt_tokens': 10, 'completion_tokens': 1, 'prompt_tokens_details': {'cached_tokens': 6}},
    }
).encode('utf-8')
_CANNED_SSE = (
    b'data: {"choices": [{"delta": {"content": "one word"}}]}\n'
    b'data: {"usage": {"prompt_tokens": 10, "completion_tokens": 1, "prompt_tokens_details": {"cached_tokens": 6}}}\n'
    b'data: [DONE]\n'
)


def _provider() -> OpenAIChatProvider:
    return OpenAIChatProvider('k', 'gpt-6.1-terra', base_url='https://api.aizzz.xyz/v1', stream=False)


def test_no_caller_key_means_the_body_carries_no_key(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p')
    assert 'prompt_cache_key' not in seen[0]['body']


def test_caller_does_not_invent_a_key_by_default() -> None:
    assert all(
        field is None
        for field in (_provider()._opener,)
    )
    assert _provider()._opener is None


def test_caller_can_opt_in_to_a_specific_key(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p', prompt_cache_key='football-os-knowledge')
    assert seen[0]['body']['prompt_cache_key'] == 'football-os-knowledge'


def test_stream_exposes_include_usage_and_no_key_by_default(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_SSE)
    p = OpenAIChatProvider('k', 'gpt-6.1-terra', base_url='https://api.aizzz.xyz/v1', stream=True)
    p.complete(system='sys', prompt='p')
    assert seen[0]['body']['stream_options'] == {'include_usage': True}
    assert 'prompt_cache_key' not in seen[0]['body']


def test_settings_default_applies_without_a_call_site(monkeypatch) -> None:
    monkeypatch.setattr(providers, 'settings', SimpleNamespace(openai_prompt_cache_key='project-default'))
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p')
    assert seen[0]['body']['prompt_cache_key'] == 'project-default'


def test_the_caller_key_wins_over_the_settings_default(monkeypatch) -> None:
    monkeypatch.setattr(providers, 'settings', SimpleNamespace(openai_prompt_cache_key='project-default'))
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p', prompt_cache_key='football-os-coach')
    assert seen[0]['body']['prompt_cache_key'] == 'football-os-coach'


def test_mock_still_answers_when_asked_for_a_key() -> None:
    result = MockLLMProvider().complete(system='sys', prompt='p', prompt_cache_key='football-os-coach')
    assert result.demo_mode is True


def test_a_proxy_is_kept_out_of_the_call_until_the_operator_sets_one() -> None:
    assert _provider()._opener is None

    warm = OpenAIChatProvider('k', 'gpt-6.1-terra', base_url='https://api.aizzz.xyz/v1', stream=False, proxy='http://127.0.0.1:7897')
    assert warm._opener is not None
    mapping = {scheme: url for handler in warm._opener.handlers for scheme, url in getattr(handler, 'proxies', {}).items()}
    assert mapping.get('http') == 'http://127.0.0.1:7897'
    assert mapping.get('https') == 'http://127.0.0.1:7897'
