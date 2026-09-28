# M6 verification — a challenge you can open in a browser

Backend evidence for manager live challenges is [`M6_VERIFICATION.md`](M6_VERIFICATION.md) §11: the six
authored scenarios, the window enforced inside `career.play_round`, the verdict recomputed from a run's
own `career_fixtures`, and the 32 tests that hold those claims on both engines. What was missing was the
thing §21 promises a *manager* rather than a reviewer: a page.

Date: 2026-09-24. Build: `NEXT_DIST_DIR=.next-ci SITE_URL=http://127.0.0.1:3211 npx next build`, served
by `next start` on the throwaway port and driven by `scripts/visual-qa.mjs` (system Chrome,
puppeteer-core) against the API on 8731. Every number below is something the browser read back, not
something a test asserted about source.

Walk total for the platform after this increment: **226/226 checks**, 70 screenshots, exit 0, 8 browser
console errors and every one of them provoked on purpose by the walk itself.

Re-measured 2026-09-28 on a production build, after §60's refresh fix added three checks of its own:
**233/233 checks**, 71 screenshots, exit 0 — every figure below re-read rather than carried over.

## 1. Two pages, and the split between what is public and what is not

| Route | What it is | Visibility |
| --- | --- | --- |
| `/challenges` | the six-scenario catalogue, the start form, and this account's runs | `PROTECTED_PREFIXES` — `noindex`, disallowed in `robots.ts`, absent from the sitemap |
| `/challenges/runs/{slug}` | one run: verdict, window, record, constraints, the rounds the verdict is summed from, tools | same wall; another account gets 404 |

The two halves of the feature have different privacy, and the pages follow the API rather than the other
way round. `GET /api/v1/challenges` stays public because the scenarios are this project's own fiction —
already readable in source and in the catalogue's `problems: 0` integrity line — while
`/api/v1/challenges/runs`, `POST …/{slug}/start` and the run's own routes sit behind the session wall
like careers. So a signed-out visitor gets `307 → /login?next=%2Fchallenges` for the page, `200` for the
catalogue, and `401` for the run list. The walk asserts all three in one line, because a feature whose
public half leaked into the private half would otherwise look fine.

Entry point is a sentence on `/career` — *be judged by one that was fixed before you started* — linking
to `/challenges`, since a run is a career and the reader already knows what a season costs.

## 2. What the walk asked, and what it got

Seventeen of the platform's 226 checks belong to this increment. Printed by the walk verbatim:

```text
PASS  a signed-out visitor cannot open the challenge page or list runs, while the authored catalogue stays public — page 307 -> /login?next=%2Fchallenges · catalogue 200 · runs 401
PASS  the catalogue screen holds one card per authored scenario, each with its window and a formula behind every target — 6 scenarios · 6 window chips · problems: 0 · 10 targets / 10 formulas
PASS  every card counts its own constraints correctly, and each one that is only stated says why in a sentence — 18 applied · 4 stated only (all explained) · declared 18/22
PASS  the start form offers the choices a caller may make and nothing that would move a target — Scenario / Manager name / Competition to take the weakest club from / Tactical system — the part the engine reads · negotiable fields 0
PASS  the club the scenario gave is the lowest rating in the ranking the same response printed, not a club the walk named — Braeford Athletic at 0.4891 of 5 measured · lowest measured: 0.4891 · gap to runner-up: 0.0018
PASS  a fresh run opens inside the scenario window with the goal already fixed and the reward unearned — rounds 0 of 6 · IN_PROGRESS · 6 left in the window · SHORT Four wins from six — 0 of 4 count of career_fixtures where outcome = W · bar 0%
PASS  the run page carries the scenario constraints and admits what the window and the reward do not do — APPLIED, APPLIED, APPLIED, STATED ONLY · 2 limitation notices
PASS  two rounds in, the window is still open and the verdict says so with the numbers it used — rounds 2 of 6 · 4 left in the window · IN_PROGRESS · 2 fixtures of 6 played
PASS  the rounds the walk played are six distinct seeded fixtures, each with its own report — 6 rounds · 6 distinct seeds · reports /simulate/braa-v-dunt-… /simulate/braa-v-durm-… /simulate/braa-v-elna-… /simulate/braa-v-hals-… /simulate/dunt-v-braa-…
PASS  the verdict is the fixture table added up: the points figure is the Pts column and the win target is the W rows — Pts column sums to 4 and Points reads 4 · 0 W rows against objective Four wins from six — 0 of 4 · record 0 / 4 / 2
PASS  the window closed at six rounds: the bar is full, the button is out, and the verdict is no longer in progress — rounds 6 of 6 · 0 left in the window · status MISSED · play disabled true · the window closed at round 6
PASS  the reward is earned by the verdict and by nothing else: met exactly when every objective was reached — MISSED · objectives MET badge false · Reward: Homegrown — not earned. 0 of 1 objectives met after 6 of 6 rounds · 200,000 career credits · 350 xp
PASS  the round past the window is refused by the route, not just by the button, and the refusal carries the verdict — 409 window_closed · 6/6 rounds · verdict missed 0/1
PASS  a run is a career: the season page titles the goals as the scenario's, names its window, and links back to the run — Objectives the scenario set · win-with-academy-players · /challenges/runs/qa-challenge-keeper-braa
PASS  another signed-in account cannot read a run, play its rounds, or even see it in a list of its own — run 404 · season 404 · play 404 · page 404 · own runs 0
PASS  deleting a run removes the run and keeps the match reports its rounds produced — runs 0 · stored match reports left 8
PASS  a challenge run stays out of the crawl: robots disallows the surface and the sitemap does not list it — robots rule true · sitemap mentions false
PASS  every browser console error was one this walk provoked on purpose — 8 seen, all of them deliberate
```

