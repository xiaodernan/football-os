# M13 verification - a development plan behind a link its family can hand over

Phase 5's item 18 asked for the remaining read-only surfaces, and the academy's public plan is the second
half of that sentence: the scout report shipped on 2026-10-29, and this increment puts one plan behind a
token that a guardian, a coach or a lead can send to somebody without an account - and take back.

Date: 2026-10-30.

## 1. Four doors and one row

The backend lives in `apps/api/app/services/club/sharing.py`; the routes are in
`apps/api/app/api/v1/club_academy.py` and the table is migration `0042_plan_shares.py`.

| Door | Who may call it | What it answers |
| --- | --- | --- |
| `POST /api/v1/club/academy/{ident}/plans/{plan}/share` | the caller who can open the plan (`academy.plan_for_reader`), plus the minors' gate | the live token this account already holds for that plan, or a new one; `created` says which |
| `GET /api/v1/club/academy/shares` | any signed-in account | that account's ledger, owner-scoped so a link outlives a membership: `opened` / `live` / `revoked`, `max_live` 20 |
| `DELETE /api/v1/club/academy/shares/{token}` | the account that minted it | the row with `live: false`, `token: null`; 409 `share_already_revoked` on a second press |
| `GET /api/v1/club/academy/shared/{token}` | nobody in particular - the token is the whole credential | one plan's shape, recomputed from the plan's own rows on this request |

The row stores the *question* - tenant, plan, owner, token, `revoked_at` - and no measured value at all.
A token is `secrets.token_hex(16)` in a `String(64)` unique column, the same shape §17's board token and
§38's CV token use: a door that has to read the value back cannot store a digest. An unknown token, a
closed one and somebody else's are one 404 `no_such_share`; a plan that has since been erased is
`share_subject_gone` one level down. The refusal set is published beside the academy's own at
`GET /club/academy/capabilities` (`share_refusals`, and `sharing.LIMITATION` in `limitations`).

A link may only be minted over a plan its owner could open *and*, for a child, over a granted `plan`
consent: `open_share` walks `academy.plan_for_reader` and then `academy.plan_consent`, so the refusals at
this door are the private doors' own (`no_such_plan`, `insufficient_role`, `consent_required`,
`scope_not_consented`). Sharing an adult's plan needs no consent, because there is no guardian to ask.

## 2. What a stranger sees, and what the page says it is not

`public_plan` prints the plan's status, focus, goals, review cadence, opening date and stage (youth or
adult), `progress_of()` over the plan's own reviews, each review's ratings / missing axes / mean /
the world rating copied on the day, and the counts of assessments, feedback rows, feedback shared with the
guardian and evidence citations. It never prints a name, an exact age, a position, a rating, a team, an
author, a free-text coach note or a clip, and every figure is counted from the rows at read time.

`redacted` is nine pairs, each naming the omission and the reason: `name`, `exact_age`,
`position_and_rating`, `team_name`, `coach`, `feedback_text`, `review_notes`, `video`,
`account_and_guardian`. A minimised page and a thin page look alike from outside; only one of them is a
decision, and the page prints which.

## 3. The defect the live walk found: a live read behind a stale answer

The module promised that a review filed after the link was minted would be on the next public read.
Recomputing was true; *serving* was not. `app.main.cached_response_for` holds a successful anonymous GET
for sixty seconds, and the public path is anonymous by design, so the walk filed a third review and the
next read answered with the two-review payload it had cached. The recomputation was right and the page
was still wrong - the class of defect this project keeps landing against.

The fix, in `sharing.public_paths_of` plus `academy._retire_public_shares`: every write that changes what
a public page prints drops the cached path of each live token over that plan. The writes are plan edit,
plan erase, assessment, feedback, evidence citation and un-citation, and player-data erase. Deletes
collect the paths *before* the delete, because erasing a plan cascades its share rows away and there
would be nothing left to name the doors that have to shut. Closing a link already swept its own path;
that router now spells the path from `sharing.PUBLIC_PATH` so the sweep and the door cannot drift.

