# M13 verification — a career's season is the calendar the world drew

ROADMAP_NEXT item 12 ("real-structure simulation tie-in") landed 2026-10-31 on top of item 8's season
model and item 9's two-tier world. Until this change a career's fixtures were a rotation the career
invented: opponents in slug order, the first cycle at home and the second away, while the generated
world already held a full double round-robin for that club. Now the season's Nth round is the club's
Nth generated fixture — same opponent, same side, same venue, same matchday label — and the career's
own published rotation is the fallback it turns to when that calendar runs out or the world holds none
for the season it has reached. Each played round also records *which* generated fixture it filled, so
the world's own record can be read beside the career's (the tie half, migration `0046`).

Date: 2026-10-31.

## 1. The plan is the club's own row

`calendar_fixtures(session, career, *, bounds=None)` reads `real_matches` for the career's
competition and the season's label (the label `season_bounds` derives — a 2026 career's second season
asks for 2027), keeps the rows where the club is home or away, and orders them by `kickoff_at` then
`slug`. It returns `[]` when the career has no club or competition, and `[]` when the world holds no
fixture for that season and competition.

`next_fixture_plan` keeps its refusal first (no competition → `available: false` with a sentence),
computes `round_in_season = max(1, round_index − bounds["first_round"] + 1)`, and, when the calendar
has a row at that position, answers from it:

* `source: "world_calendar"`, `match_slug` and `round_label` from the row;
* `side` from which side of the row the club is on, `opponent_*` from the other club;
* `venue_name` from the row — the generated venue, not the club's stadium guessed;
* `calendar: {season, position, of}` so the page can say "season fixture N of M";
* `basis`: "the club's {round_label} fixture in the generated {season} calendar, season fixture N of M,
  as the world drew it";
* `round_in_season` and `season_index` beside the existing `round_index`, and a `seed` that is still the
  digest of `(career.id, round_index)` — the world draws the fixture, the career's own seed draws the
  score.

The world row is a **schedule**, not a result. The career's simulation plays its own match from its own
seed and stores the simulation's slug on `career_fixtures.match_slug`; the plan's `match_slug` names
the world fixture whose slot it fills. A 2026 world row is already `completed` with the world's score —
the walk below reads it before and after the career and finds it unchanged — so nothing in the plan
copies a goal into a career or a career's goals into the world.

The tie half (also item 12) records the slot on the career's own row. `play_round` copies the plan's
generated fixture id and slug onto `career_fixtures` (`world_match_id`, `world_match_slug`) when the
round's source is `world_calendar`, and leaves both null when the round continued on the career's
rotation — no fixture is invented for a round the world never drew. The columns are plain strings, not
foreign keys (migration `0046`): a career outlives the generated world re-syncs rewrite, so the stored
slug is what a link and a re-read use. Rows written before the migration keep both null — no backfill
is possible, because the fixture a pre-migration round played was never stored — and the view says a
round has no world row rather than guessing one.

## 2. The fallback is published, not hidden

When the calendar has no row for the round, the plan says so and continues on the career's rotation:

```
fallback_round = round_in_season − len(calendar)   (or round_in_season when the calendar is empty)
cycle, position = divmod(fallback_round − 1, len(opponents))
side = home in odd cycles, away in even ones
```

Two bases, each naming its cause: after an exhausted calendar, "the generated {season} calendar holds
{N} fixture(s) for this club, so season round R begins the career's own rotation: opponents ordered by
slug, position P of K in cycle C of season I; the first cycle is played at home and the second away";
with no calendar at all, "the generated world has no {season} calendar for this competition, so the
career rotates its own opponents" plus the same rotation sentence. Counting is **within the season**:
the fallback starts at its own round 1 after the calendar ends, not at whatever phase the absolute
round number would have had. `cycle` and `of` are on the wire; the page prints the `basis` sentence,
so the fallback is as visible as the calendar branch.

The no-calendar branch is the usual case after a promotion or relegation: the career's competition
moves at the boundary (item 8) while the club's world membership does not (item 9), so the new league's
calendar names other clubs. The 2027 opening fixtures the world leaves `scheduled` are the exception
the other way — when the club holds one, it is played as that season's calendar's first fixture.

## 3. Isolation: the world keeps its own results, on purpose

The old roadmap line read "results feed the public world pages (M3) and the career ledger (M6) from the
same rows". This delivery **rejects the first half** and says why: `real_matches` is shared,
deterministic and read by every account, while a career's scores are one manager's private fiction.
Feeding them back would rewrite the world under every other reader and break the seed-reproducible
fingerprint the world gate pins. The ledger half is kept: the career's own fixtures are the rows its
page, board, development and ledger blocks sum.

