# M8 — §39/§41: a tenant is a row, a role is data, and isolation is a door-by-door proof

Spec lines: **§39 CLUB OS** asks for Club, Teams, Players, Coaches, Training, Matches, Tactics, Scouting, Video,
Development and Communication behind one club; **§41 B2B** names the paying tenants — Academy, Amateur Club,
School, Coach, Scout — demands a *multi-tenant architecture*, and lists the parts: Organization, Members, Teams,
Roles, Permissions, Players, Sessions, Reports.

This document certifies the tier that answers the storage half of both: migration `0016`,
`app/services/club/{access,organizations}.py`, thirteen routes under `/api/v1/club`, and the gate that reads them.
§41's `Sessions` and `Reports` rows and §40's whole academy page are named as outstanding in §8 below — this tier
decides *who may see them*, which is the part they all depend on.

## 1. The three decisions the tier is built on

**Membership is a row, and only a row.** `organization_members` — `(organization_id, user_id, role, status,
invited_by)` — is the sole fact this tier consults when it decides whether to answer a request. Two consequences
are load-bearing:

* one account can stand in up to five tenants, so the old single-pointer column cannot express the model at all;
* a standing can *stop* without the record of it disappearing, because `status` goes to `revoked` and keeps the
  row. A delete would have destroyed the answer to "who was allowed in here in March".

**The role is stored and the matrix is code.** `role` is the only permission-shaped thing in the database. What
it *opens* lives in `access._MATRIX`, is published by `GET /club/capabilities`, and is what the routes compare a
request against. Storing grants per row would let one membership drift away from its title with no record of when
or by whom. Unknown role ⇒ empty grant, and `grant()` says so in words; a typo in a role string is refused at the
door that sets it, so the silent case is unreachable through the API.

**The legacy column is watched, never trusted.** `users.organization_id` predates this service. It is filled once
— at the account's *first* active membership — and never read for an authorisation decision. `access_problems()`
reports a divergence between it and the membership rows rather than resolving it silently, and deleting a tenant
rewrites every pointer aimed at it, because an account pointing at a tenant that no longer exists would report
later as an organisation that no longer answers to anybody.

| | `users.organization_id` (pre-existing) | `organization_members` (§41) |
| --- | --- | --- |
| cardinality | one account → one tenant | one account → up to 5, one tenant → up to 40 |
| read for access? | **never** | every request, through `require()` |
| carries a role? | no | yes, and a status |
| who may change it | this tier, at first membership and at tenant deletion | an `org.member.*` holder, or the invitee themselves |

## 2. What `0016` stores, and what the schema refuses on its own

Four tables. The constraints are the interesting part, because each one is a lie a test would otherwise have to
catch after the fact:

* `organizations` — `slug` **globally unique**, `name` ≤ 160, `kind` ∈ `academy · club · school · scout_desk`,
  `country` two characters and `NOT NULL` (blank is the legal "no country named"), `visibility_default` ∈
  `members · staff · private`, `created_by → users` on `SET NULL`. A slug is unique *across* tenants, not inside
  one, so a tenant's address can never be ambiguous.
* `organization_members` — `UNIQUE(organization_id, user_id)`, both FKs `CASCADE`, `invited_by → users` on
  `SET NULL`. One standing per account per tenant is a schema fact, so a tenant's staff count cannot double-count
  a person.
* `club_teams` — `UNIQUE(organization_id, name)` and `world_team_id → teams.id` on **`SET NULL`**. Two tenants may
  name a team the same words; a team may exist with no counterpart in the generated world. Deleting a tenant takes
  its teams; the world's club it pointed at is untouched.
* `club_team_members` — `UNIQUE(team_id, player_id)`, both FKs `CASCADE`, `note` ≤ 240. **No figure column.** A
  sheet stores a pointer and a sentence: age, overall, potential and position are re-read from `real_players` on
  every request, the same choice §23's shortlist made, so a rating cannot go stale on a sheet.

Caps the service publishes and enforces: 5 tenants per account, 40 members per tenant, 12 teams per tenant,
40 players per sheet.

