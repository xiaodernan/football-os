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

1. **Substitutions.** **Done (2026-10-25):** the engine takes `substitutions: int = 0` and, when set,
   applies a deterministic, bounded fresh-legs bonus to each side's `midfield` and `attack` from a fixed
   minute via `dataclasses.replace` — no named-player swap, no shape change. Default `0` keeps the selected
   eleven on the pitch and the digest byte-identical (all existing determinism tests stay green); 4 new
   `TestSubstitutions` cases pin the contract. The parameter is plumbed end-to-end: `SimulateIn.substitutions`
   (0–11) → `run_simulation` → `MatchInputs` → stored on `SimulationMatch.substitutions` (migration `0037`,
   SQLite-safe nullable→backfill→NOT NULL, no `server_default` to avoid drift), surfaced in `row()` and
   `engine_description()`, and replayed through `replay_is_identical` so a stored match re-derives identically.
   **Pending:** the web `SimulatorForm` selector with `en`/`zh`/`zh-TW` keys (i18n, owned by the concurrent
   session's message set — slot after the current locale gates land).
2. **In-match tactical shift.** **Done (2026-10-25):** `MatchInputs` gains `tactical_shift_minute: int = 0`.
   From that minute the side trailing on goals pushes — a bounded, authored midfield (+12%) and attack (+10%)
   lift that recomputes `possession_share` and raises chance quality for the rest of the match, applied once
   through `dataclasses.replace`, naming no player and changing no shape. Default `0` never triggers it, so the
   digest is untouched unless a caller opts in; 4 new `TestTacticalShift` cases pin determinism, no-named-player,
   published factor, and digest change when a side is behind. Plumbed `SimulateIn.tactical_shift_minute` (0–120)
   → `run_simulation` → stored on `SimulationMatch.tactical_shift_minute` (migration `0038`) → exposed in `row()`
   and `engine_description()` → replayed through `replay_is_identical`. **Pending:** the web `SimulatorForm`
   control with `en`/`zh`/`zh-TW` keys (i18n).
3. **Momentum / form carry.** **Done (2026-10-25):** `MatchInputs` gains `home_momentum` / `away_momentum`
   (0..1, default 0). A side riding form gets a bounded, authored attack (+10%·m) and press (+10%·m) lift from
   kick-off, applied once through `dataclasses.replace` — no named player, no shape change, default 0 leaves the
   profile untouched so the digest is identical. 4 new `TestMomentum` cases pin default-clean, determinism +
   digest change, per-side-only boost, and the published factor. Plumbed `SimulateIn.home_momentum/away_momentum`
   → `run_simulation` → stored on `SimulationMatch` (migration `0039`, two Float columns) → exposed in `row()` and
   `engine_description()` → replayed through `replay_is_identical`. **Pending:** the web `SimulatorForm` controls
   (i18n).
4. **Career-linked development.** **Done (2026-10-25):** a player's attributes now *project* from the
   career's own rows — `development_view` sums each player's `career_appearances.minutes` across the whole
   career, folds in the world's `real_training_sessions` load (`effective_minutes = match_minutes +
   0.5·training_load_units`), and runs the deterministic, saturating curve in `development` toward that
   player's stored `potential` (`development_summary`). The result is recomputed from the rows on every
   read and **never written back** — the squad the rest of the page reads keeps its stored attributes, and
   `limitations()["carry_over"]` now says so in so many words. The curve is pure and pinned by
   `test_development.py` (7 cases: zero-minutes-unchanged, deterministic, monotonic-and-saturating,
   no-growth-at/above-potential, floor-read, summary before/after/delta); `TestDevelopment` in
   `test_career.py` pins the projection against a played career (delta = after − before, never lowers an
   attribute, never crosses potential from below) and the empty-career zero state. **Pending (not my call to
   unblock):** writing the developed attributes *back* to the squad — deferred because the shared Postgres is
   stuck at migration `0031` and cannot be advanced safely; the read-only projection is the honest, verifiable
   half that ships now. Web career view rendering of this block belongs to the concurrent i18n session.

*Gate:* the match report still pins `digest` equality for same seed/inputs; new branches get a probe arm;
`test_simulation.py` gains the substitution/momentum cases; `next build` + a `/simulate` walk stay green.

## Phase 2 — Career & finance depth

M6 shipped Career Mode, the market and the season ledger. What is intentionally shallow:

5. **Transfer windows.** Open/closed windows gate `POST /transfers`; a career tracks window state and
   rejects out-of-window moves with a published sentence.
6. **Contracts & wages.** **Read-only half done (2026-10-25):** the wage bill and budget were already
   recomputed from `career_squad_moves`/`career_wage_charges` (`wage_bill`, `budget_position`). Added
   `affordability_view` (market.py) composing them into a **wage runway** (`max(0, remaining ÷
   weekly_wage_committed)`, `None` when the bill is zero) and a **signing preview** (`signing_impact`:
   `fee_affordable = remaining − price ≥ 0`, the balance after the fee, the new wage bill and its new
   runway). Pure helpers `wage_runway`/`signing_impact` are pinned by `test_affordability.py`; the block is
   surfaced read-only on `career_view["affordability"]` and asserted in `test_career.py`. Everything is
   recomputed on the read — no stored counter. Also added **`budget_timeline`**: the running balance walked
   in round order from `career.budget`, cross-checked against each row's stored `budget_after`, with any
   disagreement counted (`test_transfers.py::TestLedger` pins it). That walk exposed a latent ordering bug:
   `ledger_of` sorted only by timestamp, so a round's move and wage charge written in the same instant could
   tie and be ordered arbitrarily, breaking the stored-balance invariant depending on write speed. Fixed by
   ordering a round's moves before its wage charge explicitly (the order they are actually written in).
   The per-listing "can I afford this" arithmetic is now on the wire too: `listing_row` carries a
   `signing` block (`fee_affordable`, `remaining_after_fee`, the new wage bill and its runway) computed by
   the same `signing_impact`, pinned by `test_transfers.py`. **Career-page rendering done (2026-10-27):**
   `components/CareerFinance.tsx` now renders `career_view["affordability"]` on `/career/{slug}` — the
   standing figures, the wage runway with the API's own formula, and the budget timeline row by row with
   each row's stored `budget_after` beside the recomputed balance and an agreement badge; a career with no
   ledger rows gets an explicit empty state. The page does no arithmetic of its own, and the zero-deal
   `signing` block is deliberately not printed (a preview at no fee and no wage states nothing). Verified
   on a production build: 31/31 checks on a career that signed one player and played two rounds (rows
   9,331,750 / 9,330,415 / 9,329,080, all agreeing; runway 6,988) and 9/9 on a zero-wage, empty-timeline
   career, in `en` and `zh`. Recorded in [M13_CAREER_FINANCE_VERIFICATION.md](M13_CAREER_FINANCE_VERIFICATION.md).
   **Transfers rendering done (2026-10-27):** each buying-board row now has an **After signing** cell —
   the balance verdict (`covered` / `over budget`), the balance the fee would leave (or how short it is),
   the new weekly bill and its runway (`no wage limit` when the signing would leave no wage obligation).
   The figures are the listing's own `signing` block; the page prints them and decides nothing. Verified
   on a production build over 12 listings on each side — a career with wages already on the books (all
   affordable) and a fresh 100,000-budget career (all 12 over budget, sign buttons disabled) — for
   **156/156** checks in `en` and `zh`, including each listing's four figures and the button state.
   **Pending:** a budget *ceiling* (a hard cap distinct from a balance).
7. **Youth academy outcomes.** Academy trainees graduate into the squad with attributes derived from
   their `Sessions`/`Reports` (M8 already stores the load); the graduation is a deterministic roll.
8. **Board expectations & relegation.** **Read-only half done (2026-10-25):** `board_view` (career.py)
   projects the season at the career's current pace — `projected = round(actual ÷ played × season_rounds)`,
   where the horizon is the challenge's window or a double round-robin over the competition's clubs — and
   marks each additive objective (wins / points / goal difference) `on_pace`; an unbeaten run is a streak,
   not a sum, so it is reported as it stands rather than extrapolated. Surfaced read-only on
   `career_view["board"]`, pinned by `TestBoard` in `test_career.py`. **Career-page rendering done
   (2026-10-27):** `components/CareerBoard.tsx` renders the block on `/career/{slug}` — the horizon and
   its source, both per-round paces, the three projected figures or an explicit "nothing projected yet",
   the on-track verdict, and one row per objective with target / so far / at this pace / on pace / off the
   pace / as it stands. Twenty-five keys per locale (population **3,657**, **3,612** translated; shared-key
   ceiling stays **234 bindings / 98 rows**). Verified on a production build: **93/93** checks across three
   careers — 3 rounds with all three row verdicts (projection 3 wins · 8 points · −5 GD, one target off
   pace), a never-played career (empty projection, unprojectable verdict), and a two-round career whose
   target is on pace — in `en` and `zh`. Recorded in
   [M13_BOARD_PROJECTION_VERIFICATION.md](M13_BOARD_PROJECTION_VERIFICATION.md). **Pending:** the pyramid
   move itself (promotion/relegation) needs a multi-tier league structure (see item 9).

*Gate:* the season ledger still sums from `sim_events` rows; a new door gets a route-citation entry;
isolation walk over any new tenant-scoped door.

## Phase 3 — World scale & structure

M3 seeded 20 teams / 300 players / 130 matches / 500 articles. A "very large" world needs a structure.

9. **League pyramid.** **Partially present (verified 2026-10-25):** `Competition.tier` exists and
   `api/v1/world.py` already computes a read-time `standings` table from `real_matches` (never a stored
   total). **Pending:** a second league tier in the generated world and the promotion/relegation move
   computed from that table at the season boundary — blocked by the same content expansion as item 11,
   which changes the world fingerprint and the `population-floor` baseline.
10. **Fixture calendar.** **Already implemented (verified 2026-10-25):** `world/builder.py` generates a
    deterministic double round-robin per league and a 7-game knockout per cup (`_round_robin`,
    `_league_fixtures`, `_cup_fixtures`, `_simulate`) from the world seed; `real_matches` is the result and
    the world fingerprint gate keeps it reproducible. No new work needed here.
11. **Content expansion.** More teams/players/competitions behind the existing `population-floor` gate so
    the catalogue never regresses; each addition is a seeded, fictional, fingerprint-stable generator.
12. **Real-structure simulation tie-in.** Career clubs play the generated fixtures; results feed the
    public world pages (M3) and the career ledger (M6) from the same rows.

*Gate:* `qa-population-floor` stays green; world seed fingerprint unchanged for equal seed; public
`/world/*` walks stay 200.

## Phase 4 — Performance & scale

13. **Read-path caching.** Cache the deterministic, seed-keyed world reads and the catalogue compiles;
    a cache key is the seed + version, so a coefficient bump invalidates cleanly.
14. **Query profiling.** **First fix landed (2026-10-27):** the career-detail finance block was reading the
    ledger several times per request — `budget_position` fetched `career_squad_moves` twice (once directly,
    once through `wage_bill`→`held_deals`), and `affordability_view` then had `budget_timeline` fetch both
    tables again. `held_deals`/`wage_bill`/`budget_position`/`budget_timeline` now take optional pre-fetched
    rows, and `affordability_view` fetches the ledger once and hands it to both. A `before_cursor_execute`
    test in `test_transfers.py` pins it at exactly one read of each table. **Second fix landed (2026-10-27):**
    `carry_over_view` read `career_appearances` twice (once via `appearances_as_of`, once for the full list),
    and `development_view` and `ledger_view`'s `_season_leaders` each read it again — five reads of the
    appearance table and three of `real_training_sessions` per career-detail read. `carry_over_view`,
    `development_view` and `ledger_view` now take pre-fetched `appearances`/`training`, and `career_view`
    fetches both once and hands them to all three (carry-over derives its round window from the same list).
    A `before_cursor_execute` test in `test_career.py` now pins appearances/training at exactly **1** each:
    the last read came from `next_fixture_brief`'s `squad_as_of`→`condition_map` (the career side's condition
    for its profile), and `condition_map`/`squad_as_of` now accept the pre-fetched rows too, so the whole
    detail read shares one fetch. **Third fix landed (2026-10-27):** the fixtures loop called `_team_slug`
    once per round (`select teams.slug … where teams.id = ?`), an N+1 over the season; the view now
    resolves every opponent's slug in one `where teams.id in (...)` batch, and a `before_cursor_execute`
    test pins it at no per-round slug reads. The consistency re-check was the same shape — `session.get(
    SimulationMatch, …)` once per fixture — and now reads every linked report in one batch, pinned by the
    same test class. The fixture list itself was also re-read by `head_to_head` and `ledger_view`; both now
    take the view's list, so `career_fixtures` is read once per detail read (pinned by a test). **Pending:** a
    full-scale profile (a league season) to decide whether an index is worth more than the plumbing.
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

- **Career-view depth, all read-only and recomputed from rows.** `development` (fixture minutes + training
  projected toward potential), `affordability` (wage runway + signing preview + budget timeline),
  `contracts` (the deal book: projected expiry from the stored terms, flagged inside a warning window, and
  explicitly not enforced — plus the squad's age profile and retirement flags from the stored ages),
  `board` (season pace projection against the objectives), `head_to_head`
  (this career's own record against the next opponent, from its fixtures and nothing else), and
  `next_fixture_brief` (the engine's own band measurements of the next fixture's two sides, side by side,
  with the delta — a comparison, not a forecast), and `highlights` (the season's story: biggest win, worst
  loss, longest winning and unbeaten runs, clean sheets, failed-to-score, and the home/away split — a
  retrospective read off the same fixture list, no extra query). Each has its own formula in the payload
  and its own tests; none writes a stored counter. `limitations()["projections"]` says all of them are read-only
  projections that change no stored attribute, expire no contract and trigger no board decision — the
  page's own statement of what it does not claim. A determinism test reads the whole view twice and asserts
  byte-identical JSON, so no block can quietly start inventing state.
- **The next opponent's two measurements are rendered (2026-10-27).** `components/CareerNextOpponent.tsx`
  reads `career_view["head_to_head"]` and `career_view["next_fixture_brief"]` on `/career/{slug}` in one
  panel: the never-met empty state or the meetings grid and table, the two sides' venue/formation/system/
  overall/form grid, the five-band table with signed deltas, and the stronger / weaker / level sentence
  the API's own lists select; the page formats numbers and does no arithmetic. Thirty-six keys per locale
  (population **3,712**, **3,667** translated; shared-key ceiling stays **234 bindings / 98 rows**).
  Verified on a production build: **23/23** checks across four careers (never-met all-weaker, all-stronger,
  mixed with a `0.000` level band, a two-meeting head-to-head) in `en` plus the mixed career in `zh`;
  a reverse control on the pre-change build shows none of the panel's strings. Recorded in
  [M13_NEXT_OPPONENT_VERIFICATION.md](M13_NEXT_OPPONENT_VERIFICATION.md). **Disclosed:** the
  level-in-every-band sentence has no reachable pairing in the generated world (0 of 190 measured), and
  the API's 60-second response cache can still serve the page a minute of pre-play data — queued as its
  own unit.
- **A write drops the answers it made false (2026-10-27).** The response cache's read-your-writes
  defect, measured live and closed: after a 2xx non-GET the middleware drops every cache entry keyed
  to the writing caller (`CacheTier.drop_identity`; the key's percent-encoded colon-free components
  make the identity suffix exact), while an anonymous write and a non-2xx write drop nothing. The
  shared Redis tier is never swept — it holds no private answer by RFC 9111 §3.5. Five unit tests, a
  five-arm mutation battery (control clean, zero extra reds), and a live leg: A's post-write read is a
  MISS of the new round, A's next read is a HIT of the *new* answer, B's warm entry survives. Recorded
  in [M13_READ_YOUR_WRITES_VERIFICATION.md](M13_READ_YOUR_WRITES_VERIFICATION.md).
- **The deal book is on the page (2026-10-28).** `career_view["contracts"]` (landed in `90739d7`) was
  published but unrendered and untyped. The career page now carries the contract book:
  `components/CareerContracts.tsx` prints each held deal's projected expiry, its "expiring" flag
  inside the 3-round warning window, the API's own basis string, and the squad's stored age profile
  with its bands and retirement risks — in all three locales. Signed one buy through a rival's
  release clause and one 2-round loan on a live career; 46/46 checks against the API's own response,
  plus the zero-deal career's empty branch. Recorded in
  [M13_CONTRACTS_PANEL_VERIFICATION.md](M13_CONTRACTS_PANEL_VERIFICATION.md).
- **Season leaders, with true per-90.** `ledger_view` now also names the top scorer, top xG, most-booked and
  best goals-per-90, and adds each player's appearance count and minutes from `career_appearances` so the
  per-90 is read from the minutes the rounds actually stored (no appearance minutes ⇒ no per-90, not a zero;
  the per-90 board ignores anyone under a 90-minute floor). Recomputed from the rows, pinned by
  `TestSeasonLeaders` in `test_sim_ledger.py`.
- **Off-host backup leg now runs and is gated.** `scripts/backup_db.sh` extracts
  `upload_backup_to_s3`; two gate tests in `apps/api/tests/test_dr_scripts.py` run the real script with
  stubbed `aws`/`pg_dump` to prove the off-host hop fires with the named bucket + `STANDARD_IA` and lands
  the artifact, and that an unset bucket performs no upload. Committed into the tree (carried by the
  concurrent session's push) and on `origin/master`.
