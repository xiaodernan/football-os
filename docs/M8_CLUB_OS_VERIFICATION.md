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

| Role | Rights (12 in total) |
| --- | --- |
| `owner` | all twelve, including `org.delete` and handing roles over |
| `director` | everything except `org.delete`, `plan.write` — runs the roster and staffing, cannot delete the tenant or own the plan |
| `coach` | `team.edit`, `squad.read`, `squad.write`, `plan.read_all`, `plan.write` |
| `analyst` | `squad.read`, `plan.read_all`, `plan.write` |
| `scout` | `squad.read` — sees sheets, changes nothing |
| `parent` | **nothing yet** |

`parent`'s empty row is a stated position, not an oversight: §40 gives it a right scoped to one child's own plan,
so an empty row is the honest answer and `limitations()` says which tier fills it. `plan.read_all` and `plan.write`
are therefore already in the vocabulary and already covered by the matrix-completeness test, which is what lets §40
land without re-cutting the permission names. `director` holding `plan.read_all` but not `plan.write` is the same
decision §39's Communication row will be read against: a director runs the tenant's staffing and may read a plan,
and writing one is the coach's and analyst's act.

## 8. Where this tier stops

Published in seven sentences by `limitations()` — six at this tier's landing, the seventh added when §42's
ceiling door and its pages went in — and repeated here so the ROADMAP row cannot overclaim:

* **no match report or message exists in this tier** — §39's remaining rows (`Matches`, `Tactics`, `Video`,
  `Communication`) arrive in the milestones after this one, which is why only `Permissions` and the addressing of
  everything else are settled here; §40's development plans, §41's sessions and saved reports and §42's ceilings
  are separate services, the first three read through `/club/academy`. The tenant page prints this list, so a row
  that has landed and a sentence saying it has not are read together by everybody who opens `/club/{ident}` —
  which is why the wording has been corrected twice: once 2026-09-27, when the shipped sentence still called a
  training session missing after §41 had written one — the code was stale then — and once in this document, which
  listed `Development` as unwritten several hours after §40 had written exactly that row, while `limitations()`
  above was already right. A page that rewrites the door's sentences has to be re-read when the door moves;
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