## 3. The thirteen doors

| Door | Session | Answers |
| --- | --- | --- |
| `GET /club/capabilities` | **no** | the rulebook: roles, the matrix, caps, vocabularies, counts, refusals, limitations |
| `GET /club` | required | this account's *active* standings, each with role, status, members, teams and room left |
| `POST /club` | required | open a tenant; the founder becomes owner and active member in the same transaction |
| `GET /club/invitations` | required | invitations addressed to this account, which grant nothing until answered |
| `GET/PATCH/DELETE /club/{ident}` | required · `org.rename` · `org.delete` | one tenant's standing, staff, teams and sheets; rename; close |
| `POST /club/{ident}/invites` | required · `org.member.invite` | offer a standing to an existing account — a row, not an email |
| `POST /club/{ident}/accept` · `/decline` | required | the two ways an invitation ends; declining deletes the row, revoking does not |
| `PATCH /club/{ident}/members` | required · `org.member.role` | change a role, the only way a member's rights change |
| `DELETE /club/{ident}/members/{email}` | required · `org.member.revoke` | revoke; the row stays, grants nothing, and gives its seat back to the 40 |
| `POST /club/{ident}/teams` | required · `team.create` | name a team of the tenant, optionally placed against the world |
| `PATCH/DELETE /club/{ident}/teams/{team}` | required · `team.edit` · `team.delete` | change or remove a team |
| `GET/POST /club/{ident}/teams/{team}/players` | required · `squad.read` · `squad.write` | read one sheet, or put a stored player on it |
| `DELETE /club/{ident}/teams/{team}/players/{player}` | required · `squad.write` | take him off; the rows that stay keep their order |

A tenant is reached by slug **or** id; a team by id **or** name — and a name is scoped to its tenant, which is why
there is no `GET /club/{ident}/teams` route: the tenant's own read prints its sheets. The contract carries
**104 paths and 124 operations** (from 91/106), regenerated from this tree as `docs/api/openapi.json`.

## 4. Refusals, each with the figures behind its sentence

Twenty codes, and the suite asserts the set is **closed** and that every one has exactly one HTTP answer:
`no_such_organization · no_such_team · no_such_member · no_such_player · no_such_world_club · no_such_user` answer
404/409 as written; **403 exists for one code only** — `insufficient_role`. Nine codes are 422 candidates
(`UNPROCESSABLE_CODES`), and the pydantic bounds sit *above* the published caps on purpose: at `NOTE_MAX` a schema
`max_length` would have answered a long note with a bare validation error, while `rules()["note_max"]` promises the
refusal that carries `length` and `max`. `insufficient_role` carries the permission named, the role held, the
tenant addressed, `permissions_held`, `known_role` and the matrix's own `why`.

Two of these were found by a red test, not by reading:

* `unknown_country` — `POL` had been **truncated to `PO`**, which is nobody's country code, so the page would have
  shown a wrong flag instead of an error. The guard now refuses anything that is not two ASCII letters or blank,
  and prints the length it was given.
* `holds_this: False` — the refusal published a figure that was constant by construction, i.e. a number no state
  of the world could change. It is gone; `known_role` and `why` replaced it.

## 5. Isolation, proved door by door rather than by one example

§41's whole promise is one sentence: *a member of one organisation cannot read or change another's rows.* One
hand-written example would only prove that one URL checks. So the suite derives the doors from `app.routes` itself
— every route whose path contains `{ident}`, **14 of them** — and parametrizes the same attack over all 14: an
owner of tenant A, a stranger with no standing, and a member of an unrelated tenant B knock on each of the 14 with
a body shaped for that door. Every answer must be the 404 `no_such_organization`, and it must not name the tenant
it belongs to, the team standing inside it, or either account's email. The read route answers through
`organization_view`, which therefore takes the caller's address as a **required keyword argument** — a view that
had already resolved the row must not be the thing that composes the sentence about it.

That second half of the rule was carried by a probe, and the probe failed at first. The tier has **four** sites
that raise `no_such_organization`, and only the read route's site had been taught to echo the caller's address:
`accept` was built from the row it had just resolved —

