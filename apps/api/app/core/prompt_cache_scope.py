"""Per-request prompt-cache sharding for the gateway.

Multiple concurrent sessions hitting one gateway with one static `prompt_cache_key`
interleave their prompts in a single cache region, which is how a stable shared prefix
stops being stable: Codex threads its cache key per conversation, and this module does
the same per request — every address on this process that passes a `prompt_cache_key`
into `OpenAIChatProvider.complete()` gets it suffixed with the caller's shard.

Shard shape: `football-os/<feature>#u<user_id>` for authenticated traffic; anonymous
traffic gets `...#anon`. The suffix is not a secret and carries no PII (the public id
prefix, never the email), and unset scopes pass the key through unchanged so tests and
the demo door are untouched.
"""

from __future__ import annotations

import contextvars

#: Empty string inherits the plain static key (library tests rely on exactly that).
_scope: contextvars.ContextVar[str] = contextvars.ContextVar("prompt_cache_scope", default="")


def set_prompt_cache_scope(scope: str | None) -> contextvars.Token[str]:
    """Pin the cache shard for this request; the token restores the previous shard."""
    return _scope.set(scope or "")


def reset_prompt_cache_scope(token: contextvars.Token[str]) -> None:
    """Restore the shard that was active before `set_prompt_cache_scope` ran."""
    _scope.reset(token)


def scoped_prompt_cache_key(base: str | None) -> str | None:
    """The gateway gets the static key suffixed with the active shard, or the key unchanged."""
    if not base:
        return None or base
    scope = _scope.get()
    if not scope:
        return base
    return f"{base}#{scope}"


def current_scope() -> str:
    return _scope.get()
