# M6 verification — a season in the browser

Backend evidence for Career Mode is [`M6_VERIFICATION.md`](M6_VERIFICATION.md) §10: the tables, the
rotation, the seed rule and the 28 tests. [`M6_WEB_VERIFICATION.md`](M6_WEB_VERIFICATION.md) covered
the simulator and the world's training log. This document is the increment that gave the season a
page, and the evidence that a person can open a career, play rounds through the engine, and read
figures the server recomputed.

Date: 2026-09-23. Build: `NEXT_DIST_DIR=.next-ci SITE_URL=http://127.0.0.1:3211 npx next build`,
served by `next start` on the throwaway port, driven by `scripts/visual-qa.mjs` (system Chrome,
puppeteer-core) against the API on 8731 — which is why every number below is something the browser
reported rather than something a test asserted about source.

Walk total for the platform after this increment: **207/207 checks**, 66 screenshots,
exit 0.

## 1. Two pages, both behind the same wall as the simulator

| Route | What it is | Visibility |
| --- | --- | --- |
| `/career` | the account's seasons and the form that opens one | `PROTECTED_PREFIXES` — `noindex`, disallowed in `robots.ts`, absent from the sitemap |
| `/career/{slug}` | one season: record, objectives, fixture list, table of clubs met, tools | same wall; another account gets 404 |

The entry point is a panel action on `/simulate` ("Run a season instead") rather than another nav
item: the nav is checked at 375px for overflow by this same walk, and a fourteenth link is the kind
of change that needs its own measurement.

`GET /api/v1/careers/options` is deliberately public, because everything it returns — the generated
clubs, the fifty authored systems, the four objective kinds with their formulas — is already readable
under `/world` and `/tactics`.

## 2. What the walk asked the season page

Seventeen of the platform's checks belong to this increment, plus the console gate that follows them. Printed by the walk against a production build, each line's tail is the value the browser read:

```text
PASS  a signed-out visitor cannot open, list or read a career, while the knobs it is built from stay public — page 307 -> /login?next=%2Fcareer · list 401 · options 200
PASS  the simulator hands a visitor on to a season, so the career is reachable without typing a URL — 1 link(s) from /simulate to /career
PASS  the career form offers the world clubs and the four objective kinds, and admits what a budget does not do — 20 clubs · 4 objective kinds · budget caveat true · engine true
PASS  a fresh season prints a zero record with the formula behind each figure, and an unmet objective with its criterion — /career/qa-season-keeper-braa · sum(career_fixtures.points), win 3 / draw 1 / loss 0 · 1 unmet · 
PASS  the round about to be played is explained before it is played — seed named true · zero record true
PASS  playing a round reports the match that decided it, with digest, seed and model version on the row — Round 1 played: BRAA 0–0 DUNT (home, Braeford Yard). A draw is 1 point on the record, which now reads 1 played · 4
PASS  the record the page prints is the arithmetic of the round it just played — Rounds 1 · W/D/L 0 / 1 / 0 · points cell 1 · sum(career_fixtures.points), w · row 1
PASS  the season re-checks its copied score against the stored match report — 1 of 1 fixtures re-checked against their stored match report; all agree
PASS  two rounds make a fixture list, and the table of clubs met adds to two rows per round — 2 rounds · plays per club 2, 1, 1
PASS  each round links out to the match report that decided it — /simulate/braa-v-dunt-bf6aa754e2727b3b · /simulate/braa-v-durm-286dd162c4e8172e
PASS  the linked report is a page of its own and answers 200 for the owner — /simulate/braa-v-dunt-bf6aa754e2727b3b -> 200
PASS  the account list counts the season it holds and states its ceiling — total 1 · objectives 0/1 · ceiling 5
PASS  the career list shows the season with the record the season page summed — Your seasons MANAGER CLUB COMPETITION ROUNDS P W D L GD PTS OBJECTIVES MET STATUS QA Season Keeper Braeford Athletic Braehaven Eli
PASS  retiring the season stops the rounds and says so on the page — copy true · button found true · play disabled true
PASS  taking charge again re-enables the next round — play still disabled after resuming: false
PASS  deleting a season removes the season and keeps the match reports the account chose to play — careers 0 · stored matches left 2
PASS  a season stays out of the crawl: robots disallows it and the sitemap does not list it — robots rule true · sitemap mentions false
PASS  every browser console error was one this walk provoked on purpose — 8 seen, all of them deliberate
```

