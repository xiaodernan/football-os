# M13 verification — a career's season boundary decides which league it plays next

ROADMAP Phase 2 item 8's write half landed 2026-10-30 on top of item 9's two-tier world. The engine
already played a career's fixtures; what was missing was the moment the season ends. A career now
counts the round that completes its season, writes the boundary decision on that round, and — only
when the two published lines say so — moves the career's own league.

Date: 2026-10-30.

## 1. What closes a season, and what it decides

`season_bounds` (career.py) describes the season being played: its index (`len(closed) + 1`), its
label (`season_label`, where a numeric opening season `2026` advances to `2027` and a named one is
kept as written), its first round (`last closed row's last_round + 1`, so a shorter or longer season
after a move stays readable), its length (the challenge's window when it has one, else the double
round-robin horizon), and its last round. `rounds = 0` means no horizon: there is no last round and
nothing to close.

`play_round` calls `close_season` after the round is paid for. `close_season` returns early unless
`career.rounds_played` has reached the last round, and it returns the **existing** row when the career
stands on the boundary the last closed row already describes — asking twice is the same request, not
a second season. `season_index` is unique per career (`uq_career_season_index`).

`boundary_decision` is the whole judgement, and it only reads this career's record plus stored world
rows:

```
pace = points ÷ played          (win 3 / draw 1 / loss 0, over the season's own fixtures)
promoted   if the league above exists and pace ≥ 1.8   (lowest tier can rise)
relegated  if the league below exists and pace <  1.0   (top tier can fall)
stayed     otherwise — and the note names the line that was missed
```

The two lines are authored constants (`PROMOTION_PACE = 1.8`, `RELEGATION_PACE = 1.0` points per
round), not a table, because a career plays only its own fixtures: no other club's results exist to
finish above or below. A double round-robin over seven opponents makes 1.80 = 25 points in 14 rounds
and 1.00 = 14, which the page prints beside the career's own pace in `SEASON_FORMULA`.

