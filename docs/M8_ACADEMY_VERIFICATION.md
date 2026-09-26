# M8 · §40 Youth Academy — verification

Spec section 40 asks for seven things (`Player Development`, `Individual Development Plan`,
`Training Curriculum`, `Assessment`, `Coach Feedback`, `Video Evidence`, `Progress`) and, for minors,
six priorities (`Parental consent`, `Privacy`, `Data minimization`, `Access controls`, `Deletion`,
`Age-appropriate design`) plus a list of what must never be public by default.

The tier that answers them is `apps/api/app/services/club/academy.py`, routed through
`apps/api/app/api/v1/club_academy.py`, tested by `apps/api/tests/test_club_academy.py`.

The sentence this milestone is built on: **a child's plan exists only while a guardian's consent says it
may, and the only record of that consent is the row that gates it.** Everything below is that sentence
made checkable.

## The seven requirements, and the door each one answers to

| §40 asks for | Where it lives | How it is proven |
| --- | --- | --- |
| Training Curriculum | `GET/POST /club/academy/{ident}/curricula`, `PATCH/DELETE …/curricula/{curriculum}` | A curriculum names no child, so every standing in the tenant may read it and two may write it; `unassigned_minutes` is printed with its formula, and a curriculum a plan still uses cannot vanish silently — deleting it reports `plans_repointed`. |
| Individual Development Plan | `GET/POST /club/academy/{ident}/plans`, `GET/PATCH/DELETE …/plans/{plan}` | One live plan per child per tenant (`plan_already_open` names the plan that holds the seat); a closed one frees the seat and refuses further writes (`plan_is_closed`). |
| Assessment | `POST …/plans/{plan}/assessments` | Five published axes, each 0–100; `assessed_on` is an ISO day the caller typed, refused if it has not happened yet or if it would slide under the newest row. `overall_observed` is the world's rating copied on that day, not a live join. |
| Coach Feedback | `POST …/plans/{plan}/feedback` | Every note carries `shared_with_guardian`; a note withheld from the guardian is counted in `academy_counts()` rather than hidden, because "how much have you written that we cannot see" is a question a guardian is entitled to ask. |
| Video Evidence | `POST …/plans/{plan}/evidence`, `DELETE …/evidence/{evidence}` | A plan cites a window of a clip M5 already holds and never receives a way to watch it; playback still answers only to the uploader. Deleting a citation unlinks, it does not delete the file. |
| Progress | `GET …/plans/{plan}` → `progress` | Nothing is stored: every figure is arithmetic over this plan's own review rows, with the formula printed beside it. One review is not a direction, and the answer says so (`one_review_is_not_a_direction`). |
| Player Development | the plan page's own shape | `age_at_open`/`minor_at_open` are frozen when the plan opens, so a child who turns 18 mid-plan does not retroactively become an adult who consented for themselves. |

## The six minor-data priorities, as code

* **Parental consent** — `guardian_consents` is the gate, the scope ceiling, the record and the erasure
  anchor: one row does all four jobs. A player under `MINOR_AGE` (18) cannot have a plan, a review, a
  note or a citation until a granted row names the scope. Withdrawal stops the next write and touches
  nothing already written. Guardianship is **self-declared** and the answers say so: this platform can
  check that a child trains in this tenant and nothing beyond that.
* **Privacy / data minimisation** — minimisation *is* the column list. `rules()["stored_fields"]` publishes
  69 columns across 6 tables, and the suite asserts that list equals the live schema, table by table —
  so the sentence cannot drift from the migration. `never_stored` names ten things (home address,
  postcode, telephone, email, date of birth, precise location, school, medical or injury record,
  government identifier, photo outside the consented clip) and the suite asserts no academy column
  contains any of those tokens.
* **Access controls** — §39's role matrix plus one scoped set. `parent` holds exactly three rights, two of
  them (`plan.read_own_child`, `consent.grant_own`) settled only by a consent row. A parent reading
  another family's child is answered with `no_such_plan`/`no_such_player`, never a 403 — the useful half
  of a 403 would confirm the row exists. §40 adds **no 403 of its own**: `FORBIDDEN_CODES` is empty and
  the suite pins that.
* **Deletion** — `GET …/players/{player}/data` prints what is held, table by table, before anything is
  removed; `DELETE` without `confirm` is a dry run that returns the counts it is about to act on. Erasure
  takes this tenant's rows about this child and leaves the world's player row, §39's sheet rows and the
  uploader's clip file — each of which is asserted by name.
* **Age-appropriate design** — the refusal bodies carry figures, not prose a child has to interpret
  (`age`, `threshold`, `scope`, `consent_rows`, `scopes_present`, `scopes_available`), and a 422 never
  echoes the value that was submitted.

