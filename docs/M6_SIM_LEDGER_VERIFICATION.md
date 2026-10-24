# M6 item 10 — a season ledger, and the second reading that keeps the first honest

`sim_events` (item 4) made "who scored most in this career" a question a database could answer. This
module is the code that finally asks it: a per-player, per-type ledger over the fixtures one career
played, summed from stored rows on the request, shown on the career page beside the two figures it has to
agree with.

Backend: `apps/api/app/services/simulation/ledger.py` (new), wired in at `career_view` in
`app/services/simulation/career.py` and one `limitations()["ledger"]` sentence beside it. No migration —
`alembic check` answers "No new upgrade operations detected" against head `0014`.
Tests: `apps/api/tests/test_sim_ledger.py` — 22 in six classes.
Surface: the "Who did it, counted off the event rows" panel of `/career/{slug}`, typed in
`apps/web/lib/ledger.ts`, walked by `apps/web/scripts/qa-ledger.mjs`.

---

## 1. What the season looked like when it was measured

The walk's own run, on a production build, is the clearest statement of what this thing does. A fresh
account opened a career at the generated world's strongest club (Cordale Town, overall 68 — the world's
ceiling is well short of 90, which is why "strongest" is chosen for scoring and not for realism), played
three rounds, and the ledger answered:

| figure | value |
| --- | --- |
| club-side event rows read | 40, across 4 event types |
| rounds played / traced | 3 / 3 |
| names the rows could attribute | 10, all 10 shown, `truncated: false` |
| goals for the club | 1, and exactly 1 carries a `player_id` |
| attempts and their quality | 35 attempts, `expected_goals` 3.565 |
| events with no player behind the name | 0 |
| the fixture list's own goal figure for the same three matches | 1 |

The last row is the point of the module. Six of those seven numbers are sums the ledger takes over
`sim_events`. The seventh is taken over a different table (`career_fixtures.club_goals`, copied out of the
reports when each round was played). They are equal here, and the panel prints the sentence saying so —
but it prints a different sentence when they are not, which is the only reason the equality means
anything.

## 2. Two rules this module holds to

* **Everything is summed from stored rows, on the request.** Nothing is cached, denormalised or written
  back. `test_reading_the_ledger_writes_nothing_back` asserts two reads return equal payloads *and* that
  the session holds nothing new, dirty or deleted afterwards — a "derived" counter that had drifted from
  `sim_events` would pass a screenshot and fail that test.
* **A sum is published beside the number it has to agree with.** `ledger_view` returns `consistency`
  computed from two independent readings, and it names both:

  ```
  1 goal(s) on the event rows and 1 on this career's fixture list, over 3 traced fixture(s): the two
  readings agree
  ```

  When they disagree the sentence says so and rewrites neither figure
  (`test_a_goal_the_rows_lose_makes_the_two_readings_disagree_without_rewriting_either`). When a round has
  no rows at all the sentence distinguishes the two ways that happens — a fixture whose report was deleted
  is *a gap*, and the count of gaps is appended (`test_a_fixture_whose_rows_are_gone_is_reported_as_a_gap_
  not_a_scoreless_match`, `test_a_deleted_report_takes_its_round_out_of_the_ledger_without_taking_it_out_of_
  the_season`). A career that has never played says `every figure in this ledger is a sum over no rows`
  rather than presenting an empty table as a season of nobody doing anything.

Reach is stated too. `scope` says the count covers "only events whose side is this career's club (CORT)",
because a fixture's home side is not that club on away rounds and an event belongs to the side that
printed it — `test_an_away_round_contributes_the_clubs_events_from_the_away_side` is the case that would be
quietly wrong if the ledger filtered by `is_home` instead of `team_id`.

## 3. The bug found before it was written

`matches_with_events` — in how many of this career's traced fixtures does the name appear at all — looks
like it belongs in the same `GROUP BY`. It does not, and cannot: `count(distinct match_id)` inside an
event-type grouping answers "in how many matches did this player score", and no sum or maximum of those
per-type answers is the union of matches the player appears in. A player with a goal and a booking in the
same round would be counted twice by the first shape and once by the correct one. So the ledger runs a
second, much smaller query over the same fixture ids and groups only by player.

