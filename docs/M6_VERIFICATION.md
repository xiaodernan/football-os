# M6 Football Simulation — engine and storage verification (spec §19, §20–§22, §60, §61, §62)

Date: 2026-09-22 · Tier: `apps/api` · Scope: the match model itself — the eleven it selects, the
rates it applies, the report it writes, the row it stores and who may read that row.
**The web surface is not claimed here**; it is `docs/M6_WEB_VERIFICATION.md`.

M6 in the spec is a milestone of seven parts (Simulation Engine, Career, Manager, Squad, Training,
Transfers, Matches). This document closes the first and the last of those: a deterministic engine
that plays one match between two stored clubs, and the private record of every match an account has
asked it to play. §9 lists what is therefore *not* claimed.

## 1. Why this engine prints its arithmetic

A simulated scoreline is the easiest thing in this product to lie with, because nothing contradicts
it. So the rule the build follows is that every number a reader cannot check is a number the engine
does not get to state:

* **Inputs are measured from stored rows, never typed in.** `profile.py` reads the club's squad out
  of `teams`, `real_players` and `tactical_systems` and derives each index from what is there —
  the mean of the eleven the formation actually selects, the metres of the chosen shape. There is no
  request field that says "attack: 0.8"; the API accepts two club slugs, two system slugs, a length
  and a seed, and refuses anything not present in the world.
* **Every rate ships its own expression.** `report["model"]["factors"]` carries nine named rates,
  each with the formula string the code actually evaluates and a plain sentence of what it reads.
  The report's `sides.*.inputs.factors` carries the same for the ten measured inputs per side, so a
  reader can compare an index against the metres and attributes it was computed from.
* **The coefficients are authored, and say so.** `CALIBRATION_NOTE` is shipped in every report:
  *"coefficients authored by this project; no real match data was used to fit them, and the engine
  claims no accuracy against real football."* Nothing in the repository fits them to anything.
* **What it refuses to model is listed, not hinted at.** `model["what_it_does_not_model"]` states
  five absences (substitutions, scoreline-dependent possession, set-piece routines beyond corners,
  goalkeeping as its own attribute, weather/referee/crowd/travel). A reader who wonders why a red
  card did not change a team's shape is told in words rather than left to infer.
* **§19's sentence travels with the payload**, verbatim, not with the page: *"Simulation result is
  fictional / model-generated and should not be interpreted as a real-world prediction."* beside
  `data_origin: "simulation"` and `is_demo_data: true`. A caller that ignores the API's own fields
  still has to delete them to present the match as a fact.

| Layer | File | Owns |
| --- | --- | --- |
| profile | `app/services/simulation/profile.py` | formation split, band selection with borrowing, the ten measured inputs per side, each with its formula |
| engine | `app/services/simulation/engine.py` | `possession-block-v1@1.0.0`, the 6′ blocks, the nine rates, events, the digest, the self-description |
| service | `app/services/simulation/service.py` | storing a match, reading it back, replaying it, the per-account ceiling, `row()` and `report` mapping |
| routes | `app/api/v1/simulations.py` | 6 endpoints behind 4 paths: options, play, list, detail, replay, delete |
| table | `sim_matches` (migration `0007`) | the chosen inputs, the seed, the report JSON, its digest, owner and timestamps |

`real_players` is the synthetic world's player table (its own docstring: *a generated footballer in
the synthetic world — strictly separate from `UserPlayer`*). The name predates M6; no real person's
attributes are stored anywhere in this database.

## 2. What "measured from stored rows" means concretely

* A formation string splits into back/mid/front counts; the first digit is the back line and the
  last is the front line, so `4-2-3-1` is 4–5–1 in bands. Unreadable data falls back to a stated
  default instead of crashing or inventing a shape.
* Each band takes the best-rated players available in it. A short band borrows from another band and
  nobody is picked twice — and the borrowed count is itself one of the shipped metrics
  (`defence_short` and its siblings), because a filled band whose index came from elsewhere should
  not read as the club's reputation.