## Refusal contract (measured, not remembered)

`REFUSALS` = **36** codes: 6 → 404, 26 → 422, 4 → 409, 0 → 403. Four more
(`no_such_organization`, `no_such_player`, `name_required`, `insufficient_role`) are shared with §39 and
answer with §39's status. One code means exactly one thing — which is why an over-long field is
`text_too_long` with `field`/`length`/`max` rather than `focus_limit`, `feedback_limit` and three more
codes that would let a caller branch on the wrong fix.

Caps, each tested from both sides: 12 curricula, 8 phases, 0–1200 weekly minutes, 100 plans, 1–52 review
weeks, 6 focus areas, 8 goals, 52 reviews, 200 notes, 20 citations, 10 claims per guardian, plus the
per-field character ceilings.

## Doors and isolation

The academy publishes **12 door-guide lines / 19 doors** (`GET /club/academy/capabilities` is the one
public door; the other 18 name a tenant). §39's two-way isolation walk therefore reaches **32**
tenant-naming doors — 14 of its own plus §40's 18 — counted from the route table at test time rather
than from a list somebody maintains. A stranger knocking on an academy door and a director of an
unrelated tenant get byte-identical answers, and every id in the probe is one that belongs to nobody.

## What the suite caught in the product (not in itself)

The first full end-to-end run of `test_club_academy.py` was not a green-first milestone. Three of its
failures were real defects, and no earlier probe had surfaced any of them:

1. **A role refusal answered 500.** `GET …/plans/{plan}` as a `scout` raised
   `ClubRefusal(..., role=member.role, **access.grant(...))` — `grant()` already returns a `role` key, so
   the call collided on the keyword. Two doors carried it. A parent-facing tier's 403 was a crash for any
   staff role the matrix sits below the door. Fixed by letting `grant()` own the field.
2. **Any staff account could fabricate a guardian's yes.** `grant_consent` and `withdraw_consent` asked
   the matrix for `consent.grant_own`, which `owner`, `director`, `coach`, `analyst` and `scout` all hold
   or pass through — so a tenant's own director could mint the consent row that gates that tenant's
   children, which is precisely the thing the published scoped rule promises cannot happen. Now both
   doors require a `parent` standing and refuse with `insufficient_role` quoting the published sentence
   and `required_role`. The rule was already published by `rules()` and `matrix()["scoped"]`; it simply
   was not enforced anywhere.
3. **The cadence figure flattered itself.** `reviews_due_by_cadence` was
   `floor(span_days / cadence) + 1` over `last_review − first_review`, where `span_days` can only be
   measured between rows that exist — so a plan with a single review reported itself zero reviews behind
   no matter how long it had been owed the next one. It is now
   `floor(plan_days_open / (review_weeks × 7))` against the plan's own `created_at`, `reviews_behind`
   reports for a plan with no rows at all, and `span_days` survives as the separate figure the axis
   directions are measured over. The test moves the plan's open date to prove the number follows the
   plan's age rather than its history.

Plus one clock defect in the test module itself: it computed "today" from local time while the service
reads `datetime.now(UTC).date()`, which is a day off on this UTC+8 host — the kind of bug that makes a
boundary test pass on one machine and fail on another.

## Proven by mutation, not by assertion count

An 83-test file that stays green whether or not the gate works is decoration. Each probe below changes one
load-bearing *value* in `academy.py`, re-runs the whole file against a fresh database, and names the tests
that went red. The clean-source baseline ran first and exited 0 with zero named failures, so every red
below is the mutation's own doing.

| Mutation (behavior, not syntax) | What it breaks | Noticed by |
| --- | --- | --- |
| `if not _is_minor(player.age): return None` → `if True: return None` | the age check never fires, so an unplanned child needs no guardian | **5** tests: `a_minor_cannot_be_planned_for_until_somebody_answers_for_them`, `a_scope_nobody_ticked_is_refused_and_names_the_ones_that_were`, `a_withdrawal_stops_new_writes_and_touches_nothing_already_written`, `footage_the_consent_did_not_cover_is_withheld_from_the_parent_and_kept_for_staff`, `the_consent_that_lets_a_plan_open_is_named_in_the_answer` |
| `if scope in _scope_names(row.scopes):` → `if True:` | one granted purpose unlocks every purpose | **2** tests: `a_scope_nobody_ticked_is_refused_and_names_the_ones_that_were`, `footage_the_consent_did_not_cover_is_withheld_from_the_parent_and_kept_for_staff` |
| `if member.role != "parent":` → `if False:` | staff may mint a guardian's yes | **1** test: `only_a_parent_standing_in_the_tenant_may_answer_for_a_child` |
| `"plan_assessments": ("areas", …)` → prepend `"medical_note",` | the published column list claims a column the tables do not have | **1** test: `the_published_column_list_is_the_tables_own` |

