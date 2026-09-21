# AI_POLICY — FOOTBALL OS

## Epistemic rules (hard requirements on every AI surface)

1. **Estimate ≠ fact.** Model-derived values render with `AI-generated` + `Estimated` + confidence. Only stored provider/user data renders as fact.
2. **Simulation ≠ prediction.** Every simulated result is stamped `Simulation result is fictional / model-generated and should not be interpreted as a real-world prediction.`
3. **News**: answers separate `Fact` / `Analysis` / `Speculation`; a speculating sentence without that label is a bug.
4. **No medical claims.** Pain, concussion, head-injury or return-to-play questions are refused with a "consult a qualified medical professional" route; load prescriptions stay inside generic training guidance.
5. **Minors**: no maximal-intensity or contact-heavy prescriptions for youth profiles; the plan generator caps load by age band and refuses overrides.
6. **No fabricated data or citations.** If no source was retrieved, say so; a citation must resolve to a stored document row (spec §79).
7. **No hidden randomness in progression.** Attribute changes come from `XpEvent` rows with `reason` + `evidence_ids`; an LLM may never write an attribute (spec §8).

## Required UI contract

Every AI payload includes: `demo_mode`, `provider`, `model`, `confidence`, `reasons[]`, `sources[]`, `generated_at`. Rendering is centralised in `<AiBadge>`/`<SourceList>` so no page can drop the label.

## Provider behaviour

Real keys optional. Absent keys ⇒ `DEMO MODE` with template reasoning, self-labelled, never presented as a real model (ADR-005). Provider outage ⇒ fallback or `Provider unavailable`; the product degrades instead of inventing output (spec §77).

## Cost & safety accounting

`model_calls` ledger: provider, model, input/output/reasoning tokens, latency, estimated vs actual cost, success/error, user + feature tag. Per-user and global daily budgets with hard stop and a visible notice, cache-then-deduplicate-then-batch before any new spend (spec §76).

## Evaluation before shipping

Agent/RAG changes must pass the benchmark set (tool correctness, citation correctness, hallucination rate, retrieval quality, task completion, latency, cost) — spec §63–64. A failing gate blocks the merge, with the report attached to the PR.
