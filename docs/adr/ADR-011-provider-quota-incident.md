# ADR-011: the upstream quota incident — recorded, not argued

* `Status`: accepted · `Date`: 2026-11-16 · `relates to`: ADR-010, `app/providers/__init__.py`, `app/services/model_ledger.py::cache_hit_rate`, the wkapi.pro account behind `sk-4W8L…`

## Context

The user reported the LLM ledger showed `provider=mock`, `demo_mode=true`, `cached_tokens=0`,
`cache_reported=false` for virtually every coach call — "low cache-hit rate" in their words.
Diagnostics across one window:

1. Live HTTP probe (`apps/api/app/providers/__init__.py`, `_complete_stream` and the non-stream
   `_complete`) returned `HTTP 403` with the upstream `code` being `insufficient_user_quota`.
2. A direct reproduction with the provider's exact headers, retried across an hour, printed
   the same 403 with `剩余额度: ¥-0.000088`.
3. The provider fell back to `MockLLMProvider` for every single call. That is the correct product
   behaviour for an unreachable upstream — the arithmetic on the player's rows answers the
   question regardless of whether the model phrases the prose.
4. The `_http_failure_detail(...)` helper was added in this window: the log line now prints
   `code=403, reason=Forbidden, body=…insufficient_user_quota…` instead of a bare `HTTPError`.

## Decision

1. **No change to the LLM door.** The provider correctly falls back to mock on any upstream
   failure it cannot recover from. The coach drawer still answers; the ledger keeps the
   provider that answered (`mock` in this window).
2. **The cache-hit dashboard does not move** until the upstream quota is recharged.
   `cache_hit_rate` divides by `input_tokens` on `cache_reported=true` rows only — by design.
   Zero is the honest value: nothing reported from the paid provider this window.
3. **The cache-hit story is unchanged.** ADR-010 records what the gateway prints on warm
   repeats (~95–97%). That report is *of real 200 OK answers*; it is only measurable when
   the account holds credit.
4. **The 4.5k-stable-prefix design stays the contract.** Cold first-calls never cache;
   roughly half of all calls print no `prompt_tokens_details` at all. A user with a freshly
   topped-up account will see mediocre numbers on their first handful of asks before the
   warm-up settles. The ADR documents this so the next "cache-hit is very low" incident
   traces back to this one.

## Consequences

* Anyone asking whether this project caches correctly has the evidence: the warm-repeat
  measurements are preserved in ADR-010's Context section from 2026-11-16.
* Anyone asking why the dashboard says `provider=mock` will find this file before any code.
* This ADR is not a bug report. It is the evidence pair with ADR-010.