That reasoning was checked the cheap way afterwards: mutation B deletes the second query's result loop, and
`test_a_match_a_player_appears_in_is_counted_once_however_many_events_it_holds` goes red — the claim is
pinned by a test, not by a comment.

## 4. What a name is not

The rows credit a player only when `attribution == "identified"`: exactly one man in that side's eleven
bears the name the event printed. A shared name yields `ambiguous` and claims nobody, and an event naming
nothing yields `unnamed`. Both shares are printed in the same panel as the top-scorer list, with the
offending names beside them, because a list of names is only honest next to the count of events that could
not be attributed to one.

What the ledger cannot do is say anything about a player it never named. There is no save credit: every
chance event names the shooter, never the keeper who stopped it, and `limitations()["ledger"]` says that
rather than letting the absence read as "the goalkeeper had a quiet season". `xG` is summed only over the
three chance types; `attempts` includes goals; and `matches_with_events` is *not* appearances — a full
ninety minutes with no touch worth recording leaves no row, which is why the panel's eyebrow reads
"10 of 10 name(s)" and not "10 players used".

## 5. Measured

* 22 new tests, six classes: totals are the rows (6), only the club's own side (3), the ledger audits
  itself (5), what the panel publishes (2), through the API (4), the ledger goes with its season (2).
* Full API suite, both legs: **498 passed on SQLite (940.20s) and 498 passed on PostgreSQL (1395.94s)**,
  exit 0. Baseline before this module was 476.
* API gates: `ruff format app` (77 files unchanged), `ruff check app` (All checks passed!), `mypy app`
  (no issues in 77 source files), `alembic check` (no new upgrade operations).
* Web gates: `tsc --noEmit` clean, `next lint` clean.
* Four defects planted in `ledger.py` and run through the suite, each restored afterwards (file sha
  verified unchanged at `51ff5e7132cd351f` before and after):

  | planted | suite | red test |
  | --- | --- | --- |
  | the totals query stops filtering to the career's club | 8 failed, 14 passed | the club totals, the per-player goal count, the xG sum, the agreement sentence |
  | the second (footprint) query never runs | 2 failed, 20 passed | `matches_with_events`, plus the direct-count comparison |
  | the audit prefers the fixture list on disagreement | 1 failed, 21 passed | the disagreement sentence |
  | the unattributed share is reported as zero | 1 failed, 21 passed | the named-apart test for unidentified events |

* Browser walk: `scripts/qa-ledger.mjs`, **39/39 checks**, run `202609241945` against a fresh production
  build (`NEXT_DIST_DIR=.next-ledger next build`) with API on 8736 and web on 3216, desktop + mobile
  screenshots, zero console errors. It registers a throwaway account, plays until the club has a goal on
  the rows, then reads the season three ways: the `ledger` block, a re-count of every fixture's stored
  report restricted to the career's own side, and a second re-count of the same reports **grouped by
  name** so each printed row is held against its own player. Two of those readings are computed in the
  walk, not fetched, which is what makes the third one a test rather than an echo.
* Three more defects planted and read through the walk: the club-side filter (5 checks red, including the
  disagreement sentence the panel then prints), one chance type dropped from a row's attempts while the
  club total stayed correct (exactly 1 red — the per-name reading, the only one that can see it), and the
  40-name cap cut to 4.
* The two neighbouring walks were re-run on the same build to confirm nothing regressed: `qa-timeline.mjs`
  29/29, `qa-carry.mjs` 45/45.

## 6. Two things the walk corrected in itself

