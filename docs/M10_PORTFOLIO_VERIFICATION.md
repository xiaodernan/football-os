# M10 verification — §38 Football CV, the page and the walk

Every figure in this file was read out of a command this run executed and printed, with the plane it was measured
on named beside it. Where a figure could not be read, the row says so rather than carrying a number forward.

## What landed

| commit | what it carries |
| --- | --- |
| `471da30` | `services/portfolio/cv.py` (the ten sections and their formulas), `api/v1/portfolio.py` (two doors, no code registered), `tests/test_portfolio.py` 14 cases, the contract at 146 paths / 189 operations |
| this one | `lib/portfolio.ts`, `app/portfolio/page.tsx`, the `Football CV` nav arm, `/portfolio` in `robots.ts`'s disallow list, and `scripts/qa-portfolio.mjs` — §38's read on the browser plane |
| the next section | `models/CvShare` + migration `0025` + `services/portfolio/sharing.py` + four doors + `tests/test_portfolio_share.py` 24 cases — §38's **second permitted public output**, the revocable share link, at the API tier |

The tier owns no table and the page owns no figure: the CV is assembled at the moment of the read from rows the
other tiers write, which is why the walk's central witness is a *moved count* rather than a stored one.

## The figures, with the plane each was measured on

Measured on the API plane, on the tree this run holds:

* `pytest tests/test_portfolio.py tests/test_community.py tests/test_creator.py` with
  `--junitxml=.scratch/_p38web.xml` — **96 tests, 0 failures, 0 errors, 0 skipped in 23.153s**. Those three files
  are the ones that read `apps/web/app/**/page.tsx`: §35's pointer-prefix census walks the page tree, so a new
  route is a change they can refuse. The other two files were already green over `471da30`.
* No migration, no model, no schema change in this slice — it adds nothing the API plane has to re-verify.

Measured on the web plane (per-run, on this tree):

* `npx tsc --noEmit` — **rc=0**, its whole output file **0 lines**.
* `npm run build` — **rc=0**. `BUILD_ID` `o3aqLsLeDlsz-nNbGpI8I`, read by the walk out of `.next/BUILD_ID` and
  matched inside the HTML the preview server served, so the page driven below is the build just compiled.
* `npm run lint` — **rc=0**, `✔ No ESLint warnings or errors`.
* `curl http://127.0.0.1:3218/portfolio` with no cookie — **307** to `/login?next=%2Fportfolio`.

Measured in Chrome (`QA_BASE=http://127.0.0.1:3218 node scripts/qa-portfolio.mjs`, API on `127.0.0.1:8743` over a
scratch database at `C:/Users/18414/AppData/Local/Temp/qa38_api.db`; both ports checked for a listening socket
before binding, the shared dev API on `8731` never touched):

* **37 of 37 checks passed, exit 0**, 3 screenshots, 6 recorded door knocks, **0 console errors**.
* The rules door answered a caller with no session: the ten sections in §38's own order and with the spec's own
  words (`… | AI Reports | Development History`), exactly two marked not fillable, each with a reason and a
  `would_be_read_from`, three permitted public outputs all reading `not in this build`, and an empty
  `refusal_answers` table.
* `GET /api/v1/portfolio/cv` with no cookie — **401** `unauthenticated`, before any row was read;
  `GET /api/v1/portfolio/nope` — **404**, and no 403 or 400 turned up in any of the six knocks
  (statuses seen: 200, 201, 401, 404).
* A brand-new account: `has_player=false`, **0 of 10 sections filled**, and the page painted **0** blocks marked
  available — the count in the eyebrow is the count of blocks, not a number typed in TSX. Ten section blocks, in
  the published order, each printing the reason the door sent for the ones it cannot fill.
* §38's `Matches` and `Stats` printed their reason and the tables they would need, and **no figure cell at all**
  (0 of them), so the page neither drops them nor zeroes them.
