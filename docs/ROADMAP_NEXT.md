# ROADMAP_NEXT — FOOTBALL OS long-term trajectory

Status check (2026-10-24): M0–M12 are all **verified**. The i18n quality suite is **complete** across
`en` / `zh` / `zh-TW` (literals, ICU coverage + message parsing, placeholder parity, key-drift,
locale-completeness, locale-content, locale-formatting, locale-tokens, namespace-ownership,
plural-select, population-floor, shared-key, token-drift, translation-freshness, unused-keys,
api-strings, field-labels — `qa-translation-quality.mjs` is the last one still in flight). The
deterministic match engine (`possession-block-v1`) is exhaustively pinned (determinism, transparency,
disclaimer, "what it does not model"). The off-host backup leg now actually runs and is gated.

So the product is feature-complete through its first twelve milestones plus a hardened, multilingual
shell. The "very large final goal" is no longer *more milestones* — it is **depth, scale and finish**:
turn the verified skeleton into a deep, believable, performant football club management game that a
player can live inside for a career.

Every phase below follows the house rules already proven across M0–M12:

- a feature does not "land" until it is **running, tested and visually verified** on a production build;
- **every figure is recomputed at read time from the row it reports on** — no cached aggregates that can drift;
- **the engine stays deterministic** (one `WorldRng`, same seed ⇒ same digest);
- **no 403 where absence suffices**, **no 400 fall-through** — answers come from the one registered table;
- **gates are real**: a new behaviour gets a test, and a new gate gets a baseline, before the branch closes.

---

## Phase 1 — Gameplay realism (the heart of a football sim)

The engine's own `model["what_it_does_not_model"]` names the two biggest realism gaps. Closing them is
the single highest-leverage work.

1. **Substitutions.** **Engine landed (2026-10-24):** `simulate_match` takes `substitutions: int = 0`
   and, when set, applies a deterministic, bounded fresh-legs bonus to each side's `midfield` and `attack`
   from a fixed minute via `dataclasses.replace` — no named-player swap, no shape change. Default `0` keeps
   the selected eleven on the pitch and the digest byte-identical (all existing determinism tests stay
   green); 4 new `TestSubstitutions` cases pin the contract. **Pending:** plumb `substitutions` through
   `SimulateIn` → `service` → `MatchInputs` and store it on `SimulationMatch` (a migration) so a replay with
   subs re-derives the same report; the web `SimulatorForm` then gets a selector with `en`/`zh`/`zh-TW` keys.
2. **In-match tactical shift.** Let a formation change at a minute boundary move possession share and
   chance quality, tracing the new multipliers into `report["model"]["factors"]` exactly as today.
3. **Momentum / form carry.** A side on a win streak gets a bounded, documented edge; the edge is a
   coefficient, not a fitted curve, and is printed with its formula.
4. **Career-linked development.** Player attributes drift across a career's fixtures from minutes played
   and session completion, so a squad you develop actually changes — recomputed from the career's own rows.

*Gate:* the match report still pins `digest` equality for same seed/inputs; new branches get a probe arm;
`test_simulation.py` gains the substitution/momentum cases; `next build` + a `/simulate` walk stay green.

## Phase 2 — Career & finance depth

M6 shipped Career Mode, the market and the season ledger. What is intentionally shallow:

5. **Transfer windows.** Open/closed windows gate `POST /transfers`; a career tracks window state and
   rejects out-of-window moves with a published sentence.
6. **Contracts & wages.** A wage bill per club, a budget ceiling, and a "can I afford this signing"
   arithmetic that the scout already reasons over — make it a stored, recomputed figure.
7. **Youth academy outcomes.** Academy trainees graduate into the squad with attributes derived from
   their `Sessions`/`Reports` (M8 already stores the load); the graduation is a deterministic roll.
8. **Board expectations & relegation.** A season target (points / position) and a pyramid move at the
   ledger boundary, both read from the season's own `sim_events` rows.

