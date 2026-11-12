# ADR-007 — One limiter, one clock, one identity: a shared token bucket in front of a local one

- Status: Accepted (M15, 2026-11-12) · Relates to: ADR-001, ADR-006, §58, §88
- **Context**: `RateLimiter` in `app/core/security.py` has held a fixed window in a dict since M1 and its
  own docstring says "swap for Redis when horizontally scaled". The service plane added a second door
  (`services/edge`) with its own in-process bucket, so the product now has two ceilings that do not know
  about each other, and four uvicorn workers multiply the core's by four.
- **Problem**: A limit is a statement about *the caller*, and a per-process dict cannot make one. Three
  concrete failures follow from that: a caller that reconnects lands on another worker with a fresh
  budget; a fixed window admits `2 × limit` across its boundary, so the published `Retry-After` describes
  an interval the server does not honour; and the two doors count different identities, so a caller can be
  refused by one and admitted by the other in the same second.
- **Options**: (a) keep the dict and accept per-process limits; (b) `INCR`/`EXPIRE` a counter per window
  in Redis; (c) one Lua script holding a token bucket, evaluated on the Redis server, with the server's
  clock; (d) a stock gateway filter (`RequestRateLimiter`) at the edge only.
- **Decision**: (c), in both tiers.
  - **Algorithm**: a token bucket, because it admits `capacity + rate × t` over any interval, which is the
    property `Retry-After` promises. A fixed window does not have it.
  - **Atomicity**: read-refill-spend is one `EVALSHA`, so two workers cannot both spend the last token.
    The script is registered once per process and called by digest.
  - **Clock**: `redis.call('TIME')` inside the script. With N workers, a bucket stamped by whichever
    worker answered would refill at a rate that depends on the door the caller used; the server's clock
    is the only one every worker agrees on, and `elapsed` is clamped at zero so a replica whose wall clock
    is behind cannot mint tokens by travelling backwards.
  - **Memory**: a bucket expires at the instant it would have refilled to capacity, because from then on
    it carries no information — the state it holds is the state a missing key produces. That is a bound
    without evicting a live bucket, which is what the old limiter did (and which handed that caller a
    fresh budget).
  - **Identity**: credential digest first (`acct:`), then a forwarded address only from a configured
    trusted proxy (`fwd:`, left-most entry), then the socket's peer (`ip:`). The same three branches are
    implemented in Python (`app/core/rate_policy.py`) and Java (`CallerKey`), so a caller cannot be two
    different people depending on which tier judged it.
  - **Cost**: the local bucket is an *admission pre-filter* with the cluster's capacity. It can never
    refuse a request the cluster would admit (its capacity is not smaller), and once a caller has spent
    the burst it answers locally — so a flood reaches the shared store at the refill rate, not at the
    flood's rate. At the edge the same shape: `DistributedRateLimitFilter` (order +5) judges and stamps
    the exchange; `RateLimitFilter` (+10) steps aside rather than spending a second token.
  - **Degradation**: a store that is absent, slow (over the filter's budget) or broken resolves to the
    local bucket, and the response says `X-RateLimit-Scope: process`. Availability over strictness, but
    never silently: the scope header and the metrics door both name the tier that answered.
- **Consequences**: every request that reaches a priced door pays one Redis round trip when the store is
  up (sub-millisecond on a local instance; the shared tier is optional and off in tests). The published
  limit is per caller per door, not per process, and the number in `X-RateLimit-Remaining` is now the one
  the next request will be judged against. What this does not do: it is not a WAF and does not shape
  bandwidth; it prices requests, and a proxy that rewrites `X-Forwarded-For` from an untrusted peer is
  ignored by construction.