* Figure-by-figure agreement: every painted `Figure / Value` cell compared with `figureText` of the value the same
  door answered with — **0 cells disagreed** on the first read (no section was filled yet) and **0 disagreed** on
  the second read across the **3** filled sections.
* The write that moves a count: `POST /api/v1/players` → **201**, then a re-navigation and a re-read —
  **filled 0 → 3**, Position / Archetype / Skills available, `Matches` and `Stats` still unavailable for a player
  that now exists. Nothing was cached in between, because nothing is stored to cache.
* Vocabulary: **10 formulas**, **3 outputs**, **2 doors** and the tier's `limitation` sentence all printed on the
  page; a deep key-walk of the CV payload covered **95 keys** and found **0** money-shaped ones (`price`,
  `currency`, `amount`, `checkout`, `payment`, `provider`, `stripe`, `invoice`), and the body text prints no
  `price` word.
* 375 px viewport: `scrollWidth - innerWidth = 0px`.

## What this run corrected, and what its walk got wrong first

The run's one red was the walk's own comparison, not the product: a needle had every whitespace character removed
while the haystack only collapsed runs of whitespace to a single space, so `has()` could not match a section block
inside the body text even though the block was on the page. It is reported as a harness defect because a green
first pass would have hidden it — the fix normalises both sides the same way, and the re-run is the 37/37 above.
No product defect surfaced on this slice.

Two sentences in `ROADMAP.md`'s M10 row were falsified by the tree while this slice was being measured, and are
corrected in the same commit rather than repeated: the row claimed `/creator` had no browser walk (
`apps/web/scripts/qa-creator.mjs` landed in `ab2d4c8` at **56 of 56 checks, exit 0**) and that §38 "is not started"
(`471da30` landed its two doors, its CV assembler and 14 cases).

## §38's second public output — the revocable share link, API tier (measured 2026-09-29)

**What landed.** One table, `cv_shares`, behind migration `0025`; `app/services/portfolio/sharing.py`; and four doors
added to the tier — `POST /portfolio/share`, `GET /portfolio/shares`, `DELETE /portfolio/share/{token}`,
`GET /portfolio/share/{token}` — so `/portfolio` now declares **6 doors**: five private, one that answers with no
session at all. `/api/v1/portfolio` therefore covers **3 new paths and 4 new operations** (`/share/{token}` carries
both the public read and the close). The sharing tier joined `answers.TIERS`, which is what makes its four codes
publish with a status instead of falling through to 400: `no_such_share` → 404, `section_unknown` → 422,
`minor_section_blocked` → 422, `share_already_revoked` → 409, and `FORBIDDEN_CODES` deliberately empty because 403 is
reserved project-wide for `insufficient_role`.

**The shape.** The token is `secrets.token_hex(16)` — 32 characters of `[0-9a-f]` — stored raw in the `String(64)`
unique column the migration declares, on §17's revocable-token precedent: one open link per account, re-pointing an
open link keeps its token so a scrape of the old URL is not a second link, closing sets `revoked_at` and keeps the row
so the account can say *when* it shut. The public read is `build_cv` **minus** the `account` block minus
`PRIVATE_KEYS` — a subtraction, not a second assembler, so the link cannot drift from the CV door behind it. An
unknown token and a closed token answer the same 404 with the same sentence: the door reaches, it never confirms
which of the two the caller found. §40 reaches here too: an account under the minor threshold may not put `videos`
in a link, and the refusal names the threshold it hit.

**The figures, each read out of the command named beside it** (all re-run over the bytes this commit holds):

* `pytest tests/test_portfolio_share.py tests/test_portfolio.py -q --junitxml=…` → **38 tests / 0 failures /
  0 errors / 0 skipped, rc=0**. The addends are the probe's own control line (that file is **24**) and the 14 §38
  recorded; `test_portfolio.py` is re-run rather than quoted because its import block and one of its claims both
  changed. junit reported 131.441 s for the pair — a concurrent run shared the machine for this measurement, so the
  wall time is not comparable to the 21 s the same two files took alone, and only the counts are carried forward.
