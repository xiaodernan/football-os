# M10 verification — §38 Football CV, the page and the walk

Every figure in this file was read out of a command this run executed and printed, with the plane it was measured
on named beside it. Where a figure could not be read, the row says so rather than carrying a number forward.

## What landed

| commit | what it carries |
| --- | --- |
| `471da30` | `services/portfolio/cv.py` (the ten sections and their formulas), `api/v1/portfolio.py` (two doors, no code registered), `tests/test_portfolio.py` 14 cases, the contract at 146 paths / 189 operations |
| this one | `lib/portfolio.ts`, `app/portfolio/page.tsx`, the `Football CV` nav arm, `/portfolio` in `robots.ts`'s disallow list, and `scripts/qa-portfolio.mjs` — §38's read on the browser plane |

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

## Not claimed here

* **The whole-suite legs have not been run over this commit.** The 96-item figure above is three files, not the
  suite; both engines still owe their own tallies for `471da30` and for this slice.
* A **public player profile, a share link and a PDF** do not exist. `PUBLIC_OUTPUTS` prints each with its reason
  and the walk checks the page prints those reasons — the page is not one of those three things.
* `Matches` and `Stats` remain **unfilled**. The walk proves the page says so honestly; it does not make the rows
  exist. Filling them needs a table that records *this* account's player appearing in a match, which §39's
  `club_match_appearances` is not: that one belongs to a tenant and points at world players.
* The page has **no write control**, so this walk carries no press-a-button-moves-a-figure witness of its own; the
  only write it drives is §7's player row through its own door.
* `robots.ts` gained `/portfolio` and the page carries `index: false, follow: false`; no crawl test was re-run
  beyond the build and the lint above.
