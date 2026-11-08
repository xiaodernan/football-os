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
   all green. **Career payload (2026-10-28):** `career_view["window"]` now carries the same block (read through
   the same local import as `_affordability`), so the career page is self-contained and need not fetch `/market`
   for the window state. **Window panel done (2026-11-02):** `/career/[slug]/market` renders it as its own
   `data-testid="market-window"` panel — a notice that follows `state`, six grid rows (state, the season being
   judged, which table the length came from, every range with its label, the range holding this round, and where
   the next one opens) and the tier's own formula beside the two constants it is built from. 16 keys per locale.
   The live walk re-draws the block from the published constants and reconciles all six printed rows against the
   wire: `node scripts/run-walks.mjs market` → **144/144 checks, exit 0, 1/1 walks green** on build
   `VNv19az9qYbeALp8GaIdh` (API :8772, web :3249, fresh SQLite). The panel is held by a new file-only gate,
   `apps/web/scripts/qa-wire-readers.mjs` (12 checks, **12/12** on the basis it lands on, 10/10 killing arms
   MATCHED), which reads three populations off bytes every run — the service's own `return {…}` literals, the
   properties `lib/market.ts` declares, and the fields `page.tsx` actually asks for — and refused to pass the
   day another lane published three constants nothing typed. Recorded in
   [M6_MARKET_WEB_VERIFICATION.md](M6_MARKET_WEB_VERIFICATION.md) §6. **A window that spans several rounds of
   real fixtures** is the half still open: `season_rounds` is read from the competition's double round-robin, so
   the ranges land in rounds the career plays, but nothing yet asks whether a window *straddles* a fixture that
   is already stored and completed, and a career may sign in a round whose match the world has already drawn.
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
   **Squad depth (2026-10-28):** `contract_book` also publishes `positions` — the player count at each position in
   the current squad, from the same squad the age profile walked (no extra query), so a manager can see a thin
   position before signing. **Budget ceiling done (2026-10-30):** `careers.wage_ceiling` (migration `0044`) is the board's hard cap on one round's wage bill, an object the balance cannot stand in for -- sales income walks the balance back up without widening what may be committed. It is stated when the career is opened (`CareerIn.wage_ceiling`, same units as the budget; `0` means the board sets none, which is also what rows that predate the column hold after the migration's `0` backfill). It is authored rather than derived because a budget-derived cap is structurally inert: wages are 500× cheaper than fees in the engine's own arithmetic, so the balance always binds first and a derived ceiling could never refuse a signing a solvent career intended to make. `buy` and `loan` share one check, so both answer `409 wage_ceiling_exceeded` with the standing bill, the proposed wage, the bill after the deal, the ceiling and the headroom; a bill exactly at the ceiling is within it. `budget_position`, `affordability_view` and every listing's `signing` block publish the cap (`wage_ceiling`, `wage_headroom`, `wage_affordable`), `RULES["wage_ceiling"]` prints the formula, the finance panel prints the ceiling beside the runway, and each listing's After-signing cell prints the cap verdict. Pinned by `tests/test_wage_ceiling.py` and two wire cases in `tests/test_transfers_api.py`; the evidence record is [M13_WAGE_CEILING_VERIFICATION.md](M13_WAGE_CEILING_VERIFICATION.md) (58/58 live checks, three locales, and a browser pass).
   **Contract expiry enforced (2026-11-02):** the read-only half is closed by item 25. A permanent deal
   now stores the last round it covers, and the round after that date writes an `expire` row that takes
   the player out of the eleven and stops the wage; a departure that would leave the club unable to field
   eleven with a keeper becomes a one-season `renew` at the same wage. Recorded in
   [M13_CONTRACT_EXPIRY_VERIFICATION.md](M13_CONTRACT_EXPIRY_VERIFICATION.md).
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
   [M13_ACADEMY_OUTCOMES_VERIFICATION.md](M13_ACADEMY_OUTCOMES_VERIFICATION.md). **Career-page panel
   done (2026-10-28):** `lib/types.ts` types the block (`CareerAcademy`, `CareerAcademyTrainee`) and
   `components/CareerAcademy.tsx` renders it on `/career/{slug}` between the development and board
   panels — eight columns (player, position, age, minutes, stored→projected, potential headroom,
   standing against the band's seats, verdict), the API's own `note`, `academy_formula` and six
   `formulas` sentences, and an explicit empty branch. 20 new `careerDetail` keys in all three
   locales. Walked on a fresh `next build`/`next start` by surgery on the walked player's stored
   overall — restart the API between phases, the response cache replays the previous answer — so all
   three verdicts, all three badge classes and the gap interpolation are each reached live: **686
   checks over four phase runs (171 + 172 + 172 + 171), 0 red**, with an anti-vacuity clause per
   surgery phase that a trainee row really carries that phase's verdict on the wire. Recorded in
   [M13_ACADEMY_PANEL_VERIFICATION.md](M13_ACADEMY_PANEL_VERIFICATION.md). **Pending:** the gate gap
   the panel's own first run exposed, opened as item 22.
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
   [M13_BOARD_PROJECTION_VERIFICATION.md](M13_BOARD_PROJECTION_VERIFICATION.md). **Write half done
   (2026-10-30):** the round that completes a career's season now closes it and writes the boundary
   decision — `season_bounds` (index, label, span, length), `boundary_decision` judged by the two
   published per-round lines (`PROMOTION_PACE = 1.8` / `RELEGATION_PACE = 1.0`, printed as
   `SEASON_FORMULA`), only the lowest tier promotable and only the top tier relegatable, and
   `_pyramid_neighbours` reading the world's own item-9 pairing instead of slug order. `close_season`
   writes one `career_seasons` row (migration **0045**, `uq_career_season_index`, names copied so the
   row outlives a deleted league) — a decision, not a cache — and moves `career.competition_id/name`
   alone, never `Team.competition_id`; a challenge season, a club with no competition, an unplayed
   season and a league with no pyramid edge each decide nothing and say why. `career_view` is now
   season-scoped (`record`, `objectives`, `table`, `highlights`, `board` read the season being
   played) with `career_record` lifetime, and `seasons_view` recomputes each closed season's record
   and pace from `career_fixtures` on the read, printing a `recheck` sentence when the stored verdict
   and the rows disagree. Pinned by eight `TestSeasons` tests (`test_career.py` 41 passed).
   **Panel done (2026-10-30):** `components/CareerSeasons.tsx` renders the block on `/career/{slug}` —
   eyebrow, seven standing rows (season, span, pace, line, pace against it, both lines, lifetime record),
   the closed-seasons table with the API's recheck beneath the pace, the verdict badge, the next league or
   "no move", the season note, the formula, the limitation and an explicit empty state; 34 keys in all
   three locales (population **4,005**, **3,960** translated). Walked live on a `next build` over a
   migrated QA database: four careers played to their boundary (three full seasons stayed at 1.857 /
   1.5 / 1.429 points per round, one never played), **150/150** page checks across `en`, `zh` and
   `zh-TW`, all 13 catalogue gates and `next build` green. Recorded in
   [M13_SEASON_BOUNDARY_VERIFICATION.md](M13_SEASON_BOUNDARY_VERIFICATION.md). **Limitation:** no live
   promotion or relegation was reachable — every walked season landed between the lines, so the two move
   branches are covered by unit tests only.

*Gate:* the season ledger still sums from `sim_events` rows; a new door gets a route-citation entry;
isolation walk over any new tenant-scoped door.

## Phase 3 — World scale & structure

M3 seeded 20 teams / 300 players / 130 matches / 500 articles. A "very large" world needs a structure.

9. **League pyramid.** **Done (2026-10-30).** `Competition.tier` and the read-time `standings` table
   (aggregated from `real_matches`, never a stored total) were already present; item 11 added the second
   division — two tier-1 leagues over two tier-2 leagues of eight clubs, tier-banded strengths, cups at
   `tier = 0`. **The season boundary:** `builder._league_table` aggregates each league's final table from
   the stored scores (points, goal difference, goals scored, slug) and `_apply_promotion_relegation` swaps
   the bottom club of every tier-1 league with the top club of its paired tier-2 league before next
   season's opening round is drawn. `Team.competition_id` carries the new membership; `_Club.season_league`
   keeps naming the league the completed season was played in, so the newsroom's 2026 notes still quote
   it. The competition page builds its table from the season's fixtures rather than from membership today,
   so a relegated club still has a row, and publishes `movement: {season, promoted[], relegated[]}` with
   each club's old and new league (`null` for cups). `WorldSizes.movement_slots` switches the move off at
   0. Pinned by `tests/test_world.py` (`test_the_season_boundary_moves_one_club_per_pairing`,
   `test_the_boundary_can_be_switched_off`, `test_next_seasons_fixtures_are_drawn_from_the_new_membership`,
   `test_the_league_boundary_is_computed_from_the_stored_table`,
   `test_every_club_is_registered_in_exactly_one_league`,
   `test_next_seasons_fixtures_name_only_the_new_membership`,
   `test_a_league_page_names_the_clubs_that_played_not_just_the_ones_left`,
   `test_a_future_season_page_lists_the_membership_registered_for_it`,
   `test_a_cup_publishes_no_tier_movement`,
   `test_the_competitions_list_counts_membership_not_every_club_that_ever_played`); the record is
   `docs/M13_PROMOTION_RELEGATION_VERIFICATION.md`.
10. **Fixture calendar.** **Already implemented (verified 2026-10-25):** `world/builder.py` generates a
    deterministic double round-robin per league and a 7-game knockout per cup (`_round_robin`,
    `_league_fixtures`, `_cup_fixtures`, `_simulate`) from the world seed; `real_matches` is the result and
    the world fingerprint gate keeps it reproducible. No new work needed here.
11. **Content expansion.** **Done (2026-10-30):** the world grew from 20 clubs / 300 players / 130
    matches / 500 articles to 32 clubs / 480 players / 288 matches / 824 articles, in a two-tier pyramid
    (`WorldSizes.tiers = (2, 2)`, eight clubs per league, eight cups). Clubs are drawn from tier bands
    (0.52–0.95 and 0.30–0.66, overlapping), so the top flight is stronger by construction rather than by
    luck. The newsroom's quotas are now derived from the world it is given (one report per completed
    fixture, one preview per scheduled fixture, three notes per club, two per competition, a spotlight
    for every second player, a transfer line for every fifth); the tactical desk keeps a fixed budget of
    80. The §65 floors in `GATE` are unchanged — the world sits above them — and the plan is still a
    pure function of the seed. Pinned by `tests/test_world.py` (`test_default_sizes_are_the_documented_gate`,
    `test_the_leagues_form_a_two_tier_pyramid`). The larger world also re-measured the graph's
    depth-2 ceiling (`MAX_EDGES` 400 -> 800: the narrowest articles walk 656-774 edges) and moved
    the career ledger's away half to round 8, derived from the competition; the record is
    `docs/M13_WORLD_EXPANSION_VERIFICATION.md`.
12. **Real-structure simulation tie-in.** **Done (2026-10-31):** a career's season is the club's own
    generated fixture list. `calendar_fixtures` reads `real_matches` for the career's competition and the
    season's label (the label advancing at the boundary, item 8) and orders the club's fixtures by kickoff;
    `next_fixture_plan` plays them in that order (`source: "world_calendar"`, with `match_slug`,
    `round_label` and `calendar {season, position, of}`), so opponent, side and venue are the world's, not
    the career's. Once the calendar is exhausted — or in a season the world holds none for the career's
    competition, the usual case after a promotion or relegation — the career continues on its own
    published rotation (`source: "career_rotation"`, `cycle`/`of`, `basis` naming why), counted within the
    season and starting at its own round 1; the 2027 opening fixtures the world leaves `scheduled` are
    played as that season's first calendar fixtures when the club holds any. **The results do not flow back into
    the public world pages.** `real_matches` is shared, deterministic and read by every account, while a
    career's scores live in its own simulation and its own rows; feeding one manager's fiction into
    another manager's world would break both the isolation and the seed-reproducible world. The calendar
    supplies the order, never the score: the world fixture a career slot names keeps its own status and
    result (the live walk re-read all fourteen and found none changed). Pinned by `tests/test_career.py`
    (`TestCalendar`, seven cases), `tests/test_career_api.py` (the basis on the wire),
    `tests/test_scout_transfer_sim.py` (a projection reads the same calendar) and
    `tests/test_sim_ledger.py` (the away half derived from the calendar); the record is
    `docs/M13_CAREER_CALENDAR_VERIFICATION.md`. **The tie half (same day):** the round also records which
    generated fixture it filled (`career_fixtures.world_match_id`/`world_match_slug`, migration `0046`,
    by value, nullable — null on a round that continued on the rotation), and `career_view` prints the
    world's own status and score beside the career's (`world_match_path`, `world_match_still_stored`,
    `world_status`, `world_goals`), keeping the stored slug and dropping the link when the world row is
    gone. The career page's World fixture column prints that score with the link ("world fixture deleted"
    when the row is gone, "—" on a rotation round) and prints the new `world_calendar` limitation saying
    the tie is one-way, in all three locales. Pinned by `TestWorldTie` (six cases) and the live tie walk
    (`.scratch/walk-tie.py`: three rounds, 0 world rows changed); the page itself was walked on the
    production build (`.scratch/walk-career-world-column.py`: 10/10 — the column, the world's score, the
    link, the limitation, `en`/`zh`, no missing-message marker). **The boundary fix that followed (item 8
    follow-up, same day):** closing a challenge window wrote a `career_seasons` row that `season_bounds` read
    as a finished season, so the span advanced past a window `play_round` refuses to fill and every season
    read summed zero rows while the fixture table still listed the rounds (`Pts 8 / Points 0 / 0-0-0` on the
    challenge walk). A challenge career's one season is its window: the span now stays rounds 1…window, the
    one row is returned rather than decided again, the view offers no next fixture once the window is closed
    (`available: false` with the closing round named), and the regression case reads `(1, 1, 2, 2)` where the
    old code read `(2, 3, 2, 4)`; the live six-round run reads Points 11 = the Pts column's 11, record 3-2-1
    (`.scratch/walk-challenge-record.py`).

