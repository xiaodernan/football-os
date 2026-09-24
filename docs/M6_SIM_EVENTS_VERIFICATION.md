# M6 item 4 — the match timeline as rows, and the check that they still say what the report says

Spec §19 asks a simulation to be honest about being a model and reproducible in its own terms. This
module adds the third thing a stored match needs to be worth reading: a timeline a query can answer a
question about, plus the sentence saying whether that timeline still agrees with the report it was
copied from.

Backend: `apps/api/app/models/__init__.py` (`SimulationEvent`), `apps/api/migrations/versions/0014_sim_events.py`,
`apps/api/app/services/simulation/events.py`, the writer and the new `timeline` field in `service.py`, two
call sites in `simulations.py`.
Tests: `apps/api/tests/test_sim_events.py` — 26 in six classes.
Surface: the Timeline panel of `/simulate/{slug}`, walked by `apps/web/scripts/qa-timeline.mjs`.

---

## 1. The premise the roadmap line got wrong

ROADMAP item 4 read *"a `sim_events` table so the timeline is stored rather than regenerated"*. Nothing
was being regenerated. `simulate_match` builds the event list once, `run_simulation` stores the whole
report — `events` included — in `sim_matches.report`, and `GET /api/v1/simulate/{ident}` reads that JSON
back without asking the engine anything. The only path that re-derives events is `/replay`, and it does
so deliberately, to prove the engine still agrees with itself.

So this table is not a performance fix and not a duplication of the blob. Its value is that it is
**addressable**:

| question | with only `report` | with `sim_events` |
| --- | --- | --- |
| who scored most in this career | load every match row and pick the JSON apart in Python | `GROUP BY player_id WHERE event_type = 'goal'` |
| how many sendings-off in this competition | same | `WHERE event_type = 'red_card'` on an indexed column |
| who took the most attempts, and at what quality | same | three `event_type`s grouped by `player_id`, `SUM(expected_goals)` alongside |

The third column is why `ix_sim_event_player_type (player_id, event_type)` and
`ix_sim_event_type_minute (event_type, minute)` exist: they are the shapes the next modules (a scoring
chart, a disciplinary balance, the §23 AI scout reasoning over a *season* rather than a match) will ask,
not decorations on every column.

## 2. Two rules this module will not bend

* **The rows are a copy, not a second opinion.** They are written in the same transaction as the report
  they came from, they never feed the engine, and nothing here recomputes an event. When the two
  disagree, the disagreement is *reported*, in the report's favour — `compare_with_report` names the
  field and prints both values rather than averaging them or trusting the newer copy.
  `test_the_timeline_is_never_written_back_into_the_report` pins the "never feeds the engine" half: it
  asserts the stored report still carries no `player_id` anywhere in its JSON, and that `replay_is_identical`
  still answers `identical: True` after the rows were written.
* **A name is not an identity.** The engine names a scorer out of the side's eleven, and the printed
  `lineup` is inside every stored match's digest (`engine.py` `_digest`), so it cannot gain ids without
  making every stored report disagree with its own hash. Identity is recovered by looking the name back
  up in that same eleven — and where two selected players share a name the row says `ambiguous` and
  claims no player. Guessing between them would write one man's record under another's name, which is
  worse than no record. `attribution` therefore has three values, each defined in `EVENT_ATTRIBUTION`
  and each reached by its own test.

## 3. What `ordinal` buys

`ordinal` is the event's index in the report's own list, and `(match_id, ordinal)` is unique — that pair
is an event's whole identity. The report is sorted by minute with ties broken by the order the engine
appended them (`_apply_running_score`), so two events in one minute are distinguishable only by which
came first. Two consequences, both tested:

* `test_a_match_and_a_ordinal_name_one_row_only` drives a real `IntegrityError` by inserting a second
  row at a taken ordinal — the constraint is not merely declared.
* `test_a_moved_minute_is_caught_even_though_the_length_is_unchanged` is why the comparison is field by
  field rather than by count. A report rewritten in place keeps its length, so a `len` check would pass
  over a tampered timeline.