* Ten inputs per side carry a formula: the four indices (attack, midfield, defence, press), form, the
  three band counts, and the shape's own metres when an authored system was chosen. Every index is
  asserted to land in the documented 0–1 range, and re-deriving them from the squad that is
  *actually* stored reproduces them.
* A club may be played with no authored system. That is not an error and not a zero: the report's
  input list then says the shape metrics are empty, and the page prints that sentence.

## 3. Determinism, and what the digest covers

Randomness comes from `WorldRng` — the project's own seeded generator, chosen over
`random.Random` whose `sample`/`shuffle` internals have changed between Python releases. One seed
drives the whole match: block order, shot attempts, chance quality, cards, injuries.

`_digest()` hashes a canonical dump of the finished report and keeps the first 16 hex characters,
**taken before the `digest` key exists** — a report cannot contain its own hash, and cannot change
after the hash is written.

What the tests assert:

1. the same seed and the same inputs replay identically, byte for byte;
2. a different seed is a different match (the digest moves);
3. changing one stored attribute changes the match — the model is sensitive to its inputs, not just
   to its seed;
4. the order of rows in a squad list does not change a report (selection is by measured value, not
   by iteration order);
5. a shorter match is its own simulation, not a truncation of a longer one;
6. `GET /simulate/{ident}/replay` re-derives the report from the stored inputs on the server and
   compares digests, answering `identical: true` with both values beside it. When it answers
   `false` the row is kept as a record of what was claimed, and the page says the engine moved
   without its version moving.

## 4. What a test run checks about the numbers themselves

`tests/test_simulation.py` (38 tests) does not accept "the model produced a JSON":

* goals equal the number of goal events, cannot exceed shots, and each goal event carries a running
  score whose last value is the final line;
* every scorer came from the eleven their own side lists — a goal by a player not on the pitch is a
  bug, not a stat;
* the blocks tile the match with no gap or overlap and end on the final score;
* the totals table agrees with both side blocks, and `pass_accuracy_pct` is a rate of its own
  attempts rather than of passes;
* events are in minute order;
* goals and expected goals are reported *apart*, so an over- or under-performing match is visible
  rather than smoothed;
* a man-down side's multipliers actually move (fewer chances made, more conceded), fatigue is
  crossed with late space and form decides which of the two wins, a stretched shape makes more
  chances than a deep one.

## 5. Storage, ceilings and ownership

* `sim_matches` holds the chosen inputs (two nullable team ids with `SET NULL`: a regenerated world
  must not destroy a match record, which keeps its own copies of the names), the seed, the length,
  the report JSON, the digest, `data_origin` and `is_demo_data`.
* The slug is derived from the two short names and the digest, so the same fixture and seed collide
  by design and take a random suffix instead — which is how the walk proves two separately stored
  rows can carry the same digest.
* 100 stored matches per account (`SIM_LIMIT_PER_USER`), refused with 409 and the ceiling in the
  message.
* Every door except `/options` requires a session. A row belonging to somebody else answers **404**
  on detail, on replay and on delete — not 403, so existence is not leaked. `/options` is public
  deliberately: the clubs and systems it lists are already public under `/world` and `/tactics`;
  what is private is which fixtures an account played.
* Deletion removes the row; the digest and report go with it.

## 6. Served surface

| Route | Auth | Notes |
| --- | --- | --- |
| `GET /api/v1/simulate/options` | public | 20 clubs, 50 authored systems, lengths 30/60/90/120 at 6′ per block, the nine rates, calibration note, `ready` |
| `POST /api/v1/simulate` | session | 201 with the stored row; 20/min and 60/h |
| `GET /api/v1/simulate` | session | this account only, newest first |
| `GET /api/v1/simulate/{ident}` | session | by id or slug; the full report |
| `GET /api/v1/simulate/{ident}/replay` | session | re-derive and compare digests |
| `DELETE /api/v1/simulate/{ident}` | session | 204 |

