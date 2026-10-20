# M11 §64 — Agent Evaluation Benchmark (verification record)

Spec §64 asks for an "agent evaluation benchmark" that covers 9 categories of agent capability and can be run whenever agent code changes. This unit lands that benchmark with golden test cases, measurable thresholds, and a gating test that fails the suite when quality slips.

## What shipped

| path | role |
| --- | --- |
| `apps/api/evals/golden_agent_benchmark.json` | 27 golden cases across 9 categories + 3 refusal controls |
| `apps/api/evals/run_agent_benchmark.py` | evaluation harness with metrics: answer_rate, avg_confidence, citation_integrity, refusal_accuracy, multi_step_completion, trace_integrity |
| `apps/api/tests/test_agents_benchmark.py` | 9 gating tests that import `evaluate()` and fail on threshold breach |

### Categories covered (per §64's list)

1. **Football Research** (3 cases) — tactical history, role explanations
2. **Player Comparison** (2 cases) — position contrasts, attribute trade-offs
3. **Match Analysis** (3 cases) — simulation engine mechanics, xG, limitations
4. **Training Plan** (3 cases) — skill improvement drills, load management
5. **Tactical Analysis** (3 cases) — formation characteristics, comparisons, concept explanations
6. **Scouting** (3 cases) — natural language player search with filters
7. **News Research** (2 cases) — transfer rumors, injury updates
8. **RAG Integration** (2 cases) — knowledge base queries requiring citations
9. **Multi-step Tool Use** (3 cases) — composite tasks chaining multiple agents

### Metrics and thresholds

| metric | gate | purpose |
| --- | --- | --- |
| overall_answer_rate | ≥ 0.80 | Agents must answer most questions |
| avg_confidence | ≥ 0.55 | Answers must carry meaningful confidence |
| citation_integrity | ≥ 0.90 | Citation quotes must be verbatim from chunks |
| refusal_accuracy | 1.0 | Out-of-scope questions must be refused |
| multi_step_completion | ≥ 0.75 | Composite tasks must execute expected agents |
| trace_integrity | 1.0 | Every composite run's stored trace must replay the steps its answer named (added 2026-10-20 with §33's stored trace — [evidence](M11_AGENT_TRACE_VERIFICATION.md)) |

## Measurements (current HEAD, corpus loaded)

* `tests/test_agents_benchmark.py`: **9 collected / 9 passed** (every threshold gate green).
* `python -m evals.run_agent_benchmark --json` on a **fresh, empty database** (temp SQLite, cold start): exit 0, `failures: []`.
* Total cases: **27** across 9 categories.
* Refusal cases: **3** (non-football question, live scores request, prediction request).

### Current performance

| metric | value | gate | status |
| --- | --- | --- | --- |
| overall_answer_rate | 1.0 | ≥ 0.80 | PASS ✅ |
| avg_confidence | 0.7684 | ≥ 0.55 | PASS ✅ |
| citation_integrity | 1.0 | ≥ 0.90 | PASS ✅ |
| refusal_accuracy | 1.0 | 1.0 | PASS ✅ |
| multi_step_completion | 1.0 | ≥ 0.75 | PASS ✅ |
| trace_integrity | 1.0 | 1.0 | PASS ✅ |

All six metrics pass their gates, both through the pytest gate (`evaluate()` with a real app/client) and through the standalone CLI entry point. The benchmark is a reliable quality gate, not a source of false failures.

**Measured 2026-10-20** (the run that added `trace_integrity`, against the seeded PostgreSQL database).
`avg_confidence` reads 0.7684 here against the 0.7724 recorded on 2026-10-07: the corpus and the world were
re-seeded between the two, and the golden cases' answers are recomputed from whatever is stored, so a
confidence mean is a reading of a database and not a constant. Both are above the 0.55 gate.

### Per-category breakdown (current HEAD)

| category | cases | answered | answer_rate | avg_confidence | topic_coverage |
| --- | --- | --- | --- | --- | --- |
| Football Research | 3 | 3 | 100% | 0.74 | 100% |
| Player Comparison | 2 | 2 | 100% | 0.49 | 80% |
| Match Analysis | 3 | 3 | 100% | 0.95 | 75% |
| Training Plan | 3 | 3 | 100% | 0.80 | 64% |
| Tactical Analysis | 3 | 3 | 100% | 0.85 | 64% |
| Scouting | 3 | 3 | 100% | 0.90 | 64% |
| News Research | 2 | 2 | 100% | 0.63 | 69% |
| RAG Integration | 2 | 2 | 100% | 0.68 | 69% |
| Multi-step Tool Use | 3 | 3 | 100% | 0.74 | 69% |