```python
raise ClubRefusal("no_such_organization", f"nobody has invited you to {organization.slug!r}", ident=organization.slug)
```

— so `POST /club/{opaque id}/accept`, open to any signed-in account with no invitation anywhere, answered a
guessed id with the readable slug behind it. One loop over an id range would have listed every academy on the
platform through a door whose entire purpose is to withhold that list. It now echoes `str(ident)` the way
`decline` already did, and `test_a_tenant_addressed_by_its_opaque_id_leaks_nothing_at_any_door` keeps all three
sites watched: mutating any one of them back to the resolved row turns that test red.

Three more claims the same class carries: the director of another tenant and a total stranger get **the same words**
(modulo the caller's own email), so nothing is confirmed either way; an `invited` standing and a `revoked` one are
answered identically, which is what stops "invited and has not answered" being distinguishable from "never invited";
and a 404 body holds exactly four keys — `code`, `message`, `ident`, `permission` — so a refusal may name the right
that was missing and the tenant as it was addressed, and nothing that was looked up. A separate test then closes the
other half of the promise: every tenant that appears on `GET /club` is one the same account can open, so a listing
cannot point at rows the doors refuse.

## 6. The gate that ships with the tier

`club_tables_present()` is the gate — table presence, not a try-block — because the capability flags sit on a
page-load path and an un-migrated database must report an empty working surface rather than a 500. Above it:

* `club_counts()` — organizations, memberships, **active** memberships, teams, squad rows;
* `access_problems(user)` — over the caller's own tenants only: a tenant with no active owner, a role outside the
  published six, a status this tier does not understand, a non-active membership that still grants a permission, a
  sheet above the 40 cap, an unnamed team, and a `users.organization_id` pointing at a tenant the account is not an
  active member of;
* `rules()` / `limitations()` — the published vocabulary and the honest list of what is *not* here.

The self-description is machine-checked in both directions: `routes` is structured data (`ROUTE_GUIDE`), and
`test_every_door_the_page_is_handed_is_a_door_and_every_door_is_handed_to_the_page` asserts the published
`(path, method)` set equals the FastAPI route table — a phantom door, a dropped door and a wrong verb each turn it
red. Prose that no test reads is not a contract.

## 7. The matrix, as published

| Role | Rights (20 in total) |
| --- | --- |
| `owner` | all twenty, including `org.delete` and handing roles over |
| `director` | sixteen — everything except `org.delete`, `plan.write` and the two parent-only scoped rights: runs the roster, the staffing, the curriculum and the fixture calendar, may erase a plan, cannot write a player's focus |
| `coach` | nine: `team.edit`, `squad.read`, `squad.write`, `plan.read_all`, `plan.write`, `curriculum.read`, `curriculum.write`, `match.read`, `match.write` |
| `analyst` | five: `squad.read`, `plan.read_all`, `plan.write`, `curriculum.read`, `match.read` |
| `scout` | two: `squad.read`, `curriculum.read` — sees sheets and the age-band curriculum, changes nothing |
| `parent` | three: `curriculum.read`, `plan.read_own_child`, `consent.grant_own` — each one scoped by a consent row, not by the tenant |

These counts were read out of `matrix()` rather than remembered, and saying so is part of the record: this table
carried "12 in total" and `parent` — **nothing yet** for two milestones after both stopped being true, first when
§40 filled the parent row and then when §41 wrote the curriculum rights. No test went red, because the table is
prose and `matrix()` is the code; the door was right the whole time and the page describing it was not.
`parent`'s row was empty at §39's landing as a stated position, not an oversight — §40 then gave it three rights,
each scoped to one child by the consent row that names it, which is why the row is short and not empty.
`plan.read_all` and `plan.write` were already in the vocabulary at that landing and already covered by the
matrix-completeness test, which is what let §40 land without re-cutting the permission names. `director` holding
`plan.read_all` but not `plan.write` is the same decision §39's Communication row will be read against: a director
runs the tenant's staffing and may read a plan, and writing one is the coach's and analyst's act.

## 8. Where this tier stops

Published in seven sentences by `limitations()` — six at this tier's landing, the seventh added when §42's
ceiling door and its pages went in — and repeated here so the ROADMAP row cannot overclaim:

* **a fixture keeps a pointer and a digest, not a result** — §39's `Matches` row landed on 2026-09-27: a tenant
  arranges a fixture against a club in the generated world and plays it through the same engine every other match
  row uses, with its own sheet applied over the world club its team is bound to, and the scoreline, the timeline
  and every counted figure stay in `sim_matches` and `sim_events`. `Communication` is the one §39 noun still
  unwritten; §40's development plans, §41's sessions and saved reports and §42's ceilings are separate services,
  the first three read through `/club/academy`. The tenant page prints this list, so a row that has landed and a
  sentence saying it has not are read together by everybody who opens `/club/{ident}` — which is why the wording
  has been corrected three times: once when the shipped sentence still called a training session missing after
  §41 had written one — the code was stale then — once in this document, which listed `Development` as unwritten
  several hours after §40 had written exactly that row, and once for the fixtures, where the door's sentence, this
  bullet and §7's matrix moved together rather than one at a time. A page that rewrites the door's sentences has
  to be re-read when the door moves;
* **§40's minors' regime is not in §39's own tables**: the sheet reports `is_minor` from the stored age and a
  team carries `age_group`, and that is all §39 stores — parental consent, data minimisation, erasure and the
  parent's scoped right are §40's rows in the academy tier, landed 2026-09-26;
* an invitation is a row and not a message; no mail transport exists in this project and none is claimed;
* a revoked membership keeps its row for the record and grants nothing; there is no audit trail of *what* anybody
  did, only of who stood where;
* teams point at the generated world's players, not copies — a tenant's sheet is a selection over the rows the
  scout already searches;
* deleting a tenant removes its memberships and sheets and rewrites nothing about a player, a club or a career;
* **the per-minute ceilings are counted per client address over one path**, so behind a proxy that forwards from
  a single address every tenant shares one bucket — a 429 says the address is busy, not which account tripped it,
  and the ceilings themselves are code at each door rather than a published figure. The browser walk found this
  by tripping it: three accounts, one address, and the tenant door answering 429 in the middle of a check.

## 9. Measured

* **77 items** in `tests/test_club_organizations.py` (46 test functions, widened to 77 by the two parametrized
  door loops — 14 by slug, 14 by id — and the body-shape cases), green on **both** database engines.
* Full API suite after the tier lands: **892 items collected across 25 files, 1 skipped, 0 failed** on the
  per-run SQLite leg and on the PostgreSQL + pgvector leg (each exit code 0; the `-q` summary line is swallowed in
  a whole-suite run, so the totals here were read off the progress rows and cross-checked against
  `--collect-only`, which reports the same 892). 77 of those 892 are this tier's; M7 closed at 814.
  **That figure is §39's step, and it is kept here because the sentence above is about the tier this file
  verifies.** §40's academy tables, §41's Sessions and Reports, and §42's entitlement meter have since widened
  the suite to **1073 items across 29 files — 1072 passed, 1 skipped, 0 failed on both legs**: 1813.58s
  (0:30:13) on the per-run SQLite file and 1562.41s (0:26:02) against PostgreSQL + pgvector, each with exit code 0.
  The 1 skip is the same PostgreSQL-only case in both runs, and the two summary lines were read off the two
  transcript files rather than inferred from a progress row this time.
* **§51's measurement, over the commit that unified the answer table.** A whole-suite run on `cefd1c6`:
  **1157 passed, 2 skipped, 0 failed on both engines** — 2278.85s (0:37:58) on the per-run SQLite file and
  1198.56s (0:19:58) against PostgreSQL + pgvector, each with exit code 0, both summary lines read off their own
  transcript file. The collected count went from 1073 to **1159 items**, which is §51's own file (86 tests, read
  off `--collect-only`) added to the previous total with nothing else moving. The skips went from 1 to 2 and both
  are named rather than counted: §51's `test_the_fixture_tier_registers_every_code_it_raises` carries a
  `skipif` while §39's `Matches` tier is unwritten (`tests/test_club_answers.py:162`), and the other is the same
  case it has been since §45 — `tests/test_scout_search.py:498`, `need_fit is ranked against a career and tested
  with one`, read off `-rs` rather than inferred from a count.