`GET /api/v1/capabilities` no longer hardcodes its milestone flags. `m6_simulation` is derived from
the tables the milestone created, and `m5_video_analysis` from the media tools the host actually has
plus the count of stored clips — the endpoint answers for what is on the machine, not for what the
code contains.

## 7. Defects found and fixed while building this

1. **Nine `union-attr` complaints from mypy** on the JSON `report` column: reading `report["sides"]`
   off an `Any`-typed ORM attribute type-checked until it met a row whose JSON had been stored
   differently. Fixed by `_as_mapping()`, which copies a mapping or returns an empty one, at all
   three read sites — rather than a `cast` that asserts what the code cannot know.
2. **`alembic check` drift** on migration `0007`: the ORM declares `slug` unique, and the migration
   had expressed that as a unique *index*. Postgres accepted both; `alembic check` refused to call
   them the same thing. The migration now declares `sa.UniqueConstraint("slug")` and no slug index.
3. **A report that printed its indices but not the measurements behind them.** The first cut shipped
   `attack_index: 0.63` and the formula for the rate that used it, but not the squad means and the
   metres the index was computed from — so the §62 promise that a reader can check a number was
   only half kept. `sides.*.inputs` now carries both, with a test that asserts the printed width
   equals the profile's width to two decimals.
4. **Capability flags that lied in both directions**: `m5_video_analysis` said `false` on a host that
   had just analysed a clip, and `m6_simulation` was going to say `true` before the tables existed.
   Both are derived now.
5. **A test that used a fixture object as if it were a value** (`system_slugs[0]` on the fixture
   function) — a `TypeError` at collection, not a false pass. It is why the API tests take
   `system_slugs` as a parameter.

## 8. Reproduce

```bash
cd apps/api
python -m ruff check app tests           # All checks passed!
python -m mypy app                       # Success: no issues found in 71 source files
python -m pytest -q                      # 376 passed
FOOTBALL_OS_TEST_DATABASE_URL=postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest \
  python -m pytest -q                    # 376 passed — same tests, both engines
alembic upgrade head && alembic check    # no new upgrade operations detected
python scripts/export_openapi.py         # repo root: 73 paths / 85 operations
```

A live pass against the running server (registered account → options → play → detail → replay →
delete) reproduced `identical: true` with the stored and replayed digests equal, and answered 404 on
the row after deletion. Its account and rows were then removed from the development database, so the
counts in this document are the counts on the machine.

## 9. Not claimed by this milestone

* **The transfer market (§22)** does not exist yet. Manager live challenges (§21) landed after this
  section was written — §11 says what they are and which of their constraints bind. Career
  Mode (§20) landed as a schedule of these matches with a record and objectives read off them;
  §10 says exactly which parts of that sentence are true and which are not.
* **Finance.** A career carries a stated budget and nothing spends it: with no transfer market, no
  fixture was affected by a large or a small number, and `limitations()` on every career response says
  so instead of letting the figure look like a constraint that was tested.
* **No `sim_events` table.** Events live inside the report JSON. The query that would need them
  (a scorer's season total across simulated matches) does not exist yet, and a table for it would be
  schema ahead of demand.
* **Fatigue does not feed back into training or squad value.** The engine models fatigue *inside* a
  match. A career carries a schedule and a record across matches, but no player attribute, fatigue or
  squad value is written back to the world's rows by playing.
* **No provider is involved.** This is arithmetic on stored rows, so no `ModelCall` row is written
  and no key is consulted; the AI-labelling rule (§62) applies to the text the model generates about
  a match in later milestones, which this increment does not write.
* **The 90-minute default is not a real football clock**: blocks are 6′, so a 90′ match is 15 blocks.
  Minute-level event times are block-derived.

## 10. Career Mode (added 2026-09-23, backend)

`app/services/simulation/career.py` + `app/api/v1/careers.py` + migration `0009`. The evidence here is
28 tests (`tests/test_career.py`, `tests/test_career_api.py`) green on SQLite and
PostgreSQL+pgvector, plus the contract rows in `docs/api/openapi.json`. Its page landed the same day and
is browser-verified in [`M6_CAREER_WEB_VERIFICATION.md`](M6_CAREER_WEB_VERIFICATION.md).

What a career is, and what it deliberately is not:

* **The container, not a second engine.** `play_round` calls `run_simulation`; every round lands in
  `sim_matches` with its own digest, and `career_fixtures` stores the round's inputs (opponent, side,
  seed) plus a *copy* of the score so a career still reads after its report is deleted. The
  `consistency` field re-reads the linked report and states how many fixtures were re-checked.