The last two rows are the honest finding of this exercise: each rule is carried by exactly **one**
assertion out of eighty-three. A probe that had renamed the column differently — one that exists in
*another* table — would have slipped past `the_published_column_list_is_the_tables_own`, and the
parent-only standing has no redundant witness anywhere in the file. Both are recorded here rather than
smoothed over, because the count of tests is not the strength of a suite.

**How not to run a probe (done first, discarded):** the first round filtered with `-k` per probe and
reported every mutation caught. Its clean-source baseline failed 6 tests on an *unmutated* tree, which
invalidates all four results — one per-process database means a scan over rows that other tests planted
sees a different universe once those tests are deselected. The whole file, every time, is the unit of
comparison. And a note against a superstition this file used to carry: the tally line pytest prints *does*
land in a redirected log — `apps/api/pyproject.toml` sets `addopts = "-q"`, so adding `-q` on the command
line runs the suite at `-qq`, which is what suppresses the summary. Pass `-o addopts=` and read the last
line, rather than counting progress characters and trusting `rc` alone.

## §41's two tiers, probed the same way

Six more mutations, this time across `sessions.py` and `reports.py`, each against the whole 240-item club quintet,
control green first. **All six were caught and none survived** — which is the point: a rule nobody can break
without a test failing is the only kind of rule a document may claim.

| planted defect | what a reader would have been told | caught by |
| --- | --- | --- |
| `rpe` dropped out of the derived load | a heavy session recorded as a light one | 1 test |
| the future-date guard made to never fire | work that has not happened, printed as a record | 1 test |
| attendance no longer bounded by the sheet | a session widening who a tenant trains | 2 tests |
| a report computed at staff scope for everybody | a guardian shown rows another family's data comprises | 2 tests |
| an empty window's mean switched from `null` to `0` | a measurement inferred over nothing | 1 test |
| the unknown-kind refusal made dead | a reading this tier cannot produce, answered with the nearest one | 1 test |

The first run reported one mutation as NOT APPLIED — its anchor had been reflowed by `ruff format` after the probe
was written. It was re-anchored from the current text and re-run rather than counted as a catch, and then caught:
**an anchor that matches nothing is not evidence**, in either direction.

## Six rules planted wrong, on purpose

A green suite is a claim about the tests as much as about the code, so six values in this tier were mutated one
at a time and the whole 196-item club pair re-run against each — never a filtered subset, for the reason above.
The control (`rc=0`, `196 passed`) ran first and last.

| planted defect | what would go wrong for a reader | verdict |
| --- | --- | --- |
| `MINOR_AGE` 18 → 17 | a seventeen-year-old treated as an adult: no consent needed, no `is_minor` anywhere | **caught by 34 tests** |
| the minors' scope gate made to never fire | a plan, review, note or clip on a child nobody answered for | **caught by 5 tests** |
| one review allowed to yield a direction | `overall_change: 0` printed as "flat" where nothing is measurable | caught nothing — **a hole** |
| an axis rated at one end left in the direction list | a change claimed for a figure only one review ever held | **caught by 1 test** |
| the withheld-note count pinned to zero | a parent told nothing is hidden while a note is | **caught by 1 test** |
| the plans listing's published formula removed | a derived figure printed with no account of where it came from | **caught by 1 test** |

The survivor is the interesting one, and it is the same shape as the tier's other findings: the door's
`one_review_is_not_a_direction` flag *was* asserted, and the field that actually claims a direction —
`overall_change` — was not, at exactly the moment it should have been `None`. Two assertions were added
(`test_club_academy.py`, in the cadence and the deleted-review tests), the mutation was re-planted and is now
caught by those two tests, and the pair is green again behind them. **A flag that agrees with a number nobody
checks is not a rule.**

