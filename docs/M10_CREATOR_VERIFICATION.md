# M10 verification — §36 Creator Economy

Every figure in this file was read out of a command this run executed and printed, with the plane it was
measured on named beside it. Where a figure could not be read, the row says so rather than carrying a number
forward.

## What landed

Five commits, in the order they were made:

| commit | what it carries |
| --- | --- |
| `9c6c6af` | `creator_profiles`, `creator_guides`, `guide_citations` (migration `0024`), `services/creator/publishing.py`, and 18 cases in `tests/test_creator.py` |
| `0c42529` | the eleven HTTP doors, the rulebook, and the creator tier registered in the project's one answer table |
| `2c0c5f2` | the regenerated OpenAPI contract — additions only |
| `a578597` | `/creator`, `components/CreatorWorkbench.tsx` and `lib/creator.ts` |
| `c3d1fd6` | reach read from §35's own follow table, and this tier's two §42 rows |

The tier's shape is one sentence: **a guide stores a title, a frame and addresses, and no figure about the text it
points at**. `citations`, `moved`, `tokens`, `guides` and `subscribers` are counted from the rows their own
formulas name at the moment of the read; the passages stay in `knowledge_chunks`, and a citation keys on
`(document, ordinal)` plus the hash that sat there when it was cited, because `services/knowledge/ingest.py` keeps
a document row across re-syncs but mints a fresh chunk id every time. Reach is a predicate over §35's
`community_follows` rows, so an unfollow withdraws a guide at once and deletes nothing.

## The figures, with the plane each was measured on

* `tests/test_creator.py` + `tests/test_entitlements.py`, one run on the committed tree: **50 passed, 0 failures,
  0 errors, 0 skipped in 23.84s**, read from the run's own junit report (`.scratch/creator_reach_unit.xml`,
  `tests="50" failures="0" errors="0" skipped="0"`, timestamp `2026-09-28T20:18:04+08:00`). Composition, counted
  per module out of the same report: **36 cases in `tests/test_creator.py`** and **14 in
  `tests/test_entitlements.py`**.
* What the 36 defend, in the order the file attacks them: the two column sets as sets, with `text`, `tokens`,
  `citations`, `reading_minutes`, `price`, `currency`, `provider` and `checkout` among the names they refuse; every
  figure recomputed from its own formula, proved by editing a chunk's hash under a live citation; a citation
  surviving a passage that moved, and saying so through `moved`; no currency, provider or checkout key anywhere in
  any answer; each ceiling asserted at its edge and one past it; somebody else's guide answered as **absence**;
  the codes this tier answers with belonging to it alone; the reach predicate on the shelf, at the address and
  through the citations; and the doors walked as doors — the ten private ones parametrized out of `ROUTE_GUIDE`
  so a door added later cannot arrive unguarded, and thirteen refusal codes earned through a real request each.
* `mypy app` — clean over **104 source files**. `ruff check app tests` clean, and `ruff format --check` leaving the
  five files this slice touched unchanged.
* `alembic upgrade head` reaches **`0024`** and `alembic check` answers *No new upgrade operations detected* — both
  against `.scratch/m10_creator_check.db`, never the shared dev database. That migrated database holds **67
  tables** (66 from `Base.metadata`, plus `alembic_version`), three of them this tier's.
* `docs/api/openapi.json` — **144 paths / 187 operations**, of which **7 paths / 11 operations** are
  `/api/v1/creator/…`. The tier's contract commit took the export from 137 / 176 with **611 insertions and 0
  deletions**; `c3d1fd6` added no door, and the export is untouched by it.
* The doors: **11 entries in `ROUTE_GUIDE`** — **1 public** (`GET /creator/rules`), **10 private** — over 7 paths
  and 11 operations; **15 refusal codes**, 3 of them 409, and **no 403 anywhere** in the tier.
* §42's table: **8 features** in `entitlements.FEATURES`, **2** of them this tier's (`creator_publish`,
  `creator_guide`, both kind `user`), and `ENFORCED` is still exactly **`['reports_saved']`** — so the meter prints
  both creator ceilings with `enforced: false` and `/entitlements/capabilities` lists them under
  `published_not_enforced`, which is what the rulebook's own limitation sentence repeats.
* Web tier: `tsc --noEmit` rc=0 and `NEXT_DIST_DIR=.next-ci npx next build` rc=0 on this tree (2026-09-28). The
  page is private (`currentUser()` → `redirect("/login?next=%2Fcreator")`), disallowed in robots and absent from
  the sitemap.
* The walk: **not run for this tier** — as of this 2026-09-28 measurement. Nothing under `apps/web/scripts/`
  named `/creator` then, so `/creator` had no browser evidence of its own. The walk landed on 2026-10-21 and was
  extended for the career-challenge panel on 2026-10-22; its figures are in the walk paragraphs of the sections
  below, and this bullet records only the 2026-09-28 plane.

## What §36 does not claim yet