* **A rotation, not a shuffle.** Opponents are the clubs of the career's own competition ordered by
  slug, met once at home in the first cycle and once away in the second. A round's seed comes from
  `blake2b(career_id:round_index)`, so the same two accounts managing the same club face the same
  order — a test asserts it — while the score still comes from the engine.
* **Sums, not stored numbers.** `played/won/drawn/lost/goal_difference/points/unbeaten_run` are
  computed from the career's fixture rows on each read, each with the formula that produced it; the
  mini-table is built from the same rows and says plainly that it covers only this career's fixtures,
  not the competition's table.
* **Judged by stated objectives.** A career cannot be opened without at least one objective from
  `wins / points / goal_difference / unbeaten`, and each verdict prints the formula it was compared
  with. No promotion, relegation or prize follows — the season is a fiction with a scoreboard, not a
  league simulation.
* **Private like the rest of §61.** `/careers/options` is public (it is the world's own clubs and the
  50 authored systems); opening, playing, reading and deleting a career need a session, and another
  account gets 404 rather than 403. Deleting a career removes its rounds and keeps the match reports
  the account chose to play.
* **Ceilings are enforced where they are checked:** 5 careers per account (`409 career_limit`), 90
  minutes per round, and every route rate-limited under its own scope.

## 11. Manager Live Challenges (added 2026-09-23, backend)

`app/services/simulation/challenges.py` + `app/api/v1/challenges.py` + migration `0010`. The evidence
here is 32 tests (`tests/test_challenges.py`) green on both engines, plus a live pass on a seeded
database quoted below. The page landed 2026-09-24 and is browser-verified in
[`M6_CHALLENGES_WEB_VERIFICATION.md`](M6_CHALLENGES_WEB_VERIFICATION.md): 17 walk checks over the
catalogue, the measured club, the summed verdict and the refused seventh round.

§21 asks for three properties of a challenge. This is what each one actually is:

* **Time limited.** Every scenario names a `window_rounds`, stored on the career the run opens in
  (`challenge_window`, migration `0010`). The window is enforced inside `career.play_round` — the only
  path that can play a round — which raises `WindowClosed`, and the route answers `409 window_closed`
  with the rounds that closed it **and the run's final verdict beside it**, so the page has something
  to show rather than a dead end. An open career stores `0` and is never limited.
* **Goal based.** The scenario fixes its objectives and the start endpoint accepts none, so a target
  cannot be lowered once the run is open. Verdicts reuse `OBJECTIVE_FORMULA`, the same table Career
  Mode judges open careers with, and every objective prints the formula it was compared with.
  `in_progress` while rounds remain, `met` only when the window closed *and* every objective was
  reached, `missed` when the window closed short.
* **Reward based.** The reward is earned by `met` and by nothing else — including the suspicious case:
  every objective reached with rounds still to play earns nothing, because the window has not closed.
  Nothing consumes a reward yet; the response says there is no wallet behind the number.

Two further rules keep it consistent with the rest of M6:

* **A run is a career, not a second container.** Starting a challenge opens a normal `careers` row; its
  rounds are `career_fixtures`; each round is decided by `run_simulation`. One match model, one fixture
  store, one play path — which is precisely why the window needs enforcing in only one place.