Four season shapes decide nothing, and each says why: a challenge career (`challenge` — its window's
objectives judge it and no pyramid move follows), a club with no competition (`stayed`, rule `none`),
a season with no round played (`stayed`, rule `none`, "no round was played in this season, so there
is no pace to judge"), and a league the world drew no edge to (`stayed`, rule `none`).

**The league above/below is read from the world's own boundary, not from slug order.**
`_pyramid_neighbours` recovers the pairing item 9 applied at generation: clubs this league's
completed fixtures named that are registered elsewhere today name the league on the far side, and so
do the clubs registered today that its fixtures never named (their stored season names where they
came from). A neighbour must be a league exactly one tier away, and `None` on a side means a career
does not cross an edge the world does not have — a frozen pyramid, a cup, or a league with no fixtures
at all.

## 2. The move touches the career, not the world

`close_season` writes one `career_seasons` row and, when the rule sends the club somewhere, rewrites
`career.competition_id` and `career.competition_name`. It never touches `Team.competition_id`: the
world's membership belongs to every manager reading it, not to this career's story. Two careers can
therefore leave the same league in opposite directions, and the public competition pages do not move
because a fictional manager was promoted.

The next season's length is read from the *new* competition, so a promotion into an eight-club league
is 14 rounds again, and a challenge window is still the challenge's.

## 3. A career read is season-scoped; the lifetime record is not

`career_view` now separates the two:

| Field | Scope |
| --- | --- |
| `record`, `objectives`, `table`, `highlights`, `board` | the season being played (a slice of `career_fixtures` by `season_bounds`) |
| `career_record` | the whole career, summed from every fixture row |
| `seasons` | the block below |

Before this change every one of those was lifetime, so the round after a boundary would have printed
last season's wins beside this season's fixtures. `next_fixture_plan` gained `round_in_season` and
`season_index` so the "play" card names the season it is playing.

`seasons_view` returns:

```json
"seasons": {
  "current": {
    "season_index", "season", "competition" | null, "first_round", "rounds", "last_round",
    "played", "record", "points_per_round", "rule", "line", "at_this_pace", "note", "source"
  },
  "closed": [{
    "season_index", "season", "competition", "next_competition" | null,
    "first_round", "last_round", "rounds", "played", "record",
    "points_per_round", "verdict", "rule", "line", "recheck"
  }],
  "lines": {"promotion": 1.8, "relegation": 1.0},
  "formula": "..."
}
```

Every closed block's record and pace are recomputed from `career_fixtures` on the read, and
`recheck` is `_verdict_agrees` speaking: "this season's fixtures still say what the stored verdict
said", or a sentence naming the disagreement. The stored row is a decision, not a cache — a fixture
list edited after the fact is reported, not quietly overwritten.

## 4. `career_seasons` is a decision, not a cache (migration 0045)

| Column | Meaning |
| --- | --- |
| `season_index`, `season` | which season, and the label it was played under |
| `competition_id` (FK `SET NULL`), `competition_name`, `tier` | the league the season was played in, copied |
| `first_round`, `last_round`, `rounds` | the span |
| `verdict` (`promoted` / `relegated` / `stayed` / `challenge`), `rule`, `line` | the decision and the line that produced it |
| `next_competition_id` (FK `SET NULL`), `next_competition_name` | where the rule sent the club, empty when it stayed |
| `data_origin`, `is_demo_data` | honest labelling, as every simulation row carries |

Names are copied rather than joined so the row still reads if a competition is deleted, and
`UniqueConstraint("career_id", "season_index")` makes a second decision for the same season a
database error rather than a duplicate. `Career.seasons` cascades all-delete-orphan in
`season_index` order.

## 5. The panel

`components/CareerSeasons.tsx` renders `career_view["seasons"]` on `/career/{slug}` between the board
and next-opponent panels: the eyebrow names the season and both published lines, seven key/value
rows (season being played, its span, its pace, the line it is judged against, the pace read against
that line, the two lines, the lifetime record), then **Seasons already closed** — a table of season /
league / rounds / points per round with the API's `recheck` sentence beneath the pace / verdict /
next season, the API's own season `note`, `SEASON_FORMULA`, and the shared limitation sentence.
An unwalked career gets an explicit empty state. The panel does no arithmetic of its own.

Thirty-four `careerDetail` keys carry the copy in `en`, `zh` and `zh-TW` (population **4,005**, **3,960**
translated, the same **45** identical tokens). Two copy decisions came from reading the API rather
than the design: an unplayed season prints "—" for its pace and for the pace verdict (it is `stayed`
with no line, which would have read as a decision), and "no line applies to this season" is neutral
copy rather than a challenge-specific sentence, because four different season shapes reach it.

## 6. Evidence

| Check | Result |
| --- | --- |
| `pytest tests/test_career.py` | **41 passed**, 8 of them new `TestSeasons` |
| document / migration / census gates (`test_spec_audit_currency`, `test_assert_message_forms`, `test_openapi_contract_currency`, `test_locale_claims`, `test_migration_docstrings`, `test_migration_timestamps`, `test_account_erasure_coverage`, `test_knowledge_graph_census`, `test_answer_census`, `test_authorization_census`) | **71 passed** |
| `ruff check app tests migrations` | clean |
| `mypy app` | **Success: no issues found in 161 source files** |
| `alembic upgrade head` on a fresh SQLite file, then `alembic check` | head `0045`; **"No new upgrade operations detected"** |
| web `npm run typecheck` | clean |
| `next build` | clean, `/career/[slug]` present |
| 13 catalogue gates (`qa-i18n-literals` 9/9, `qa-unused-keys` 3/3, `qa-icu-messages` 2/2, `qa-icu-coverage` 2/2, `qa-plural-select` 2/2, `qa-locale-completeness` 2/2, `qa-locale-fallback` 3/3, `qa-translation-quality` 4/4, `qa-locale-tokens` 5/5, `qa-shared-keys` 4/4 — 234 bindings / 98 rows, `qa-key-drift` 4/4, `qa-locale-formatting` 2/2, `qa-locale-content` 3/3) | **13/13 green** |

The eight tests: `test_a_numeric_season_label_advances_and_a_named_one_stays`,
`test_a_fresh_season_runs_from_the_first_round_to_the_horizons_last`,
`test_a_challenge_season_is_its_window_and_moves_no_club`,
`test_a_top_tier_season_at_exactly_the_relegation_line_stays`,
`test_a_losing_top_tier_season_is_relegated_into_the_paired_league`,
`test_a_winning_lower_tier_season_is_promoted_into_the_paired_league`,
`test_the_boundary_round_closes_once_and_asking_twice_returns_the_row`,
`test_a_career_with_no_competition_has_no_horizon_to_close`.

## 7. The live walk — API `:8734`, built web `:3213`, SQLite `.scratch/walk-seasons.db`

The walk database was copied from the QA build and upgraded `0042 → 0045` by the real migration. Four
careers, each played to its season boundary through `POST /careers/{slug}/play`:

| Career | Club (tier) | Season 2026 | Pace | Line | Verdict | Season 2027 |
| --- | --- | --- | --- | --- | --- | --- |
| A | Obrford Miners (1, Thornford Superleague) | 14 played, 7W 5D 2L, 26 pts | 1.857 | relegation 1.0 | stayed | Thornford, rounds 15–28 |
| C | Braehurst Town (2, Braehaven Elite League) | 14 played, 6W 3D 5L, 21 pts | 1.5 | promotion 1.8 | stayed | Braehaven, rounds 15–28 |
| D | Quernmoor Town (1, Lyndera Superleague) | 14 played, 4W 8D 2L, 20 pts | 1.429 | relegation 1.0 | stayed | Lyndera, rounds 15–28 |
| B | Braeford Athletic (2) | not played | — | — | — | season 1, rounds 1–14, no closed row |

Each closed row's `recheck` read "this season's fixtures still say what the stored verdict said", and
the current season opened with `played = 0`, `points_per_round = null`, the API's note "no round was
played in this season, so there is no pace to judge".

`.scratch/check-seasons-page.py` re-mints the walk account's session (`POST /auth/login` — a stored
bearer token expires), fetches all three careers in `en`, `zh` and `zh-TW`, carves the panel out by
its `<h2 class="panel__title">` and compares every figure with the API block and the compiled
catalogue: the eyebrow, all seven key/value rows, the six column headers, each closed row (season
cell, league and tier, span, pace plus the API's `recheck`, the stored verdict and its badge tone —
`badge--live` only for a move — and the next league or "no move"), the note, the formula, the
limitation, the empty state, and an English-copy leak list on the two Chinese locales. **150/150
checks passed** (50 per locale × 3 locales).

