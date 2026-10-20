# M11 §33 — The stored orchestration trace (verification record)

`PLAN.md`'s Item 5 asked for §33's smallest composite task end to end — "an orchestrator, one
specialist, one tool call and a stored trace" — and to measure it against §64's benchmark before
adding a second agent. The orchestrator and the six specialists were already here. The trace was
not, and the item was not finished without it: `/agents/composite` returned its steps to the caller
and kept nothing, so a run that answered could not be audited afterwards, and the benchmark could
measure the answer while saying nothing about the run that produced it.

This unit lands the stored half, measures it, and records the run that produced the score.

## What shipped

| path | role |
| --- | --- |
| `apps/api/app/services/agents/traces.py` | the trace store: `store_trace` / `get_trace` / `list_traces` / `summary` |
| `apps/api/app/services/agents/base.py` | `record_tool_call()` and the per-agent `tool_calls` list |
| `apps/api/app/services/agents/orchestrator.py` | mints the trace id, records each step, stores the run |
| `apps/api/app/services/agents/{research,scout,tactical,coach}.py` | record the stores they touch |
| `apps/api/app/api/v1/agents.py` | `GET /agents/traces`, `GET /agents/traces/{trace_id}`; `trace_id` on the composite answer |
| `apps/api/app/services/door_codes.py` | `no_such_trace` registered at 404 |
| `apps/api/tests/test_agent_trace.py` | 5 gating cases for the stored half |
| `apps/api/evals/run_agent_benchmark.py` | the `trace_integrity` metric |
| `apps/api/tests/test_agents_benchmark.py` | 9 gating cases; the report is now measured **once** per module |
| `apps/web/app/agents/AgentConsole.tsx` | the answer names its trace, and each step says what it looked up |
| `apps/web/scripts/visual-qa.mjs` | two browser checks: the trace id, and the tool-call line |

## The three doors

`POST /api/v1/agents/composite` now answers with `trace_id` and `status` beside its steps, and two
doors read the run back:

- `GET /agents/traces` — this account's runs, newest first, one row each (`step_count`, `agents`,
  `tool_call_count`), no answer bodies.
- `GET /agents/traces/{trace_id}` — the whole run: the plan, every step's query, status, confidence,
  start and end stamps, duration, citation count, error, and the tool calls that step made.

Both are auth-gated and scoped to the caller. A trace that never existed, has expired, or belongs to
another account answers the same 404 (`no_such_trace`) — absence must not confirm which ids exist.

## Where a trace is stored, and why there

The trace is per-account agent state, so it lives on the tier §34 already built for that
(`agent_memories`), under the `orchestrator` agent type and a `trace:` key prefix, with a 30-day
TTL. A new table would have bought a migration and no property this does not already have: it is
user-scoped by construction, it expires like every other fragment, and `prune_expired` already
knows how to sweep it. The prefix is the boundary — a reader listing `/agents/context` sees the
traces and the orchestrator's ordinary memories side by side, and `traces.py` is where that
boundary is written down.

## The tool call is recorded, not inferred

A "tool call" here is a read or write against a store an agent does not own: the knowledge corpus,
the tactical catalogue, the player rows, the training catalogue, the scouting index. Each agent
records the call at the line where it makes it, with its arguments and whether it succeeded.

The agents whose answer is a static explanation — `simulation`, `video` — record **none**, and their
step's empty list is the honest reading: nothing was looked up. A trace therefore distinguishes
"answered from stored knowledge" from "answered from a canned explanation", which a step list of
agent names could not.

## The benchmark, measured

`python -m evals.run_agent_benchmark`, 2026-10-20, against the seeded database:

```
  [PASS] overall_answer_rate       1.0      gate >= 0.8
  [PASS] avg_confidence            0.7684   gate >= 0.55
  [PASS] citation_integrity        1.0      gate >= 0.9
  [PASS] refusal_accuracy          1.0      gate >= 1.0
  [PASS] multi_step_completion     1.0      gate >= 0.75
  [PASS] trace_integrity           1.0      gate >= 1.0
```

`trace_integrity` is the new metric and it is the one this item is about: the share of composite
runs whose stored trace replays the steps the answer named — same agents, same order, same tool
calls, same query. It is 1.0, and the gate is 1.0, because a rate below 1.0 means an answer exists
that no trace can account for, which is exactly the state §33 was in before this landing.

The harness now reads each composite run's trace back over HTTP and compares it with the answer.
That is the measurement Item 5 asked for: not "the benchmark still passes" but "the benchmark's
runs are accounted for".

### The gate file now measures once