Three of these are worth separating from the rest, because they are the checks that make §21's three
adjectives mean something rather than decorate it.

**The goal cannot be moved.** The form has exactly four fields, and the check asserts that none of
their labels matches `/window|budget|objective|target|philosophy|reward/iu` — so the claim "*the
objective, the philosophy and the budget came from the scenario*" is tested by the absence of a control,
not by a promise in prose. A fifth field would fail the walk.

**The club is measured, not named.** `win-with-academy-players` selects the weakest club of a named
competition, so the walk picks the competition with the *most* clubs the page itself published (five,
from the largest league rather than a two-club one), then asserts that the club the response handed back
is the arithmetic minimum of the ranking printed by the same response: the row marked `taken` must carry
the lowest number in the table, that number must equal the `lowest measured:` chip, and the
`gap to runner-up:` chip must be a real difference. `0.4891` is a selected-eleven rating on the engine's
own 0–1 scale — the mean of `/100` attributes — which is why the page header and the server's `how`
sentence both say so instead of writing `/100` over a number below 1.

**The window is enforced by the route.** After six rounds the button is gone and the bar is full, which
is a UI fact. So the walk asks for the seventh round anyway, over `fetch`, and requires
`409 window_closed` carrying `rounds_played 6`, `window_rounds 6`, the scenario slug, and a verdict whose
`window_closed` is true and whose reward is earned *if and only if* the status is `met`. The same
`reward-iff-verdict` relation is asserted twice, from the page and from the refusal, so neither side can
drift alone. That 409 is a deliberate non-2xx and is therefore in the console gate's `provoked[]` list
by path, which is the only reason the run still exits 0.

The arithmetic check is the one that would catch a fabricated verdict: the `Pts` column of the rounds
table is summed inside the browser and compared against the `Points` figure the server printed above it,
the count of `W` rows against the objective's own `actual`, and the record line against
`W / D / L` counted from the same rows. Here it agrees at `4` points, `0` wins, `0 / 4 / 2`.

## 3. What the increment found before it was green

Six things failed, and only one of them was a page being wrong about football:

* **A `next build` failure that `tsc` and `lint` cannot see.** `app/challenges/runs/[slug]/page.tsx`
  imported its stylesheets three directories up; the file is four deep. TypeScript resolves it (the alias
  covers both) and the build does not. This is the first time the CSS path bit, and it is the reason the
  build is a gate rather than a convenience.
* **A prose claim that read better than it computed.** The server's `how` sentence and the ranking table
  header both said `(/100)` about numbers in `0–1`. Nothing asserted it, and no test failed — the fix is
  on both sides of the seam, since a reader can arrive at either one first.
* **A harness bug the walk's own structure caused.** `chipTexts.map(text => /…/u.exec(text))` returns
  `null` for every chip that is not the one being hunted, and the next line dereferenced `[1]`. Fixed by
  filtering out nulls before reading groups — the same class of error as an unguarded `exec` anywhere
  else in this file.
* **Two assertions that tested a string where the fact was structural.** "Every objective prints its
  formula" first matched the literal `career_fixtures`, and `goal_difference`'s formula does not contain
  it; it now requires a monospace child over five characters in the same `li`. "The season page links
  back to the run" ran a regex against `document.body.innerText`, which does not contain `href`s; it now
  reads the attribute. Both were checks that would have passed on a worse page.
* **An edit that renamed a variable the block did not own.** A `sed` without a line range renamed a
  pre-existing `const refused` (the knowledge-refusal block, ~1,400 lines earlier), and the walk aborted
  with `refused is not defined` at check 33. Every rename in this file is now line-range scoped.

## 4. Reproduce

```bash
cd apps/api && python -m pytest tests/test_challenges.py -q
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest tests/test_challenges.py -q
cd ../web && npx tsc --noEmit && npm run lint -- --max-warnings 0
node --check scripts/visual-qa.mjs && SKIP_BUILD=1 bash scripts/verify-production.sh
```

The block closes by deleting the run it opened, so a walk leaves no runs behind; the eight match reports
its rounds produced stay, on purpose — that is one of the assertions. Screenshots
`33-challenges-club-measured`, `34-challenge-run-before-round-1` and `35-challenge-run-window-closed` are
under `docs/screenshots/` with the run's timestamp prefix (the mobile pass adds a fourth of `/challenges`
at 375px).

## 5. Not claimed by this increment

* **Four of the twenty-two constraints are stated, not applied**, and the page says so per card: 18
  `APPLIED`, 4 `STATED ONLY`, each with the sentence naming the mechanism the build lacks. Two of them are
  `no_transfers` and `academy_only`, and both stay un-enforced until the transfer market (§22) and a squad
  read that can filter by age exist. The walk asserts the counts agree with the badges *and* that no
  stated-only constraint is unexplained, so a future card cannot quietly claim more than it does.
* **A scenario's budget is a number the run carries, not one it spends.** The run page labels the row
  `Budget (set by the scenario)` and prints the career's own limitation notices for the window and the
  reward. Nothing grants the reward either: there is no wallet behind `career credits`, so an earned
  verdict is a recorded verdict.
* **The rounds are re-played, not re-read.** Each of the six is a stored `sim_matches` row with its own
  digest and seed — the walk asserts six distinct seeds and six report links — but there is no `sim_events`
  table, so a timeline is regenerated from the block model rather than retrieved.
* **No squad or training carries between rounds.** Every round's eleven is selected from the club's stored
  rows, which is what §22's market has to change before "carry-over" means anything.

`docs/M6_CAREER_WEB_VERIFICATION.md` §5 lists "No live challenges (§21)" as a limit of the career slice.
That bullet is superseded by this document: the challenges exist, their page exists, and the two bullets
about a budget and a reward that nothing spends still stand.