Every category answers 100% of its cases. `per_category_summary.avg_confidence` is a true mean within the category (a harness bug that divided the global confidence sum by each category's answered count — producing impossible values like 6.38 — was fixed).

### Bugs fixed (e00e87d)

Six bugs were preventing the benchmark from meeting its thresholds:

1. **ScoutAgent dict vs ORM confusion**: `candidate.player` raised AttributeError because search returns dicts, not ORM objects
2. **ScoutAgent waterfall key mismatch**: Code accessed `step['requirement']` but Step.to_dict() returns `'phrase'`, `'rows_in'`, `'rows_out'`
3. **TacticalAgent citation type error**: Integer `count` value violated response model's string requirement
4. **Composite endpoint missing research detection**: "research" keyword never matched because it was only set when no other agents triggered; added explicit keywords ("history", "evolution", "origin")
5. **RAG citation integer fields**: `Hit.citation()` returned int/float for ordinal/score/similarity; response model requires strings
6. **RAG citation ref overwrite**: `assemble_context()` replaced citation["ref"] string with integer index

Additionally, ResearchAgent gained fallback response generation for low-confidence RAG results, distinguishing time-sensitive queries from general knowledge gaps.

### Second-pass fixes (current HEAD)

The original unit left a follow-up owed; three more defects kept the gates red on a clean checkout:

1. **Empty-world prerequisites**: `evaluate()` used `TestClient(app)` without a lifespan, so `sync_world`/`sync_tactics`/`seed_catalogue` never ran on a fresh database — TacticalAgent fell to its 0.3 floor, ScoutAgent to its 0.5 no-matches score, CoachAgent answered "create your profile first" with confidence 0.0, and `avg_confidence` landed at 0.4948 (< 0.55). `evaluate()` now performs all three idempotent syncs and registers a benchmark player, so cold-start runs match warm-dev runs.
2. **CoachAgent difficulty rendering**: `TrainingDrill.difficulty` is an integer column (1/2/3), but the answer formatter called `.title()` on it — every Training Plan recommendation raised `AttributeError: 'int' object has no attribute 'title'` (0/3 answered). Rendering now maps ints to Beginner/Intermediate/Advanced and sorts numerically.
3. **Per-category average bug**: category confidence was computed from the global running sum, yielding impossible values (up to 6.38). Each category now averages only its own cases.

### Identified gaps (tracked, non-gating)

Case-level quality notes still appear in `per_category_summary.failures` (topic mismatches, per-case confidence floors such as `compare-strikers: confidence 0.30 below minimum 0.5`, missing "recommendation" keyword in some coach answers). These do not touch the six threshold gates; they are follow-up quality work.

### The gate file measures once (2026-10-20)

The eight cases each called `evaluate()`, so one gate file ran the whole 27-case benchmark eight times,
registered eight accounts, and let every case disagree with the report the next case read. The report is
now computed once per module and read by all nine cases; the module's warm wall time is 30.8s against 28.4s
before, because the seven extra evaluations were cheap repeats of a warm cache. What changed is that the
suite writes one account's worth of state instead of eight, and the ninth case re-runs the benchmark on
purpose to prove the scores are reproducible.

## Reproduce

```bash
# Run full benchmark suite
cd apps/api && python -m pytest tests/test_agents_benchmark.py -v

# Run single benchmark case
python -m evals.run_agent_benchmark --json

# Run specific metric test
python -m pytest tests/test_agents_benchmark.py::test_agent_benchmark_refusal_accuracy -v
```

## Maintenance rule

The benchmark is a gate, not a vibe. Whenever agent code changes:

1. Run `python -m pytest tests/test_agents_benchmark.py -v` — all 9 must pass.
2. If thresholds slip, treat it as a real regression (the harness provisions its own world/tactics/player data, so an empty dev database is no longer an explanation).
3. Case-level notes in `per_category_summary.failures` (topic wording, per-case confidence floors) are follow-up quality work, not gate failures.
