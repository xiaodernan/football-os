---
id: prompt-caching
title: "Why warm prefixes win: the economics of cached prompts in a coaching product"
category: coaching
tags: [llm, cache, cost, prefix, token, gateway, streaming]
applies_to: [all]
difficulty: advanced
source: "FOOTBALL OS original editorial content — written for this project, no external text reproduced"
confidence: high
last_reviewed: 2026-11-17
---

## "do we pay for the same system prompt every time we ask"

A coaching agent sends a long, identical briefing with every user question — the persona, the ground rules, the citation contract, the exemplars of a good answer. Paying for all of that on every call would dominate the bill. Cached prompts are the mechanism by which a provider serves the identical prefix for a fraction of the input cost, and the entire art of an agent's economics is making the prefix stable enough to be served and the question small enough to be cheap.

## The prefix is the contract

What is cacheable is exactly what never changes between calls: the system message, the shape of the state envelope, the citation rules, the vocabulary the model is allowed to lean on. The question itself, the player's data, and today's snapshot are the suffix — the part that actually differs. Everything the product's coaching doors do on every press — the arithmetic already done, the warnings already decided, the ledger row already written — produces a prefix that is byte-identical from one ask to the next, by construction. A prefix built from fresh randomness, reordered keys, timestamps, or session-specific strings cannot be cached; cache-friendly design means the prompt is assembled deterministically, with the variable parts appended at the end.

## The provider's report is the only scoreboard

What a provider reports about cache behaviour — `cached_input_tokens`, sometimes reported only on streaming responses — is the one honest measurement. The gateway may answer "0 cached" on a cold call, or refuse to report at all, or report a percentage that means nothing at low call volumes. The discipline is to read the report on the same route the product uses, at repeat volume, and to claim only what is measured. A product honest about caching reports the ratio the gateway printed, never a ratio computed from the prompt's apparent size.

## Streaming is not a luxury feature

Some gateways only print cache usage on streaming responses; some print on neither. A product stuck estimating cache from call counts would diverge from the provider's own arithmetic. The reasonable engineering posture is: stream by default, send the usage flag with the stream, count `cached_input_tokens` from the stream's final event, and keep non-streaming as documentation of what it is — a path that prints nothing. The product's gateway does exactly this, and that is why the coach's answer envelope can report cache hits honestly rather than guess.

## Cache keys and invalidation

The cached prefix is the contract only if the key identifies the contract, not the question. Node-level caching generally keys on content hash; provider-level caching keys on prefix bytes, eligible after the first call writes the cache server-side. A cache key naming the team, the platform, or the feature is a design choice the provider makes; a product calling through one gateway wants its own hot-path prefix to hit the provider's cache, which means it wants determinism in the prefix, and it wants its own cache (the answer cache) to layer on top for repeats of identical questions.

## Measured in this product

The coaching doors on this product's gateway report `cached_input_tokens` on streaming calls through Clash Verge. On warm repeats of the Real Book's system prefix the gateway prints ~96–97% cached input tokens; on cold calls it prints nothing. The product's own answer cache coalesces repeated questions per key so two identical asks buy one phrasing, and the rate-limit middleware counts the same prefix against a shared budget. This chapter records the method; the live numbers are in the ledgers, not here.

## When this does not apply

A single static lookup — a calendar fetch at cron time, an unmodified rulebook excerpt — is free to be cache-naive; the overhead of cache-friendly prompt design is noise. A prompt composed freshly every time by design (audit prose that varies deliberately) will not and should not hit the provider's cache, and wrapping it in prefix logic only adds overhead. And a gateway that does not report cache usage renders all of this unmeasurable; the answer in that situation is to change the gateway's report, not to invent ratios.

## Evidence and its limits

This is the engineering description of one product's working assumptions — deterministic prefixes, stream-only usage reporting, a two-layer call structure (provider prefix cache below, answer cache above). It is not a benchmark of this provider against another, and the "~96–97%" figure is a warm-repeat observation from this host measured on this gateway, not a stable-token-marketing promise. The calculus changes with provider negotiations, prompt orders, and call volume, so the method — stream, read usage, aggregate honestly — is the durable part; the number is a snapshot.