Probes live in `.scratch/` (untracked, like this tree's other harnesses): the anchor is a literal string that
must appear exactly once, the file is rewritten in a `finally`, the restore is proved by comparing the text back
rather than by trusting the write, and one anchor in the first round matched nothing — which the harness prints
as "not evidence either way" instead of letting a skipped probe count as a catch.

## How to re-run

```text
cd apps/api
../../.venv/Scripts/python.exe -m pytest tests/test_club_academy.py tests/test_club_organizations.py -q -o addopts=
# the same two files against the PostgreSQL/pgvector leg
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  ../../.venv/Scripts/python.exe -m pytest tests/test_club_academy.py tests/test_club_organizations.py -q -o addopts=
```

**§41's Reports is the last noun of §41's tenant model, and it stores the question and no answer:** `club_reports`
(migration `0019`, 11 columns, none of them a figure), four doors, 13 tests in `tests/test_club_reports.py`. A
squad-load report re-sums the sessions in its window at read time and prints each formula beside the row counts it
came from; a consent-gap report names the children on the sheets whom nobody has answered for. The same saved row,
read by a director and by one guardian, returns different numbers — the scope is applied when you read, not when it
was written — and a window with nothing in it says it is empty and prints no mean, because a mean over nothing is
not zero. Its codes (`unknown_kind`, `window_reversed`, `window_too_wide`, `report_limit`, `no_such_report`) are
published in `report_refusals`, beside §40's table, so that tier's one-row-per-code claim still means something.
The isolation walk reaches **40** doors; the club suite stands at **240 items green on both database legs** (SQLite
192s, PostgreSQL 251s), mypy is clean across 93 files, and the whole API suite stands at **1054 passed + 1 skipped
on each of the two legs**. An empty-window rule worth repeating: absence prints as
absence, never as a zero that a reader would call a measurement.

§41's Sessions tier landed after this document: `club_sessions` (migration `0018`, 18 columns, which moves
the published minimisation set to **87 columns across 7 tables**), four doors, and `tests/test_club_sessions.py`'
**16 tests** — the load computed rather than stored, attendance bounded by the sheet, a minor present needing the
same consent that opens their plan, a future date refused, a guardian scoped to the sessions their own child was
at, and a slot collision answered with the slot it tripped on. The isolation walk now reaches **36** doors that
name a tenant. Evidence: [the club web document](M8_CLUB_WEB_VERIFICATION.md) for the page tier and the commit
message for the tier's own reasoning.

`test_club_academy.py` is **83 tests** (measured: `83 passed, 1 warning in 94.98s`), and the pair is
**196 items green on both legs** on 2026-09-26 (`196 passed in 156.37s` on SQLite, `196 passed in 199.61s` on
PostgreSQL, both `rc=0`, both re-run after the door-shape fix below). The whole API suite, this tree, after §41 closed: **1054 passed and 1 skipped on both legs** — SQLite in 418.43s,
PostgreSQL/pgvector in 632.63s. Another session's uncommitted work is in the tree, so the figure is the worktree's,
not this milestone's alone; the milestone's own share is the **240** items in the five `tests/test_club_*.py` files.

**Two environmental facts that read as product failures, and how each was separated from one.** First: the
first run of the pair reported six isolation tests red, and the traceback was
`ValueError: [common libcrypto routines] malloc failure` inside `hashlib.scrypt` in `app/core/security.py` —
a password hash that could not allocate because a TypeScript compile and a test run were holding the host's
memory at once, not a tenant that had begun answering another tenant. Alone, the same six were green. Second:
the PostgreSQL leg reported *all* 196 items as errors, and `psycopg2.connect` on the port said
`Connection refused` — the pgvector container had no restart policy, so a Docker Desktop restart took the
database with it hours earlier. `docker update --restart unless-stopped football_os_db` and the same line in
`infra/docker-compose.yml` is what keeps the second leg from going dark between sessions again; a leg that
errors out wholesale is a dead dependency, and the first thing to read is the connection, not the code.

## The published contract

The whole spec is now **120 paths / 151 operations** in `docs/api/openapi.json`, up from §39's 104/124, from
§40's 116/143 and from the 118/147 §41 Sessions left behind; the academy's share is **16 paths** after Reports
added two more doors. Each re-export is taken from a scratch server started from the tree being documented —
port 8737 for §40, 8735 for §41 — never from the shared dev API. **Why the number was wrong once
already:** the first export in this increment printed 104/124 and zero academy paths, because a scratch
server started hours earlier on port 8736 was still listening and answered the request. A contract
artifact exported from a process that predates the code it documents is a lie with a timestamp, so the
check is now part of the walk, and it moves with the tier: the same command printed **12** at §40's close and
prints **16** after §41's session and report doors, and a re-export that changes the number is read as a changed contract
rather than as noise.

## Deliberately not here

* **No payment.** §42's `Free/Player/Pro/Coach/Club/Academy/Enterprise` tiers are entitlement
  architecture only, and the row that gates a child's data is a guardian's claim, not a subscription.
* **The web surface arrived after this document was written**, and found two defects this file had called
  finished: the plans door answered a guardian with a key set it did not answer a coach with — which turned the
  tenant page into a 500 for exactly the members §40 exists to serve — and the plan page printed a caller-relative
  withheld count under the words "withheld from the guardian". Both are closed, held from both sides by tests, and
  walked in [the browser evidence](M8_CLUB_WEB_VERIFICATION.md): **146/146 checks on a production build**.
* **No message, training session or match report** — §39's `limitations()` still says so, and now says
  where the plans did go.
