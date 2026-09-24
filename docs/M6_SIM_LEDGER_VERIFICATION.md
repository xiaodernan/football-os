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

## 7. Not done

* No cross-career, competition-wide or all-time aggregate reads these rows. The ledger is scoped to one
  career's fixtures by design; a league-wide top-scorer is a different query with a different honesty
  problem (it would mix synthetic squads whose names repeat across clubs), and it is not claimed here.
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

Every figure in this document is fictional, produced by the labelled simulation engine over the generated
demo world. No real match, competition or player is modelled, and no real-world statistic is asserted.
