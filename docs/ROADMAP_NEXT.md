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
   **Done (2026-10-27):** the web `SimulatorForm` carries the substitution select with `en`/`zh`/`zh-TW` keys.
   The select offers 0 and 1 rather than 0–11 because the engine distinguishes only on/off — any count above
   zero plays the same single lift — and an in-place note says so; the API keeps its wider range for callers
   that store a manager's intent. Measured on `:8731` / `opp.db`: the default replay is byte-identical
   (`a9c43d63…` twice), `substitutions: 1` moves the digest to `4412ff05…`, records one fresh-legs lift per side
   at 54' naming no player, and the stored row echoes the count. The rendered page was checked in `en` and `zh`
   (17/17 assertions, no `MISSING_MESSAGE`).
2. **In-match tactical shift.** **Done (2026-10-25):** `MatchInputs` gains `tactical_shift_minute: int = 0`.
   From that minute the side trailing on goals pushes — a bounded, authored midfield (+12%) and attack (+10%)
   lift that recomputes `possession_share` and raises chance quality for the rest of the match, applied once
   through `dataclasses.replace`, naming no player and changing no shape. Default `0` never triggers it, so the
   digest is untouched unless a caller opts in; 4 new `TestTacticalShift` cases pin determinism, no-named-player,
   published factor, and digest change when a side is behind. Plumbed `SimulateIn.tactical_shift_minute` (0–120)
   → `run_simulation` → stored on `SimulationMatch.tactical_shift_minute` (migration `0038`) → exposed in `row()`
   and `engine_description()` → replayed through `replay_is_identical`. **Done (2026-10-27):** the web
   `SimulatorForm` carries the shift-minute input (0–120, 0 = never) with `en`/`zh`/`zh-TW` keys and an inline
   range error. Measured on `:8731`: at seed `12345` a side leads 2–0 after 60', and `tactical_shift_minute: 60`
   moves the digest `a9c43d63…` → `41edeef6…`, records exactly one shift at minute 60 naming no player, while
   `130` is refused `422`. The page states the rule in place: the shift pushes only the side that trails at that
   minute.
3. **Momentum / form carry.** **Done (2026-10-25):** `MatchInputs` gains `home_momentum` / `away_momentum`
   (0..1, default 0). A side riding form gets a bounded, authored attack (+10%·m) and press (+10%·m) lift from
   kick-off, applied once through `dataclasses.replace` — no named player, no shape change, default 0 leaves the
   profile untouched so the digest is identical. 4 new `TestMomentum` cases pin default-clean, determinism +
   digest change, per-side-only boost, and the published factor. Plumbed `SimulateIn.home_momentum/away_momentum`
   → `run_simulation` → stored on `SimulationMatch` (migration `0039`, two Float columns) → exposed in `row()` and
   `engine_description()` → replayed through `replay_is_identical`. **Done (2026-10-27):** the web
   `SimulatorForm` carries one range control per side (0.00–1.00, step 0.05, default 0) with `en`/`zh`/`zh-TW`
   copy and a note naming the ten-per-cent edge. Measured on `:8731` at seed `12345`: `home_momentum: 1` moves
   the digest `a9c43d63…` → `41268c21…`, `away_momentum: 1` moves it to `d51abf66…`, the two sides' rows differ
   from each other, and every row echoes its own `home_momentum` / `away_momentum` into the stored report; the
   rendered page was checked in both locales (26/26 assertions, no `MISSING_MESSAGE`).
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