* migration, on a scratch database (`DATABASE_URL=sqlite:///./_mig9b.db`, cwd `apps/api`; the shared dev database was
  not touched): `alembic upgrade head` rc=0, and its log ends `Running upgrade 0024 -> 0025, 0025 — §38's share
  output: one revocable token over a CV that stores no figures`; `alembic check` rc=0 with
  `No new upgrade operations detected.`
* `mypy app` → `Success: no issues found in **108** source files`, `sharing.py` among them.
* `ruff check app tests` → `All checks passed!`, rc=0. The first whole-tree run over these bytes found **1 error** and
  it was mine — an unsorted import block in `tests/test_portfolio.py` (I001) that the earlier per-file fix had missed.
  Fixed with `ruff check --fix` on that one file, then ruff *and* the unit pair were re-measured; no figure below is
  quoted from the run before that fix.
* contract: `docs/api/openapi.json` counted out of the file being committed — **149 paths / 193 operations /
  63 schemas**, and `git diff --numstat` against HEAD says **169 added / 1 deleted**. The single deletion is the
  reworded description of `GET /portfolio/rules`, which now names the share tier's rules too; every other line is an
  addition, so §38's doors keep the contract they had.
* mutation probe (`.scratch/m10-share-wip/probe.py`) → **SURVIVORS=0 over 6 arms**, control 24/0 before the arms and
  24/0 after the last restore, every arm a byte-exact replacement that refuses to start unless its pattern occurs
  exactly once, and every file re-hashed against the pre-run hash after each restore. Each arm's red set equalled the
  set written into the script beforehand: A1 validator-receives-the-cleaned-list → 1, A2 `PRIVATE_KEYS = ()` → 4,
  A3 dropped `revoked_at.is_(None)` → 2, A4 `MINOR_BLOCKED = ()` → 2, A5 unscoped revoke → 1, A6 caller-typed order
  kept → 1.
* the three rewritten `/portfolio` walk predicates in `apps/web/scripts/qa-portfolio.mjs` were judged by
  `.scratch/m10-share-wip/verify_walk_checks.mjs`, which extracts each shipped predicate out of that same file by a
  balanced-bracket scan (so it tests the text that ships, not a copy) and evaluates it against the rules door of a
  server started from this tree on `8739`: all three **true on the live door, false on a mutated one**, and a third
  mutation that falses only the `pdf` sentence flips the middle predicate — which is what makes that predicate's
  `startsWith('not in this build')` clause a reader rather than decoration. `VERIFY_RC=0`.