*Gate:* `qa-population-floor` stays green; world seed fingerprint unchanged for equal seed; public
`/world/*` walks stay 200.

## Phase 4 — Performance & scale

13. **Read-path caching.** **Closed as served (2026-10-28):** the HTTP response cache (with the Redis shared
    tier) already caches every world GET, and `/world/status` publishes `version` + `seed` so an external cache
    can key on exactly that pair (now pinned by a test). A computation-layer cache over the remaining internal
    reads was considered and **not** added: the candidate reads (`competition_clubs`, `fixtures_of`,
    `current_squad`) return session-bound ORM objects that must not be cached across requests, and
    `compute_cache` has no safe candidate — its `sets: 0` on `/metrics/cache` says so rather than hiding it.
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
    reads above are the whole cost. **Seventh fix (2026-10-28):** the career **list** called `career_view` per
    row just to read `record` and `objectives` — a whole view per career over a list. `career_summary` now
    computes the brief, record and objectives from the fixture rows alone, skipping the projection blocks
    (pinned by a test that the summary reads neither `career_appearances` nor `real_training_sessions`).
    **Eighth fix (2026-10-28):** `season_horizon` was computed three times per detail read (board, contract book,
    signing window), each re-reading the competition's clubs; `career_view` computes it once and passes it to all
    three (pinned by a test bounding the `where teams.competition_id = ?` reads to the horizon plus the rotation).
    **Ninth fix (2026-10-28):** `read_career` and `create_career` called `next_fixture_plan` and then
    `career_view`, which computed the same plan again; `career_view` now carries `next_fixture` itself (the plan
    it already needed for the brief), so both endpoints read it from the view. The play endpoint keeps its
    pre-play plan — that is the availability check for the round about to be played, a different round from the
    post-play next fixture.
15. **Load envelope.** **Done (2026-10-28).** `docs/LOAD_ENVELOPE.md` records the measured envelope
    (concurrent career sims: `p95_ms_ceiling: 15000`, `subprocess_seconds_ceiling: 600`; measured gate
    p95 1,655.61 ms, measure shape p95 1,745.49 ms), the two refusal arms (wrong prefix, career cap), and
    the gate that boots uvicorn and reruns `scripts/bench_api --scenario sims`
    (`apps/api/tests/test_load_envelope.py`, commit `ec5cd0b`). The M12 cost/rate-limit scaffolding is used
    as the ceiling reference rather than left implied.

*Gate:* load test exits within the published envelope; `next build` + API suite stay green on both legs.

## Phase 5 — Product finish

16. **Onboarding.** **Done (2026-10-28).** `/onboarding` keeps the M1 creation form while the account has
    no player row, and stops redirecting once one exists: it reads the account's own `/club` list and the
    first club's `/club/{slug}/fixtures`, then prints five steps — player, club, team, fixture, result —
    each with a badge (`Step done` / `Step unknown` / `Next step`), an evidence line counted from those
    rows (`Player: …`, `Club: …`, `Teams: n`, `Fixtures: n`, `Played: n`, `No club yet`), and the link
    that opens the surface for the next step. No step is ticked by hand, and a club list that cannot be
    read prints the steps after the player as **unknown** rather than done. 23 new `onboarding` keys in
    all three locales (catalogue **3,836** keys, **3,791** translated; copy gate **3,849** key calls,
    9/9). Walked live against the running API and a dev server with a fresh account
    (`onboarding-walk-20261028200845@footballos.test`): form → player (4 steps next) → club
    `walk-club-20261028200845` (3) → team `First Team` bound to `braeford-athletic`, sheet of 11 adults
    including a keeper (2) → fixture `cfx_5e9Prl-INx0q7dAD` against `cordale-town` (1) → played with
    seed 7, digest `206150031e3e7ee0…` (0, complete sentence). **523 checks, 0 red**, three locales at
    every stage; absence claims read the rendered body with scripts stripped, because the catalogue
    itself travels in the RSC payload. All eleven web gates plus `tsc --noEmit` green.