Three tests hold this: each of the five writes retires a warm answer and leaves a sibling plan's answer
warm; erasing a plan retires its answer and leaves a dead link behind; erasing a child's rows retires
every plan answer first. The browser walk proves it end to end: a note filed while the public page is
cached is on the page the reload prints (`2 * 2` - the page's own middle dot).

## 4. The web half

`apps/web/app/academy/shared/[token]/page.tsx` is a server component (`force-dynamic`) that renders the
public payload: counts panel, progress panel with its axis table and formula, the review table, and the
`redacted` list with `data-redacted-field` per omission. It is `noindex` with its canonical on `/club`,
because a link is a door, not a publication. There is no session check: the token is the credential.

`components/AcademySharePanel.tsx` sits on the plan page (`/club/{ident}/plans/{plan}`): create a link,
view it, copy it, and the account's ledger with live / closed badges and a revoke button on live rows.
Every write is followed by a read of `/club/academy/shares`, so the table shows the rows the API now
holds rather than the body a press happened to return, and a closed row loses its token - a dead key is
not printed for a reader to try. Copying shows the URL even when the browser denies clipboard access;
the printed URL is the fallback, and the panel no longer leaks a rejected promise into the console.

## 5. Catalogue and gates

42 new `club` keys in each of `en.json`, `zh.json` and `zh-TW.json`; the catalogue is now **3956 keys,
3911 translated** in both Chinese files, and `apps/web/messages/README.md` carries those figures. The
same-sense alignments the new strings forced (`career`, `opened`, `closed`, `child`, `token`, `link
ready`, `opening`) were made in the translations rather than by raising a ceiling, and
`qa-key-drift.mjs` was ratcheted from 99 to the measured **96** (over 248 shared sentences) with the
ledger entry for `club|kvChild,tableHeaderChild` retired because the two now agree. The API contract
gained the four routes (`docs/api/openapi.json`), which moves the audit's census to **215 contract
paths, 65 page routes, 43 migrations** (`docs/SPEC_COVERAGE_AUDIT.md`).

## 6. Evidence

| Command | Result |
| --- | --- |
| `python -m pytest tests/test_academy_share.py -q` | **21/21** - public/private progress equality field for field, exact private-key set absent, secret coach text absent, ageing, four gates, ledger / ceiling / revoke / owner scoping, three cache-sweep tests |
| `python -m pytest tests/test_club_academy.py tests/test_club_organizations.py -q` | **237/237** - the academy tier and the counted door walk (52 doors) |
| `python .scratch/walk-share.py` (API `:8732`, web `:3218`) | **46/46** - mint idempotence, public read vs private read, nine omissions, ageing after a review (the cache fix), three locales, revoke then 404 on the same request and on the page, 409 on a second close, closed row keeps the row and loses the token, minor consent on both sides of the yes, another account's token unclosable |
| `node .scratch/panel-share.mjs` (Chrome, headless) | **20/20** - login, panel ledger, create, copy, anonymous public page, no child, ageing while cached, revoke, 404, Chinese labels, no console errors |
| `python -m mypy app/services/club/sharing.py app/services/club/academy.py app/api/v1/club_academy.py` | clean |
| `python -m ruff check` on the changed API files and the new suite | clean |
| `npx tsc --noEmit` + `npx eslint` on the changed web files | clean |

## 7. What this does not claim

The consent gate is checked when a link is minted, not on every public read: a guardian's withdrawal
stops new plans, new writes and new links, and the link that was minted while the yes stood keeps
answering until its owner closes it. This is the tier's published rule ("new writes stop and the rows
already written stay"), and the panel's revoke button is the family's own door. The sweep is in-process
plus the shared Redis tier, like §24's revocation: a second API worker that never saw the write can
still answer from its own near cache for up to sixty seconds, where Redis is not serving.
