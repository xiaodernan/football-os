# M8 — the club tier in a browser: `/club`, the tenant page and the plan page

Walk: `apps/web/scripts/qa-club.mjs` — **215 checks, 215 passed, exit 0** on 2026-09-27, the latest run adding
§39's fixtures panel to the **194/194** of 2026-09-26 (which had itself grown from 146 as §41's sessions and
reports and §42's meters were added). Both runs went against a production build (`NEXT_DIST_DIR=.next-club
npx next build`, then `.next-fx` for the fixtures run) served on port 3214 by `next start`, with the API a scratch
`uvicorn app.main:app --port 8734` started **from this tree** (`API_INTERNAL_URL` points the web tier at it) and
running on a database `scripts/qa_db.py` created for the run rather than on anything a person works in.

**Why a scratch API rather than the dev one on 8731:** that server has been up since before the academy router
existed, and its `/api/v1/club/academy/capabilities` answers **404**. A page verified against a server that
predates the code it renders proves nothing, so the walk is run only against a process started from the tree
being committed — and the run prints the served webpack chunk and compares it to the one on disk in
`.next-club`, which is how a stale `next start` holding the port gets caught before it can pass for a result.

## What the walk insists on

It is not a screenshot pass. These properties carry it.

* **A stranger gets the answer a stranger gets.** `/club` with no session is a redirect that names where you
  were going (`/login?next=%2Fclub`); `/club/rules` is 200 and indexable; `robots.txt` Disallows `/club` and
  Allows `/club/rules`; the sitemap carries the rules page and no other `/club` address. Another tenant's
  address — page, plan page, tenant door, academy door, and §42's ceiling door — answers **404** to an account
  that was never invited, to an account whose invitation it has not answered yet, and to a third account that
  never was. A 403 there would confirm the tenant exists.
* **The page's own controls do the writing.** Every create, invite, accept, consent, plan, review and note is
  a click or a keystroke on a rendered control, not JSON posted by the walk: a button that never fires, a
  select that offers nobody, or a refresh that never re-reads fails here.
* **A refusal is painted as a refusal.** §40's order is witnessed from the browser: opening a plan for a child
  with no consent row is refused with `consent_required` and its figures beside the sentence, and the plans
  table still holds nothing. The tenant's own director pressing *Grant* is refused with `insufficient_role`
  and prints `required_role parent` — and no consent row appears, because a refusal is not a write.
* **Every printed figure is re-derived from the screen it appears on.** `overall_first/last/change` from the
  review rows as painted and from the column the door's own formula names; each axis change from that axis' two
  cells; the mean of a review from the axes it rated; `span_days`, `days_since_review`, `plan_days_open` from
  the three dates on the page; `due_in_days` and `reviews_behind` from `review_weeks`; the withheld count from
  the note rows. An empty table is not allowed to stand in for a refused read, so each academy panel's
  `data-refused` marker is compared with the HTTP status of the door behind it.

* **A ceiling that is painted is a ceiling that bites.** §42's meter table is read out of the DOM positionally
  (`tr[data-entitlement]`, one row per item the door sent), so `limit − used = remaining` is checked across the
  columns a reader actually compares rather than against a payload the walk fetched itself. The walk then spends
  the allowance for real: one saved report from the page is one act on the meter, the second is refused with the
  feature's own code, the refusal files no row and spends nothing, erasing the question gives the ceiling back
  **on the page and on the door in one assertion**, and the row it deletes is named. An account's own seat
  ceiling is not in that table, because it is not a tenant figure.
* **Nothing is invented by the walk.** The recorded session, the opened plan, the saved question and the meter
  row are all re-read from the doors afterwards; where a figure exists only because the door computed it —
  `span_days`, `load_units`, `appearances`, `days_since_review` — the check re-derives it from the rows beside it
  and prints the arithmetic it used.

## Live defects the walk found, and what each one was

Numbered through the whole page: §41's run found 1 and 2, §42's found 3, 4 and 5. The first two are the same
class — **one fact, stated two ways, disagreeing** — and so is the third.

**1. The plans door answered with two different shapes, and the page crashed for guardians.**
`GET /club/academy/{ident}/plans` had a special early return for a caller with no consent claim: `items`,
`total`, `role`, `read_through`, `rule` — and no `formulas`, `limit` or `minors_in_list`. The page, reading the
key the door documents for every other answer, raised `TypeError: Cannot read properties of undefined (reading
'progress')` and Next turned the tenant page into a **500** for exactly the class of member §40 exists to
serve. Measured first: the API answered that caller `200` with three rights and a squad row, so the door looked
fine and the page was the corpse. The fix removes the second shape — one door, one key set — and keeps the
explanatory sentence the special case existed to print by moving it into the `rule` value. The regression is
held from both sides in `tests/test_club_academy.py::test_a_parent_with_no_claim_gets_an_empty_list_rather_than_a_refusal`:
the guardian's empty answer must expose `set(staff) == set(listing)`, and the two `formulas` must be equal.

**2. The plan page labelled a caller-relative figure as guardian-specific.**
The API's `withheld.coach_feedback` counts *what this caller is not shown* — the suite already holds both sides
(staff read `0` with a held-back note on file, guardian read `1`). The panel printed that same number under the
words "of them withheld from the guardian", so a coach who had just written one shared note and one private one
was told, in their own language, that nothing was withheld from the family. The panel now reads
`N note(s) · M of them not shown to you`, and the guardian framing is left to the rule sentence the door prints
underneath. The walk asserts it twice, from the two accounts: the author's read shows 2 notes and 0 hidden from
them, the family's read of the same plan shows 1 of the 2 and names the other as withheld — and the withheld
note's text is present on one read and absent from the other.

*(§40's earlier run had already found a third: a blank axis in the review form filed as `Number("") === 0`
against the printed rule. That one was fixed before this walk was written; the walk keeps it fixed by leaving
one axis empty on purpose and asserting `axes_missing` names it.)*

## What the walk had to learn about itself

Six checks were wrong before the product was, and each wrong version is the kind of hole a green run hides:

* a Node-side helper (`selectorOf`, `data-${attribute}`) referenced inside a `page.evaluate`/`$$eval` callback —
  it runs in the browser, where the name does not exist; the crash was a `ReferenceError`, not a product bug;
* `/\bminor\b/` cannot match the rendered `17minor`, and `innerText` concatenates a badge with its number;
* asserting `answered 201` where `POST /club` honestly answers **200** (measured against the door, not assumed);
* registering the guardian with `role: 'parent'`, which is an *organisation* standing — the account roles are
  `fan/player/coach/manager/scout/academy`, and `parent` is what the invitation grants;
* reading a table the moment after a write, before the page's own re-read had landed: every state change now
  waits on either the door (`untilTrue`) or the exact painted string (`until`), never on a timer;
* counting every console line as a defect, including the 404s and the 422 the walk asked for itself. It now
  fails on a 5xx or a page exception, and prints the 4xx lines it provoked.

The register route is rate-limited per address, and a walk that cannot sign in proves nothing, so
`register()` waits out a 429 and retries; if it still ends blocked, the check prints the status rather than
letting an unrelated cascade read as a page defect.

The same lesson came back bigger with §42's pages. A tenant page re-reads several doors every time
`router.refresh()` lands, the walk drives three accounts from one address, and the walk's own `untilTrue` polls
add up — so `GET /club/{ident}` began answering **429**, and one check then crashed the run on
`Cannot read properties of undefined (reading 'permissions')` while the rest of the walk never executed. The
retry therefore moved from `register()` into `call()` itself: it honours the `Retry-After` the door prints, is
bounded, and still reports a 429 if the address really is blocked. The checks that were written against bare
JSON got the same treatment — an assertion that throws takes the remaining hundred checks with it, so
`my_grant?.permissions?.length` now prints `?` and fails that one check instead.

## What §42's session, report and entitlement pages found

Three product defects, and the first and third are the same sentence read two ways.

**3. A session recorded from the page named nobody.** `create_session` stored *the string the caller typed* in
`attendees`, while the read path resolves each entry by primary key to print a player's slug, age and
`is_minor`. The tenant page addresses players by slug — the same way every other door on this platform is
addressed — so a session recorded by clicking names on a sheet came back with empty attendance, and the two
figures built from that column inherited it: `most_attended` was `null`, a saved report's `appearances` was
`{}`, and `GET …/sessions` through `plan.read_own_child` told a guardian their own child had attended nothing.
The write now stores the id each address *resolved to*, so the write, the read and the scope all speak about one
person; `attendance_counts` and `most_attended` are keyed by the slug a reader can follow, because a figure
about a person is printed as the person. Held in
`tests/test_club_sessions.py::TestRecordingASession::test_an_attendee_addressed_by_slug_is_stored_as_the_player_that_every_later_reader_resolves`,
which asserts the slug round-trip, that one player written two ways is one attendee, and that the listing's
count and top name both answer in slugs.

**4. A capacity guard that counted spellings rather than players.** Found by the test above, on the way: with
one child on the sheet, `attendees=[slug, id]` for that same child was refused `not_on_sheet` — *"the session
names 2"*, which is false about a session that names one. The guard ran over the typed list before resolution,
so the fix moves it after: the sheet's ceiling is compared against the **distinct players the list resolves
to**. Both sides are now held — the mixed-spelling write files one attendee, and the existing test that names
two real players against a one-player sheet still refuses with `named: 2, on_sheet: 1`.

**5. `ready` was a flag with no sentence, and the rulebook paraphrased it wrongly.** Both §39's and §40's
capabilities doors carry `ready`, and the rulebook page described it as "whether their tables exist". The
actual rule is two conditions — the tables *and* at least one account — so the page's sentence was wrong about
the flag next to which it sat, and a freshly provisioned database honestly answers `false` while the page
implied a fault. The rule is now a published constant, `organizations.READY_RULE`, printed by **both** doors as
`ready_rule` (so the two cannot drift into two sentences), rendered on the rulebook page instead of the
paraphrase, and asserted as the same object on both sides of the API tier. The walk holds the flag from both
sides of its own run: `false` on the scratch database it just created, `true` after the first account it
registers, and the two doors' sentences byte-equal.

*(One more, on the walk's side rather than the product's: the erase check waited on the door and then read the
painted table, so it was measuring the walk's own race — `router.refresh()` repaints later than the note
lands. It now waits on the table and compares page **and** door in one assertion.)*


**One pattern left open on purpose.** The review, goal and rename forms still hold several fields in one
`useState` object and update it as `setForm({ ...form, field })`, which is the shape that lost the share
checkbox's value when two inputs arrived inside one React batch. The two controls that the walk drives faster
than a person can — untick a box, then type — are now functional updates; the rest are not, because nothing
here demonstrates them losing a field and rewriting fifteen handlers is not evidence. Anyone who extends these
forms should make the whole object functional at once rather than leave it half-converted.

## What §39's fixtures panel added (2026-09-27, `215/215`)

The tier's last page: an arrangement form and the tenant's calendar, mounted on `/club/{ident}` between the members
panel and the academy's consent table. Twenty-one checks, all through the page's own controls — the walk types the
opponent, picks the side, presses *Arrange the fixture*, then presses the row's *Play it* and *Erase*.

What it holds that an API test cannot:

* **no figure of its own.** The side list is read back as `select option` values and compared with
  `fixture_caps.sides` from `/club/capabilities`; the ceiling sentence with the listing's own `limit`; the block
  lengths and the eleven-and-a-keeper counts with the published caps. `caps` is a required prop of the panel, so a
  page that could not read the rulebook renders **no form** rather than one built on numbers chosen in TSX.
* **the day comes from the door.** The date field opens on the listing's `today`, and the walk asserts both the
  field's value and the `data-fixture-date` the page carries, because §41 already learned that a date read from the
  server process's clock at render time can be yesterday by the time somebody presses the button.
* **a refusal is not a write, and the page cannot make one look like the other.** An unknown opponent slug is
  answered 404 with `no_such_world_club` and the slug printed back; a date in 2099 is answered 422 with
  `date_in_future` beside the door's own today; after each, the calendar is read again server-side and is still
  empty. Pressing *Play it* on a side the tenant has not placed in the world's ladder is answered
  `no_world_side`, and the fixture stays `scheduled` with `match: null` and zero appearance rows.
* **the arithmetic is checked against the rows the page painted.** The appearances column is summed in the
  browser and compared with the door's total before either is quoted; the competition tally printed under the
  table has to be the one counted from the rows, not one typed beside them.
* **the erase is witnessed on both sides.** The button removes the row from the door's count *and* the table
  repaints to its own empty-state sentence.

**Deliberately not claimed here:** the walk never plays a fixture successfully, so this page has not been shown
producing an eleven's appearance rows. The tenant the walk builds has one child on its sheet and no world binding,
which is exactly the state the refusals above are about; a successful play needs an eleven of adults placed in the
ladder, and that path is held by §48's own suite (28 items, plus the eleven-arm planted-defect sweep in
`M8_CLUB_OS_VERIFICATION.md` §9). The panel prints that it does not narrow the named list, so the reader is not
left to infer where the arithmetic was proved.

## Three things this walk had to learn about itself

* **`typeInto` appends.** The first run arranged against `united-of-nowhere<real-slug>` because the ghost-opponent
  refusal above left its text in the field; the door's 404 was correct and the walk called it a defect. Every field
  a check re-uses is cleared first.
* **a painted row is not the same event as a written row.** `router.refresh()` re-reads on its own clock, so six
  checks failed against a page that was simply still showing the pre-write render. The fixtures section now waits
  on `waitRows(page, 'fixture')` before it presses anything a row owns — the same helper §41's panels use.
* **`innerText` is the rendered text.** A badge whose copy says "adds up to the total the door printed" is matched
  through `shouts()`, the walk's own case-folding helper, because a CSS `text-transform` uppercases it in the
  browser and not in the source.

Attribution of the build, since this run did not print the served webpack chunk the way §40's did: the panel's
controls exist only in `.next-fx` (`data-testid="fixture-arrange"`, `data-fixture=<id>` rows, the
`fixture-count-agrees` badge), port 3214 was verified free before `next start`, and both tiers were started and
stopped inside the same shell call that ran the walk — a server predating the code could not have answered the
presses that produced 215 passes.

## How to re-run

One command, from the repository root: `bash .scratch/qa-club-run.sh`. It is the only honest shape on this host,
and it does five things in one shell:

```text
python scripts/qa_db.py --name football_os_qa        # provision (and refuse to touch anything the URL names)
NEXT_DIST_DIR=.next-club SITE_URL=… npx next build   # a production build from this tree
uvicorn app.main:app --port 8734                    # DATABASE_URL = the scratch database, never the dev one
next start -p 3214                                  # API_INTERNAL_URL points the web tier at that server
QA_BASE=http://127.0.0.1:3214 node scripts/qa-club.mjs
```

`SKIP_BUILD=1` reuses `.next-club` when only the walk changed — but a run that is going to be cited as evidence
should build, because the page it verifies has to be the page this tree compiles to. After the servers answer,
the runner also prints the schema drift over the freshly provisioned database and regenerates
`docs/api/openapi.json` **from the scratch API** rather than the dev one: the process on 8731 has an older tree
loaded, and a route table exported from it would publish a door this build does not have.

Two things this host does not tolerate: a backgrounded `next start` (it does not reliably survive, and a walk
that talks to a dead port reports 25 failures rather than one environmental fact), and a shared database. The
walk now provisions its own, because `ready` is read from data — on a long-lived development database the flag
is true before the walk registers anything, and the check would only ever prove that a door answers. Screenshots
land in `docs/screenshots/` (untracked).

## Deliberately not here

* No erasure button. `DELETE …/players/{child}/data` wants a `confirm` echo of the row count it is about to
  destroy, which is not a decision a page should make in one click.
* No video evidence: the walk files no clip, and the plan page says so — a citation is a label and a window.
* No payment. §42's door prints the matrix it reads and the one feature today's plan actually costs; it does not
  print a price, because no price exists in this project to print.
* No `Matches`. §39's training, match, tactics, video and message rows are still the tier's own
  `limitations()` sentences rather than pages — and the page prints those sentences rather than paraphrasing
  them away.

## What stands behind this run

Every figure below was read off a command's own last line on the tree this document describes, on 2026-09-27.

* Browser walk: **215/215 checks** on a production build (the 2026-09-26 run was 194/194; §39's fixtures panel
  added 21), built with `NEXT_DIST_DIR=.next-fx npx next build` and walked by `node scripts/qa-club.mjs` against a
  scratch API and a scratch database of its own. `npx tsc --noEmit` exit `0`; `npm run lint` clean on the same tree.
* Whole API suite: **1072 passed, 1 skipped** — `1813.58s (0:30:13)` on the per-run SQLite file and
  `1562.41s (0:26:02)` against PostgreSQL + pgvector, both `rc=0`; `--collect-only` reports **1073 items across
  29 files**, which is what makes the single skip a countable thing rather than a gap in the progress rows.
* Club tier alone, as a group: **258 passed in 558.98s**.
* `mypy app`: **no issues found in 95 source files**. `ruff check .`: **All checks passed**.
* `ruff format --check`: **5 files would be reformatted, 145 already formatted** — `seed.py`,
  `evals/run_rag_eval.py`, `tests/test_challenges.py`, `tests/test_sim_ledger.py`, `tests/test_transfers.py`.
  All five are unmodified at `HEAD` and belong to earlier milestones, so this run left them alone: the gate
  states what is dirty rather than formatting somebody else's file to print a cleaner number.
* `npx tsc --noEmit`: exit `0`. `npm run lint`: **No ESLint warnings or errors**.
* Contract: **123 paths / 154 operations**, 30 of them under `/api/v1/club`, regenerated from the scratch API.
