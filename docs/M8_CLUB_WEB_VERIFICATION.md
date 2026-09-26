# M8 — the club tier in a browser: `/club`, the tenant page and the plan page

Walk: `apps/web/scripts/qa-club.mjs` — **146 checks, 146 passed, exit 0**, 2026-09-26, against a production
build (`NEXT_DIST_DIR=.next-club npx next build`) served on port 3214 by `next start`, with the API a scratch
`uvicorn app.main:app --port 8734` started **from this tree** (`API_INTERNAL_URL` points the web tier at it).

**Why a scratch API rather than the dev one on 8731:** that server has been up since before the academy router
existed, and its `/api/v1/club/academy/capabilities` answers **404**. A page verified against a server that
predates the code it renders proves nothing, so the walk is run only against a process started from the tree
being committed — and the run prints the served webpack chunk and compares it to the one on disk in
`.next-club`, which is how a stale `next start` holding the port gets caught before it can pass for a result.

## What the walk insists on

It is not a screenshot pass. Four properties carry it.

* **A stranger gets the answer a stranger gets.** `/club` with no session is a redirect that names where you
  were going (`/login?next=%2Fclub`); `/club/rules` is 200 and indexable; `robots.txt` Disallows `/club` and
  Allows `/club/rules`; the sitemap carries the rules page and no other `/club` address. Another tenant's
  address — page, plan page, tenant door, academy door — answers **404** to an account that was never invited,
  to an account whose invitation it has not answered yet, and to a third account that never was. A 403 there
  would confirm the tenant exists.
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

## Two live defects the walk found, and what each one was

Both were in code this milestone had already called finished, and both are the same class: **one fact, stated
two ways, disagreeing.**

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

**One pattern left open on purpose.** The review, goal and rename forms still hold several fields in one
`useState` object and update it as `setForm({ ...form, field })`, which is the shape that lost the share
checkbox's value when two inputs arrived inside one React batch. The two controls that the walk drives faster
than a person can — untick a box, then type — are now functional updates; the rest are not, because nothing
here demonstrates them losing a field and rewriting fifteen handlers is not evidence. Anyone who extends these
forms should make the whole object functional at once rather than leave it half-converted.

## How to re-run

```text
# apps/api: a scratch server from this tree, never the shared dev one
python -m uvicorn app.main:app --host 127.0.0.1 --port 8734
# apps/web
npx tsc --noEmit && npm run lint
NEXT_DIST_DIR=.next-club SITE_URL=http://127.0.0.1:3214 npx next build
NEXT_DIST_DIR=.next-club SITE_URL=http://127.0.0.1:3214 API_INTERNAL_URL=http://127.0.0.1:8734 \
  node node_modules/next/dist/bin/next start -p 3214
QA_BASE=http://127.0.0.1:3214 node scripts/qa-club.mjs
```
Start the server, wait for the chunk to match and run the walk **inside one shell invocation**: a backgrounded
`next start` does not reliably survive this host, and a walk that talks to a dead port reports 25 failures
rather than one environmental fact. Screenshots land in `docs/screenshots/` (untracked).

## Deliberately not here

* No erasure button. `DELETE …/players/{child}/data` wants a `confirm` echo of the row count it is about to
  destroy, which is not a decision a page should make in one click.
* No video evidence: the walk files no clip, and the plan page says so — a citation is a label and a window.
* No payment, and no `Sessions`/`Reports` (§41's next items) — the tenant page prints the API's own
  `limitations()` sentences rather than paraphrasing them away.
