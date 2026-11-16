"""The provider must shard the gateway's prompt cache, or nobody's cache hits warm.

2026-11 (the aizzz.xyz / gpt-6.1-terra swap and the wkapi.pro era before it): the ledger
showed cache-reported tokens at zero across every call, and the operator's read on the
gateway's dashboard was that streams fare better. The cacheable surface here is the fixed
system prefix; the knob that makes a gateway route identical prefixes to the same cache
shard is `prompt_cache_key`. These tests pin the wiring rather than the provider's price
sheet: the key is sent on both lanes (stream and non-stream), is absent when nothing asked
for one, and the explicit call-site lane wins over the process default.
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


def test_non_stream_sends_the_call_site_cache_key(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    provider = _provider()
    provider.complete(system='sys', prompt='p', prompt_cache_key='football-os-coach')
    assert seen[0]['body']['prompt_cache_key'] == 'football-os-coach'


def test_non_stream_omits_the_key_when_nobody_asked(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    provider = _provider()
    provider.complete(system='sys', prompt='p')
    assert 'prompt_cache_key' not in seen[0]['body']


def test_stream_sends_the_call_site_cache_key(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_SSE)
    provider = OpenAIChatProvider('k', 'gpt-6.1-terra', base_url='https://api.aizzz.xyz/v1', stream=True)
    result = provider.complete(system='sys', prompt='p', prompt_cache_key='football-os-knowledge')
    assert seen[0]['body']['prompt_cache_key'] == 'football-os-knowledge'
    assert seen[0]['body']['stream_options'] == {'include_usage': True}
    assert result.cached_input_tokens == 6


def test_the_settings_default_applies_without_a_call_site(monkeypatch) -> None:
    monkeypatch.setattr(providers, 'settings', SimpleNamespace(openai_prompt_cache_key='project-default'))
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p')
    assert seen[0]['body']['prompt_cache_key'] == 'project-default'


def test_the_call_site_wins_over_the_settings_default(monkeypatch) -> None:
    monkeypatch.setattr(providers, 'settings', SimpleNamespace(openai_prompt_cache_key='project-default'))
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p', prompt_cache_key='football-os-coach')
    assert seen[0]['body']['prompt_cache_key'] == 'football-os-coach'


def test_mock_accepts_the_call_site_key() -> None:
    result = MockLLMProvider().complete(system='sys', prompt='p', prompt_cache_key='football-os-coach')
    assert result.demo_mode is True


def test_a_proxy_is_kept_out_of_the_call_until_the_operator_sets_one() -> None:
    cold = _provider()
    assert cold._opener is None

    warm = OpenAIChatProvider('k', 'gpt-6.1-terra', base_url='https://api.aizzz.xyz/v1', stream=False, proxy='http://127.0.0.1:7897')
    assert warm._opener is not None
    mapping = {scheme: url for handler in warm._opener.handlers for scheme, url in getattr(handler, 'proxies', {}).items()}
    assert mapping.get('http') == 'http://127.0.0.1:7897'
    assert mapping.get('https') == 'http://127.0.0.1:7897'