## 8. What this does not claim

* **No live promotion or relegation.** All three played careers landed *between* the lines, so the
  two move branches are covered by unit tests only; the engine's results decide them and the API
  offers no way to force a verdict. The panel's live evidence is therefore the `stayed`, the
  challenge-free and the empty branches.
* **The career's league is a career fact.** A move rewrites `career.competition_id/name`; the world's
  `Team.competition_id`, the competition pages and the newsroom do not move, and a second career's
  season is unaffected.
* **No ability to play past the horizon.** The season closes at its last round, and the next one
  opens at the following round; nothing resets `rounds_played`, extends a career past its horizon, or
  plays a third season.
* **A judgement of pace, not a table.** The lines are authored constants, so "promoted" means "at or
  above 1.8 points per round in the lowest tier", not "finished above the club below you" — there is
  no second club's season to finish above.
* **No board reaction to the move.** The verdict is written; the board block still projects the
  career's own objectives and nothing dismisses, fines or re-arms a manager on a relegation.
* **One career per boundary row.** The row records the span and the decision; it does not claim a
  historical table, a match report per round or a season summary beyond what `record` sums.

## 9. Reproduce

```bash
# the tests
cd apps/api && python -m pytest tests/test_career.py -q

# the migration, on a fresh file
cd apps/api && DATABASE_URL="sqlite:///$TEMP/seasons-fresh.db" python -m alembic upgrade head
cd apps/api && DATABASE_URL="sqlite:///$TEMP/seasons-fresh.db" python -m alembic check

# the live walk (API over a migrated copy of the QA database)
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-seasons.db" KNOWLEDGE_AUTO_INGEST=0 \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8734
cd apps/web && API_INTERNAL_URL=http://127.0.0.1:8734 npx next build && API_INTERNAL_URL=http://127.0.0.1:8734 npx next start -p 3213

# register, open a career, play to the boundary
python .scratch/walk-seasons.py
python .scratch/check-seasons-page.py
```