The calendar supplies order, opponent, side and venue — never the score. The live walk re-read every
world fixture the career's season named and found status and score unchanged, and every 2027 opening
fixture still `scheduled` and scoreless.

### The tie, read beside the career's own row

`career_view` names the world fixture for every round that played one: `world_match_slug` (the stored
slug, repeated on the row), `world_match_path` (`/match/{slug}` while the world still holds it),
`world_match_still_stored`, `world_status` and `world_goals` (the world's own home and away figures as
the world drew them). A rotation round carries nulls in all five. A world row a re-sync removed keeps
the stored slug and loses the path, status and goals — the same shape `match_still_stored` gives a
deleted simulation report — so the page can say "world fixture deleted" without pretending the round
had no fixture. The `limitations` block gained `world_calendar`, whose own words say the tie is
one-way; `TestWorldTie`'s sixth case asserts that wording rather than trusting it.

## 4. The web page

`apps/web/lib/types.ts`'s `CareerNextFixture` gained `source?: "world_calendar" | "career_rotation"`,
`match_slug?`, `round_label?`, `calendar?: {season, position, of}` and `basis?`, and dropped the old
`rotation?` count pair. `career/[slug]/page.tsx` and `challenges/runs/[slug]/page.tsx` feed the
unchanged `nextUp` ICU message `rotation: next.basis ?? ""`, so the same slot now prints the calendar
sentence for calendar rounds and the fallback sentence (naming the cycle) for rotation rounds — no
catalogue key changed, no placeholder renamed.

The fixture table gained a World fixture column between the score and the venue: when
`world_match_path` is present the cell links to the generated fixture and prints the world's own score
(the status when it has none), when only the stored slug survives it prints "world fixture deleted",
and a rotation round prints "—". The table prints `limitations.world_calendar` under it whenever any
row carries a tie. Three new keys (`thWorld`, `worldTieHint`, `worldFixtureDeleted`) landed in all
three catalogues; the dead-key scan (`qa-unused-keys.mjs`) finds them used on the page.

## 5. Evidence

| Check | Result |
| --- | --- |
| `pytest tests/test_career.py` | **50 passed**, 7 `TestCalendar` + 6 `TestWorldTie` |
| `pytest tests/test_career_api.py tests/test_scout_transfer_sim.py tests/test_sim_ledger.py` | green (122 passed in the four-file set) |
| `pytest tests/test_transfers.py tests/test_challenges.py` with the set above | **208 passed** (six files) |
| `alembic upgrade head` on a fresh SQLite file | clean through `0046` (`0045 → 0046`) |
| `ruff check app tests migrations` | clean |
| `mypy app` | **Success: no issues found in 161 source files** |
| web `tsc --noEmit` | clean |
| `next lint` | clean |
| full API suite | *(recorded below once the run on `af6abda` finishes)* |

The seven calendar cases: `test_every_round_is_the_clubs_own_generated_fixture`,
`test_the_calendar_meets_every_club_once_at_home_and_once_away`,
`test_a_round_after_the_generated_calendar_continues_on_the_careers_rotation`,
`test_a_scheduled_opening_round_is_still_the_worlds_calendar`,
`test_a_season_the_world_never_drew_keeps_the_careers_rotation`,
`test_a_round_seed_comes_from_the_career_and_the_round_only`,
`test_a_club_with_no_competition_is_refused_in_words`.

The six tie cases: `test_a_calendar_round_records_the_generated_fixture_it_played`,
`test_the_generated_fixture_keeps_the_score_the_world_played`,
`test_a_rotation_round_names_no_generated_fixture`,
`test_the_view_prints_the_careers_score_beside_the_worlds_own`,
`test_a_fixture_the_world_no_longer_holds_keeps_the_slug_and_loses_the_link`,
`test_the_limitation_says_the_tie_is_one_way`.

The transfer simulation reads the same rule: `test_the_rounds_follow_the_plan_the_career_would_really_play`
and `test_the_second_half_mirrors_the_first_on_the_other_side` project the next fixtures through
`calendar_fixtures` + `next_fixture_plan`, and `transfer_sim.py`'s `fixtures_from` names the calendar
and its published fallback. `test_sim_ledger.py`'s away-round case derives the first away round from
the calendar instead of assuming the away half begins at `len(opponents) + 1`.