## 4. The writer's idempotence, and the bug a test caught

`write_timeline` replaces a match's rows rather than adding to them. That is what the first run of the
new suite refused to believe:

```
IntegrityError: UNIQUE constraint failed: sim_events.match_id, sim_events.ordinal
```

Root cause was not in the new code. `SessionLocal` is built with **`autoflush=False`**
(`app/core/db.py:35`), so a `SELECT` cannot see rows an earlier call in the *same* transaction queued
with `session.add()`. `rows_of()` returned an empty list, the delete loop deleted nothing, and the fresh
rows collided with the copy they were replacing. Two flushes fix it, and both are load-bearing:

```python
session.flush()                      # land rows queued earlier in this transaction
for row in rows_of(session, match):  # now the query can find them
    session.delete(row)
session.flush()                      # deletes reach the database before ordinals are re-claimed
rows = build_rows(match, _as_mapping(match.report), sides)
session.add_all(rows)
```

The second flush was already there for the obvious reason — `(match_id, ordinal)` is unique, so a flush
that wrote inserts first would collide with its own old rows. The missing one was the interesting half.
`test_rewriting_a_timeline_replaces_it_instead_of_doubling_it` calls the writer twice and asserts the
count is unchanged; it is red on the pre-fix code and green after.

Worth naming for what it is: a docstring that claimed an idempotence the code did not have, in a module
that had no tests yet. The previous two milestones' reds were all in walk scripts; this is the first
production defect this session's tests caught before a page could meet it.

## 5. What the API now publishes

`GET /api/v1/simulate/{ident}` and a fresh `POST /api/v1/simulate` carry a `timeline` object next to
`report`; a `GET /api/v1/simulate` list row carries neither, because it carries no report either. The
field is absent, not empty, when the caller has no session to query with — rebuilding it out of the blob
and labelling it a stored timeline is exactly the confusion the object exists to prevent.

| key | content |
| --- | --- |
| `events`, `count`, `stored_rows`, `report_events` | the timeline as rows re-built, and the three numbers to compare |
| `source`, `source_note` | `"sim_events rows"` or `"the match report's own JSON"` — a page **must** print this, because the two branches are different claims |
| `consistency` | the verdict sentence from `compare_with_report`, including the offenders when there are any |
| `by_type` | event type → count, from the events actually being returned |
| `identified`, `ambiguous_names`, `unnamed_names` | how far a name in this timeline reaches |
| `formula`, `attribution_formula`, `disclaimer` | the two rules of §2 in the reader's own words |

Falling back is not silence: a match played before migration `0014` returns
`"this match was played before the events table existed; the report is its only surviving timeline"`,
which `test_a_match_with_no_rows_names_the_table_rather_than_the_match` pins. And a match with **no rows
and no events** says so in a different sentence, rather than being called stale.

## 6. What the 26 tests pin

With these 26 in place the API suite is **476 tests, green on both engines** on 2026-09-24: 316.01s on
the default SQLite leg and 354.09s on the PostgreSQL leg, each in its own per-run database.

| class | n | what it holds still |
| --- | --- | --- |
| `TestRowsAreTheReportsEvents` | 7 | `timeline_of(session, match) == report["events"]`; the exact key set of all six engine event types, hand-built rather than sampled; goals and bookings from a real fixture attributed the same way; ids pointing inside the side that printed them; the report carrying no ids and still replaying identical; the §4 idempotence; the `IntegrityError` |
| `TestComparisonAgainstTheReport` | 7 | a fresh timeline agrees and says what it counted; a renamed scorer is caught with both values printed while the row keeps the original; a moved minute is caught at unchanged length; a lost row is reported as a count, not as silence; the no-rows and no-events verdicts; offenders capped at 3 while the verdict still states the true total |
| `TestAttribution` | 5 | unique name → that player's row; shared name → neither; name outside the eleven → `unnamed`; a side with no profile keeps its club and claims no player; `identities` lists every row behind a shared name |
| `TestWhatAReaderGets` | 3 | the view's `source`/`by_type`; the report fallback and its wording; **a career round reaches rows through the same single `run_simulation` call site**, so `play_round` needs no separate wiring |
| `TestRowsLeaveWithTheirMatch` | 1 | `DELETE /simulate/{id}` leaves no orphans (FK is `CASCADE`) |
| `TestThroughTheApi` | 3 | a detail carries the timeline and a list row does not; an HTTP-played match has rows on disk; an HTTP delete takes them |

