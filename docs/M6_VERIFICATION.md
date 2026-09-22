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
python -m mypy app                       # Success: no issues found in 67 source files
python -m pytest -q                      # 308 passed
FOOTBALL_OS_TEST_DATABASE_URL=postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest \
  python -m pytest -q                    # 308 passed — same tests, both engines
alembic upgrade head && alembic check    # no new upgrade operations detected
python scripts/export_openapi.py         # repo root: 63 paths / 73 operations
```

A live pass against the running server (registered account → options → play → detail → replay →
delete) reproduced `identical: true` with the stored and replayed digests equal, and answered 404 on
the row after deletion. Its account and rows were then removed from the development database, so the
counts in this document are the counts on the machine.

## 9. Not claimed by this milestone

* **Career Mode (§20), Manager live challenges (§21) and the transfer market (§22)** — none of them
  exist yet. A career is a schedule of these matches plus standings, finances and a club to manage;
  the schedule, competition-place tables and money model are the next slice, not this one.
* **No `sim_events` table.** Events live inside the report JSON. The query that would need them
  (a scorer's season total across simulated matches) does not exist yet, and a table for it would be
  schema ahead of demand.
* **Fatigue does not feed back into training or squad value.** The engine models fatigue *inside* a
  match; nothing carries across matches, because there is no competition state to carry it in.
* **No provider is involved.** This is arithmetic on stored rows, so no `ModelCall` row is written
  and no key is consulted; the AI-labelling rule (§62) applies to the text the model generates about
  a match in later milestones, which this increment does not write.
* **The 90-minute default is not a real football clock**: blocks are 6′, so a 90′ match is 15 blocks.
  Minute-level event times are block-derived.