`tests/test_agents_benchmark.py` had eight cases, each of which called `evaluate()` — so one gate file
ran the whole 27-case benchmark eight times, registered eight accounts, wrote eight sets of agent
memories, and let every case disagree with the report the next case read. The report is now computed
once per module and read by every assertion.

The wall time did not change much, and it is worth saying why rather than claiming a win: the seven
extra evaluations were cheap repeats of a warm cache. The module now takes **30.8s** warm — 23.6s
in the one cold evaluation, 6.0s in the deliberate second run that proves the scores are
reproducible — against 28.4s for the eight-run file. What changed is that the suite writes one
account's worth of state instead of eight, and the nine cases now read one report instead of nine.

## The run that produced the score

`POST /api/v1/agents/composite` with the §64 case `tactics-to-training` — *"Analyze our team's
pressing patterns and recommend training drills to improve them"* — and the trace it left:

```json
{
  "trace_id": "trc_g6AOAh69WNgnkfdq",
  "query": "Analyze our team's pressing patterns and recommend training drills to improve them",
  "status": "completed",
  "duration_ms": 1666,
  "confidence": 0.825,
  "answer_chars": 791,
  "plan": { "steps": ["coach", "tactical"] },
  "steps": [
    {
      "agent_type": "coach",
      "status": "completed",
      "confidence": 0.8,
      "duration_ms": 333,
      "citations": 0,
      "tool_calls": [
        { "tool": "players.profile",  "ok": true, "detail": "profile found" },
        { "tool": "training.drills",  "ok": true, "detail": "3 of 24 drills matched" },
        { "tool": "training.sessions","ok": true, "detail": "0 completed sessions" }
      ],
      "error": null
    },
    {
      "agent_type": "tactical",
      "status": "completed",
      "confidence": 0.85,
      "duration_ms": 1334,
      "citations": 1,
      "tool_calls": [
        { "tool": "tactics.systems", "ok": true, "detail": "50 systems" }
      ],
      "error": null
    }
  ]
}
```

Two specialists, four tool calls, one stored run. The order is the plan's: `coach` outranks
`tactical` because the plan's score is *share of a rule's keywords the query matched* — the query
says "training", "drills" and "improve" (3 of the coach rule's 8 keywords) and only "pressing" (1 of
the tactical rule's 8) — so the step that knows more about the question runs first.

The full trace, with every stamp and every argument, is what `GET /agents/traces/{trace_id}`
returns; the block above is that object with the answer body and the plan's context keys cut.

## The gates

| gate | what it holds |
| --- | --- |
| `tests/test_agent_trace.py` (5) | a run leaves one readable trace naming its agent, its tool calls and its timings; a foreign id and a never-issued id answer the same 404; the list door lists only the caller's runs and no answer bodies; a run where **every step failed** is still traced, with the error on each step; both doors are auth-gated |
| `tests/test_agents_benchmark.py` (9) | the six thresholds, including `trace_integrity == 1.0`; the report is reproducible across two runs |
| `tests/test_answer_census.py` | `no_such_trace` is registered at 404 and the raise site agrees with the table |
| `tests/test_openapi_contract_currency.py` (4) | the contract carries the two new doors (187 paths / 236 operations / 83 schemas) |
| `apps/web/scripts/visual-qa.mjs` | the console names the trace the answer came from, and every step says what it looked up |

The failed-run case is the one worth keeping: the orchestrator is fail-soft (a step that raises is
recorded and the run continues), which is right for answering and wrong for auditing if the audit
only sees the runs that worked. The trace is written after the run whether or not it worked.

## What this does not claim

- **Not a second source of truth.** The trace stores what the run *did*; it is never read to
  produce an answer. A stale trace cannot make an answer wrong — it can only make a claim about the
  past wrong, and it expires in 30 days.
- **Not a full agent-trace standard.** There is no span tree, no OpenTelemetry export, no
  cross-service propagation. M12's tracing tier is where that belongs, and this is a project-local
  record of one orchestrator's run.
- **Not every agent's store is instrumented.** `simulation` and `video` read nothing and record
  nothing; `research`'s corpus call, `scout`'s index query, `tactical`'s catalogue read and
  `coach`'s three reads are the four that are. An agent that starts reading a new store and does
  not record it would show a step with no tool calls, which reads as "nothing was looked up" —
  the trace's empty list is only as honest as the instrumentation, and that is stated here rather
  than implied.
- **Not a second agent.** Item 5 said to measure the smallest composite task *before* adding a
  second agent, and this unit did not add one: the six specialists are the six that were already
  here, and the multi-step cases in the golden set already route to two of them.
