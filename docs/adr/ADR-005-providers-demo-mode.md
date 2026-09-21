# ADR-005 — Provider abstraction with self-labelled DEMO MODE

- Status: Accepted · Relates to: §45–47, §62, §77, NEVER-DO list
- **Context**: No LLM/embedding/vision/data API keys exist on this host. The spec forbids both fake AI and a crashed product when a provider is missing.
- **Problem**: Ship AI-native features (Coach, analysis, RAG) with zero credentials, without ever presenting generated placeholder text as model output.
- **Options**: (a) block until keys exist; (b) hardcode canned responses; (c) `LLMProvider` interface with `MockLLMProvider` selected when `OPENAI_API_KEY`/`ANTHROPIC_API_KEY` absent, and a `demo_mode: true` field on every response.
- **Decision**: (c), plus a stronger rule for M1: the Coach's *recommendation logic is not an LLM at all*. `coach_engine` computes today's session from the player's attributes, goal, recent history, available time/equipment with transparent weighted rules; the LLM provider is only used for optional prose phrasing, and in DEMO MODE the phrasing is template-based and stamped `DEMO MODE`. Every response DTO carries `demo_mode`, `confidence` and `reasons[]`.
- **Consequences**: Quality is measurable without spend; swapping in a real model changes phrasing only, never the recommendation traceability. UI must render the `DEMO MODE` badge whenever `demo_mode === true` — enforced by a shared component, not per-page judgement.
