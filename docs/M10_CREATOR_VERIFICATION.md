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

* **The six kinds are six sections, not six objects — and the first kind now has an object of its
  own (2026-10-21).** §36 lists Training Program, Tactical Guide, Player Analysis, Match Analysis,
  Career Challenge and Scouting List; the tier's `GUIDE_SECTIONS` is `plan, drill, match, tactic,
  scout, video`, and a guide is a title, a frame, a section and citations in every one of them.
  A **Training Program** is now a row of its own: a schedule, a dose and a progression, with a step
  naming a catalogue drill, and starting one plans the learner's own training sessions. What is still
  not there: the other five kinds have no object of their own, a program is a plan rather than an
  enrolled course, and there is no progress model beyond the training tier's own sessions.
* **No money, by design.** `creator_publish` and `creator_guide` are ceilings the data holds and **no door refuses
  on** — the caps that actually bite are the lifetime counts in `CAPS` (100 guides, 24 citations a guide).
* **The feedback half of §36's loop is §35's.** "Users → Feedback → Creator" is reactions, comments and follows on
  §35's rows; this tier stores no per-guide feedback of its own and counts `subscribers` from `community_follows`.
* **§38 is not started.** Football Career Portfolio is M10's second subject and the next slice, with the minors'
  part held back until §40's consent shape is read rather than duplicated.

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