## 6. The live walk — API `:8755`, SQLite `.scratch/walk-calendar.db`

`.scratch/walk-calendar.py` registers an account, opens a career for Braeford Athletic (Braehaven
Elite League, eight clubs), and plays it through `POST /careers/{slug}/play` while checking every plan
against the public pages:

* **Season one, 14 rounds.** For each round the plan's `source` was `world_calendar`, its
  `round_in_season` was 1…14, its `calendar` block read `{2026, N, 14}`, and its `match_slug`,
  `round_label` and `side` equalled the club's Nth row of
  `GET /world/competitions/braehaven-elite-league?season=2026` ordered by kickoff — 7 home and 7 away,
  14 distinct slugs. The boundary closed at round 14 and the next plan's `season_index` was 2.
* **Season two, 2027.** The world holds exactly one fixture for this club
  (`2027-braehaven-elite-league-braeford-athletic-thornwick-miners-matchday-1-game-1`); it was played
  as calendar position 1 of 1. The next plan was `career_rotation`, cycle 1, `of` 7, side home, basis
  "the generated 2027 calendar holds 1 fixture for this club, so season round 2 begins the career's own
  rotation: opponents ordered by slug, position 1 of 7 in cycle 1 of season 2"; the round after it
  continued at position 2 of 7 in the same cycle. The walk played both.
* **Isolation.** All 14 world rows the career's season named were compared on `status`, `score`,
  `home_goals` and `away_goals` before and after: **0 changed**. The 2027 opening fixture was still
  `scheduled` and scoreless after being played as a career slot.
* **The ledger rows.** The career's 16 played fixtures each carry their own simulation `match_slug`
  (`without_sim: []`), and the plan's world slugs never appear as the simulation's.

## 7. The tie walk — API `:8756`, SQLite `.scratch/walk-tie.db`

`.scratch/walk-tie.py` registers an account, opens a career for Braeford Athletic, and plays three
rounds through `POST /careers/{ident}/play` against a database created by `alembic upgrade head` (the
migration chain, not `create_all`). For each round the played ledger row named the world fixture the
plan had named (`world_match_slug`), linked to `/match/{slug}`, reported
`world_match_still_stored: true`, and carried the world's own status and score — `0–0`, `2–0`, `0–0`
on the 2026 rows — while the career's own report slug stayed distinct (`braa-v-thom-…`,
`ostn-v-braa-…`, `braa-v-hals-…`). The `world_calendar` limitation answered the one-way sentence.
Re-reading the competition's fixtures afterwards found **0 world rows changed**.

## 8. The browser pass — dev web `:3219`/`:3220`, API `:8755`/`:8756`