* `mypy` clean on the four owned source files; `ruff format` and `ruff check` clean on `app/` and `migrations/`
  files this milestone owns; `alembic upgrade head` over the whole chain on a scratch database and
  `alembic check` reporting **no drift** between `0016` and the models.
* Twelve behavioural mutations, each applied alone to the working tree and restored by checksum. The first three
  are the same leak planted at three different refusal sites, which is the point of writing them separately:

| Probe | Mutation | Caught? |
| --- | --- | --- |
| P1a | the write doors echo the slug they resolved instead of the address typed | RED — 11 doors answered with a slug they were never given |
| P1b | `accept` is turned back into a directory of tenants | RED — 1 assertion, the `post-/{ident}/accept` door |
| P1c | the decline door echoes the resolved row instead of the address typed | RED — 1 assertion, the `post-/{ident}/decline` door |
| P2 | the listing stops filtering on an active standing | RED — 2 assertions, first `test_every_tenant_on_the_list_is_one_the_list_can_open` |
| P3 | the refusal asserts the role is known instead of reading it from the grant | RED — 1 assertion, `test_a_role_nobody_wrote_grants_nothing…` |
| P4 | a country longer than two letters is cut down rather than refused | RED — 2 assertions, first the body-shape sweep |
| P5 | the schema answers a long country before the service can | RED — 1 assertion, the body-shape sweep |
| P6 | the schema answers a long squad note before the service can | RED — 1 assertion, `test_a_player_is_put_on_a_sheet_once_and_off_it_by_name` |
| P7 | a door no route implements is published to the page | RED — 2 assertions, first the capabilities page |
| P8 | a real door is dropped from the guide the page is handed | RED — 1 assertion, the two-way route test |
| P9 | a published method is not the method the route takes | RED — 1 assertion, the two-way route test |