* **Constraints publish whether they bind.** §21's own examples are mostly rules the build cannot apply
  yet, so each constraint ships `enforced: true|false` and the sentence that says what it does. The
  window and the fixed goal are enforced; the budget is enforced as a number that cannot be raised and
  says that nothing spends it; `no_transfers` and `academy_only` are published and **not** applied,
  because there is no transfer market and the eleven has no age filter. A test asserts they say so.

The weakest club a scenario hands you is chosen by **measurement**, not by an adjective:
`resolve_challenge_club` builds every club in the named competition with `profile.team_profile` — the
same reader the engine uses — ranks them by selected-eleven rating, and takes the lowest. The whole
ranking and the gap to the runner-up travel with the choice. That rating is on the engine's **0–1**
scale (the mean of `/100` player attributes, divided), which is what `/challenges` prints and what the
browser walk reads back — `0.4891` is a low club, not a broken one.

| Route | Auth | Notes |
| --- | --- | --- |
| `GET /api/v1/challenges` | public | 6 scenarios, integrity, fingerprint, objective formulas, how a verdict is decided, limitations |
| `POST /api/v1/challenges/{slug}/start` | session | 201; the club choice and the live verdict |
| `GET /api/v1/challenges/runs` | session | this account's runs, each with its verdict recomputed |
| `GET /api/v1/challenges/runs/{ident}` | session | one run: scenario, verdict, fixtures, limitations |

Playing goes through `POST /api/v1/careers/{ident}/play`, which now also returns `challenge_verdict`
(a run) or `null` (an open career). `GET /api/v1/capabilities` gained `m6_manager_challenges`, derived
from the catalogue being sound, the run columns being present and the world being there — not from
someone having started a run.

Live pass on a seeded database (SQLite, 2026-09-23), after which the run and its account were removed:

```text
competition 'Thornford Superleague' holds 5 clubs
catalogue 6 scenarios · integrity clean: True · fingerprint 1345294b922361f9
start 201 · club chosen: Thorndera Town overall 0.4982
  field: Cordale Town 0.6791 · Corgard Town 0.6727 · Ildwick Athletic 0.6627 ·
         Ostford Wanderers 0.5891 · Thorndera Town 0.4982
  window 6 · budget 100000 · objectives [('wins', 4)]
round 1/6 -> in_progress remaining 5   …   round 6/6 -> missed remaining 0
7th round: 409 window_closed | this challenge's window closed after 6 of 6 rounds
  verdict carried by the refusal: missed · reward earned False
final verdict: missed · objectives [('wins', 0, 4, False)]
  reward: Homegrown earned False | 0 of 1 objectives met after 6 of 6 rounds
capabilities: m6_manager_challenges = True · {'runs': 1, 'scenarios': 6}
```

**Both engine legs re-run 2026-09-24, and the second one reported a defect worth recording.**
`alembic upgrade head` applied `0010` on PostgreSQL+pgvector and `alembic check` reported no drift;
`ruff check app tests` and `mypy app` (71 files) are clean; the full suite is **376 tests green on
SQLite and 376 green on PostgreSQL+pgvector**.

The first PostgreSQL run of the full suite was **not** green: it reported one error,
`tests/test_knowledge_rag.py::test_ingest_endpoint_is_staff_only` —
`UndefinedTable: relation "training_drills" does not exist` — in a test that asserts a 403 and never
queries that table, on a file that passes alone and passes again in the full run. The honest reading is
that the throwaway database is a **single shared resource** whose session fixture starts with
`Base.metadata.drop_all()`: two runs against `football_os_pytest` overlap, and one drops the schema
under the other. Nothing in §21 caused it and nothing here should pretend the leg was clean on the
first attempt — it was clean on the second. The race itself is fixed in §13.

## 12. Defects found while building this section

