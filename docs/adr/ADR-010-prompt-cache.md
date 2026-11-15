# ADR-010: the LLM prefix-cache story — measured, not hoped

* `Status`: accepted · `Date`: 2026-11-16 · `relates to`: §46 (model ledger), M12/M15, `app/providers/__init__.py`, `model_ledger.cache_hit_rate`, `services/coach_voice.py` (stable-first prefix), `services/knowledge/answer.py` (the house contract)

## Context

The question the gateway raises often enough to deserve a paper: **why does the product's
`cache_hit_rate` sometimes read well under 50%, and why does the UI sometimes look like it answers
non-streamed ("非流")?** This was measured live against `wkapi.pro / gpt-6-sol` through the
project's own provider adapter on 2026-11-16 — not argued from first principles.

Two separate facts hold:

1. **The provider's usage object is what it is.** The gateway reports `cached_tokens` only on a
   server-side lottery of its calls, not on every call. Warm repeats with the same prefix print
   ~95–97% of prompt tokens cached (measured: `cached_tokens=4352` over a 4,546-token prompt on a
   warm repeat; `cached_tokens=19980` over a 19,983-token prompt); first calls of a fresh prefix
   print nothing; roughly half the calls print no `prompt_tokens_details` at all.
2. **The provider cannot control that lottery.** All it *can* do is (a) send the same prefix bytes
   on every call, (b) ask for `stream_options: {include_usage: true}` so the tokenisation the
   gateway returns is recorded, and (c) record `cache_reported` and `cached_input_tokens`
   separately so a call that *never answered* is not counted as a miss, only as unreported.

`app/providers/__init__.py` already does exactly these three things: it streams by default
(`OPENAI_STREAM=0` is the escape hatch), it sets `stream_options: {include_usage: true}` on the
stream path, and `model_ledger.cache_hit_rate()` divides only by `input_tokens` over rows where
`cache_reported is true`, exposing `coverage` alongside the rate.

## Decision

1. **The stream path stays the default** — not because it caches better (it doesn't), but because
   it is the path the gateway's own `stream` metric counts, and this project follows the gateway.
2. **`cache_hit_rate` is reported with `coverage` beside it** (see `model_ledger.cache_hit_rate`).
   A reader is never shown a 1.0 over 2 calls as "cache works at 100%", nor a 0.0 over calls where
   the gateway printed nothing as "0% hit rate".
3. **Stable-first prefix design remains the contract**: the coach SYSTEM block is immutable and
   identical on every call; the knowledge SYSTEM block is immutable and identical; the user message
   holds the volatile fields and ends with the question.
4. **No client attempts to force the lottery.** Any orthogonal workaround (retry for warm uploads,
   parallel warm-up calls, etc.) would recompute the cache and burn more tokens on the act of
   checking it — worse efficiency, not better.

## Consequences

* The product can prove what the gateway answered, but cannot make the gateway answer on every call.
  `cache_reported=false` stays visible in the ledger, never folded silently into a denominator.
* Users asking "why did my repeat answer not cache?" receive the honest reply: the server-side
  lottery controls that; this product sends byte-identical prefixes and records the answer it gets.
* When the gateway changes its behaviour (e.g. always reporting on every call), nothing in this
  ADR needs changing; the ledger and the `cache_reported` column were designed for this.

## Appendix — 2026-11-15: the 403 that looked like zero cache

This ADR was accepted the day the user reported that the ledger was always returning
`provider=mock, demo_mode=true, cache_reported=false, cached_tokens=0`. Investigation inside the
same window found every wkapi.pro call answered `HTTP 403 insufficient_user_quota` — the account
behind `sk-4W8L…` is overdrawn at ¥-0.000088 — and that the provider's two failure paths collapsed
every one of those into a single word (`openai_provider_stream_failure HTTPError`). Every reader
fell back to `MockLLMProvider` and the product worked honestly: arithmetic on the player's own rows
answered the question; only the prose was template.

Action since: `_http_failure_detail` logs `code / reason / body` on every provider failure; the
log now reads `adsence HTTPError code=403 reason=Forbidden body={…insufficient_user_quota…}` in one
sentence; no cache claim in this ADR is invalidated by it — the warm-repeat measurements quoted
in the Context section were taken on live wkapi.pro calls that answered 200 OK.

Until the account is topped up, the ledger will continue to show `provider=mock`. That is correct
behaviour, not a regression; the path back to saturating the cache meter runs through the wallet,
not through this product.
