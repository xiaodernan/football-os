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
* The walk: **not run for this tier**. Nothing under `apps/web/scripts/` names `/creator`, so `/creator` has no
  browser evidence of its own — this is the one plane on which §36 stands behind §35, whose page shipped with its
  own 38-check walk. Named as the next slice rather than implied away.

## What §36 does not claim yet

* **The six kinds are six sections, not six objects — and the first four kinds now have objects
  of their own (2026-10-21).** §36 lists Training Program, Tactical Guide, Player Analysis, Match
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
  and stats. What is still not there: the other two kinds have no object of their own, a program is a
  plan rather than an enrolled course, and there is no progress model beyond the training tier's own
  sessions.
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

1. ~~a walk for `/creator`~~ — landed after this section was written, in `ab2d4c8`, at **56 of 56 checks, exit 0**
   on a production build; the figures it measured and the three defects it found are recorded in that commit and in
   `docs/M10_CREATOR_VERIFICATION.md`'s own walk section, not re-derived here;
2. §38 Football Career Portfolio — its read landed in `471da30` (ten sections, two doors, 14 cases) and its page in
   the commit that strikes this line (`/portfolio`, **37 of 37 checks** — see
   `docs/M10_PORTFOLIO_VERIFICATION.md`). What remains of §38 is its three permitted public outputs: a public
   player profile, a share link on §17's revocable-token precedent, and a PDF. None of the three exists, and the
   page prints that sentence rather than being one of them;
3. §30 Knowledge Graph, still unowned by a milestone and proposed for M11 in `docs/SPEC_COVERAGE_AUDIT.md`.

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