* The web surface (`/club`, `/club/{slug}`) and its browser walk were task #42 at the time this was written; the
  counts above are §39's own landing, and §40's, §41's and §42's work is recorded in the sections below and in
  `M8_ACADEMY_VERIFICATION.md` / `M8_CLUB_WEB_VERIFICATION.md`.

* **§48's measurement, over the commit that landed the fixtures tier.** `06de944`, the whole suite on both legs,
  each `rc=0`: **1192 passed, 1 skipped in 3229.89s** on per-run SQLite and **1192 passed, 1 skipped in 2626.82s**
  on PostgreSQL + pgvector — 1193 items, of which §48's own file was 24 at that commit and the six club files 364
  in 516.79s. The one skip is named from the printed summary rather than subtracted from a total:
  `tests/test_scout_search.py:498: need_fit is ranked against a career and tested with one`. It fell from two skips
  to one because §48 made `services/club/matches.py` importable, which is the condition a §51 tier-registration
  case used to skip on — a skip that disappears is a gate that started working, and the two have to be tellable
  apart, which is why the sentence is here.
* **§48's probe, and the two holes it opened.** Eight arms over that commit, one value at a time, control first:
  five turned the suite red. Two survivors were coverage, not design, and both were the same mistake in
  different clothes — a rule tested far from its boundary, and a rule whose refusal state no case reaches. The fix
  (`99a94ee`) moved the attribution decision into `_appearance_agreement` so its four shapes are a table, gave the
  head count a case at ten names and the keeper rule a case at eleven-with-no-keeper, and handed the play door a
  disagreement it can be caught ignoring. Eleven arms, re-measured over `99a94ee` with an unmutated control
  (`rc=0`, 0 red, 108s):

