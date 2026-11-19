"""One cache region per user per door, never one merged region for every session."""

from __future__ import annotations

from app.core.prompt_cache_scope import reset_prompt_cache_scope, scoped_prompt_cache_key, set_prompt_cache_scope
from app.providers import OpenAIChatProvider
from tests.test_provider_cache_key import _CANNED_JSON, _capture


def test_scope_suffixes_the_key_on_the_wire(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    provider = OpenAIChatProvider("k", "gpt-6.1-terra", base_url="https://api.aizzz.xyz/v1", stream=False)
    token = set_prompt_cache_scope("u-usr_abc123")
    try:
        provider.complete(system="sys", prompt="p", prompt_cache_key="football-os/knowledge-ask")
    finally:
        reset_prompt_cache_scope(token)
    assert seen[0]["body"]["prompt_cache_key"] == "football-os/knowledge-ask#u-usr_abc123"


def test_anon_shard_from_the_edge_suffixes_too(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    provider = OpenAIChatProvider("k", "gpt-6.1-terra", base_url="https://api.aizzz.xyz/v1", stream=False)
    token = set_prompt_cache_scope("anon")
    try:
        provider.complete(system="sys", prompt="p", prompt_cache_key="football-os/manual-ask")
    finally:
        reset_prompt_cache_scope(token)
    assert seen[0]["body"]["prompt_cache_key"] == "football-os/manual-ask#anon"


def test_unset_scope_passes_the_static_key_through(monkeypatch) -> None:
    seen = _capture(monkeypatch, _CANNED_JSON)
    provider = OpenAIChatProvider("k", "gpt-6.1-terra", base_url="https://api.aizzz.xyz/v1", stream=False)
    provider.complete(system="sys", prompt="p", prompt_cache_key="football-os/football-ws")
    assert seen[0]["body"]["prompt_cache_key"] == "football-os/football-ws"


def test_scoped_view_of_a_blank_key_stays_blank() -> None:
    token = set_prompt_cache_scope("u-usr_zzz")
    try:
        assert scoped_prompt_cache_key(None) is None
        assert scoped_prompt_cache_key("") == ""
    finally:
        reset_prompt_cache_scope(token)


def test_two_parallel_sessions_no_longer_interleave() -> None:
    token_a = set_prompt_cache_scope("u-usr_alpha00000001")
    key_a = scoped_prompt_cache_key("knowledge.deep_read.draft")
    reset_prompt_cache_scope(token_a)
    token_b = set_prompt_cache_scope("u-usr_beta00000002")
    key_b = scoped_prompt_cache_key("knowledge.deep_read.draft")
    reset_prompt_cache_scope(token_b)
    assert key_a != key_b
    assert key_a == "knowledge.deep_read.draft#u-usr_alpha00000001"
    assert key_b == "knowledge.deep_read.draft#u-usr_beta00000002"
