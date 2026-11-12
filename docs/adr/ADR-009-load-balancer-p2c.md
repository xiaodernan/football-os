# ADR-009 — power of two choices for `lb://football-core`, with exploration and decay

- Status: Accepted (M17, 2026-11-12) · Relates to: ADR-007, ADR-008, §47, §75
- **Context**: The edge resolves `lb://football-core` through Eureka and, until this slice, let Spring
  Cloud's default `RoundRobinLoadBalancer` choose the instance. Round robin is correct while every
  instance is equally good, and the deployment this product describes is not that: the core is a Python
  process whose latency moves with the query it is serving, the size of the table it touches, and whatever
  else the machine is doing. A rotation is a fixed permutation; it cannot see any of that.
- **Problem**: Tail latency under partial degradation. With two instances and one of them at three times
  the latency of the other, every caller pays the degraded latency on half of its requests — and the edge
  has no way to notice, because the only per-instance fact it kept was "registered".
- **Options**:
  - (a) **Least connections.** The classic repair, and it fails in a specific way here: HTTP requests
    through a gateway are short, so the in-flight count is 0 or 1 almost always, which makes the signal
    noise; and a freshly started instance at zero connections attracts every request at once.
  - (b) **Weighted round robin from configuration.** A human assigns weights and forgets them. This is an
    opinion about capacity, not a measurement of health, and it cannot react to a GC pause.
  - (c) **Power of two choices over measured latency.** Draw two instances at random, keep the one with
    the lower moving average. Randomness prevents a herd; the comparison finds the better of any pair.
  - (d) **A service mesh.** Correct, and a second control plane, a second proxy and a second thing to
    operate. The gateway is already in the path.
- **Decision**: (c), with two corrections that the implementation proved necessary.
  1. **The score is latency plus failure, decayed by age.** `InstanceStats` keeps one EWMA per instance
     (`edge.lb.ewma-alpha`, default 0.3) and a consecutive-failure streak. A failing instance is not
     merely slow — a 5 ms connection refusal would beat a healthy 60 ms answer — so `failStreak` adds
     `penalty × target` to the score until the instance answers once. And a sample older than
     `edge.lb.stale-after-ms` (30 s) is blended back toward the target, because memory that never expires
     is a decision made by a number from an hour ago.
  2. **Five percent of draws ignore the score.** This is not a hedge for its own sake; it is what makes
     the loop open. See the first consequence below.
- **Consequences**:
  - **The closed loop is real, and it was measured.** A stub core whose first exchange cost 298 ms — cold
    connection pool, uncompiled path — was scored at 124 against the other core's 62. Power of two then
    never chose it again, so its average never corrected, so it was never chosen: **1 request in 40** while
    the statistics said the fast instance had answered 35 times. Exploration plus decay is the fix, and
    the integration test asserts the behaviour (≥ 28 of 40 to the fast core) rather than the arithmetic.
  - **The gateway's terminal signal is not a verdict.** The first response-path filter skipped every
    cancellation as "the caller left", which is what a cancellation means in ordinary Reactor. In the
    gateway the response body is written by Netty and the routing chain terminates by cancelling its
    upstream, so *every successful proxied exchange* arrives as `SignalType.CANCEL`. Forty of forty
    samples were dropped and the measurement came back 21 of 40 — round robin wearing a new name. The
    status code, not the signal, separates a finished answer from an abandoned one.
  - The policy is inspectable at `GET /edge/lb`: strategy, and per instance the score the decision used,
    the EWMA behind it, the failure streak, the observation count and the sample's age, worst first.
  - The configuration class lives in `os.football.lb`, outside `@SpringBootApplication`'s scanned package,
    so it is instantiated per service by Spring Cloud rather than globally by component scan.
    `edge.lb.strategy=round-robin` restores the stock balancer, which is what makes this deployable.
- **Alternatives rejected**: A custom `ServiceInstanceListSupplier` that reorders the list would still let
  round robin reach the slow instance every Nth request; a filter that rewrites the chosen URL after the
  fact fights the load-balancing filter for the same attribute. Neither can express "compare two".
- **Evidence**: `P2cChoiceTest` 7/7 (greedy draws never pick the slower of three; a failing instance loses
  to a healthy one; a single recovery restores it; decay returns an old sample to neutral),
  `EdgeP2cRoutingTest` 1/1 through a real gateway with two stub cores, and the edge suite green.