| Arm | Defect planted in `services/club/matches.py` | Verdict |
| --- | --- | --- |
| P1a | a report naming a different eleven writes appearances anyway | RED — `test_the_attribution_rule_answers_for_every_shape_it_can_be_handed` |
| P1b | an empty lineup is treated as permission | RED — the same table case, on its empty-lineup shape |
| P1c | the play door ignores the rule it just asked | RED — `test_a_report_that_disagrees_leaves_the_result_standing_and_the_appearances_unwritten` |
| P2 | the world club's own squad stays on the pitch | RED — `test_the_eleven_that_played_is_the_tenants_sheet` |
| P3 | a minor is no longer gated on the default selection | RED — `test_a_minor_on_the_default_selection_stops_the_arrangement_until_a_guardian_answers` |
| P4 | a fixture may be played twice | RED — `test_a_fixture_answers_once_and_the_refusal_prints_the_first_answer` |
| P5 | the block length drifts away from the engine's choices | RED — `test_a_block_length_the_engine_does_not_play_is_refused_with_its_choices` |
| P6 | ten names field an eleven | RED — `test_the_head_count_is_held_at_its_own_boundary_and_not_only_far_below_it` |
| P6b | the keeper half of the same rule is dropped | RED — `test_eleven_names_reach_the_head_count_and_still_cannot_field_without_a_keeper` |
| P7 | the 200-fixture cap is raised where nobody looks | GREEN by design — reaching it means arranging two hundred fixtures, and the ceiling is held from the other side by the count the listing prints |
| P8 | a fixture and the engine's match row are erased together | RED — `test_a_fixture_answers_once_and_the_refusal_prints_the_first_answer` |

  **10 of 11 arms turned the suite red**, and two of the answers are worth reading twice: P8 was caught by the
  replay case rather than by the erasure case that names the same rule, so the erasure test on its own would not
  have noticed a deleted match row — the tier is covered, but not by the case a reader would expect. Over the same
  Over the same commit the six club files stand at **368 passed in 1568.02s** under a concurrently running suite,
  and `ruff check`, `ruff format --check` and `mypy app` (97 source files) are clean. The two whole-suite legs then
  ran over the docs commit `5e01714` — the first figures in this section measured over the fixtures tier *after*
  its own probe fix — and both are `rc=0`: **1196 passed, 1 skipped in 1958.79s** on per-run SQLite and
  **1196 passed, 1 skipped in 1531.97s** on PostgreSQL + pgvector. 1196 is 1192 plus §48's four new cases, and the
  single skip is the same one named above, printed by `-rs` on both legs rather than inferred:
  `tests/test_scout_search.py:498: need_fit is ranked against a career and tested with one`. Nothing in this
  milestone's club tier is now unlegged.

## 10. What the later tiers of this milestone changed in §39's own code

§39's tier was already called finished when §41's pages and §42's ceiling door started reading it in a browser.
Four things moved, each because a reader disagreed with a writer:

* **One clock.** `utc_today()` in `app/models/__init__.py` is now the single day the tier reasons from: §41's
  `date_in_future` rule, §42's `period_key` and a report's `generated_on` all read it. Before this, a host ahead
  of UTC could be told yesterday's session was in the future while the meter stamped today, and the tests agreed
  with the host rather than with the code. `tests/test_entitlements.py` holds the two doors to one day:
  a tenant's `sessions.today` must equal its meter's `as_of`, and the usage row the meter counted must be keyed on
  the day the tenant's own doors publish. Mutating `entitlements_view` back to `date.today()` turns that test red
  (`.scratch/one_clock_probe.py`, restored by checksum).
* **`ready` grew a sentence.** `organizations.READY_RULE` is published as `ready_rule` by *both* capability doors,
  so the flag cannot mean one thing at §39 and another at §40; the rulebook page prints the constant instead of
  paraphrasing it, and both API tests assert they were handed the same object.
* **Attendance stores the person, not the spelling.** `create_session` used to write the string the caller typed
  into `attendees`, while every read resolves each entry by primary key. It now stores the resolved id, dedup on
  the resolved id, and `list_sessions` counts under the slug a reader can follow. See §42's walk document, defect 3.