*Gate:* the season ledger still sums from `sim_events` rows; a new door gets a route-citation entry;
isolation walk over any new tenant-scoped door.

## Phase 3 — World scale & structure

M3 seeded 20 teams / 300 players / 130 matches / 500 articles. A "very large" world needs a structure.

9. **League pyramid.** Multiple divisions with promotion/relegation computed from the fixture table the
   engine already produces; the table is a read-time aggregation, never a stored total.
10. **Fixture calendar.** A deterministic season schedule (round-robin + cup) generated from the world
    seed, reproducible across both databases.
11. **Content expansion.** More teams/players/competitions behind the existing `population-floor` gate so
    the catalogue never regresses; each addition is a seeded, fictional, fingerprint-stable generator.
12. **Real-structure simulation tie-in.** Career clubs play the generated fixtures; results feed the
    public world pages (M3) and the career ledger (M6) from the same rows.

*Gate:* `qa-population-floor` stays green; world seed fingerprint unchanged for equal seed; public
`/world/*` walks stay 200.

## Phase 4 — Performance & scale

13. **Read-path caching.** Cache the deterministic, seed-keyed world reads and the catalogue compiles;
    a cache key is the seed + version, so a coefficient bump invalidates cleanly.
14. **Query profiling.** The career/season aggregates are read-time sums today; profile them at scale
    (a full league season) and add the minimal index/query fix if a walk shows drift.
15. **Load envelope.** A recorded load test (concurrent career sims) with a published ceiling; the
    M12 cost/rate-limit work already gives the scaffolding.

*Gate:* load test exits within the published envelope; `next build` + API suite stay green on both legs.

## Phase 5 — Product finish

16. **Onboarding.** A first-run path that creates a player → joins/creates a club → runs a match, reusing
    the M1 vertical slice but inside the M8 club OS.
17. **Accessibility & mobile.** The walk checks already run mobile viewports; lift the remaining
    contrast/focus/aria findings to green and keep them green via a gate.
18. **More surfaces.** Remaining read-only pages (academy public view, scout public report) rendered from
    the same live reads the private doors use.

*Gate:* `visual-qa.mjs` gains the new flows; `npm run lint` + `tsc --noEmit` clean.

## Phase 6 — Operational maturity

19. **Trace dashboards.** The M12 OTEL/`request_spans` store is an operator window; a minimal read-only
    dashboard over it (slowest paths, error rate by route) reuses the existing trace door's RBAC.
20. **Runbooks.** A one-page runbook per M12 subsystem (backup/DR, erasure, rate limits, tracing) drawn
    from the verification docs already written.
21. **Cost guardrails.** The provider abstraction (M0) + M12 cost work get a published monthly ceiling
    alert, not just a rate limit.

*Gate:* each runbook cites the door it documents (§83 pattern); the cost ceiling is a tested boundary.

---

## How this plan is executed

- One phase at a time; a phase does not "open" until the previous one is running, tested and verified
  (the §96 rule from ROADMAP.md).
- Each numbered item is its own small, pathspec'd commit with a verification note; the i18n gates and the
  existing suite are never broken by a feature branch.
- The concurrent session that owns the i18n suite (`qa-translation-quality.mjs` and friends) is not
  disturbed: features land in `apps/api/app/services/simulation`, `world`, `club`, and the new web flows,
  not in `apps/web/scripts/qa-*.mjs` or `messages/*.json` unless an item explicitly touches i18n.

## Completed this session (evidence)

- **Off-host backup leg now runs and is gated.** `scripts/backup_db.sh` extracts
  `upload_backup_to_s3`; two gate tests in `apps/api/tests/test_dr_scripts.py` run the real script with
  stubbed `aws`/`pg_dump` to prove the off-host hop fires with the named bucket + `STANDARD_IA` and lands
  the artifact, and that an unset bucket performs no upload. Committed into the tree (carried by the
  concurrent session's push) and on `origin/master`.