The walk also probes every one of the sitemap's 1037 `<loc>` entries for a 200, which is how a session-gated route published by mistake would be caught.

## 3. What the first runs of these checks caught

Sixteen career checks were written before any of them had run against a browser. The first run failed
four, the second failed one, and none of the five was the product being wrong about football:

* **A formula is not a label.** The record panel printed its `points_formula` in the `Panel eyebrow`,
  which the stylesheet upper-cases — so the reader saw `SUM(CAREER_FIXTURES.POINTS, WIN 3 / DRAW 1 /
  LOSS 0)` shouted at them and the walk could not match the string as arithmetic. The formulas now
  sit in the panel body as ordinary monospace text. This is the same `text-transform` trap the
  training-log checks had hit an hour earlier: `innerText` reports what a reader sees, not what the
  source wrote.
* **A Node-side fetch is not the owner.** The check that a round's match report "answers 200 for the
  owner" asked from outside the browser and got `307 → /login`. That is the privacy rule working
  correctly; the assertion was asking the wrong agent. It now asks from inside the page, with the
  cookie and `cache: 'no-store'`.
* **Two assertions described text the page never had** — the list cell prints `0 of 1`, not `0/1`,
  and the play control is found by its label, not by `button.btn`, which on that page is a different
  button.
* **A page change invalidated its own check.** Moving the points formula into the Points row made that
  cell read `0 · sum(career_fixtures.points), win 3 / draw 1 / loss 0`, while the arithmetic assertion
  still demanded `points === "0"`. The check now reads the number as a prefix and asserts the formula
  is present in the same cell — which is the stronger claim anyway: the page must show *both* the
  figure and how it was made, in one place.

The one deliberate product behaviour among them: retiring a season disables the round button rather
than hiding it, so the page can say there is nothing to play and why.

## 4. Reproduce

```bash
cd apps/api && python -m pytest tests/test_career.py tests/test_career_api.py -q
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest tests/test_career.py tests/test_career_api.py -q
cd ../web && npx tsc --noEmit && npm run lint -- --max-warnings 0
node --check scripts/visual-qa.mjs && SKIP_BUILD=1 bash scripts/verify-production.sh
```

The career block deletes the season it opened, so the run leaves no careers behind; the match reports
it played stay, on purpose — that is one of the assertions — and are scrubbed from the dev database
before the numbers in `ROADMAP.md` are quoted.

## 5. Not claimed by this increment

* **No live challenges (§21) and no transfer market (§22).** The budget field is stated intent: the
  page says so, the API's `limitations` block says so, and the walk asserts the sentence is rendered.
* **No squad-based promise can be kept yet.** The engine's lineup records `{player, position, band}`
  and nothing else, so "build a U23 squad" or "win with academy players" cannot be evaluated from
  stored rows. Recording age or contract status would change what a report contains, and therefore
  the digests of stored matches — a version bump to think about, not a field to slip in.
* **No reward semantics exist.** §21 asks challenges to be reward-based; there is no currency in this
  product that is not XP for the learner's own player, and a career awarding that would be a claim
  about a person's progress made by a fictional season. Challenges therefore land as goal + time
  limit + verdict, and the reward question stays open rather than being answered with a badge.
* **A season is not a competition.** The table on the page covers the clubs this career met, and the
  world's own league tables live under `/world/competitions`. Nothing writes back to the generated
  world's rows: no promotion, no relegation, no transfer.