* **The six kinds are six sections, and all six have objects of their own (2026-10-21/2026-10-22).**
  §36 lists Training Program, Tactical Guide, Player Analysis, Match
  Analysis, Career Challenge and Scouting List; the tier's `GUIDE_SECTIONS` is `plan, drill, match,
  tactic, scout, video`, and a guide is a title, a frame, a section and citations in every one of
  them. A **Training Program** is now a row of its own: a schedule, a dose and a progression, with a
  step naming a catalogue drill, and starting one plans the learner's own training sessions. A
  **Tactical Guide** is now a row anchored to a stored system: it keeps the system's address and a
  hash witness, and every measurement is computed on the read from the system's own dots. A
  **Player Analysis** is now a row anchored to a stored footballer: it keeps his address and a hash
  witness, and its five rates are computed on the read from the player row's own columns. A
  **Match Analysis** is now a row anchored to a stored fixture: it keeps the fixture's address and a
  hash witness, and its five measurements are computed on the read from the fixture row's own score
  and stats. A **Scouting List** is now a row anchored to many stored footballers: each selection
  keeps the player's address, a hash witness and the author's own note, every attribute is read
  from the player row on the read, and a retired player leaves a bare address instead of erasing
  the list. A **Career Challenge** is now a row carrying the author's rule — an objective, a target
  and a window of rounds — and an attempt that stores only the entrant's own career address and the
  round the window opened at, so the verdict is summed from that career's own fixtures on the read.
  What is still not there: a program is a plan rather than an enrolled course, and there is no
  progress model beyond the training tier's own sessions.
* **No money, by design.** `creator_publish` and `creator_guide` are ceilings the data holds and **no door refuses
  on** — the caps that actually bite are the lifetime counts in `CAPS` (100 guides, 24 citations a guide).
* **The feedback half of §36's loop is §35's.** "Users → Feedback → Creator" is reactions, comments and follows on
  §35's rows; this tier stores no per-guide feedback of its own and counts `subscribers` from `community_follows`.
* **§38 is no longer unstarted.** Football Career Portfolio's read landed in `471da30` and its `/portfolio` page
  landed after that ([evidence](docs/M10_PORTFOLIO_VERIFICATION.md)); its permitted public outputs are the part
  still open, as the section below records.

## The training program — §36's first kind of content (2026-10-21)

The list above said what this tier could not do, and it is worth reading the sentence again:
*"The six kinds are six sections, not six objects. §36 lists Training Program, Tactical Guide,
Player Analysis, Match Analysis, Career Challenge and Scouting List; the tier's `GUIDE_SECTIONS` is
`plan, drill, match, tactic, scout, video`, and a guide is a title, a frame, a section and citations
in every one of them. **Nothing here is a runnable program: no row carries a schedule, a dose or a
progression.**"*

A program is those three things and nothing else.

* **A schedule** — the steps, in order, one row each. `creator_program_steps.position` is unique per
  program, so a program cannot hold two steps at the same place in its own schedule.
* **A dose** — the minutes each step asks for, and the total the program asks for, counted now.
* **A progression** — the order, which is the position column and nothing more.

**A step names a drill from the training catalogue**, so a program is runnable by construction: the
drill is the one the learner opens and the minutes are the ones the learner is asked for. A step
naming a drill the catalogue does not hold is refused **at publication** (404 `no_such_drill`), not at
the learner's first session — a plan that cannot be walked is not a plan.

**Starting a program plans the caller's own training sessions.** They are the training tier's rows
(`training_sessions.program_id` remembers which program planned one), so completing one of them is the
same act as completing any other session, and the schedule is dated from today: the first step is
today and each later step is the next day. An account with no player row is refused with the
platform's own `no_player` (409) — a program needs a player to plan for.

**Five doors**, under the tier's existing prefix and its existing rules: publish, the shelf, one
program, erase (which takes the sessions it planned with it), and start. The shelf and the read need a
session, like every other door in this tier. The codes join the tier's own sets — one tier owns its
codes — and the rulebook publishes the program's ceilings, its formulas and its rule beside the guide's.

**The figures are counted now**, like every other figure in this tier: `steps` is a count of the step
rows, `minutes` is their sum, `sessions` is the count of the planned sessions this program has
produced, and `programs` is the count of program rows. The formulas are published beside them.

**The page.** The creator workbench gains a **programs panel** beside its profile and guide panels:
a publish form (title, summary, visibility and a step editor — the drill is chosen from the
training catalogue, the minutes and the author's note are typed), the shelf of the account's own
programs with each program's step count, and a **Start** button beside each one that plans the
steps as the learner's own training sessions, and an **Erase** button that takes the program and
the sessions it planned with it. Every string the panel shows is a catalogue key, so the panel adds
no English literal site — the copy gate's count did not move when it landed.

**Measured against the live API** (2026-10-21, `127.0.0.1:8099`): the drill catalogue answered 24
drills; publishing a program answered **201** with its step (`1v1-isolation-channel`, 20 minutes)
and its figures (`steps` 1, `minutes` 20); the scoped shelf answered **200** with the program it
had just published; starting it answered **201** with the planned session
(`ses_2I42XAkxPacccOet`) and the dose; erasing it answered **200** with `sessions_erased: 1`.

**The browser walk, which is the plane that matters** (2026-10-21, `apps/web/scripts/qa-creator.mjs`):
**72 of 72 checks passed, exit 0** on a production build served on `127.0.0.1:3218` against the
API on `127.0.0.1:8741` over a fresh SQLite database. The programs panel is walked in the tier's own
house style — every press is re-read through the door rather than trusted from the note it painted:

* the page publishes a program from its own controls, and the **program panel** is where the answer
  lands (the walk reads each note out of the panel whose control was pressed);
* the door holds the program the page pressed for, with the one step it named, and the panel
  repaints with it;
* **a step naming a drill the catalogue does not hold is refused at publication** (404
  `no_such_drill`), and that refusal wrote nothing — the shelf still held the one program it did;
* **starting a program with no player to plan for is refused** with the platform's own `no_player`
  (409), and once the account has a player the start button on the program's own row plans the
  caller's training sessions — which are the training tier's own rows, with the program recorded on
  them (so the sessions list says which program planned each one);
* a second account's program does not appear on this account's shelf, which is the account's own
  listing; and erasing a program from its row erases the program **and the sessions it planned**.

**Three defects the walk found, all of them in the harness or the surface rather than in the tier:**

* **the walk was silently locale-dependent.** The page answers in the browser's language (§81), and
  this host's Chrome asks for Chinese — so every English needle in the walk failed for a reason that
  had nothing to do with the tier. The walk now **pins the locale** with the `fo_locale` cookie
  before it opens its first page, and says so in its header.
* **the walk counted the tier's doors.** It asserted "the eleven doors it declares", and the tier
  publishes more now, so the check was wrong rather than the door. It now compares the published
  routes with the operations the API's own contract holds — count-free, and a real invariant.
* **the hand-written plurals the i18n arc introduced.** "{count} guide(s) on your shelf" is not
  English, and a page that says "0 GUIDE(S) ON YOUR SHELF" is a page that says nothing. Every
  plural in the catalogues is now **ICU** — `{count, plural, one {# guide} other {# guides}}` — and
  the Chinese keeps its plain form, because Chinese has no plural.

**What this does not claim.** A program is a plan and the plan is walked in the training tier; there
is no progress model of its own (a step is not "done" until a session is completed, and that session
is the training tier's row), no enrolment, no cohort, and no pricing beyond §42's table — which
still names two features and refuses on neither.

Measured: `tests/test_creator_programs.py` (10 cases) and `tests/test_creator.py` (42) are green
together; mypy is clean over 149 files; the contract is regenerated at 191 paths / 242 operations.

## The tactical guide — §36's second kind of content (2026-10-21)

The sentence above has been corrected rather than repeated: the `tactic` section was a guide whose
subject was a word. A tactical guide now anchors to a system the tactics tier stores, and what it keeps
about that system is the address and a witness — never a measurement.

* **The anchor is an address, not a foreign key.** `creator_tactical_guides.system_slug` names a row in
  `tactical_systems` and is deliberately a plain pointer: `services/tactics/sync.py` retires catalogue
  rows, so a foreign key would either block the retirement or take an author's words with it.
  Publication resolves the anchor (by slug or id) and refuses one the catalogue does not hold there
  (404 `no_such_system`) — a reading of nothing is not a reading.
* **No measurement is stored.** The column set is asserted as a set: author, slug, title, summary,
  visibility, the address, the hash witness, the date and provenance — no board, no coordinate, no
  metric. The eight metrics on both phases are computed on the read by `metrics_for_rows`, the same
  function `/api/v1/tactics/{ident}` answers with; a case compares the two answers metric for metric and
  checks each one carries its formula.
* **The proof is behavioural.** A scratch system's board is edited between two reads of the same guide:
  the answer follows the dots, equals the pure function's output, and `moved` flips. A stored copy could
  not pass that case.
* **`moved` is the citation rule applied to a board.** `system_hash` records the system's `content_hash`
  at publication; a revised system is still readable and says it moved. A **retired** system is absence
  at the address (404 `no_such_system`), while the shelf keeps the address with `name`, `formation` and
  `path` null — the author can see what to re-anchor, and the catalogue's retirement deleted nothing of
  theirs.
* **Four doors** under the tier's existing prefix: publish, the shelf, one guide (which carries the
  measurements), and erase. Erasing a guide leaves the system untouched. The shelf and the read need a
  session; reach is §35's follow predicate, so a `followers` guide opens on a follow and closes on an
  unfollow without deleting it; another account's guide is absence, and no door in this tier answers 403.

Measured 2026-10-21: `tests/test_creator_tactical.py` **15 cases**; the three creator files together
(`test_creator.py` 42, `test_creator_programs.py` 10, `test_creator_tactical.py` 15) answer **71 tests /
0 failures / 0 errors / 0 skipped in 36.783s** (junit, `.scratch/leg_tactical_creator.xml`); `mypy app`
clean over **150 source files**; `ruff check` clean on the five touched Python files; the contract is
regenerated at **193 paths / 246 operations**, the four new operations being its only delta.

**A whole-suite leg over the pre-unit tree, recorded honestly.** SQLite, on a frozen plane at
`f4d6146` (an ancestor that holds none of this unit's files), launched 2026-10-20T19:43Z: **1,740 tests /
1 failure / 0 errors / 4 skipped in 1,359.6s**, exit 1. The failure is
`test_openapi_contract_currency::test_the_exporter_derives_the_contract_from_the_tree_and_reproduces_the_committed_bytes`,
and the plane's own diff is `b'\n' != b'\r'`: the plane carried a CRLF copy of the contract, while the
same case is green in the tree where the artifact is LF (0 CRLF / 16,218 LF) and the exporter writes LF.
The estimate carried into the run (~1,662 tests / 0 failures / 2 skipped) was wrong on all three
counts; the run is recorded rather than dropped.

## The player analysis — §36's third kind of content (2026-10-21)

The third kind applies the second's rule to a different noun: **an address, never a copy**.

* **The anchor is an address, not a foreign key.** `creator_player_analyses.player_slug` names a row
  in `real_players` and is deliberately a plain pointer: `services/world/sync.py` retires generated
  rows, so a foreign key would either block a refresh or take an author's words with it. Publication
  resolves the anchor (by slug or id) and refuses one the world does not hold there
  (404 `no_such_analysed_player`) — a reading of nobody is not a reading. The first draft named this
  code `no_such_player`; the tier's own invariant case caught that §39–§41 already publish it, and
  the code was renamed before the unit landed.
* **No total is stored.** The column set is asserted as a set: author, slug, title, summary,
  visibility, the address, the hash witness, the date and provenance — no minute, goal, rate or
  rating. Five rates (`minutes_per_appearance`, `goal_contributions_per_90`, `scoring_rate`,
  `availability`, `cards_per_90`) are computed on the read from the anchored row's own columns, and
  each one prints its value, its unit and its formula.
* **The witness covers exactly what is read.** `player_hash` records the player's `content_hash` at
  publication. Every metric is derived from the anchored row's own columns, so a refresh that moves a
  number also moves the hash and the read says `moved`. The rates are deliberately *not* derived from
  `real_player_match_stats` lines: the hash covers the player row only, so a line-derived figure
  could move while the witness stood still.
* **The proof is behavioural.** A scratch player's totals are edited between two reads of the same
  analysis: the answer follows the columns, equals the world door's own `season_stats` fed through
  the published formulas, and `moved` flips. A stored copy could not pass that case.
* **`moved`, a retired player, reach and four doors.** A retired player is absence at the address
  (404 `no_such_analysed_player`), while the shelf keeps the address with `name`, `position`,
  `overall`, `team` and `path` null — and the author's row survives the world's refresh. Four doors
  under the tier's existing prefix: publish, the shelf, one analysis (which carries the metrics), and
  erase. Erasing an analysis leaves the player untouched; reach is §35's follow predicate, so a
  `followers` analysis opens on a follow and closes on an unfollow without deleting it; another
  account's analysis is absence, and no door in this tier answers 403.

Measured 2026-10-21: `tests/test_creator_analyses.py` **15 cases**; the four creator files together
answer **90 tests / 0 failures / 0 errors / 0 skipped in 48.356s** (junit,
`.scratch/leg_analyses_creator.xml`); `mypy app` clean over **151 source files**; `ruff check` clean
on the six touched Python files; the contract is regenerated at **195 paths / 250 operations**, the
four new operations being its only delta; migration `0032` upgrades to head, passes `alembic check`
silently and downgrades/upgrades cleanly on a scratch SQLite database.

## The match analysis — §36's fourth kind of content (2026-10-21)

The fourth kind applies the same rule to the fixture the world already plays: **an address, never a
copy**.

* **The anchor is an address, not a foreign key.** `creator_match_analyses.match_slug` names a row in
  `real_matches` and is deliberately a plain pointer: `services/world/sync.py` retires and re-creates
  generated fixtures, so a foreign key would either block a refresh or take an author's words with
  it. Publication resolves the anchor (by slug or id) and refuses one the world does not hold there
  (404 `no_such_match`).
* **An unplayed fixture is refused, not read as a blank result.** `match_not_played` answers 409 at
  publication, and again on a later read if the anchored fixture has lost its result: the tier has
  no measurements for a match that has not been played, and an analysis of a scoreless fixture would
  be a claim about nothing.
* **No score or stat line is stored.** The column set is asserted as a set: author, slug, title,
  summary, visibility, the address, the hash witness, the date and provenance — no goal, margin,
  percentage or stat pair. Five measurements (`total_goals`, `goal_margin`, `shot_accuracy`,
  `chance_conversion`, `possession_edge`) are computed on the read from the anchored fixture row's
  own score columns and `stats` object, and each one prints its value, its unit and its formula.
* **The witness covers exactly what is read.** `match_hash` records the fixture's `content_hash` at
  publication. Every measurement derives from the anchored row's score and stats, and the hash is
  computed over exactly those columns (`plan.content_hash(fixture.columns())` covers status, both
  goal columns and the whole `stats` object), so a revised result moves the hash and the read says
  `moved`. The measurements are deliberately *not* derived from `real_player_match_stats` lines: the
  hash covers the fixture row only, so a line-derived figure could move while the witness stood
  still.
* **The proof is behavioural.** A scratch fixture is replayed with a different score and different
  stats between two reads of the same analysis: the answer follows the row, equals the world door's
  own score and stats fed through the published formulas, and `moved` flips. A stored copy could not
  pass that case.
* **`moved`, a retired fixture, reach and four doors.** A retired fixture is absence at the address
  (404 `no_such_match`), while the shelf keeps the address with `home`, `away`, `kickoff_at`,
  `status` and `path` null — and the author's row survives the world's refresh. Four doors under the
  tier's existing prefix: publish, the shelf, one analysis (which carries the measurements), and
  erase. Erasing an analysis leaves the fixture untouched; reach is §35's follow predicate, so a
  `followers` analysis opens on a follow and closes on an unfollow without deleting it; another
  account's analysis is absence, and no door in this tier answers 403.

Measured 2026-10-21: `tests/test_creator_matches.py` **16 cases**; the five creator files together
answer **110 tests / 0 failures / 0 errors / 0 skipped in 52.428s** (junit,
`.scratch/leg_matches_creator.xml`); `mypy app` clean over **152 source files**; `ruff check` clean
on the seven touched Python files; the contract is regenerated at **197 paths / 254 operations**, the
four new operations being its only delta; migration `0033` upgrades to head, passes `alembic check`
silently and downgrades/upgrades cleanly on a scratch SQLite database.

## The scouting list — §36's sixth kind of content (2026-10-21)

The sixth kind is the first object anchored to **many** rows, and it keeps the same rule: **an
address, never a copy**.

* **The anchors are addresses, not foreign keys.** `creator_scouting_entries.player_slug` names a
  row in `real_players` and is a plain pointer for the same reason the analyses' anchors are:
  `services/world/sync.py` retires and re-creates generated players. Publication resolves every
  selection (by slug or id) and refuses one the world does not hold there (404
  `no_such_scouted_player`) — a list with a broken row would be a page that cannot say whose note it
  is showing. Two selections naming one footballer are refused (422 `scouting_duplicate_player`,
  with the player, the first position and the repeated one in the details): a list cannot hold two
  notes on one address and still say which is the reading.
* **No attribute of a player is stored.** Both tables' column sets are asserted as sets: the list
  holds author, slug, title, summary, visibility, the date and provenance; an entry holds the list,
  the position, the address, the hash witness and the author's note. No name, position, overall,
  club or sentence about a player. Every attribute a read shows is read from the player row on that
  read, and the shelf's `players` figure counts entries, not any measurement of a player.
* **The witness is per entry, because the anchors are.** Each entry stores the player's
  `content_hash` at publication; a read compares each entry with its own player, so a single
  refreshed footballer says `moved` on their own line while the rest of the list stands still. A
  player the world has retired leaves a **bare address** — `retired: true` and the brief's fields
  null — and the list stays readable. That is deliberately not the single-anchor shape an analysis
  uses, where a retired anchor is absence: there the whole content is about that one row, while a
  list is a selection of many and one retirement must not erase the author's other selections.
* **The proof is behavioural.** Two scratch players are published and then one is edited between
  two reads of the same list: that entry's answer follows its own row and flips `moved`, the other
  entry stands still, and the figures read `players=2, moved=1, retired=0`. A stored copy could not
  pass that case. A retirement is exercised as its own case, not inferred.
* **Erasing takes the entries and leaves the players.** The entries carry `ondelete="CASCADE"` and
  SQLite's own `PRAGMA foreign_keys=ON` is on in tests, so erasing a list takes its selection rows
  and touches no world row; the case asserts both ends.
* **Reach and four doors.** Publish, the shelf, one list (which carries the entries and figures),
  and erase — four private doors under the existing prefix. Reach is §35's follow predicate, so a
  `followers` list opens on a follow and closes on an unfollow without deleting it; an `unlisted`
  list is readable at its address and in no listing; another account's list is absence, and no door
  in this tier answers 403. The ceiling is 40 lists per creator (409 `scouting_list_limit`), a list
  holds 1–50 players (422 `scouting_players`), and the title, summary, visibility and note
  refusals name the field and its vocabulary.

Measured 2026-10-21: `tests/test_creator_scouting.py` **17 cases**; the six creator files together
answer **131 tests / 0 failures / 0 errors / 0 skipped in 58.799s** (junit,
`.scratch/leg_creator6.xml`); `mypy app` clean over **153 source files**; `ruff check` clean on the
six touched Python files; the contract is regenerated at **199 paths / 258 operations**, the four
new operations being its only delta; migration `0034` upgrades to head, passes `alembic check`
silently and downgrades/upgrades cleanly on a scratch SQLite database.

The first run of the new suite answered 409 on every publication: the unit of work had inserted the
entries before their parent list, because the entry carries a plain FK and no ORM relationship, and
SQLite's foreign-key enforcement refused it. The fix is an explicit `session.flush()` after the list
row is added — the order the schema requires is the tier's job, not a relationship's. The
project-wide guide census then caught the second mismatch before it landed: the router names its
path parameter `{list_id}` while `ROUTE_GUIDE` said `{list}`, and
`tests/test_creator.py::test_the_guide_names_exactly_the_doors_that_are_routed` compares the guide
with the app's own routed paths, so the two now agree on `{list_id}`.

## The career challenge — §36's fifth kind of content (2026-10-22)

The fifth kind is the first object whose figure is **another account's play**, and the tier's rule
survives it: **an address, never a copy**.

* **The challenge stores the author's rule, and the rule is the whole content.**
  `creator_career_challenges` holds the author's title and summary and three rule columns —
  `objective_kind`, `target`, `window_rounds` — over the career tier's own objective vocabulary
  (`OBJECTIVE_KINDS` and `OBJECTIVE_FORMULA`, imported rather than retyped, so a kind the career
  tier adds cannot become a challenge the engine cannot judge). Both tables' column sets are
  asserted as sets; no column could hold a score, a table position or any figure a career produces.
* **An attempt stores an address and a starting line, nothing else.** `creator_career_attempts`
  holds the entrant, the challenge, the entrant's own `career_slug` and `start_round` — a plain
  pointer with no foreign key, for the same reason the analyses' anchors are plain pointers: the
  career tier allows a career to be erased, and an attempt must not block that or take the
  challenge with it. A career the entrant no longer holds is a **bare address**
  (`career_missing`, brief fields null, `stored: false`, nothing summed into a zero), and the
  challenge stays readable for every other entrant.
* **The verdict is summed on the read, inside the window.** `_attempt_view` slices the career's
  `career_fixtures` rows to `start_round < round_index <= start_round + window_rounds` and hands
  them to the career tier's own `record_of`; `actual` is the objective read off that record
  (wins / points / goal difference / unbeaten run), and `rounds` lists the fixtures the sum used.
  The proof is behavioural: a career enters with two wins already behind it, and they do not
  count; the case then flips one in-window fixture from W to L between two reads and watches
  `actual` move from 6 to 3 while the career's own stored totals do not move.
* **The target is earned only when the window closes**, which is the career tier's own
  `verdict_for` discipline: while `played < window_rounds` the status is `in_progress` and
  `earned` is false even when `actual` already meets the target; at the closing round it is
  `met`/`missed`; a career that stops being active before the window closes reads
  `career_retired` rather than a verdict it did not earn.
* **Entering is refused twice, with figures.** A career that is not active, or has already spent
  the career tier's own challenge window, is refused at entry (409 `career_challenge_inactive`,
  with its status and rounds in the details); a second entry to the same challenge answers 409
  `career_challenge_entered` with the first attempt, its career and its `start_round`. Withdrawing
  removes only the attempt and leaves the career. Erasing a challenge takes its attempts (FK
  cascade) and touches no career row.
* **Reach and six doors.** Publish, the shelf (each row joined to the viewer's own `entered` flag),
  one challenge (which carries the viewer's attempt and the challenge's figures), erase, enter and
  withdraw — six private doors under the existing prefix. Reach is §35's follow predicate again.
  A stranger reading a public challenge sees `attempt: null` and the attempt **count** but not the
  entrant's career slug; an unlisted challenge is readable at its address and in no listing;
  erasing another account's challenge and entering with another account's career are the same
  absence; no door in this tier answers 403. The ceiling is 30 challenges per creator (409
  `career_challenge_limit`), a target is 1–99 and a window 1–38 rounds (422
  `career_challenge_target` / `career_challenge_window`).

Measured 2026-10-22: `tests/test_creator_challenges.py` **20 cases**; the seven creator files
together answer **157 tests / 0 failures / 0 errors / 0 skipped in 121.069s** (junit,
`.scratch/leg_challenges_creator.xml`); `mypy app` clean over **154 source files**; `ruff check`
clean on the six touched Python files; the contract is regenerated at **202 paths / 264
operations**, the six new operations being its only delta; migration `0035` upgrades to head,
passes `alembic check` silently and downgrades/upgrades cleanly on a scratch SQLite database.

## The career challenge on the page (2026-10-22)

`/creator` gained a fifth writing panel, and it is the first one whose subject is another
account's play: the author publishes the rule, the shelf shows the runs it drew, and the panel
that opens a challenge pins **this viewer's own** attempt.

* **The vocabulary panel has readers for the challenge rule.** The eight caps, the four objective
  kinds with the door's own formula for each, the two row counts and the limitation sentence are
  printed from `career_challenge_caps` / `career_challenge_objective_kinds` /
  `career_challenge_counts` / `career_challenge_rule` — no ceiling, kind or count is typed into
  the page. The walk reads them out of the panel before it publishes anything, and the door's
  own answer at that moment was `career_challenge_target_min/max = 1/99`,
  `career_challenge_window_min/max = 1/38`, four objective kinds and `0` challenges / `0` runs.
* **The shelf is this account's listing.** Each `tr[data-creator-challenge]` is a row of the
  door's answer: title + slug, `kind target`, the window, the visibility, the attempt count,
  whether this viewer entered, the publication date and Open/Erase. Erase asks first, exactly as
  the program and guide rows do.
* **Opening a row is a read, not a copy of the row.** `openChallenge` calls
  `GET /creator/challenges/{id}` and paints the author's summary and the objective's formula, the
  career picker built from `GET /careers` (this account's own careers), and — once a run exists —
  the verdict: the translated status, `actual` vs `target`, the career address, the window line
  (`start_round`–end, played, remaining, open/closed), the door's reason, the per-fixture table
  the sum used, or the no-run marker with the picker.
* **Each panel answers its own press.** Publish and erase run through one runner, enter and
  withdraw through another; the note is painted in the submitting panel and names the door's code
  when it refuses (`career_challenge_target`, `career_challenge_entered`, …). The walk reads the
  note out of the challenge panel, not the profile panel's.
* **The panel speaks all three catalogues.** The `creator` namespace went **99 → 148** keys per
  catalogue (49 added: 48 for the challenge surface and the open guide's eyebrow, which the same
  commit moves out of an inline literal). English uses ICU plurals; the two Chinese catalogues
  keep the plain forms. `qa-i18n-literals.mjs` passes **8/8** over **3593** key calls, and
  `qa-field-labels.mjs` **2/2** over 111 `.tsx` files.

**The browser walk** (`apps/web/scripts/qa-creator.mjs`, extended 2026-10-22): **97 of 97 checks
passed, exit 0** on a production build (`NEXT_DIST_DIR=.next-ci npm run build`, BUILD_ID
`G3GPpkpU_Mv57zF3c0X6e` served on `127.0.0.1:3218`) against the API on `127.0.0.1:8741` over a
fresh SQLite database (`.scratch/m10-challenge-walk.db`, migrated to `0035`). The 25 new checks:

* before anything is published: the vocabulary panel prints the challenge caps/targets/windows
  and the door's rule, and its two row counts are the door's own;
* the page publishes an **unbeaten, target 3, window 2** challenge from its own controls, the
  challenge panel paints the answer, and the door holds exactly that rule; the painted row reads
  `eight rounds unbeaten / eight-rounds-unbeaten · unbeaten 3 · 2 · public · 0 · NO`;
* a target of **0** is refused by name with the floor beside it (`422 career_challenge_target`: a
  target is between 1 and 99 and this one is 0) and writes nothing;
* the walk opens a career from the career door's own catalogue (`qa-challenge-manager-braa`),
  opens the challenge from its row, sees the no-run marker and the picker, and enters; the run
  panel reads *rounds 0–2 · 0 played · 2 remaining · window open* and the door agrees
  (`in_progress`, `played 0`, `remaining 2`, `actual 0`, start round 0); the shelf's Entered cell
  flips to yes;
* a second account reads the public challenge with `attempt: null` and **one** attempt — the rule
  and the count, never the entrant's career; a second entry is `409 career_challenge_entered` at
  round 0; withdrawing leaves `attempt: null` and zero attempts; the withdrawn run can be entered
  again; erasing the challenge answers 200, the row leaves the shelf, the address answers
  `404 no_such_career_challenge`, and the career that played it still answers 200.

Across the whole walk, **46 knocks** were made and **none answered 400 or 403**; every console line
left behind is a 4xx the walk knocked for itself, with no 5xx and no page exception. Screenshots:
`docs/screenshots/202610211719-creator-studio.png` (the challenge panel and its vocabulary rows in
the studio), `…-creator-shelf-mobile.png`, `…-creator-studio-final.png`,
`…-creator-stranger-studio.png`. `tsc --noEmit` is clean on the same tree.

## A finding this milestone corrected

`/community` (§35) and `/creator` (§36) both redirect a signed-out visitor to `/login`, and both were missing from
`robots.ts`'s `DISALLOWED` list while every other session-gated prefix was in it. The pages carry `noindex` of
their own, so the harm was bounded, but the project's §80 rule — a session-gated route is disallowed rather than
offered to the crawl as a redirect chain — was not kept for the two newest surfaces. Fixed in `3df6496`, with the
walk's own probe list extended so the next walk fails if either prefix leaves the served `/robots.txt`.

The gap was found by a script over `apps/web/app/**/page.tsx`, not by the browser: **26 routes redirect a
signed-out visitor to `/login`, 25 of them are covered by a `Disallow` prefix**, and the one exception is the site
root `/` — which cannot be disallowed without blocking the site, and is recorded here rather than changed.

## A second finding, and one this milestone's walk claims have to carry

`/creator`, `/community` and everything else answered **404** from 19:22 until `f8034c0`: `9ba8178` had wired
next-intl's path-rewriting middleware without the `app/[locale]/…` tree that rewrite expects. Two claims made while
that was true are withdrawn rather than repeated — `a578597`'s and `9ba8178`'s "production walk still 233/233"
lines, where the last real walk is `.scratch/vqa/walk.log` at 18:15, an hour before the commit they were quoted in.
Nothing in this file's own figures depends on them: they were measured with `pytest`, `mypy`, `ruff`, `alembic` and a
`next build` whose *build* succeeded, which is exactly how a site-wide 404 can hide behind a green pipeline. The
browser plane for §36 is therefore not "unwalked yet" in the ordinary sense — it could not have been walked.

## Outstanding, and the next slice

*All three were closed after this section was written; the milestone close-out at the end of this file is the
measurement.*

1. ~~a walk for `/creator`~~ — landed after this section was written, in `ab2d4c8`, at **56 of 56 checks, exit 0**
   on a production build; the figures it measured and the three defects it found are recorded in that commit and in
   `docs/M10_CREATOR_VERIFICATION.md`'s own walk section, not re-derived here. It was extended to **97 of 97** on
   2026-10-22 by the career-challenge panel and re-run on a detached plane at `c79f2dd`; that run is in the
   close-out below.
2. ~~§38 Football Career Portfolio~~ — its read landed in `471da30` (ten sections, two doors, 14 cases), its page in
   the commit that struck the original line, and **all three permitted public outputs landed after it**: the share
   link and its public projection (`/portfolio/share/{token}`, migration `0025`), and the owner-authenticated PDF
   (`/api/v1/portfolio/cv.pdf`). The sentence this bullet carried — "None of the three exists" — was true when it was
   written and is false now; the close-out's portfolio walk is **53/53**.
3. ~~§30 Knowledge Graph~~ — landed under M11 (2026-10-20), with its joint-retrieval evidence and §33's stored trace,
   in `docs/M11_AGENT_TRACE_VERIFICATION.md`; it was never an M10 noun.

## The whole-suite legs over §36, recorded late

Both engines were run over `2c0c5f2` — §36's noun, its doors and its contract — on 2026-09-28, and the tallies sat
in `.scratch/` unread by any document until the §38 page was measured. They are recorded here, out of each leg's
own `--junitxml` report:

| leg | tests | failures | errors | skipped | junit-reported duration |
| --- | --- | --- | --- | --- | --- |
| per-run SQLite | **1293** | **0** | **0** | **1** | 791.252s |
| PostgreSQL + pgvector | **1293** | **0** | **0** | **1** | 924.152s |

1293 is §35's closeout population of **1275** plus the **18** cases `9c6c6af` added in `tests/test_creator.py`, so
both legs agree with each other and with the arithmetic. The population has grown since (`§36`'s door cases and
`tests/test_portfolio.py`), which is why the figure belongs to §36 and to nothing later.

What these two legs do **not** record: an exit code. The wrapper printed one per leg and its own output belonged to
a superseded background task, while each `.log` file has the same missing last line a bash redirect has now caused
**four** times in this milestone — the junit `generated xml file` line is the last thing either log contains. The
reports themselves say 0 failures and 0 errors over 1293 tests, which is the substance an `rc=0` would have
reported, and the absence of the code is named rather than back-filled.

## The milestone, verified at `c79f2dd` (2026-10-22)

§36's six content objects and §38's three outputs are all landed, and this section measures the milestone on the
commit that carries the last of them. The ten files that hold M10's tiers were run on both engines over the same
bytes; the wires and the two pages were walked on a detached plane checked out at that commit, so the figures below
are not a reading of the shared worktree's uncommitted neighbours.

**The tier, on both engines.** One invocation per engine over the ten files:

| leg | tests | failures | errors | skipped | junit duration |
| --- | --- | --- | --- | --- | --- |
| per-run SQLite | **211** | **0** | **0** | **0** | 241.922s |
| PostgreSQL + pgvector | **211** | **0** | **0** | **0** | 1346.638s |

Both `rc=0`. The 211 are `tests/test_creator.py` **64**, the six content objects' files — programs **10**,
tactical **15**, player analyses **15**, match analyses **16**, scouting **17**, career challenges **20** — §38's
`tests/test_portfolio.py` **16** and `tests/test_portfolio_share.py` **24**, and §42's `tests/test_entitlements.py`
**14**. The case counts are the `<testcase>` elements of each engine's own `--junitxml` report, not a declaration.

**The static gates.** `scripts/lint.sh` — the one target both `scripts/check.sh` and CI call — answers *All checks
passed!*; `mypy app` is clean over **154 source files**; the contract exported in-process from this tree reads
**202 paths / 264 operations**, of which **21 paths / 38 operations** are `/api/v1/creator/…` (the figure §36's row
in `docs/SPEC_COVERAGE_AUDIT.md` publishes); `tsc --noEmit` on the plane writes an output file of **0 lines** and
exits **0**; `NEXT_DIST_DIR=.next-m10 next build` exits **0** with `BUILD_ID` **`wNhMbFrFqP2r54UwK1XNI`**.

**The walks, on that build.** The API answers on `127.0.0.1:8742` over a fresh SQLite database migrated through
**0035**, the web on `127.0.0.1:3219`, both under the plane's own tree. `qa-creator.mjs` — the walk whose 97 checks
include the five writing panels, the challenge rule and its verdict — passes **97/97, exit 0**, and
`qa-portfolio.mjs` passes **53/53, exit 0** with **11** recorded knocks whose statuses are exactly `200, 201, 401,
404`, **no** 403/400/5xx and **0** console errors. Both walks pin the locale to English with `fo_locale` before
their first page, so a host whose Chrome asks for Chinese cannot turn their needles red for a reason outside the
tier.

**What is still owed.** §42's payments remain unimplemented by design, and the two `creator_*` features stay
ceilings no door refuses on. A program is a plan, not an enrolled course with progress of its own. **The whole-suite
legs are not part of this claim**: the ten files above are the M10 reading on both engines, the last completed
whole-suite pair in this file is the 1293-case record over `2c0c5f2` above, and no whole-suite run over `c79f2dd` is
claimed here. The 2026-09-29 legs' missing exit code is not back-filled either.