5. **Transfer windows.** **Done (2026-10-27):** `market.transfer_window()` reads the career's next round
   (`rounds_played + 1`) against the season's two published windows — rounds 1–4 and three rounds around
   the midpoint (`mid ± 1`, `mid = floor(season_rounds ÷ 2)`), clipped to the season and merged where they
   overlap — with `season_rounds` taken from `career.season_horizon` (a challenge's window, else the
   competition's double round-robin). Rounds group into seasons of that length, so a career past round
   `season_rounds` is judged against the next season rather than locked out. A closed window answers
   `transfer_window_closed` (409) from `transferable()` and therefore from `open_market`, `negotiate`,
   `buy`, `loan`, `sell` and `release`; the refusal carries the round, the season's length and
   `opens_in_rounds`. `market_view()` now publishes `window` beside `transfers_allowed` and
   `RULES["window"]` = `WINDOW_FORMULA`. **Measured:** on the test world's five-club competition
   (`season_rounds = 8`) the windows merge to rounds 1–5 and rounds 6–8 are closed; a 34-round season
   publishes `[(1, 4), (16, 18)]`. `tests/test_transfers.py` grows `TestTransferWindow` (6 tests) and
   `tests/test_transfers_api.py` proves the wire: `GET` prints `window.state="closed"` at round 6,
   `POST /market` answers 409 `transfer_window_closed` with `opens_in_rounds = season_rounds − 5`.
   `pytest tests/test_transfers.py tests/test_transfers_api.py tests/test_answer_census.py
   tests/test_challenges.py tests/test_scout_transfer_sim.py tests/test_career.py tests/test_carry_over.py`
   all green. Not yet surfaced as its own panel on `/career/[slug]/market`; the blocked-tools notice
   already prints the refusal sentence. Next: the window block on the page, and a window that spans
   several rounds of real fixtures.
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
7. **Youth academy outcomes.** **Career-domain block done (2026-10-28):** `career_view["academy"]`
   (`academy_view` in `simulation/academy.py`) reads the career's under-21 squad players and judges
   each against the eleven the engine's own selection picks from the career's current squad (the
   transfer overlay applied, the career's system formation or the team's own) — `selected`,
   `next_in_line` (band rank = seats + 1), or `off_the_pace` at band rank — and projects the stored
   overall toward the stored potential with the same curve the `development` block runs, via the new
   scalar `developed_overall`. Pinned by `TestAcademyBlock` plus 8 pure cases in
   `test_academy_outcomes.py`, green on both database legs (11 + 38 SQLite, 49 PostgreSQL). Two
   re-scopes are published on the wire rather than silently taken: **the M8-tenant bridge is
   deliberately not built** (M8's academy tier hangs off user-created organizations, the demo world
   seeds none, and no door writes an org↔career link — inventing one is a migration with its own
   door, not this block's assumption), and **the graduation is measured, not drawn** (a "deterministic
   roll" is a contradiction; a roll would break the replay identity the career mode's determinism
   guard owns, so the block measures the engine's own selection instead). Recorded in
   [M13_ACADEMY_OUTCOMES_VERIFICATION.md](M13_ACADEMY_OUTCOMES_VERIFICATION.md). **Pending:** the
   career page's panel (types, `CareerAcademy.tsx`, three locales, shipped-build walk).
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
    take the view's list, so `career_fixtures` is read once per detail read (pinned by a test). **Profiled
    (2026-10-28):** a detail read on a 2-round career and on a 4-round career issues the *same* number of
    SELECTs — the view is O(1) in rounds, not O(N) — so no index is needed on this path; the per-table batch
    reads above are the whole cost.
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

19. **Trace dashboards.** **Backend done (2026-10-28):** `GET /api/v1/traces/summary` (admin, the same
    `TRACE_STANDING` as the detail door) reads the `request_spans` store over a window (`window_minutes`, 1–1440,
    default 60; `limit` caps the scan and `truncated` says when it bit) and publishes, per route, the span count,
    error count and rate, and nearest-rank p50/p95/max — grouped by `attributes.http.route` (else the span name),
    SERVER spans only, error = `status == ERROR` or `http.status_code ≥ 500`. Declared before `/{trace_id}` so
    `summary` is a door, not a trace id. `span_store.route_summary` + `ROUTE_SUMMARY_FORMULA`; pinned by
    `TestTheSummary` in `test_trace_store.py`. **Pending:** the Web panel over this door.
20. **Runbooks.** A one-page runbook per M12 subsystem (backup/DR, erasure, rate limits, tracing) drawn
    from the verification docs already written.
21. **Cost guardrails.** **Monthly ceiling done (2026-10-28):** `settings.ai_monthly_ceiling_usd`
    (`AI_MONTHLY_CEILING_USD`, `0` = not configured) and `cost_advisor.monthly_state()` — month-to-date spend
    since the first instant of the UTC month, the ceiling, remaining, used_pct, a pace projection to month end,
    and `exceeded` / `projected_over`. `recommend()` publishes it as a `monthly` block and adds a
    `monthly_ceiling` recommendation when a ceiling is configured and the month is over or projected over; with
    no ceiling it says so rather than inventing one. Pinned by `TestMonthlyCeiling` and the door's key-set
    assertion. **Pending:** wiring the recommendation to an out-of-band alert channel (email/pager), which needs
    a delivery decision.

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
- **The season's story is on the page (2026-10-28).** `career_view["highlights"]` was published but
  unrendered and untyped. The career page now carries the highlights panel:
  `components/CareerHighlights.tsx` prints the biggest win and worst loss as meeting lines, the two
  runs, clean sheets kept, rounds without a goal, and the same played rounds split by venue — in all
  three locales, with an explicit empty branch for the career that has not kicked off. Four sentences
  reuse the namespace's existing keys (`thPlayed`, `rowPoints`, `rowUnbeaten`, the venue names) so the
  shared-key ceiling stays at exactly 234 bindings / 98 rows; 78/78 checks against the API's own
  response on a shipped build (three-round career and an untouched career, en/zh/zh-TW). Recorded in
  [M13_HIGHLIGHTS_PANEL_VERIFICATION.md](M13_HIGHLIGHTS_PANEL_VERIFICATION.md). **Disclosed:** the
  concurrent momentum batch (`b05804e`..`08199bb`) had staled `qa-key-drift` (a new label/aria pair
  sharing "Substitutions" with deliberately divergent Chinese) and `qa-locale-tokens` (README census)
  on master; both cured in `b59544b` before this unit landed — their CI run caught both reds.
- **The development curve is on the page (2026-10-28).** `career_view["development"]` was published
  but unrendered and untyped. The career page now carries the development panel, directly under the
  season's story: `components/CareerDevelopment.tsx` prints the curve's own constants (τ, rate),
  minutes on the pitch, and the top players by minutes with each player's moved attributes rebuilt
  from the wire's own `delta` dict (`ball control 43→44 · first touch 41→43`) — the attribute names
  are the wire's machine keys printed spaced, the player-page idiom, not new catalogue keys. Ten new
  keys per locale, worded to avoid the taken "Potential" value; column headers reuse
  `thPlayer`/`thPosition`/`thTrainingLoad`/`thTimelineChange`, so the shared-key ceiling stays at
  exactly 234 bindings / 98 rows; 111/111 checks against the API's own response on a shipped build,
  both branches (a career played to its season's end and an untouched career) × en/zh/zh-TW. The
  walk's first attempt recorded a real curve property: at three played rounds the τ=3000 saturating
  curve had not moved a single attribute, so the walk plays the season out to give the movement cell
  a live population. Recorded in
  [M13_DEVELOPMENT_PANEL_VERIFICATION.md](M13_DEVELOPMENT_PANEL_VERIFICATION.md). **Disclosed:**
  master's api CI job is red from the foreign market batch (`bb712f0`, 13 mypy errors in
  `market.py` whose file carries that lane's uncommitted edits) — not cured here.
- **The key-drift ceilings ratcheted onto the measured drift (2026-10-28).** The cross-namespace
  ceilings in `qa-key-drift.mjs` were still the 2026-10-25 review's 119/107 while the tree measures
  **99 / 42** — the same-sense alignment cures of 2026-10-27..28 (16 changed values per CJK file)
  dissolved most of the reviewed population and no new drift arrived. Both constants now sit exactly
  on the measured counts, so any new divergence is red; a three-plane arm battery proves it bites
  (control green; one mutated shared sentence reds check 3 at 100>99; one mutated shared key name
  reds check 4 at 44>42 — the count is once per namespace holding the key). The gate's docstring
  re-reads the census it quotes (117 groups / 13 sites, was stale at 115/12). Recorded in
  [M13_KEY_DRIFT_CEILING_RATCHET.md](M13_KEY_DRIFT_CEILING_RATCHET.md).
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
- **The API's load story is published and gated.** `scripts/bench_api.py` gained a `sims` scenario alongside
  the M12 duration loop: a task-count career walk (register accounts, open careers, play a fixed number of
  rounds each, then re-read every career and check its own count) whose concurrency is *across* careers — one
  worker owns a career and plays its rounds sequentially, because the same-career race is refused by the
  database layer: a probe (`K=2` concurrent plays, 10 trials, rounds read back from the SQLite rows) returned
  10/10 one-200-one-409 with zero duplicate rounds and `rounds_played` never disagreeing with the rows; the
  loser's 409 is the global `IntegrityError` handler's coarse `conflict`, not a domain answer. `docs/LOAD_ENVELOPE.md`
  publishes the envelope (measured 2026-10-28: p95 1745 ms at 36 plays, 3.44 plays/s; gate shape 2×2×2 = 8
  plays p95 1656 ms) as the single JSON author of two generous ceilings (p95 ≤ 15000 ms ≈ 9× headroom,
  subprocess ≤ 600 s), and `apps/api/tests/test_load_envelope.py` boots a real `uvicorn.Server` in a thread
  against the test run's own seeded database — both legs — drives the script as a subprocess three times, and
  requires the gate shape green on every invariant (0 non-2xx, exact rounds per career, p95 under the ceiling)
  and both refusal arms red: a wrong prefix exits 1 naming the setup 404, and `--careers 6` exits 1 naming the
  409 `career_limit` after exactly 5 careers opened. Throughput is reported, not gated — a floor measured on
  one machine flakes on a slower one for reasons that are not defects.
- **The youth academy outcomes block landed in the career domain (2026-10-28).** `career_view["academy"]`
  reads the under-21 squad players and judges each against the eleven the engine's own selection picks
  from the career's current squad — `selected` / `next_in_line` / `off_the_pace` — and projects the
  stored overall toward the stored potential with the development curve's new scalar `developed_overall`
  (one `_develop_one` behind both projections, so they cannot disagree). Two re-scopes are published on
  the wire, not silently taken: no invented org↔career link to M8's tenant tier, and graduation
  **measured, not drawn** — a deterministic roll would break the replay identity the Phase 2 guard owns.
  11 pure+DB cases green on both legs (SQLite 11+38, PostgreSQL 49); the career page's panel is the
  next unit. The unit also burned a real trap into the record: `FOOTBALL_OS_TEST_DATABASE_URL` is
  conftest-only, while `apps/api/.env`'s `DATABASE_URL` wins in any other process — the live read first
  created its rows in the PG dev database and was cleaned by counted deletes (33 appearances, 53 events,
  3 matches, 3 fixtures, 1 career, 1 user, zero leftovers verified). Recorded in
  [M13_ACADEMY_OUTCOMES_VERIFICATION.md](M13_ACADEMY_OUTCOMES_VERIFICATION.md).