1. **A pre-existing lint failure the docs claimed was clean.** `ruff check app tests` reported
   `UP038` in `app/services/tactics/sync.py` — a file untouched since M4 — so the committed tree did
   not pass the gate that §8 and the M4 and M6 documents say passes. Fixed by writing the isinstance
   tuple as `int | float`. Finding it is why `ruff check app tests migrations` (a wider target than
   either document quotes) was run rather than the quoted command alone.
2. **Three tests that asserted the wrong thing**, each caught by the first run: a crafted run with a
   two-round window was expected `met` when four wins were asked for and two were played (`missed` is
   correct); the window loop asserted `in_progress` on the round that closes the window; and the
   open-career test read `challenge_verdict` off a `POST /careers` response, which only `play` sets.
   The implementation was right in all three; the tests were wrong.
3. **The OpenAPI counts in §8 were stale.** Career Mode (§10) had already taken the contract from
   63 paths / 73 operations to 69, and §8 was not updated with it. Corrected to the live figure.
4. **`str(sqlalchemy.URL)` is not the URL.** While isolating the test database (§13), the first
   provisioning attempt died with `password authentication failed for user "football"` — against a
   server the same credentials had been connecting to all morning. `str()` on a `URL` renders through
   `hide_password=True`, so the connection string handed to `create_engine` carried a literal `***`
   where the secret belongs. The repr in the traceback even showed `football:***@…`, which reads as
   SQLAlchemy being considerate rather than as the bug. Use `render_as_string(hide_password=False)` or
   pass the `URL` object itself.

## 13. The server-backed test run got its own database (2026-09-24)

The defect §11 records is structural, not a one-off: `tests/conftest.py` pointed every run at one
fixed `football_os_pytest`, and its session fixture began with `Base.metadata.drop_all()`. Two
overlapping runs therefore emptied the schema on each other mid-flight, and the failure surfaced in
whichever query happened to run next — which is why it looked unrelated to anything. Retrying,
serialising runs, or declaring the leg flaky would all have been lies. So:

* `_run_scoped_url()` rewrites a non-SQLite `FOOTBALL_OS_TEST_DATABASE_URL` at **import** time, because
  a test module that imports an app module binds `app.core.db.engine` to `DATABASE_URL` at that moment —
  doing it in the fixture would have left the engine pointed at the old name. It keeps the
  "must contain `test`" guard, insists the name be a plain identifier (it has to create and drop it),
  and appends a run uuid.
* The session fixture then `CREATE DATABASE`s that name on the server's `postgres` maintenance database
  (AUTOCOMMIT, `NullPool` — neither optional), installs `vector` in it because the extension is not in
  `template1` on this server, and `DROP DATABASE … WITH (FORCE)`s it afterwards. A failure after
  creation releases the database too, so a red run leaves no residue.
* The SQLite leg is untouched: the rewrite returns early and `--collect-only` creates nothing at all.

Measured on this host (PostgreSQL 16.0.15, role `football` holding `CREATEDB`), two full suites started
at once against the same server:

```text
--- databases live mid-run ---
football_os_pytest_493a0a
football_os_pytest_4e6d2b
run A rc=0 tests=376
run B rc=0 tests=376
--- leftovers after both runs ---
0
```

The two names are the point: the runs could not have touched each other's schema even if they wanted
to, both reported green, and the server was left as it was found. That is the shape of proof the rest
of this milestone has used — the claim is the thing you can run, and the numbers above are the counts
on the machine, not an expectation about them.

The same path was then run against a stem that exists nowhere on the server —
`…/football_os_ci_simulated_test`, 45 world tests, green, zero databases left behind — because that is
the shape CI hands it: `.github/workflows/ci.yml` names `football_os_test` and used to create it and
its extension by hand immediately before `python -m pytest`. Those two `psql` steps are now gone, since
a run that provisions its own database does not need a pre-made one, and a pre-made one is exactly the
shared resource that caused this section.