17. **Accessibility & mobile.** **Done (2026-10-28):** every finding the audit raised is fixed, and the
    fix is held by `apps/web/scripts/qa-a11y.mjs`, which recomputes it on every run: eight text tokens hold
    ≥4.5:1 on all five surfaces (`--text-3` moved #6f8098 → #788aa1, worst 4.20 → 4.79:1 on `--bg-panel-2`),
    `--line-control` (#556a86) holds 3.05–3.45:1 against the field and panel it draws (`--line` is a 1.2:1
    border), every `outline: none` is answered by a `:focus` rule declared after it and one global
    `:where(…):focus-visible` paints a 2px accent ring, the layout's first focusable element is
    `<a class="skip-link" href="#main">` backed by `<main id="main" tabIndex={-1}>`, `<nav>` is named from
    `nav.primaryNav` and the current page is `aria-current="page"`, `prefers-reduced-motion` zeroes transitions,
    all 614 `<th>` carry `scope` (17 were bare) and the tree's one `<img>` carries `alt`.
    `qa-a11y-witness.mjs` plants fifteen defects in scratch copies of the shell and holds each named red
    (**16/16**). Walked live: **58/58** HTTP checks over three locales and two pages — the served CSS carries
    the five new rules — and **8/8** Chrome checks: the first Tab lands on the off-screen skip link, Enter moves
    focus into `<main>`, the next Tab paints `2px solid rgb(53, 240, 164)` at `2px` offset, 375×812 has no
    page-level horizontal scroll with all 12 nav links laid out, and a reduced-motion reader gets `1e-05s`
    transitions. All 32 web gates named in `scripts/check.sh`, `next lint`, and `tsc --noEmit` green; catalogue
    3876 keys, 3831 translated in both Chinese files.
18. **More surfaces.** Remaining read-only pages (academy public view, scout public report) rendered from
    the same live reads the private doors use.
    **Scout public report done (2026-10-29):** `POST /scout/share` mints a link over the question a report
    answered — player, role, career, comparator, round — and stores the question rather than any figure;
    `GET /scout/shares` is the account's ledger (`live` / `revoked` / `max_live` 20), `DELETE /scout/share/{token}`
    closes one and then drops the public answer from **both** cache tiers, and `GET /scout/shared/{token}`
    rebuilds all thirteen fields from the stored rows on every read. A token is 32 hex in a `String(64)` unique
    column; an unknown, a revoked and another account's token are one 404 `no_such_share`, and a closed row keeps
    its question while losing its token. The web half is `/scout/shared/[token]` (no session, `noindex`,
    middleware exception) plus `ScoutSharePanel` on `/scout`, placed **outside** the search block so a manager
    reads and closes doors without running a new search. 38 new `scout` keys × three locales. The measured bug
    this unit had to fix: revocation was true in the table and false at the door for up to a minute, because a
    public answer is cached under the empty identity and the per-caller drop could not reach it — hence
    `cache.drop_public_response` sweeping anonymous keys by path in `TTLCache` and `RedisCache`. Evidence:
    `.scratch/walk-18.py` **44/44** (mint idempotence, ceiling, public read matching the private report
    field-for-field, no account key, three locales, revoke → immediate 404, the other link untouched); `visual-qa.mjs`
    now carries the flow as **10b-2**, and the same nine browser steps passed **9/9** on the running stack
    (20 candidates → `Corand Ruceek` → `/scout/shared/9f19…` → anonymous 200 with no leak → 375px overflow 0 →
    close → 404). `test_scout_share.py` + `test_response_cache.py` (32 tests) pin the mint, the ledger and the
    sweep; `ruff` and `mypy app` (159 files) clean; web gates green.
    **Academy public view done (2026-10-30):** four doors over §40's plan — `POST
    /club/academy/{ident}/plans/{plan}/share` mints or returns a link whose gate is the private read's
    (`plan_for_reader`) plus the minors' one (`plan_consent`); `GET /club/academy/shares` is the account's
    ledger (`opened` / `live` / `revoked`, 20 open), owner-scoped so it outlives a membership; `DELETE
    /club/academy/shares/{token}` closes one and sweeps the public answer from both cache tiers; `GET
    /club/academy/shared/{token}` recomputes status, focus, goals, stage, progress, review rows and the
    feedback/evidence counts from the plan's own rows, and names all nine omissions in `redacted`. The
    defect this half had to fix: the page recomputed per request but the sixty-second response cache could
    still answer for it, so a review filed after a public read was missing from the next page. Every plan
    write (edit, erase, assessment, feedback, evidence add/remove, player-data erase) now drops each live
    token's cached path — collected before a delete, because the share rows cascade with the plan. Web:
    `/academy/shared/[token]` (no session, `noindex`, canonical `/club`) and `AcademySharePanel` on the
    plan page (create / view / copy with the URL printed when the clipboard is denied / revoke; the ledger
    is re-read after every write). 42 new `club` keys × three locales; catalogue 3956 / 3911. Evidence:
    `test_academy_share.py` **21/21** (progress equality field for field, exact private-key set absent,
    ageing, the four gates, ledger / ceiling / revoke / owner scoping, three cache sweeps);
    `.scratch/walk-share.py` **46/46** live in three locales (revoke → 404 on the same request, minor
    consent on both sides of the yes); `.scratch/panel-share.mjs` **20/20** in Chrome (login → panel → copy
    → public page → note filed while cached → reload counts it → revoke → 404 → Chinese labels); adjacent
    academy + organization suites **237/237**; `ruff`, `mypy`, `tsc`, `eslint` clean. Record:
    [M13_ACADEMY_SHARE_VERIFICATION.md](M13_ACADEMY_SHARE_VERIFICATION.md).

*Gate:* `visual-qa.mjs` gains the new flows; `npm run lint` + `tsc --noEmit` clean.

## Phase 6 — Operational maturity

19. **Trace dashboards.** **Backend done (2026-10-28):** `GET /api/v1/traces/summary` (admin, the same
    `TRACE_STANDING` as the detail door) reads the `request_spans` store over a window (`window_minutes`, 1–1440,
    default 60; `limit` caps the scan and `truncated` says when it bit) and publishes, per route, the span count,
    error count and rate, and nearest-rank p50/p95/max — grouped by `attributes.http.route` (else the span name),
    SERVER spans only, error = `status == ERROR` or `http.status_code ≥ 500`. Declared before `/{trace_id}` so
    `summary` is a door, not a trace id. `span_store.route_summary` + `ROUTE_SUMMARY_FORMULA`; pinned by
    `TestTheSummary` in `test_trace_store.py`. **Web panel done (2026-10-28):** `/traces` reads the door with the
    reader's own session, so a non-admin is shown the door's 403 `insufficient_role` sentence instead of a page that
    pre-judges the role. It renders the window chips (15 / 60 / 1440; a window the page does not offer falls back to
    60 rather than erroring), four totals recomputed from the rows it prints (routes, spans, errors, errors ÷ spans)
    and a seven-column table whose cells are recomposed per row (route, count, errors, errors ÷ count, p50 / p95 /
    slowest in the locale's own unit). The nav door is admin-only (`Nav.tsx`), `/traces` is in `middleware.ts`'s
    protected prefixes, `robots.ts` disallows it and the tab is `noindex`. Copy is 37 keys × three locales plus
    `nav.traces`. Verified by `.scratch/walk-traces.py` — **190/190 checks** on `:3218` against a frozen store: 60
    minutes over six seeded SERVER spans in three routes with one failure (1/4, p50 15, p95 250), 15 minutes drops
    the thirty-minute span (5 spans, 2 routes), `?window=999` falls back to 60, INTERNAL and two-day-old spans are
    never read, an unnamed route renders its em-dash row, all three locales match the API cell by cell, a non-admin
    reads the localized refusal with no nav door, an anonymous reader is 307'd to `/login?next=%2Ftraces`, and an
    empty store renders the empty panel. The store is frozen for the walk **because the first run proved a live one
    cannot be compared cell by cell**: every page render writes three SERVER spans of its own (`/capabilities` from
    the layout, `/auth/me` from `currentUser()`, `/traces/summary`), so the summary moved between the API's answer
    and the rendered table — the exporter's write path is pinned by `test_trace_store.py`, and this walk pins the
    panel's read of a fixed store.
20. **Runbooks.** **Done (2026-10-28):** [`docs/RUNBOOKS.md`](RUNBOOKS.md) indexes one page per subsystem —
    backup/DR (`full_restore`, `pitr_recovery`, `partial_restore`, `region_failover`, `secret_rotation`),
    erasure (`erasure`), rate limits (`rate_limits`) and tracing (`tracing`) — each grounded in the script or
    door it documents and each carrying a "what this runbook does not claim" section. The backup/DR pages were
    written against `scripts/backup_db.sh`/`restore_db.sh`/`dr_lib.sh` (the `docs/runbooks/` directory
    `BACKUP_RECOVERY.md` referenced did not exist); erasure cites `/api/v1/auth/account` and the academy's
    player-data door; rate limits cites `limit()` in `security.py` and ADR-001's Redis caveat; tracing cites the
    span store and both admin doors.
21. **Cost guardrails.** **Monthly ceiling done (2026-10-28):** `settings.ai_monthly_ceiling_usd`
    (`AI_MONTHLY_CEILING_USD`, `0` = not configured) and `cost_advisor.monthly_state()` — month-to-date spend
    since the first instant of the UTC month, the ceiling, remaining, used_pct, a pace projection to month end,
    and `exceeded` / `projected_over`. `recommend()` publishes it as a `monthly` block and adds a
    `monthly_ceiling` recommendation when a ceiling is configured and the month is over or projected over; with
    no ceiling it says so rather than inventing one. Pinned by `TestMonthlyCeiling` and the door's key-set
    assertion. **Done (2026-10-30):** the channel is a signed webhook plus a stored ledger, the delivery decision
    this item asked for. `services/ops_alerts.py` recomputes `monthly_state` at each sweep, raises at
    most one row per `(kind, month, condition)` (`...:projected_over` and `...:exceeded` are separate
    rows, so a month first over its pace and later over its ceiling raises both), writes the row before
    any POST, and retries an undelivered row on each sweep up to five attempts, recording the
    receiver's own words on failure. With no `OPS_ALERT_WEBHOOK_URL` the ledger is the channel, and a
    webhook configured later delivers the backlog on the next sweep. Each POST is signed with
    `APP_SECRET` over the exact bytes (`X-Football-Alert-Signature: sha256=<hex>`, plus
    `X-Football-Alert-Id`); the body is canonical JSON. Three admin doors under the metrics standing:
    `GET /api/v1/metrics/alerts` (state filter `open` / `acknowledged`; an unknown value is 422, not an
    empty list), `POST /api/v1/metrics/alerts/check` (the sweep), and
    `POST /api/v1/metrics/alerts/{alert}/acknowledge` (404 `no_such_alert`). Migration `0043`;
    `tests/test_ops_alerts.py` (17 cases), `.scratch/walk-alerts.py` **29/29** against a live API and a
    real sink, and the runbook [`docs/runbooks/cost_alerts.md`](runbooks/cost_alerts.md).
22. **Gate the bare key calls a prop-translator component makes.** **Opened by item 7's first walk run; Done
    (2026-10-28).** `qa-i18n-literals.mjs` records a bare `t("key")` call against the namespace the
    *calling file itself* binds (the `candidates` list built in its translator-read branch; cited here by its identifier
    rather than by line numbers, which move under every other lane's commit); when the translator
    arrives as a prop and the file never calls `getTranslations`/`useTranslations`, the candidate list is
    empty and the call contributes nothing — the key is never checked, and neither are its placeholders.
    Measured population today: **7 files under `apps/web/components/` make 167 bare `t("…")` calls that are
    outside the gate's recorded set** (`CareerNextOpponent` 34, `CareerContracts` 29, `CareerBoard` 25,
    `CareerFinance` 24, `CareerAcademy` 23, `CareerHighlights` 18, `CareerDevelopment` 14). The defect is
    not hypothetical: the academy panel's first run died at runtime on `KeyError: 'thAge'` — two header keys
    borrowed from namespaces the page's `t` does not hold — and a reversible probe (plant the old spelling,
    run the gate, restore byte-identically) showed **8/8 PASS at the same 3661 call count** with the bad keys
    in the file, i.e. the gate could not have caught it. The paired control names the boundary exactly: the
    same planted key in `app/career/[slug]/page.tsx`, which binds `careerDetail` itself, is answered
    **7/8 — 1 key the catalogue does not hold, at 3662 calls**. The fix is to bind a prop translator to the
    namespace its *caller* passes, at the page/component seam, rather than widening the component's own file;
    every panel already walks a page that binds exactly one namespace. **Fixed (2026-10-28):** the gate now
    resolves a prop translator across files at the seam — the caller's namespace is bound to the component's
    `t`, repeated until the resolution stops growing, so a panel handing the translator to a sub-panel is
    followed too — and a ninth check refuses any translator read left without a namespace. Measured witness:
    with `t("seamProbe")` planted in `components/CareerAcademy.tsx` (a prop-translator panel) the gate answers
    **8/9 — `careerDetail` has no key "seamProbe", at 3827 calls**; the restored file is **9/9 at 3826 calls**,
    and the tree's 7 prop translations are bound across the seam. *Gate:* the recorded-call count must move
    when a key is planted in a prop-translator component — that reaction, not the pass, is the witness.
23. **The dead-key gate exempts a whole namespace on one dynamic read.** **Opened 2026-10-28; Done 2026-10-30.**
    `qa-unused-keys.mjs` holds the other half of item 22's contract: is every key the catalogue holds
    asked for by a page? Its soundness rule is right in principle — a read whose argument cannot be
    resolved to literals must not let the gate promise completeness — but the exemption it applies is
    **namespace-wide**, so one dynamic read spends the whole namespace. Measured on today's tree, the gate
    reads 3/3 with **0 keys asked for by nothing** and prints the cost itself: *3 unresolved read(s) left
    2 namespace(s) unjudged — `careerDetail`, `errors`* (`t(column.hintKey)` and `t(column.labelKey)` in
    `app/career/[slug]/page.tsx`, `t(refusal.code)` in `lib/refusals.ts`). Those two namespaces hold
    **288 + 66 = 354 of the 3971 keys** in `en.json` (42 namespaces), so nine keys in a hundred are never
    asked whether anything reads them. A two-arm probe on a plane copy of the tier proves it is the
    exemption and not a dead check: a key nothing reads, planted in **`careerDetail`, leaves the gate at
    3/3 and 0 orphans (rc 0)**; the same key planted in **`common` reds it at 1 orphan (rc 1)**; the plane
    restores to 3/3 and 0. The fix keeps the rule and shrinks what it spends: (a) a key the source names
    in its **own data** is a key that source reads — the copy gate's third check already resolves that
    shape over the tree (97 named keys), and the reader census can use the same resolution instead of
    exempting; (b) `errors` is judged against the refusal codes the API publishes, which `qa-api-strings`
    and the locale-claims test already enumerate from both sides; (c) the third check is re-graded from
    "namespaces unjudged" to **keys unjudged against a floor that may only fall**, so a new dynamic read
    cannot quietly exempt a namespace again. *Gate:* the differential must invert — a dead key in
    `careerDetail` must red the gate exactly as one in `common` does, and the unjudged count must reach 0.

    **Done (2026-10-30):** the rule is kept and what it spends is measured rather than assumed. (a) A read
    whose key lives in the source's **own data** is resolved instead of exempted: the reader follows the
    identifier to the file that declares it — `lib/ledger.ts`'s `LEDGER_COLUMNS` reaches
    `t(column.hintKey)` in the career page — and folds a translator handed across a component seam to a
    **fixed point** (149 files parsed, 2 seam rounds here), so `careerDetail`'s dynamic reads are judged.
    (b) `errors` is the one read left unresolved (`t(refusal.code)` in `lib/refusals.ts`), so it is
    **delegated by name** to `apps/api/tests/test_locale_claims.py`, which recomputes those 66 keys from the
    refusal codes the API publishes; an exemption no longer counts unless a named gate is found, in the file
    it names, holding the clause that judges the namespace. (c) The check is re-graded from namespaces to
    **keys**: 3905 judged here + 66 delegated = 3971, **0 unjudged**, against a floor that may only fall.
    The differential inverted, measured by `.scratch/probe-dead-keys.py` **6/6**: a key nothing reads,
    planted in `careerDetail`, now answers **1 orphan and rc 1** exactly as the same key in `common` does;
    the catalogue is restored **byte-identically** between arms (`sha256 db436ca4…` both ways), and the
    unplanted gate is **3/3**.

*Gate:* each runbook cites the door it documents (§83 pattern); the cost ceiling is a tested boundary.

---

## Phase 7 — Career consequences

24. **The board pays a season.** **Done (2026-11-02).** Opened by items 8 and 9: a career could cross a
   boundary and keep playing, and every season it played spent the budget down. `career.budget` is written
   once when the career opens and moved only by money leaving it — a fee on `buy`/`loan`, a wage charge each
   round — with sales as the only income, so a second season always began with less than the first and a long
   career could only shrink toward a market it could no longer enter. `career_budget_awards` (migration `0047`,
   14 columns, `DRIFT: none`) is the ledger's third table and the first whose money arrives. `season_grant` is
   three authored constants and nothing else — **8,000 per round played, 2,500 per point earned, 150,000 when
   that season's verdict is `promoted`** — and it is the single place the one exemption lives: a `challenge`
   verdict pays nothing whatever its record, because that run is judged by the challenge's own reward, so the
   boundary that pays and the page that projects cannot drift apart on it. A grant of 0 writes no row.
   `close_season` pays **inside its own transaction** (award added before the same commit as the boundary row),
   so a career either has its verdict and its money or has neither, and `uq_career_award_season` makes one grant
   per season a property of the schema rather than one coin flip — a hand-written duplicate answers
   `IntegrityError`. Authored rather than derived for the same reason as the wage ceiling: a cap or a grant
   computed from the budget would be paid out of the budget it came from and change nothing. Published on every
   read that answers "what does this career have": `budget_position` (`granted`, `grant_rows`, `grant_detail`,
   and `remaining` folding `sum(budget_awards.amount)` into the printed formula), `budget_timeline` (a grant is
   rank 2 in its round, after the move and the wage charge, because that is the order they are written in),
   `market_view` (the grant as a ledger row in the moves table's own shape, `totals.grant_rows`, the three
   constants, and `RULES["grant"]` in the rule census), `affordability_view` (one query feeding both), and
   `seasons_view` (each closed season's grant beside the verdict it was paid for, `null` when it paid none, plus
   `grant_if_closed_now` — the same pure arithmetic over the rounds already stored, which writes nothing).
   `components/CareerSeasons.tsx` prints the closed grant as a seventh column and the projection as a grid row;
   the finance timeline and the market ledger print whatever rows the ledger holds, so the grant arrives there
   with no new panel, and the ledger's contract cell now treats a grant as it treats a wage — an em-dash, where
   it printed `0 years`. Money and units are composed at the call site, like every other figure in these panels.
   2 new `careerDetail` keys per locale. *Gate:* 16 new tests (`TestSeasonGrants` 12, `TestBoardGrants` 4) —
   amount and basis per verdict, the challenge case, a second season paying again, the unique key, ledger
   agreement, projection-not-payment, market-door publication; the targeted run is **34 passed, rc 0**;
   `qa-wire-readers` **12/12**, `qa-unused-keys` **3/3** at floor 0, `qa-token-drift` **2/2** (it reds on a
   `{amount} {units}` template that is byte-identical in all three locales: the remedy is the composition the
   codebase already does, not a line in another lane's gate script), locale parity at 4,012 per locale on the
   commit that holds the item — 4,028 was the working tree the gate ran, which also carried the signing-window
   batch's 16 uncommitted keys; ruff, mypy, tsc, eslint green.
   `budget: 0`, tier-2 league's weakest club) ran twice against two generated worlds, both exit 0: 14 rounds /
   14 points paid **147,000**, 14 rounds / 16 points paid **152,000**, and in both the same **90,110** loan that
   was refused from 0 before the boundary is signed from the grant alone, ending season two round one at
   55,690 / 60,690 with `['season_grant', 'loan', 'wage']` and **0 disagreements**. Measured economics, stated
   rather than assumed: the cheapest listing on that board is 668,250 to buy and 100,238 to loan, so a season's
   grant keeps a career in the market and does not buy it a first-class player. Recorded with the browser read
   in [M13_SEASON_GRANT_VERIFICATION.md](M13_SEASON_GRANT_VERIFICATION.md).
   **Landing:** these bytes reached `master` inside the concurrent batch's commit `c5d0979`, which committed the
   shared index while this item's sixteen paths were staged in it, so the subject names that lane's catalogue
   table and not this feature. The tree was graded before it moved (tsc, eslint, ruff, mypy and the 16 grant
   tests green on the staged tree itself) and the full suite ran on it after: **2132 collected, 2130 passed,
   2 failed** — the README population row and the migration census, both figures a concurrent batch committed
   alongside this one and neither one the grant's. Recorded in that file's section 9.
   **What is still open:** a boundary that ran before `0047` has a verdict and no grant (the panel prints an
   em-dash rather than inventing a payment — a backfill would be writing money for a season nobody was asked
   to play); and the grant is the only income in the game, so a cup run, a sold academy graduate and a
   stadium gate are still unmodelled.

*Gate:* a career's money has a row, a formula and a reader; no figure is paid that no row says was paid.

---

25. **The deal book starts to expire.** **Done (2026-11-02).** Item 6 had left the expiry a projection:
   `contract_years` was stored, `contract_book` derived a date, and no round ever enforced it. A signed
   player stayed forever and the wage bill never shrank — the one economic loop the season grant had just
   started to fund could not lose a player. Migration `0049_career_contract_expiry` adds
   `career_squad_moves.expiry_round`, fixed at signing from `signed_round + contract_years × the season
   length then in force − 1`; storing it is what keeps a later promotion from stretching a contract that
   was already agreed. `expire_contracts()` runs at the start of the only path that advances a career,
   before `squad_as_of` reads the eleven: a permanent deal past its stored last round writes an `expire`
   move at that round, the player leaves the overlay and `held_deals` stops charging the wage. The row
   carries `fee = 0` and the standing `budget_after`, so a contract ending is not a fee and the ledger
   still adds up. The authored exception is fieldability: if lapsing would leave fewer than eleven players
   or no keeper, a `renew` row extends the deal by one season at the same wage, and the result names the
   counts that decided it. `contract_book` publishes `recent` (the last five endings with player, kind,
   effective round, expiry and wage) and `components/CareerContracts.tsx` prints it on `/career/{slug}`;
   the ledger prints `expire`/`renew` as ordinary zero-fee rows. *Gate:* **62** transfer-service tests and
   **88** career+wire tests passed on SQLite; `alembic check` clean after `0048 → 0049`; ruff, mypy (161
   files), tsc, `qa-i18n-literals` (9/9 over 4,098 calls), `qa-unused-keys` (3/3), `qa-token-drift` (2/2)
   and `qa-wire-readers` (12/12) green. The live walk `.scratch/walk-contract-expiry.py` signed a player,
   read the stored expiry **70**, played round **71**, and measured `expire_row_round 71`, fee **0**, the
   player gone, the balance unchanged at **7,675,000**, `deals_after 0`, `recent_kind expire` and
   `wage_after 0`. **What was still open then:** no manager-chosen renewal at expiry (closed by item 26),
   no fee or compensation when a player leaves, and rows written before `0049` keep the old projection
   until re-signed. Recorded in
   [M13_CONTRACT_EXPIRY_VERIFICATION.md](M13_CONTRACT_EXPIRY_VERIFICATION.md).

26. **Manager-chosen renewals.** **Done (2026-11-02).** Item 25 could only extend a deal as a rescue:
   a departure that would leave fewer than eleven players or no keeper wrote a one-season `renew` at the
   same wage. A manager had no way to keep a player on purpose, so a long career could only leak squad
   depth. `POST /transfers/{ident}/renew` (`{ player, years? }`, 1–5) renews a **held permanent** deal
   without requiring an open signing window — the player is already this career's. The price is authored
   and published: `renewal_fee = 5% of the current asking fee, rounded to 5`; the new weekly wage is the
   player's **current valuation**, so a renewal re-prices rather than extends stale terms; and
   `expiry_round = the signing round + years × season_rounds − 1` is stored on the new row, not
   projected. A loan answers `409 loan_cannot_be_renewed`; a squad player with no stored deal answers
   `409 no_contract_to_renew`; the fee and the post-renewal bill are refused with their figures against
   the balance and the board's ceiling. `contract_book` publishes a `renewal` quote (fee, wage, bill,
   ceiling, both affordability flags, formula) on every held permanent row; `components/ContractRenewal.tsx`
   prints it in a new **Renewal** column and refreshes the page after the POST; `move_row` now publishes
   `expiry_round`, so the ledger and the deal book agree. *Gate:* **66** transfer-service tests and **89**
   transfer tests over both files passed; ruff, mypy (161 files), tsc, ESLint, `qa-i18n-literals` (9/9 over
   4,109 calls), `qa-unused-keys` (3/3), `qa-token-drift` (2/2) and `qa-wire-readers` (12/12) green. The live
   walk signed a player whose stored expiry was **14**, renewed for two seasons against the book's
   **30,040** quote, and read the stored expiry back as **28**, the balance moving from **9,098,875** to
   **9,068,835**, `recent_kind renew`, and the round's wage charge at the renewed **1,200**. **What is still
   open:** no production-build browser pass yet; the fee does not scale with the chosen term; the player
   cannot refuse; no signing bonus; and a pre-`0049` row keeps its projection until it is renewed. Recorded
   in [M13_CONTRACT_RENEWAL_VERIFICATION.md](M13_CONTRACT_RENEWAL_VERIFICATION.md). **Updated
   2026-11-03:** item 31 replaces the flat fee and valuation wage with a term-scaled fee, a
   minutes/tier demand and a refusal — see
   [M13_RENEWAL_NEGOTIATION_VERIFICATION.md](M13_RENEWAL_NEGOTIATION_VERIFICATION.md).

27. **A home round pays its gate.** **Done (2026-11-02).** The ledger had one recurring income — the
   board's season grant — while a career paid its wages out of savings and a home fixture earned nothing,
   even though the world already stored the attendance. Migration `0050` adds `career_gate_receipts`
   (unique on `career_id + round_index`): one row per home round, carrying the world fixture's stored
   attendance (or, for a round on the career's own rotation, `capacity × (62 + seed mod 38)%`), the
   authored ticket price — **3** for a tier-1 league, **2** for tier 2 or a cup — the amount, the basis
   in words and the running `budget_after`. `pay_gate_receipt` runs after the fixture is stored and
   before the wage charge, so the wage row's stored balance includes the gate; the timeline reads
   moves → gate → wage → boundary grant. `budget_position` now publishes `received_sales`,
   `received_gate`, `gate_rows` and `gate_detail` (and `received` is every cent in), `BUDGET_FORMULA`
   names the fourth table, `market_view` prints a `gate` row on the one ledger with its attendance and
   price, `affordability_view` publishes the gate total, and `CareerFinance.tsx` prints it when it is
   non-zero. A challenge's window pays no gate: its budget is an authored constraint and a gate would
   silently raise the figure the scenario stated. *Gate:* 5 new service cases (`TestGateReceipts`), 1 new wire case
   (`TestGateReceiptsWire`), **164** career+transfer tests and **9** affordability tests passed;
   `alembic check` clean after `0049 → 0050`; OpenAPI regenerated for the new routes; ruff, mypy (161),
   tsc, ESLint, the four i18n/wire gates and `qa-wire-readers` (12/12 over 17 constants) green. The live
   walk played a home round at a 48,184-seat ground: **38,725** seats × **2** = **77,450**, the away
   round wrote nothing, the balance moved **1,000,000 → 1,077,450**, the timeline held one `gate` entry
   and **0** disagreements. Recorded in [M13_GATE_RECEIPTS_VERIFICATION.md](M13_GATE_RECEIPTS_VERIFICATION.md).

47. **The honours cabinet.** **Done (2026-11-09).** A career that wins things had nothing that said so:
    the boundary wrote the verdict, the cup paid the prize, and neither surface counted what a manager
    would call a trophy. `honours_view` reads the stored facts and only the stored facts — `career_seasons`
    holds each closed season's verdict (`promoted` / `relegated` / `stayed`), so promotions, relegations and
    seasons played are counts of decisions, and a cup is won when a `career_budget_award` of kind `cup_prize`
    names the stage that ends the cup (`CUP_FINAL_STAGE`, the tie that pays 220,000 — a semi-final is a
    prize, not a trophy). The one honour a manager would most want, a league title, is deliberately absent:
    the career's own fixtures cannot see every other club's results, so a finish position invented from
    `mini_table` would be a lie with a trophy beside it, and the block's note says so rather than leaving
    the gap silent. `career_view["honours"]` carries the cabinet beside `seasons`. *Gate:* 4 new service
    cases (`TestHonours` — empty cabinet, stored verdicts, a final vs a semi, the view wiring);
    career/career-api/transfers green (185); ruff clean. A live walk and a page panel are left to the
    web tier, which owns `CareerHonours.tsx`.

## Phase 8 — a living economy and a living squad

The seventh phase made a career's decisions consequential: a season pays, a contract ends, a manager can
renew, and a home round earns. The next phase makes the **people and the club** change over a long
career, rather than the ledger alone. Items 28–33 are all done.

28. **Players age and retire at the season boundary (done 2026-11-03).** `ageing.effective_age` reads a
   player as `stored age + seasons this career has closed`; nothing writes the shared world row.
   `close_season` calls `retire_at_boundary` after writing its season row, and a player who reaches
   `RETIREMENT_AGE = 40` on the career clock gets a `retire` move at the next season's first round:
   zero fee, the wage it was paying, and a departure the squad overlay and wage bill both honour. A
   candidate is retained when retiring him would leave fewer than eleven players or no keeper, and a
   challenge window (one season, no later boundary) retires nobody. `valuation`, `open_market`, `buy`,
   `loan`, `sell`, `release`, `renew` and `contract_book` all read the same clock, so the page cannot
   print two ages for one player. *Gate:* 4 new service cases (`test_ageing.py`), **165**
   career+transfer tests passed; `alembic check` clean (no column: `retire` is a `kind` value); ruff,
   mypy (162), tsc, ESLint and the four i18n/wire gates green. The live walk closed a 14-round season:
   the forced 39-year-old became 40, the `retire` row landed at round **15**, the wage bill moved
   **3,100 → 0**, and `recent` named `retire / Corand Ruceek`. Recorded in
   [M13_AGEING_VERIFICATION.md](M13_AGEING_VERIFICATION.md).

29. **Youth intake replaces the retirees (done 2026-11-03).** At the same boundary as a retirement,
   `intake.youth_intake` promotes young world players (no invented rows) into the squad. Candidates
   are the world's players at or under 21 on the career clock; `academy.judge_candidates` ranks them
   against the club's own eleven with the same `academy_class` the page uses, and only `selected` or
   `next_in_line` candidates are signed. The intake writes a `kind = "youth"` move with fee 0, the
   valuation's wage and contract years, and a stored expiry, so `expire_contracts`, the renewal quote
   and `renew()` treat it as a permanent deal. At most one per retiree, capped at four; a wage that
   would cross the board's ceiling is skipped and named. *Gate:* 6 cases in `test_ageing.py` (2 new),
   **176** career+transfer+academy tests passed; `alembic check` unaffected; ruff, mypy (163), tsc,
   ESLint and the four i18n/wire gates green. The live walk retired a 3,100-a-week player and
   promoted a **20-year-old** on a **5-year**, **1,730** deal with expiry **84**; the bill ended at
   exactly **1,730**. Recorded in [M13_YOUTH_INTAKE_VERIFICATION.md](M13_YOUTH_INTAKE_VERIFICATION.md).

30. **A window that straddles a played fixture (done 2026-11-03).** `transferable` now refuses a move
   into a round that already has a `career_fixtures` row (`round_already_played`, constraint
   `stored_fixture`), and `transfer_window` counts stored rows in the current window instead of trusting
   the counter alone: `played_in_window` is the larger of the counter's count and the stored-row count,
   and `signing_rounds_left` subtracts rounds already stored. The career view hands its own fixture list
   to the window, so the page still reads `career_fixtures` once. *Gate:* 2 new cases in
   `TestTransferWindow` (11 in the class), **173** career+transfer tests passed; the read-efficiency and
   query-count tests unchanged; ruff, mypy (163), tsc, ESLint and the four i18n/wire gates green. The
   live walk rewound the counter to 0 against a stored round 1: `round_already_played`, window
   **1/3**, and the same career transferable once the counter was restored. Recorded in
   [M13_WINDOW_STORED_FIXTURE_VERIFICATION.md](M13_WINDOW_STORED_FIXTURE_VERIFICATION.md).

31. **Renewals that negotiate (done 2026-11-03).** The signing-on fee is now
   `fee_per_year × years` (`fee_per_year = round_5(asking × 5%)`), and the player's demand is
   `round_5(valuation wage × tier_factor × minutes_factor)`, with tier factors 1.15 / 1.00 / 0.90 for
   tier 1 / tier 2 / cup and `minutes_factor = 0.90 + 0.20 × (appearance minutes ÷ (rounds_played ×
   90), clamped)`. `POST /renew` accepts an optional `wage`: at or above the demand it is accepted at
   the offer, below it the player answers `409 renewal_refused` with `demanded_wage` and
   `offered_wage`. Omitting `wage` pays the demand, so item 26's one-click path still works.
   `ContractRenewal.tsx` gained a weekly wage offer input. *Gate:* 2 new service cases and 1 new wire
   case (10 renewal cases across both files), **176** career+transfer tests passed; OpenAPI
   regenerated for the new field and 4/4 currency tests passed; ruff, mypy (163), tsc, ESLint and the
   four i18n/wire gates green. The live walk read **64,575** for one year and **193,725** for three,
   refused **2,320** against a **2,325** demand, then accepted two years for **129,150** with expiry
   **28**. Recorded in [M13_RENEWAL_NEGOTIATION_VERIFICATION.md](M13_RENEWAL_NEGOTIATION_VERIFICATION.md).

32. **Cup runs and prize money (done 2026-11-03).** The world already holds a knockout cup per season
   (eight entrants, 4 + 2 + 1 ties). A career is entered in it when the world's own rows put its club in
   one, and plays its route through that bracket: the quarter-final the draw gave it, then the semi the
   draw made for that half with the other club in it, then the final at a neutral venue — the career's
   own result *replacing* the slot the world's simulation filled, so a club the world knocked out still
   has a route. Each tie is played by the same engine a league round uses, with the career's overlay; a
   draw is separated on penalties by the match digest. A tie is not a round: `rounds_played` does not
   move, and `career_cup_ties.round_index` is the league round it was played after. A round won pays
   **40,000 / 90,000 / 220,000** into `career_budget_awards` (`kind = "cup_prize"`, `stage =
   "<cup>:<round>"`) — the one ledger, not a fifth table; `uq_career_award_stage` keeps one prize per
   round and one grant per season. A challenge career enters no cup, like its grant and its gate.
   `career_view["cup"]` publishes the run, the next tie and every played tie; `CareerCup.tsx` prints it
   with a **Play the cup tie** button. *Gate:* 13 service cases and 3 wire cases, **196**
   career+transfer+cup tests passed; `alembic check` clean after `0051`; OpenAPI regenerated (4/4);
   ruff, mypy (164), tsc, ESLint and the four i18n/wire gates green. The live walk won a quarter-final on
   penalties and a semi-final 1-0, lost the final 0-1, and read **130,000** in prizes against a balance
   of **1,000,000 → 1,130,000** with `rounds_played` still **0**. Recorded in
   [M13_CUP_PRIZE_VERIFICATION.md](M13_CUP_PRIZE_VERIFICATION.md).

33. **A ground that responds (done 2026-11-03).** `gate_capacity` now reads an *effective* capacity —
   the stored row × **1.25** in tier 1, **×1.10** in tier 2, ×1.00 otherwise — and never writes the
   shared `teams.capacity`, so two careers can share one world. `gate_form` reads the career's own last
   five results (W 1, D 0.5, L 0; no history 0.5) and the gate sells `min(effective_capacity, base ×
   (0.90 + 0.20 × form))`. The receipt's basis names both factors, and `GATE_FORMULA` publishes them.
   *Gate:* 2 new cases in `TestGateReceipts` (7 in the class), **187** career+transfer tests passed;
   ruff, mypy (163), tsc, ESLint and the four i18n/wire gates green; no migration. The live walk read
   **46,641** seats after five wins against **38,161** after five losses on the same fixture and seed —
   **93,282** against **76,322** credits. Recorded in
   [M13_GROUND_RESPONSE_VERIFICATION.md](M13_GROUND_RESPONSE_VERIFICATION.md).

## Phase 9 — the cup becomes part of the season

Phase 8 made a tie real and paid it. Phase 9 closes the gaps it had to leave open, so a cup is a full
part of a career's year rather than a parallel exhibition.

34. **A cup tie that pays its gate and its minutes (done).** `career_gate_receipts` and
   `career_appearances` carry a nullable `tie_id`; the league uniques are partial indexes over
   `tie_id IS NULL`, and each tie has its own unique key. A home tie pays a gate from the same
   `gate_capacity`/`gate_form` arithmetic item 33 shipped (capacity-built crowd, form including the
   round the tie follows), a final pays none, and the eleven's 90 minutes land in `career_appearances`
   under the tie, so `carry_over` and `development_view` read them. Cup ledger rows sort at timeline tier
   4 so they cannot precede the round they follow. Evidence: `docs/M13_CUP_TIE_GATE_VERIFICATION.md`
   (16 cup tests; walk: 64,624 seats x 2 = 129,248, 11 + 11 traces, timeline clean).
35. **The world draws next season's cup (done).** `world/builder.py` draws next season's four
   quarter-finals per cup with real entrants, dated and `scheduled`; a knockout cannot be drawn past the
   round whose participants exist. `cup.py` resolves the later rounds when a career's route needs them:
   the adjacent quarter-final is played by the engine's pure entry point on a seed from the row, and the
   final resolves the other half. Side is a stated bracket rule. Evidence:
   `docs/M13_NEXT_SEASON_CUP_VERIFICATION.md` (19 cup cases, 59 world cases; walk: QF from the drawn row,
   semi opponent `Ostdera Naval` from `engine 2-1`, gates 135,057, one 40,000 prize).
36. **Objectives that pay (done 2026-11-04).** Every objective a closed season met writes an award
   row of its own beside item 24's grant — kind `objective_bonus`, stage the objective's kind — at
   30,000 wins / 40,000 points / 25,000 goal_difference / 50,000 unbeaten (145,000 for all four, under
   one season's 174,500 grant). `objective_bonus_report` states the rule once; `close_season` pays it
   in the same transaction and `seasons_view` projects `bonus_if_closed_now` without writing. Migration
   `0049` adds `stage` and widens the key to `uq_career_award_stage (career_id, season_index, kind,
   stage)`. Evidence: `docs/M13_OBJECTIVE_BONUS_VERIFICATION.md`. **Landing:** `0cf34c1` (21 paths
   through a private index; `40762fa` re-cut to LF blobs, `git diff -w` empty between them).
    **Integration (done 2026-11-05):** the duplicate `0049_objective_bonuses.py` was removed, so the chain
    is `0049_career_contract_expiry` through `0054_career_stadium_works` with one head at `0054`; the
    contract-expiry revision owns the award-table `stage` and key changes and `0051` no longer repeats them.
37. **A stadium a manager buys (done 2026-11-05).** `career_stadium_works` stores each purchase (500–20,000
    seats at 120 credits each) with the ground either side and its `budget_after`; the gate reads
    `round(stored x tier factor) + bought seats`, so every bought seat is one more seat sold while a
    career that bought nothing still reads item 33's figure. A challenge career owns no ground, a
    purchase is a ledger row of its own, and `CareerStadium.tsx` plus `POST /careers/{ident}/stadium`
    make it a page decision. Evidence: `docs/M13_STADIUM_VERIFICATION.md` (4 service cases, 2 wire cases;
    walk: 53,002 -> 54,502 seats, 180,000 spent, 77,450 gate, timeline 0 disagreements).
38. **A prose figure pinned to a working tree is red at the commit and green in the run (done 2026-11-04).**
   `test_locale_claims.py` took both inputs from disk while `test_spec_audit_currency.py` took its ledgers
   from the commit: `25c6873` fails its own `test_the_readme_table_states_the_coverage…` (`3988 of 4033`
   against a catalogue of 4,053 keys, so the true pair is `4008 of 4053`) and was green in the shared tree,
   whose row had moved to `4074 of 4119`. The catalogues, the five prose carriers and the API-source refusal
   census now read the commit through `git show HEAD:…` / `git ls-tree HEAD`, with disk only as the no-`.git`
   fallback. *Gate:* three arms on a clean worktree — a dirty `en.json` (4,059 keys vs 4,058), a README row
   rewritten to `1 of 1` plus a planted `287/288` line in `ARCHITECTURE.md`, and a working-tree-only
   `zz_item38_probe` refusal — left this file green in all three while HEAD's old reader failed each arm (the
   census one naming `["zz_item38_probe -> 'Probe refusal'"]`). Evidence:
   `docs/I18N_ARC_VERIFICATION.md` §21. **Landing:** `e8fa569`, one path through a private index.
39. **The contract-currency gate reads the checkout, not the commit (done 2026-11-04).**
   `test_openapi_contract_currency.py` opens by saying it holds "the committed OpenAPI contract" to the app
   "committed next to it", then reads both sides from the working tree: `committed()` is
   `CONTRACT.read_bytes()` and `answers()` is `app.openapi()` from the imported checkout, and the exporter
   case compares the disk exporter's bytes to the disk contract. The shared tree currently carries an
   uncommitted `docs/api/openapi.json`, so a local green says the disk pair agrees, not that the commit does —
   the same mixed-tree sourcing item 38 cured, with a higher price: this contract is what the §80/§81 gates
   and every "contract: N paths / M operations" line quote. *Gate:* a contract dirty on disk alone must leave
   the gate green while HEAD is self-consistent, and a route the checkout's app answers but HEAD's contract
   lacks must red before the commit rather than after it.
   **Landing:** `f10e232`, one path through a private index; the record and this row are the commit after it
   (`1877db5`). Three arms on a clean plane: the baseline green on both sources, a contract dirty on disk alone
   (HEAD's reader 3 failed / 1 passed against the cure's 4 passed), a planted route with its contract
   regenerated beside it (HEAD's reader 4 passed against the cure's 3 failed) -- and the live shared tree, old
   4 passed against new 4 failed.
40. **A landing reverted a landed unit; two gates saw it and no gate saw the schema (done 2026-11-04).**
   `c0d376c` carried 22 paths: `qa-wire-readers.mjs` and section 20 of the i18n record were its own, the other
   twenty answered HEAD's item-36 bytes with pre-item-36 text from a plane older than `0cf34c1` -- the stage
   column and its key, `pay_objective_bonuses`, `TestObjectiveBonuses`, the market ledger, 5 catalogue keys per
   locale, the README rows and `migrations=50` back to `49` -- while `0049_objective_bonuses.py` stayed.
   `test_spec_audit_currency` (49 claimed, 50 revision files) and `test_locale_claims` (README 4,033 against an
   `en.json` of 4,053) red on that tree; the schema itself was invisible, because `create_all` builds the model's
   schema and nothing ran the chain against `Base.metadata`. `21bbf86` restores the twenty blobs as `e8fa569` held
   them and keeps the lane's two paths: 208 passed across the six API files, the file-only web gates at 194/194,
   and the whole suite at 1 failed / 2148 passed / 4 skipped -- the population item 38 measured, the one red being
   row 43. Evidence: `docs/MIGRATION_MODEL_DRIFT_VERIFICATION.md` sections 1-3. **Landing:** `21bbf86`, 20 paths through
   a private index.
41. **The chain and the models describe one schema (done 2026-11-04).** The half of `c0d376c` no test could see.
   `apps/api/tests/test_migration_model_drift.py` upgrades a fresh temporary SQLite file through the committed
   chain in a subprocess with its own `DATABASE_URL` -- so the checkout's `.env`, the suite's database and the dev
   database are all out of the picture -- and asks alembic's `compare_metadata` what would move that schema to the
   committed models, with revisions and models both read from the commit. Four clauses, each failing alone: a
   column the chain builds and no model declares (its message names the revision that shipped it), a column a
   model declares and no revision builds, the tables in both directions, and everything else `compare_metadata`
   can name. 4 passed at master; 2 failed / 2 passed on the real `c0d376c`, clause 1 answering
   `career_budget_awards.stage ... ['0049_objective_bonuses.py']`; a planted model column and a planted model table
   each red on exactly one clause. Types and widths stay `scripts/schema_drift.py`'s claim against a live
   database. Evidence: `docs/MIGRATION_MODEL_DRIFT_VERIFICATION.md` sections 4-7. **Landing:** `f5d6abf` (gate) and
   `265e7a7` (record).
42. **The wire-readers gate promises a `totals` census it never computes (done 2026-11-05).**
    `qa-wire-readers.mjs` now scans `viewScan.children.totals` from the same dict scan that reads the view,
    follows `MarketView["totals"]` in `lib/market.ts`, and reads the block on both planes: the page's own
    `view.totals.x` and the `totals.x` a `passesProp` AST clause proves the page hands to
    `components/MarketTools.tsx`. Three checks are real: 12 equality both ways, 13 every declared field read
    or named with a proof the bytes re-measure, 14 a stale exemption. The gate now prints **18/18** (was
    12/12) and the table's wires are view 18 / window 16 / range 3 / constants 22 / totals 10 / moves 30.
    Four arms each red on its own clause -- a deleted wire key (12/13/14), a deleted type key (12), a removed
    `totals={view.totals}` prop (13 naming the seam), and a removed `signed` reader (13 naming the field) --
    while the untouched copy stays green. Evidence: `docs/M13_WIRE_READERS_TOTALS_VERIFICATION.md`.
43. **A gate that is green only under a fabricated CI environment (done 2026-11-05).**
   `test_ci_trigger.py` asked the workflow's push trigger of "the branch the run is about" and read that branch
   with `git rev-parse --abbrev-ref HEAD`, which answers the literal `HEAD` on a detached checkout -- and every
   landing here is graded on a detached `git worktree`. So the full suite was red on the instrument: at `21bbf86`
   1 failed / 2148 passed / 4 skipped, the one failure that case (`.scratch/item40-suite.log`), and the identical
   run only reached rc=0 when handed `GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master`, which is how item 38's
   post-landing verdict was reached without its record naming the prefix. `_pushed_branches()` now takes the event
   first, the checked-out branch second, and otherwise `git for-each-ref --contains HEAD` against the branch the
   project publishes to; a commit no branch carries skips, naming the refs it looked for, and all four shapes are
   asserted on a throwaway repository. HEAD's own reader on the same detached plane answers 1 failed against the
   cure's 1 passed; `ci.yml`'s trigger rewritten `[master]` to `[main]` still reds, naming `master`. Evidence:
   `docs/CI_TRIGGER_BRANCH_READ_VERIFICATION.md` (this unit's record). **Landing:** `ef649ef` carries
   the cure; the record, this row and the `PLAN.md` section land beside it.


## Phase 10 — the ground has a business

Phase 9 made a ground something a manager buys. Phase 10 makes it something a manager runs: the price
of a seat, the crowd that price draws, and later the upkeep and the season ticket. The rule stays the
same — a decision changes a stored row, every figure is recomputed from that row on the read, and a
receipt keeps the numbers it was actually paid on.

44. **A manager prices the gate (done 2026-11-06).** `careers.ticket_price_pct` stores the setting
    (50–200% in steps of five, 100 = the competition's price) and migration `0055` copies the setting
    and the demand it drew onto every gate receipt, so a later change cannot rewrite a paid crowd. One
    curve, `demand_pct_for`, is read by both the preview and the gate: `d = (pct − 100)/100`,
    `demand = max(20%, 1 − 0.50d − 0.50d²)`, `gate = round(attendance × base × pct/100)`. The revenue
    peak is **120% / index 106**, while 120% sells 88% of the neutral crowd — the panel states the
    trade instead of hiding it. `GET`/`PUT /careers/{ident}/tickets`, `career_view["tickets"]`,
    `market_view["tickets"]`, `RULES["ticket_price"]`, `CareerTickets.tsx`, the market page's price
    panel and the ledger row's own `price_pct`/`demand_pct` make it a page decision. Evidence:
    `docs/M13_TICKET_PRICING_VERIFICATION.md` (7 service cases, 2 wire cases; walk: 38,725 @ 100% →
    33,806 @ 120%, 77,450 → 81,134, old receipt unchanged, timeline 0 disagreements).
45. **The ground costs money to run (done 2026-11-06).** A home round now pays
    `round(capacity × 25%)` credits for the seats it opens — 12,046 on a 48,184-seat ground, and 125
    more for each 500 seats bought. `career_upkeep_charges` (migration `0056`) stores one row per home
    league round or home cup tie with the capacity, rate, amount, basis and `budget_after`; `BUDGET_FORMULA`
    subtracts it, `budget_timeline` puts it after the gate and before the wage charge, and the ledger
    carries kind `upkeep` / `cup_upkeep`. An away round, a neutral final and a challenge career pay
    none. `stadium_view`, `CareerFinance`, `CareerStadium` and the market page print the rate and the
    running total. Evidence: `docs/M13_UPKEEP_VERIFICATION.md` (5 service cases, the cup tie's own row;
    walk: gate 77,450 − upkeep 12,046 = 65,404, +500 seats → +125 a round, timeline 0 disagreements).
46. **Season tickets (done 2026-11-06).** Before the first round a manager sells one block of seats
    for every home league round at 85% of the walk-up price — `round(home_rounds × base × 85%)` —
    capped at half the ground and sold in blocks of 100. `career_season_tickets` (migration `0057`)
    stores the sale once per season, `career_gate_receipts.season_ticket_seats` stores the seats a
    receipt did not charge, and the league gate charges `attendance − season_ticket_seats` while the
    stored crowd stays whole. `BUDGET_FORMULA` adds the income, the timeline places it before round
    one, the ledger carries kind `season_tickets`, and `GET`/`POST /careers/{ident}/season-tickets`
    plus `career_view["season_tickets"]` and
    `CareerSeasonTickets.tsx` make it a page decision. A second sale, a started season, an off-step
    block, a challenge career and a retired career are each refused with their own code. Evidence:
    `docs/M13_SEASON_TICKETS_VERIFICATION.md` (7 service cases, 2 wire cases; walk: 1,000 seats for
    12,000, 38,725 in the ground with 37,725 paid, gate 75,450, timeline 0 disagreements).


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
- **Objectives that pay (2026-11-04).** The objectives a manager sets were prose: `objectives_of` judged
  them and the board printed `met`, and the money never saw them. Every objective a closed season met is
  now an award row of its own (`kind = "objective_bonus"`, `stage` = the objective's kind) beside item 24's
  grant: **30,000 wins · 40,000 points · 25,000 goal_difference · 50,000 unbeaten** — 145,000 for all four,
  sized a little under one full season's grant (174,500), so meeting the board's targets is a good season's
  extra income rather than a reset button. One pure function, `objective_bonus_report`, states the whole
  rule once — `actual >= target` read from the same report the board prints, a target of zero or less pays
  nothing because nothing had to be met, a miss writes no row, and a `challenge` window pays nothing because
  that run is judged by the challenge's own reward — and both the boundary (`pay_objective_bonuses`, inside
  `close_season`'s transaction, flushed before each balance read because `SessionLocal` runs with
  `autoflush=False`) and the seasons projection call it. Migration `0049` adds `stage` and swaps
  `uq_career_award_season` for `uq_career_award_stage (career_id, season_index, kind, stage)`, so one row
  per met objective is a schema property; a fresh SQLite reports head 0049 and **DRIFT none**, and the
  audit's machine-checked migration figure moves 49 → 50 in both carriers `test_spec_audit_currency.py`
  reads. The grant and the bonuses share the ledger's boundary tier, ordered by stage, and the timeline's
  running balance replays that order with 0 disagreements. Published in `budget_position` (`received_objectives`, `objective_rows`,
  `objective_detail`, and the printed sum), the timeline, the market ledger (a moves-shaped row carrying
  `OBJECTIVE_BONUS_EFFECT`), `market_view` (`totals.bonus_rows`, `constants.objective_bonus_by_kind`,
  `RULES["objective_bonus"]`), `affordability_view`, and `seasons_view` (each closed season's `bonuses`
  block and `bonus_if_closed_now`, a projection that writes nothing); rendered in `CareerSeasons`,
  `CareerFinance` and the market page's ledger and balance sentence, with 5 new keys per locale. *Gate:* 9
  new tests in `TestObjectiveBonuses` (21 with `TestSeasonGrants`), the clean worktree's full suite, ruff,
  mypy, tsc and eslint green, `qa-wire-readers` 12/12, `qa-key-drift` 4/4, `qa-token-drift` 2/2,
  `qa-unused-keys` 3/3 at floor 0, `qa-locale-completeness` 2/2 at 4,058 and `qa-locale-tokens` 5/5. The
  live walk (`.scratch/walk-bonus.py` on the shared tree, two generated worlds, both exit 0) projected
  145,000 and 90,000 mid-season and paid 145,000 at both boundaries, each stored bonus balance the grant's
  balance plus the kinds before it. Recorded in
  [M13_OBJECTIVE_BONUS_VERIFICATION.md](M13_OBJECTIVE_BONUS_VERIFICATION.md). **Landing:** `0cf34c1`,
  21 paths through a private index; the first tip `40762fa` was re-cut to LF blobs (`git diff -w` empty
  between them). Section 9 of the record carries the method, the shared-index warning and the migration
  renumbering note.