A dev server from the `world-calendar` worktree (its own `.next`, so it does not collide with the
shared tree's other dev server) ran against the walk's API; the walk account was logged in and
`/career/calendar-walker-braa` was opened. The page rendered:

* the next-fixture line — "下一场：第 17 轮，主场对阵 Dunmoor Town（Braeford Yard）。the generated 2027
  calendar holds 1 fixture for this club, so season round 3 begins the career's own rotation: opponents
  ordered by slug, position 2 of 7 in cycle 1 of season 2…" — the API's `basis` inside the unchanged
  ICU sentence, with round 17 = season round 3, the same arithmetic the API returned;
* the season block — "第 2 个赛季 · 2027", rounds 15–28 of 14, the closed 2026 row ("留级", no move),
  and 16 played fixtures in the list.

No screenshot was taken: the in-app browser had no attached viewport (`0x0`), so the pass is the
rendered DOM text read after hydration. Pointer clicks were unavailable for the same reason; the login
form was submitted through the page's own button element.

After the tie landed, a second pass ran from a worktree at `af6abda` (its own `.next`) against the tie
walk's API on `:8756`. The session was authenticated by a same-origin `POST /api/v1/auth/login` from
the page (the walk account), then `/career/tie-walker-braa` was opened; the reader's locale was
Chinese. The fixture table's fourth header read 世界赛程, and each of the three played rounds carried a
world cell linking to `/match/2026-…-matchday-N` — `0–0`, `2–0`, `0–0`, the world's own figures — with
the hint "生成赛程自身的记录——本职业的轮次从不会改写它。". The career's own report links beside them
stayed `/simulate/braa-v-thom-…` and the like, and the limitation under the table was the
`world_calendar` sentence. Two links, two records: the world's own and the career's.

## 9. What this does not claim

* **The world's pages do not move.** The 2026 scores shown anywhere in `/world/*` are the generated
  world's own; a career's identical fixture is a different match with a different report. This is the
  deliberate half of item 12 that was not built as the roadmap once worded it.
* **The calendar is not a score source.** Only opponent, side, venue, order and label come from the
  world. A world fixture already `completed` stays exactly as it was.
* **One club, one competition in the live walk.** The moved-league branch (no 2027 calendar for the new
  competition) is covered by `test_a_season_the_world_never_drew_keeps_the_careers_rotation`, not by a
  live promotion — the engine's results decide the boundary and the walk's career stayed.
* **No third season was played live.** The label advancing past 2027 is item 8's `season_label` rule and
  its tests; this walk shows the first boundary and three rounds of the second season.
* **The page header still reads the base season.** "Braeford Athletic · 2026" beside a season block that
  reads 2027 is item 8's stored base label (the season block shows the label being played), unchanged
  by this item.
* **No new endpoint.** The plan rides on the existing career view and play response; the wire gained
  fields, not doors, so the contract census and the probe's population are unchanged.
* **The tie is identity, not result.** A round stores which generated fixture it filled; the world's
  status and score are read from that row and printed beside the career's. No career score moves into
  `real_matches` and no world score moves into the career's row — `TestWorldTie` compares the world row
  before and after a play, and the tie walk re-read every 2026 row after three rounds.
* **Pre-`0046` rounds carry no tie.** The columns are nullable and no backfill was attempted; such a
  round prints "—" in the world column, not a guessed fixture.
* **The tie walk plays three rounds, not a season.** The season-length order evidence is the calendar
  walk above; the tie evidence is `TestWorldTie` plus these three live rounds.

## 10. Reproduce

```bash
# the tests
cd apps/api && python -m pytest tests/test_career.py tests/test_career_api.py \
  tests/test_scout_transfer_sim.py tests/test_sim_ledger.py -q

# the live walk: API on a fresh SQLite file, then the script
cd apps/api && ENV=development DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-calendar.db" \
  CORS_ORIGINS="http://localhost:3210,http://127.0.0.1:3210" \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 8755
python .scratch/walk-calendar.py          # writes .scratch/calendar-walk.json

# the tie: a fresh file migrated through the chain, then the tie walk (API on :8756)
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-tie.db" python -m alembic upgrade head
bash .scratch/run-walk-tie.sh             # serves :8756 on that file
python .scratch/walk-tie.py               # writes .scratch/tie-walk.json

# the page, from the calendar worktree so its .next is its own
cd .scratch/wt-calendar/apps/web && API_INTERNAL_URL=http://127.0.0.1:8755 npx next dev -p 3219
```

## 11. The boundary fix the challenge walk named

The challenge walk (`apps/web/scripts/visual-qa.mjs`, the section that plays a six-round run to its window) failed
its verdict check with `Pts 8 / Points 0 / record 0-0-0`. The cause was item 8's boundary meeting item 12's
careers: `close_season` writes a `career_seasons` row for a challenge career too (verdict `challenge`), and
`season_bounds` treated every closed row as the last season's, so the span advanced to rounds 7–12 the moment the
window closed. `play_round` refuses past the window, so no round can fill the new span: `career_view`'s season
slice was empty while `fixtures` still listed the six played rounds — the table summed the Pts column, and the
record, objectives, board and highlights summed nothing.

A challenge career has exactly one season — its round window — so the fix is in `season_bounds`: a career with a
challenge window returns rounds 1…window whatever boundary rows exist, and `close_season` returns that one row
instead of deciding a second season. The regression case is
`tests/test_career.py::TestSeasons::test_a_closed_challenge_window_still_sums_its_own_rounds`; on the old code it
reads the span as `(2, 3, 2, 4)` and fails, on the fixed one `(1, 1, 2, 2)` and passes. The live walk is
`.scratch/walk-challenge-record.py` (API `:8757`, fresh `alembic upgrade head` file `.scratch/walk-challenge.db`):
a six-round `win-with-academy-players` run, then `GET /challenges/runs/{ident}` read the way the page reads it —
**Points 9 = the Pts column's 9, record 2-3-1, the wins objective at 2, season 1 spanning rounds 1–6**, the closed
block at season 1 with verdict `challenge`, and the round past the window refused `409 window_closed`. Evidence:
`.scratch/challenge-walk.json`. The command:

```bash
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-challenge.db" python -m alembic upgrade head
bash .scratch/run-walk-challenge.sh       # serves :8757 on that file
python .scratch/walk-challenge-record.py  # writes .scratch/challenge-walk.json
```