* **The sheet's ceiling counts players.** The `not_on_sheet` guard moved after resolution, so a one-child sheet
  and an attendance of `slug, id` for that child is one attendee rather than a refusal that claims there were two.
* **§51 took the answer tables away from the routers.** Three routers each assembled a code→status map by hand,
  so a code raised at a door that had not listed it was answered 400 while the same sentence earned 404 or 422 a
  path away. `services/club/answers.py` now owns the one table, assembled from each tier's own four code sets —
  a new tier appends its module to `TIERS` rather than editing a literal in a router — and `assemble()` raises at
  import when two tiers register one code with two different statuses, so the disagreement cannot be settled by
  dictionary order. Both club doors read the same object (`test_the_two_club_doors…` asserts identity, not
  equality), and both rulebooks print their rows through `answers.published()`, so a page cannot be shown a
  status its door does not use. Assembling the table is also what found two codes the tier had been
  double-claiming: §41's reading is now `unknown_report_kind` beside §39's `unknown_kind`, and §42's ceiling row
  is `no_such_entitlement_plan` beside §40's child's `no_such_plan`. Both renames are payload-visible and nothing
  else — no path, field or schema moved, so the contract still measures 123 paths / 154 operations.
* **§51's owed probe, run 2026-09-27.** The commit that landed the table said the whole-suite legs and the
  planted-defect probe were not yet run, so both are now, over `cefd1c6`. The plant is the mistake the tier
  exists to prevent: unregister one renamed code from its tier's own status set and the door falls through to
  400. Each plant was applied alone, after an unmutated control on the same slice, and restored from the bytes
  read before the probe (`.scratch/answers_plant_probe.py`):

| Probe | Mutation | Caught? |
| --- | --- | --- |
| control | neither code unregistered | GREEN — 97 passed + 1 skipped, and 99 passed + 1 skipped on the two slices |
| S1 | `unknown_report_kind` dropped from `reports.UNPROCESSABLE_CODES` | RED — 2 assertions, first the report door's own refusal test, which sees the HTTP status change |
| S2 | `no_such_entitlement_plan` dropped from `entitlements.NOT_FOUND_CODES` | RED — 3 assertions, first `test_a_published_code_has_an_answer_everywhere_it_can_be_raised[no_such_entitlement_plan]` |

* **§48 changed**: two tables (`club_fixtures`, `club_match_appearances`, migration `0021`), five doors, three
  permissions (`match.read`/`match.write`/`match.erase` — the matrix is 20 over six roles, and §7's table had been
  stale at twelve for two milestones with nothing turning red), `limitations()`[0] rewritten rather than grown, and
  `answers.TIERS` gained a member. Two of its drafted claims were wrong in ways only a run shows — a 422 the door
  could not answer twice, and an isolation entry whose empty body never reached `require()` — and two more were
  untested in ways only a mutation shows, which is what §9's eleven-arm table is for. The contract moved from 123
  paths / 154 operations to **126 / 159**.

## 11. §49 and §50: one ceiling, and the page reads its numbers out of the door

`sessions.py` enforced `attendance_max = 60` by writing the literal `60` three times — in the cap the rulebook
publishes, in the guard, and inside the refusal's own sentence — and `tests/test_club_sessions.py` had no case that
knocked on any of them. A figure written three times is a figure that can disagree with itself, which is the shape
§42's meter exists to catch, so the number became one constant, `MAX_ATTENDEES_PER_SESSION`, and four cases were
written against it:

| case | what it holds |
| --- | --- |
| edge accepted, one past refused | `MAX` names accepted, `MAX+1` refused, and the refusal's `max` figure is `CAPS["attendance_max"]` is the constant |
| the door writes nothing | 422 + `code: attendance_limit` + `named`/`max`, and the listing still reports `total == 0` |
| the rulebook publishes the same number | `GET /club/academy/capabilities → session_limits.attendance_max` equals the constant |
| the listing prints the per-row arithmetic | `formulas.load_units` is `LOAD_FORMULA`, and `total_load_units` is that string plus its own summation clause |