One test guards the digest rather than the data: `test_the_timeline_is_never_written_back_into_the_report`
asserts `"player_id" not in json.dumps(match.report)`, so the blob stayed name-only, and that
`replay_is_identical(...)["identical"] is True`, so writing rows left the inputs bit-for-bit as they
were — a `sim_events` migration cannot silently change what a stored match hashes to.

The shared `match` fixture searches seeds `5150–5179` for a fixture holding two goals and a booking, and
`pytest.skip`s rather than passing if the range yields none — a scenario test that quietly selects
nothing is the failure mode this suite checks itself for. Which types a drawn fixture contains is the
draw's business, so `test_a_real_fixture_carries_its_goals_and_bookings_the_same_way` asserts only that
real rows neither leak a scoreline into a booking nor drop a chance from a shot; the six shapes
themselves are pinned by hand in the test above it.

**The tests were measured against the code they claim to test.** Deleting one branch from `event_dict`
(`if row.event_type in _SCORE_TYPES: event["score"] = row.score`) turned **5 of 26 red** —
`test_every_event_becomes_one_row_in_the_reports_order`, the hand-pinned key set, the fresh-agreement
verdict, the reader view's own `source`/`by_type` test, and the career-round test — and the file was
restored to its recorded sha (`86ae2645…`) before the suite went green again. A line whose removal
nobody notices does not have tests; this one does.

## 7. The panel on the report page, walked in a browser

`apps/web/app/simulate/[slug]/page.tsx` now reads `match.timeline` where it exists and falls back to
`report.events` where it does not, and prints which of the two it did in the panel's own eyebrow
(`20 events · read from sim_events rows`). Below the timeline rows: the attribution rule verbatim, one
`{type} {count}` chip per server-computed split entry, `{n} stored rows`, `{identified} of {count} traced
to a player`, an ambiguity warning naming the shared names when there are any, and the consistency
sentence. The `SimTimeline` type in `lib/types.ts` mirrors §5 field for field.

`node scripts/qa-timeline.mjs` against a production build (`next start`, port 3215) on 2026-09-24:
**29/29 walk checks**, two screenshots (`docs/screenshots/202609241806-timeline-report-desktop.png`,
`…-mobile.png`). The checks worth reading:

| what the walk insists on | what it found |
| --- | --- |
| the fixture it walks actually contains a goal | it plays seeds in turn until one scores — the first, `20260925`, produced 11 events and no goal, and is recorded as an attempt, not as a pass |
| one row per event the report printed | `20 rows for 20 events`, and `count == stored_rows == report_events` |
| the stored events hold the report's values | `20 events, 9 keys each`, compared **per key** — the walk started as a `JSON.stringify` equality and was changed, because the engine's dict order and `event_dict`'s are legitimately different and the blob comparison was red for the wrong reason |
| the page's rows are the server's | every printed event matched, in report order, first minute `3` |
| a printed goal carries the model's own scoreline | `1-0` against `1-0`, on the same minute |
| the per-type chips are the server's split, not a recount | `{"shot_off_target":10,"shot_saved":8,"goal":2}` |
| the agreement sentence is the API's | `20 events re-read from the timeline table; all of them agree with the report` |
| the list route claims no per-match timeline | no `\d+ stored rows` anywhere on `/simulate` — a per-match figure has no business on a list. This needle is narrow because the index has *always* carried a chip beginning "stored rows keep the seed…", and the first version of this check was red on that pre-existing copy |
| the panel survives a phone viewport | `0px` sideways scroll, and the stored-rows figure still shouted on screen |
| nothing was thrown anywhere | 0 console errors |

