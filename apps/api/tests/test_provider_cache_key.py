"""The provider never sends `prompt_cache_key` — by design (2026-11-20 policy).

Prefix-cache reuse is achieved by a single stable unkeyed prefix (charter + stable system
blocks) and streaming with `stream_options.include_usage=true`, so the gateway can
prefix-match across sessions without caller-supplied cache shards that fragment reuse.

`prompt_cache_key` remains accepted in call signatures for backward compatibility but is
ignored and never included in outbound request bodies.
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


def _provider(*, stream: bool = False) -> OpenAIChatProvider:
    return OpenAIChatProvider('k', 'gpt-6.2-sol', base_url='https://api.aizzz.xyz/v1', stream=stream)


def test_no_prompt_cache_key_is_sent_by_default(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p')
    assert 'prompt_cache_key' not in seen[0]['body']


def test_caller_supplied_prompt_cache_key_is_ignored(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p', prompt_cache_key='football-os-knowledge')
    assert 'prompt_cache_key' not in seen[0]['body']


def test_settings_prompt_cache_key_is_ignored(monkeypatch) -> None:
    monkeypatch.setattr(providers, 'settings', SimpleNamespace(openai_prompt_cache_key='project-default'))
    seen = _capture(monkeypatch, _CANNED_JSON)
    _provider().complete(system='sys', prompt='p')
    assert 'prompt_cache_key' not in seen[0]['body']


def test_stream_never_sends_prompt_cache_key_but_requests_usage(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_SSE)
    _provider(stream=True).complete(system='sys', prompt='p', prompt_cache_key='x')
    assert seen[0]['body']['stream_options'] == {'include_usage': True}
    assert 'prompt_cache_key' not in seen[0]['body']


def test_mock_still_accepts_prompt_cache_key_arg() -> None:
    result = MockLLMProvider().complete(system='sys', prompt='p', prompt_cache_key='football-os-coach')
    assert result.demo_mode is True


def test_a_proxy_is_kept_out_of_the_call_until_the_operator_sets_one() -> None:
    assert _provider()._opener is None

    warm = OpenAIChatProvider('k', 'gpt-6.2-sol', base_url='https://api.aizzz.xyz/v1', stream=False, proxy='http://127.0.0.1:7897')
    assert warm._opener is not None
    mapping = {scheme: url for handler in warm._opener.handlers for scheme, url in getattr(handler, 'proxies', {}).items()}
    assert mapping.get('http') == 'http://127.0.0.1:7897'
    assert mapping.get('https') == 'http://127.0.0.1:7897'


# 2026-11-21 live probe against gpt-6.2-sol on api.aizzz.xyz (scripts/probe_llm.py):
# a byte-identical stable system prefix reached ~95% cached_input_tokens on BOTH doors
# (stream 6206/6502 and non-stream 6206/6502). The cache hit is therefore driven by the
# stable unkeyed prefix, not by the transport. These two tests lock that in: a gateway that
# reports cached_tokens must be read identically whether the call streamed or not, otherwise
# the census under-reports one door's reuse and the "non-stream shows no cache" myth returns.
def test_stream_and_non_stream_parse_cached_tokens_identically(monkeypatch) -> None:
    streamed = _capture(monkeypatch, _CANNED_SSE)
    r_stream = _provider(stream=True).complete(system='sys', prompt='p')
    assert streamed[0]['body']['stream'] is True

    plain = _capture(monkeypatch, _CANNED_JSON)
    r_plain = _provider(stream=False).complete(system='sys', prompt='p')
    assert 'stream' not in plain[0]['body']

    assert r_stream.cached_input_tokens == r_plain.cached_input_tokens == 6
    assert r_stream.cache_reported is True and r_plain.cache_reported is True


def test_default_base_url_is_the_configured_gateway() -> None:
    from app.core.config import Settings
    # The provider appends /chat/completions, so the configured base must already carry /v1.
    assert Settings().openai_base_url.rstrip('/') == 'https://api.aizzz.xyz/v1'


# Live parallel-session probe 2026-11-21 (scripts/probe_parallel_cache.py, 4 concurrent sessions,
# gpt-6.2-sol via the aizzz gateway): the COLD wave of 4 simultaneous requests shared 46.8% cached
# tokens — 2 sessions hit a cold entry (2,651) while 2 warmed it (49,417); a one-time cold-start race.
# The WARM wave shared 88.8% — ALL FOUR sessions read the same 49,417/55,677 cached prefix, with no
# fragmentation and no mid-run drop. The gateway keys the cache on the prefix BYTES, not on a session
# id, which is why never sending `prompt_cache_key` (the tests above) makes parallel sessions converge
# on one entry instead of sharding it. The low-hit symptom was a cold race, not sessions "mixing up"
# the cache; a stable unkeyed prefix is the correct and sufficient fix.
def test_unkeyed_prefix_is_what_lets_parallel_sessions_share_one_entry(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_SSE)
    # Two independent provider instances ("sessions") with the same system prefix.
    _provider(stream=True).complete(system='the-same-stable-prefix', prompt='p')
    _provider(stream=True).complete(system='the-same-stable-prefix', prompt='p')
    assert all('prompt_cache_key' not in s['body'] for s in seen)
    assert all(s['body']['messages'][0]['content'] == 'the-same-stable-prefix' for s in seen)