§50 is the same complaint pointed at the web tier. `SessionRecorder` and `ReportSaver` took
`limits: SessionLimits | null` and, on null, built the form from five numbers this tier invented — `[1, 2, 3, 4]`
for the slots, `8` for focus areas, `280` for the note, `60` for attendance and `366` for the report window — and
printed its own `load_units = duration_min × rpe ÷ 60` sentence beside a figure the door had always published.
`limits` is now a required prop, both forms are gated on `academyRules.ok` with the missing door named in the blank,
and the sentence is the string `formulas.load_units` handed over rather than a paraphrase of it.

Measured over `22374b4`:

- `ruff check .` clean, `mypy app` clean over 97 source files, `npx tsc --noEmit` clean, `npm run lint` with no
  warnings or errors.
- `tests/test_club_sessions.py` alone: **22 passed in 31.68s**; with `test_club_answers.py`: **108 passed**, and
  **0 reds in 6 repeat runs of the identical command** (106.02s, 61.80s, 67.13s, 56.80s, 64.94s, 94.18s) — recorded
  because one earlier run of that same pair printed `1 failed, 107 passed` in
  `TestSlotsAndDeletion::test_a_plan_filed_under_a_child_who_is_not_present_is_refused` and six more could not
  reproduce it. It is logged as unreproduced, not as explained: the machine was then in the memory pressure that had
  just killed a probe child with an OpenSSL `malloc failure` inside `hashlib.scrypt` at `/auth/register`, and no
  traceback was caught on the run itself.
- Whole suite, both legs, each `rc=0`: **1200 passed + 1 skipped in 770.91s** on per-run SQLite and **1200 passed +
  1 skipped in 1066.11s** on PostgreSQL + pgvector. 1200 is 1196 plus §49's four new cases, and the one skip is the
  same line printed by `-rs` on both legs: `tests/test_scout_search.py:498: need_fit is ranked against a career and
  tested with one`.
- The §41 recorder panel's browser walk was re-run over the required props: **217/217 checks, exit 0** against a
  production build, of which two are a concurrent run's uncommitted cookie checks — 215 is the count §48b left. Two
  of those checks are the ones §50 exists for: the recorder's printed caps compared field by field with what
  `session_limits` publishes, and the report form's `window_max_days`.

### The planted defect, and the figures this section withdrew

The first pass of the attendance probe printed *A1 caught by 5, A2 caught by 3, A3 caught by 4*. Those numbers are
withdrawn, and the two flaws that produced them are worth naming because neither is in the code:

* the scraper accepted any line starting `ERROR `, which the application's own captured log writes, so a red named
  `ERROR` was counted as an assertion;
* reds that the register-500 above was causing at the time were counted as catches, so a mutation was credited with
  assertions that had nothing to do with it.

`.scratch/mutate_attendance.py` now scrapes only pytest's short summary, prints the raw lines it matched, subtracts
the control's red set from each arm's, and requires each arm to name the assertion that carries it. Re-judged over
the same three arms behind an unmutated control (`rc=0`, 22 passed, 0 red):

| Arm | Mutation — the drift the constant exists to prevent | Named witness | Result |
| --- | --- | --- | --- |
| A1 | publish a cap the guard does not apply: `attendance_max` in `CAPS` becomes `MAX - 1` | `test_the_published_limit_is_the_number_the_session_form_opens_with` | RED — 3 failed, witness among them, 19 passed |
| A2 | print a figure the guard did not use: the refusal's `max` becomes `MAX - 1` | `test_the_ceiling_accepted_at_its_edge_is_refused_one_past_it_with_its_own_figures` | RED — 2 failed, witness among them, 20 passed |
| A3 | move the guard one place off the line: `> MAX + 1` | `test_the_door_answers_the_ceiling_with_the_rulebook_status_and_writes_nothing` | RED — 2 failed, witness among them, 20 passed |

**3 of 3 arms reddened the assertion named for them**, and no arm was credited with a red the control did not
already have. Each file was restored from the bytes read before the run and re-read to prove the restore.