Two things the walk does **not** do, and says so in its own comments: it never opens a career fixture
(this account has no career, and `test_a_career_round_gets_a_timeline_the_same_way` pins that path in
the suite instead), and it does not exhibit an ambiguous or unnamed event — those branches are covered
by `TestAttribution` and by the panel's conditional rendering, not by a screenshot.

## 8. `alembic check` and the drift it refused to accept

`python -m alembic check` failed the first time this migration was on file:

```
Removed index ix_sim_event_match
```

The migration created an index the model never declared, so the two descriptions of the database
disagreed and autogenerate wanted to drop it. The fix went into the model rather than into the migration
— an index only `sim_events` has, on the column every timeline read filters by, is the one the reader
needs — and the gate is green now that both sides say the same thing. Worth stating plainly, because it
is the general lesson: `alembic check` green does not mean the schema is right, it means the model and
the migration agree; here they did not, and the direction the drift pointed was the cheaper bug to
catch.

## 9. Not claimed

* **No cross-match ledger yet.** The rows make "who scored most in this career" a query, but this module
  does not run it. That is the next increment.
* **These rows never feed the engine.** Nothing in `engine.py` or `profile.py` reads `sim_events`, so a
  timeline cannot change a future scoreline. The rule is §2's, and `run_simulation` is the only writer.
* **A match played before `0014` has no rows**, and no backfill was run — deliberately: the report is
  complete, so rows would be a copy of data that is already on file and re-deriving attribution needs
  the squads that played, which `run_simulation` no longer has. The reader is told which case it is in.
* **Attribution is exact-name matching within one side's eleven.** It does not resolve a nickname the
  engine printed against a different stored name, and it does not carry an id across clubs: an event's
  `player_id` is the row it was selected from, so a transfer between rounds can produce two ids for one
  printed name in one competition. `ambiguous_names` covers the collision the other way round.
* **A `shot_saved` row names the shooter, not the keeper.** That is what the engine draws and prints, and
  the keeper appears only inside `detail` as prose. So "which goalkeeper faced the biggest chances" is
  *not* one of the questions these rows answer — written down here because the tempting reading of
  `event_type='shot_saved' + player_id` is exactly that, and a chart built on it would credit saves to
  the men who took the shots.
* **No minutes played, no assists, no goal kinds.** The engine does not record them, so a row cannot
  publish them.

## 10. Reproduce

```bash
cd apps/api
python -m ruff format app && python -m ruff check app
python -m mypy app                        # 76 source files, up from 75 with events.py
python -m alembic upgrade head && python -m alembic check   # 0014 is the head; no new operations
python -m pytest -o addopts="" -q tests/test_sim_events.py                              # 26
python -m pytest -o addopts=""                                                          # SQLite leg: 476 passed
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest -o addopts=""                                                        # PostgreSQL leg: 476 passed, its own per-run database

cd ../web
npx tsc --noEmit && npm run lint
npm run build && NEXT_DIST_DIR=.next-timeline API_INTERNAL_URL=http://127.0.0.1:8735 \
  npx next start -p 3215 &
QA_BASE=http://127.0.0.1:3215 node scripts/qa-timeline.mjs  # 29/29
```

Note on the two legs: `conftest.py` reads `FOOTBALL_OS_TEST_DATABASE_URL` and *overwrites*
`DATABASE_URL` with it, so pointing `DATABASE_URL` at Postgres looks convincing and runs the SQLite leg
twice. Set the variable the conftest actually reads.

And to see the totals at all: `pyproject.toml` ships `addopts = "-q"`, so `python -m pytest -q` is really
`-qq` and prints the progress dots with **no "N passed" line** — a run of this suite looks complete while
silently reporting nothing. Add `-o addopts=""` (as above) to get the summary that states the count.