**A cut the walk first called a defect.** The season-wide identity ("the printed cells plus the types the
panel does not row equals the attributed total") went red on the third mutation, cap 40 → 4. That was the
walk over-claiming, not the ledger failing: a list the eyebrow labels "4 of 9 name(s)" and the body
labels with its own cut sentence is the cap working. The identity is now written to stay quiet on an
honest cut, and the cap's own contract is pinned in the suite where the number can be read
(`test_a_long_ledger_is_cut_short_out_loud`, which monkeypatches the limit to 2 and asserts the cut is
both real and announced).

**A green that meant nothing.** The walk's first run exited 0 having printed nothing at all: the file
defined `main()` and never called it. Its second failure mode was worse — a `ReferenceError` halfway
through printed "10/10 walk checks passed" and exited 0, because the checks that had run all passed. Both
holes are closed in `finish()` (zero checks is a failure) and in the crash handler (an aborted walk
records a failed check). `qa-timeline.mjs` and `qa-carry.mjs` carried the identical crash handler and were
hardened the same way.

**A needle that outlived the sentence it checked (2026-10-21).** §81 rewrote the panel's eyebrow from a
hand-written plural into an **ICU** one — `{shown} of {total, plural, one {# name} other {# names}} · {traced}
of {played, plural, one {# round} other {# rounds}} traced` — and the walk still expected the old spelling
("7 of 7 name(s) · 1 of 1 round(s) traced"). The panel was right and the walk was wrong: it compared the
page's `7 OF 7 NAMES · 1 OF 1 ROUND TRACED` with a sentence no page has printed since the arc, and called
the difference a failure. The walk now builds the expectation the way English reads it — the same
`plural(count, one, many)` helper the club walk uses — and the check is **39/39** again on the build the
arc produced.

## 7. Not done

* ~~No cross-career, competition-wide or all-time aggregate reads these rows.~~ **Corrected 2026-10-25:**
  that tier exists. It landed 2026-10-02 in `30e9d37` (`/simulation/aggregates/league/{competition_slug}`
  and `/simulation/aggregates/player/{player_slug}`), and §9 records the defect its own rules door carried
  until 2026-10-25. The ledger described above remains the career-scoped reading; the aggregate tier is a
  different query with its own honesty problem (synthetic squads whose names repeat across clubs), which
  its doors state rather than hide.
* The `ambiguous` and gap branches are proven in the suite but not by the walk: the generated world
  happened to give this career ten distinct names and three intact reports, and a walk that could only
  ever report "nothing ambiguous today" would be a green that teaches nothing.
* The ledger is only as complete as the reports still stored — deleting a match report takes its round out
  of the traced set, and the sentence says which rounds those are rather than quietly lowering a total.
* Next: §23's AI scout can now reason over a season rather than a match, since this module is the thing
  that answers "what has this player actually done in this career". ROADMAP item 9's stale needle in
  `visual-qa.mjs` still belongs to that file's owner.

## 8. Reproduce

```bash
# API tier
cd apps/api && python -m pytest tests/test_sim_ledger.py -o addopts=""     # 22 passed
python -m mypy app && python -m ruff check app                             # clean

# both tiers, fresh production build
cd apps/api && python -m uvicorn app.main:app --host 127.0.0.1 --port 8736
cd apps/web && NEXT_DIST_DIR=.next-ledger npx next build \
  && API_INTERNAL_URL=http://127.0.0.1:8736 NEXT_DIST_DIR=.next-ledger npx next start -p 3216
cd apps/web && QA_BASE=http://127.0.0.1:3216 node scripts/qa-ledger.mjs    # 39/39
```

## 9. The aggregate rules door published ten figures it could not derive (2026-10-25)

The tier added in `30e9d37` shipped a `/simulation/aggregates/rules` door with **sixteen** top-level keys.
Ten of them had no source on this tier:

* three walk ceilings — `max_depth: 1`, `max_edges: 1000`, `max_nodes: 5000` — for a tier with no
  traversal. The ceilings belong to the knowledge-graph tier, whose `/graph/rules` measures its clause
  census from live metadata;
* six clause-census fields — `spec_verbs_declined: {}`, `refusal_answers: {}`, `public_clauses: 0`,
  `clauses_with_a_verb: 0`, `clauses_declined: 0`, `private_tables_excluded: 0` — invented zeros. A
  caller receiving `clauses_declined: 0` cannot tell "nothing was declined" from "nobody measured";
* `world_ready: True`, typed by hand — the worst of the ten, because it is a claim about **the caller's
  database** made without reading it.

Under it sat the docstring "Nothing here is typed by hand: the caps are the constants the walk guards
with", which the published OpenAPI description repeated. Nothing in `apps/web` read the six census
fields, the three ceilings or `world_ready`: the index page reads `node_kinds` and `edge_verbs` and
renders two lists, and the visual walk's check is titled "publishes the vocabulary and ceilings" but
asserts only those two arrays. The invented fields were not a harmless superset with no reader — a public
door publishing a number is a claim about the thing the number names.

**The fix (`6a95540`).** `world_ready(db)` is now imported from `app.services.world` — the same
measurement `/graph/rules` uses over `world_counts` — and the nine unbacked keys are gone. The door keeps
its own vocabulary (`node_kinds`, `edge_verbs`), its own two ledger doors, the aggregate service's `caps`
and `formulas` constants, the measured readiness and the disclaimer. The docstring and published
description name where each figure comes from, and `SimAggLeagueRules` in `apps/web/lib/types.ts` was
trimmed to the same seven keys.

**The gate.** `apps/api/tests/test_simulation_aggregates_rules.py`, six cases. Before the fix, three were
red — the exact key set, readiness on a database with no tables, and the contract description — and three
were green — the caps/formulas equality, the route list against `app.routes`, and readiness after a real
`sync_world`. The green three were the fields that already derived something; the red three were the ones
this unit is about.

**The arms**, run from an isolated worktree at `d7bc120` (`PYTHONDONTWRITEBYTECODE=1`, every
`__pycache__` cleared per run, byte splices with count assertions, files restored from git): **10/10
MATCHED**, exact red sets, plane clean afterwards.

| arm | mutation | reds |
| --- | --- | --- |
| baseline | — | none |
| `world-ready-constant` | `world_ready(db)` → `True` | empty-database case |
| `world-ready-inverted` | `world_ready(db)` → `not world_ready(db)` | empty and seeded cases |
| `census-field-back` | re-adds `"public_clauses": 0` | key-set case |
| `drop-derived-key` | deletes `disclaimer` | key-set case |
| `cap-differs-from-service` | `ledger_limit` → 41 | caps case |
| `route-list-drifts` | `league` → `leagues` in the published route | routes case |
| `docstring-claim-back` | restores "Nothing here is typed by hand" | contract-description case |
| `control-punctuation` | `request's database.` → `!` | none |
| `service-constant-moves` | `LEDGER_LIMIT = 40` → `41` in the service | none |

The two no-red arms are load-bearing. `control-punctuation` says the gate does not go red on any edit to
the file, and `service-constant-moves` says the door reads the service's constant instead of restating
its value — the caps case stays green *because* the door follows. `world-ready-inverted` makes the
readiness claim a measurement from both sides: an empty database and a just-seeded one fail in opposite
directions.

**Currency owed, paid here.** Regenerating the contract exposed that the committed `openapi.json`
predated M13's four match-input fields (`substitutions`, `tactical_shift_minute`, `home_momentum`,
`away_momentum`; +30/−2 lines), and the spec audit still said 37 migrations against 40 committed (with
ROADMAP quoting the same number). The sweep brought the contract current, the audit to 40, and the three
documents that declare the contract's SHA-256 — `docs/SECURITY_PROBE_REPORT.md`,
`docs/M12_PRODUCTION_HARDENING_VERIFICATION.md`, `ROADMAP.md` — from `6c1ce207…` to
`4b283580fb4268049d0cfb8dd3e76b984b092eb4b574afa8fc13b7b4cb2f2279`. Those gates read `git show HEAD:`,
so they stay red until the commit that contains the bytes; measured after it: **38 passed** across the
five files (contract 4, spec audit, probe report, rules 6, aggregates 7), `ruff check app` clean,
`mypy app` clean in 155 files, `tsc --noEmit` clean, `next lint` clean.

Every figure in this document is fictional, produced by the labelled simulation engine over the generated
demo world. No real match, competition or player is modelled, and no real-world statistic is asserted.