**What the first run of this slice got wrong, and where the defect actually was.** Six reds, one of them production.
The five that were my test file: hand-typing the published section order instead of deriving it from
`portfolio.SECTIONS` (`matches` comes before `training`, and §38's order is the contract); expecting a *live* foreign
token to answer 404, which contradicts the tier's own claim — a live token opens the door for whoever holds it, so the
case now asks for two closed tokens from two accounts plus one never minted, and separately asserts the live one
answers 200; a figure helper that subtracted 1 from an empty section because the seeded account had no training
session; `PRIVATE_KEYS + ["id"]` (a tuple plus a list); and `test_portfolio.py`'s assertion that the tier publishes an
empty refusal map, which was true at `471da30` and false the moment the share tier joined `TIERS` — that line is now
four derived assertions ending in `400 not in … .values()` and `403 not in …`.

The production one was **`section_unknown` unreachable**: `_ordered()` dropped the unrecognised name before
`_check_sections` ever saw it, so the first run of this tier asked for `wallet` and got a link back. The fix is
ordering, not a new validator — `share()` validates the raw request and only then asks for the spec's order. Probe A1
arms exactly that swap and the test that caught it is the case that asks for `wallet`.

Two notes on the probe itself. A1's *first* arm was not evidence: it moved the call above `chosen`, which raised
`NameError` inside the request, and the arm reported **18 reds of a crash** instead of one red of a caught defect;
the number this record carries is from the re-armed behavioural swap. And A2 turning four reds is the point of a
design change made while writing the tests: a census that builds its forbidden-key list by reading the service's own
`PRIVATE_KEYS` goes **vacuous** the instant that tuple is emptied, so the list is now a literal in the test file with
a separate drift pin that makes the two declarations agree. A2 also caught a real hole in the projection — it was
dropping `unfilled_reasons`, the CV's "this section is empty because…" map, from the public read, which is why the
projection now carries that key through explicitly.

**Not claimed by this slice.** There is no page at `/portfolio/share/{token}` and `/portfolio` still has no write
control, so the press-a-button-moves-a-figure witness belongs to the web landing and is owed there. And the whole-suite
legs have not run over these bytes: the prediction written before the run is §38's recorded **1326** plus this
slice's **24** = **1350**, and that is arithmetic, not a measurement.

## Not claimed here

* **The whole-suite legs ran over this commit, and they are recorded with their exit codes.**
  `.scratch/run_legs_p38.py` ran `python -m pytest -q --junitxml=…` once per engine at `031a3c1` and appended its own
  result line, so this time the per-leg `rc` survived the run:
  **`sqlite leg rc=0 tests=1326 failures=0 errors=0 skipped=1 junit_time=1067.045 wall=1069.88s`** and
  **`postgres leg rc=0 tests=1326 failures=0 errors=0 skipped=1 junit_time=3005.326 wall=3072.96s`**.
  The population was predicted *before* the run — §36's recorded 1293, plus the 19 cases `test_creator.py` gained
  after `2c0c5f2` (18 → 37), plus §38's 14 in `tests/test_portfolio.py`, = **1326** — and both engines measured
  exactly that. The addends are then re-read from the runs' own junit reports rather than from that arithmetic:
  1326 cases over 178 test classes, of which `tests.test_creator` is 37 and `tests.test_portfolio` is 14. Each leg
  carries exactly one skip, the same count every leg has carried since §35 closed.
* Of §38's three permitted public outputs, **the PDF still does not exist**, and neither does a **page** for the two
  that landed. `PUBLIC_OUTPUTS` now prints `public_player_profile` and `share_link` as built, and both name
  `GET /portfolio/share/{token}` — the same door is the profile and what the link shows, which is why one read covers
  two of the three outputs. `pdf` still starts "not in this build". The page renders these sentences from the door
  rather than holding its own copy, and the walk's page-level check asserts each output's *name* appears in the
  painted text, so it does not re-type a sentence the tier owns.
  What is *not* claimed is a browser surface: the share doors are answerable, not reachable from `/portfolio` yet.
* `Matches` and `Stats` remain **unfilled**. The walk proves the page says so honestly; it does not make the rows
  exist. Filling them needs a table that records *this* account's player appearing in a match, which §39's
  `club_match_appearances` is not: that one belongs to a tenant and points at world players.
* The page the **37 of 37** walk ran over has **no write control**, so that walk carries no
  press-a-button-moves-a-figure witness of its own; the only write it drives is §7's player row through its own door.
  This slice adds two write **doors** (`POST /portfolio/share`, `DELETE /portfolio/share/{token}`) that no page drives
  yet, so that witness is still owed and belongs to the web landing. `apps/web/app/portfolio/page.tsx` line 31's
  comment — "Nothing on this screen is a public profile, a share link or a PDF" — was true at `471da30` and is now
  stale on the door plane: the sentences it renders changed, the file itself was not touched here.
* `robots.ts` gained `/portfolio` and the page carries `index: false, follow: false`; no crawl test was re-run
  beyond the build and the lint above.
