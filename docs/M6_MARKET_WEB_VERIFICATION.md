# M6 verification — a market a manager can actually spend in

Backend evidence for the transfer market is [`M6_VERIFICATION.md`](M6_VERIFICATION.md) §14: the two tables
(`transfer_listings`, `career_squad_moves`), the valuation that is a stored player row run through a
printed formula, the need that is this club's own weakest engine band, the budget that is a sum of move
rows, the seller that answers by a published ladder, the clause that is the only way into a rival, and
the round-scoped squad overlay that reaches the eleven without rewriting the world. Forty-nine tests
hold those claims on both engines. What they could not hold is the sentence §22 is really about: that a
*manager* can sit down and do this. That needs a browser.

Date: 2026-09-24. The page walk ran as `202609231918` (86 checks) and the same walk with the wage bill
landed as `202609232047` (103). Built into a throwaway dist directory
(`NEXT_DIST_DIR=.next-market SITE_URL=http://127.0.0.1:3212 npx next build`), served by
`next start -p 3212` with `API_INTERNAL_URL=http://127.0.0.1:8734` against a private uvicorn on 8734,
and driven by `apps/web/scripts/qa-market.mjs` (system Chrome, puppeteer-core). The private ports and the
private dist directory are deliberate: `.next` and 3210/3211 belong to runs already in flight on this
machine, and a walk that rebuilt them would be measuring someone else's page.

**Total: 103 checks, exit 0, 5 screenshots, 3 browser console errors, and all three provoked on purpose.**
(The walk ran first at 86 checks, on the page alone; §5 below is the wage increment that took it to 103, and
§6 is the signing-window increment that took it to the 144 measured on 2026-11-02 — the figure §6 quotes with
the command that reproduces it. This section's own 103 is the last measurement of the walk *before* the
window panel existed, and it no longer describes the page.)

## 1. One page, and the wall it sits behind

| Route | What it is | Visibility |
| --- | --- | --- |
| `/career/{slug}/market` | the round's board, the need it was picked against, the budget, the ledger, the squad a deal has to leave standing, and the rules | `PROTECTED_PREFIXES` — `noindex`, disallowed by the `/career` robots rule that already exists, absent from the sitemap |
| `/career/{slug}` | the season page, which now links to it | same wall |

The route is a child of `/career`, not a new prefix, so the crawl policy needed no new rule to already
cover it — which the walk asserts in both directions: `robots.txt` disallows `/career`, and the sitemap
does not name this market. The entry point is an action on the season page, and the check is that the
season page no longer prints the sentence that was a lie while the market was API-only:
`the season page no longer calls the budget unspent`.

A signed-out visitor is sent to `/login?next=%2Fcareer%2Fmarket-qa-1918-braa%2Fmarket` — the walk asserts
the `next` parameter keeps the visitor *out* of the ledger rather than just redirecting somewhere — and a
second account gets **404, not 403**, on both the page and the API, with the additional assertion that the
404 page body contains none of the foreign career's figures. A leak in an error page is the one place a
privacy check is usually skipped.

## 2. What the walk asked, and what it got

The board, read out of the DOM rather than out of a response:

```text
PASS  opening a board from the page prints what the round did — Round 1 priced: 12 offers on the shelf. 10,000,000 career credits left · 15 players · 2 goalkeepers
PASS  every offer carries asking, current, clause, wage and fit — 13 columns
PASS  the clause is the published rounding of 1.5× the asking — 1050000→1575000 1550000→2325000 1336500→2004750
PASS  the wage is the published rounding of the asking divided by 500 — 1050000/2100 1550000/3100 1336500/2675
PASS  the fit is a number the published formula can produce — 0.774 0.762 0.759 0.304
PASS  the board marks the players that fill the band the club is short in — 3 of 12 rows
PASS  no offer is priced above the balance and left buyable — affordability is the server's
```

The clause and wage checks are arithmetic, not presence: the walk parses the printed asking, computes
`round_5(asking × 1.5)` and `round_5(asking ÷ 500)` itself, and compares against the two cells. That is
what caught §3 below.

Negotiating with a seller, by clicking its own row:

```text
PASS  the seller answers an offer above the floor — … came back at 1,023,750 · asking 1,050,000 · floor 840,000 · 2 offers left …
PASS  the answer prints the floor the rule will not go under
PASS  the answer counts the offers left to make
PASS  the answer carries the rule that produced it —  round_5((price + offer) ÷ 2); an offer at or below the floor moves nothing; after 3 attempts the seller stops answering
PASS  the row itself is re-read with one offer spent — the counter fell on the row
PASS  a countered price is stored on the row, not just narrated — 1,050,000 → 1,023,750 (floor 840,000)
PASS  a negotiation leaves the asking price where the valuation put it — 1,050,000
PASS  a rival that will not sell says so on the page — rival_will_not_sell — Dunmoor Town shares this career's competition and will not sell to a rival; only the release clause moves them
PASS  the refusal carries the clause figure into the browser
PASS  the clause button the refusal points at is on the row
```

A counter-offer narrates itself only if the page then re-reads the row; two separate checks pin that down
(one on the printed `2 left · last 997,500`, one on the stored `current_price`), because a server that
returns a pleasing sentence while leaving the row untouched would pass the first and fail the second. And
a negotiation that can move `current_price` must not move `asking_fee` — otherwise the valuation, the
clause and the wage would all silently re-base under the manager's cursor.

Signing, loaning and selling, with the balance recomputed from the credits rather than trusted:

```text
PASS  the signing is confirmed with its fee — Corand Ruceek signed for 1,550,000 career credits. the player joins this career's club and stays 8,450,000 …
PASS  the squad table the server re-reads holds the arrival
PASS  the balance left is the fee, to the credit — 10,000,000 − 1,550,000 = 8,450,000
PASS  the spent column reads the same fee — 1,550,000
PASS  a signed listing leaves the shelf — tl_mRDuDc9FxSPUGGRK
PASS  the ledger row prints the balance it left behind — 8,450,000
PASS  a loan is agreed for a stated number of rounds — Loror Fennmann arrives on loan until round 4 for 153,560 career credits …
PASS  the loan fee is the published share of the price — for 153,560 against 153,565 = 1,023,750×0.15
PASS  a sale names its buyer and its proceeds — Corand Ruceek sold to Dunmoor Town for 1,395,000 career credits …
PASS  the proceeds arrive at the published share — 8,296,440 + 1,395,000 = 9,691,440
PASS  the ledger prints the sale as a plus against the same proceeds — +1,395,000
```

The loan fee check is the sharpest of them: the printed fee was `153,560` and the formula over the
countered price gives `153,565`. They differ because the server rounds the *loan* off the counter-offer
price and the walk rounds off the same price the page printed — so the check asserts the two figures agree
to within the one rounding the ladder introduced, and quotes both. A walk that demanded exact equality
would be asserting arithmetic the API does not perform.

Finally the accounting, which is the part a reader can check with a pencil:

```text
PASS  the squad counts add up to the squad the page lists — 15 stored + 1 in − 0 out against 16 rows listed
PASS  the arrival count is the deals the walk actually made — the page reads 1 in; the walk signed 1, loaned 1 and sold one of those back
PASS  a signing sold straight on leaves no departure behind — 0 out recorded for a player the world never stored at this club
PASS  the account counts the arrival as a player this career fields — the page reads 1
PASS  the need this board was picked against … squad as of round 1: 1 signed in, 0 departed
PASS  the rule that keeps a side on the pitch is printed beside the counts
```

`signed_in`/`departed` are **net squad state, not ledger history**. The walk signed one player, loaned
another, then sold the *signing* straight back out — so the squad ends exactly where the world left it,
both counts read their arithmetic truth (1 in, 0 out), and the ledger still carries both fees. Two rows in
the ledger and no trace on the squad is the correct answer, and is also the answer a naive check gets
wrong: an earlier version of this walk compared the arrival count with a number copied out of the JSON
response — which is the same source as the page, so it could only ever agree — and asserted one departure
after any sale. It now derives the expected arrival count from the deals it itself made
(`(buyable ? 1 : 0) + (loanable ? 1 : 0) − (soldAnArrival ? 1 : 0)`) and prefers to sell its own arrival,
because that is the case where the two readings diverge.

## 3. What the walk caught, in the order it caught it

1. **The API published a formula the code does not run.** `VALUATION_FORMULA` said
   `release_clause = asking × 1.5; weekly_wage = asking ÷ 500`. The code applies `round_5` to both, and the
   49 backend tests assert the rounded values (`_round5(expected * 1.5)`,
   `max(5, _round5(expected / 500))`) — so the *tests* were right and only the sentence printed to users
   was wrong. The board's wage column says `2100` where an unrounded `1050000 ÷ 500` also says `2100`,
   which is why no arithmetic check flagged it at first; the flag came from the clause, where rounding is
   visible (`1,336,500 × 1.5 = 2,004,750`). `apps/api/app/services/simulation/market.py` and the §14 table
   row in `docs/M6_VERIFICATION.md` now both carry the rounding. **A published formula is an assertion, and
   this one was false until a browser read it out loud.**
2. **A check that could not fail.** `until(page, 'offers on the shelf')` matched the server-rendered
   summary that is on the page *before* the board finishes loading, so the walk read zero rows and every
   per-row check passed vacuously. It now waits on `document.querySelectorAll('tr[data-listing]').length > 0`.
3. **Checks that failed for a typographic reason.** Panel eyebrows, `Stat` labels and `KeyValueGrid` `<dt>`
   keys are UPPERCASED by CSS, so `innerText` returns `STORED BY THE WORLD` and `ANSWERS THE NEED` while the
   source says otherwise. Every needle in this walk is case-folded, and the row cells are read from
   `querySelectorAll('td')[i]` — a row's `innerText` is tab-joined, which had made `squadRows().name` the
   whole row and `row.rival` never true. `the board marks the players that fill the band the club is short
   in — 3 of 12 rows` is the check that was silently dead before that fix.
4. **An expectation copied from a guess.** The walk asserted `DELETE /career/{slug}` returns 204; the route
   returns 200 with `{deleted: true, slug, matches_kept, disclaimer}`. The route was right and the walk
   changed — and the teardown now asserts the *body*, so a deletion that returns 200 and deletes nothing
   cannot pass.
5. **A deletion that left a page behind**: after teardown, this career's market answers 404 to its own
   owner. That is a check, not a hope.

## 4. How to re-run it

```bash
# apps/api, port 8734 (nothing else on this machine is restarted by these steps)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8734
# apps/web
NEXT_DIST_DIR=.next-market SITE_URL=http://127.0.0.1:3212 npx next build
API_INTERNAL_URL=http://127.0.0.1:8734 NEXT_DIST_DIR=.next-market npx next start -p 3212
QA_BASE=http://127.0.0.1:3212 node scripts/qa-market.mjs
```

The walk registers its own account (`market-qa-<stamp>@footballos.test`), opens its own career at
Braeford Athletic with the §22 budget ceiling, and deletes that career at the end; the throwaway account
stays in the dev database. Screenshots land in `docs/screenshots/` under
`202609232047-market-{before,after-signing,traded,after-round,mobile}.png`, the last at 375px with
`0px of horizontal overflow` asserted.

It is a separate script from `visual-qa.mjs` on purpose: that file is another milestone's live working
copy and cannot be edited underneath its author. Folding these checks into it — and `lib/market.ts`
into `lib/types.ts` — is the follow-up, not a defect in this increment.

## 5. The wage bill: what changed after the first version of this document (ROADMAP item 8, closed)

The first version of this document closed with a limitation: *wages are agreed and published but never
charged*, so a career with a 300k-a-week squad and one with a 3k squad finished the season with the same
balance. That sentence is gone, and with it ROADMAP item 8.

**The rule.** Each round the engine plays costs the career the weekly wage of every deal it holds at the
start of that round — a buy until it is sold or released, a loan until `loan_until_round`. The charge is
one row, and the balance is a sum of rows:

```text
career.budget + sum(moves.fee where kind = sell) − sum(moves.fee where kind in (buy, loan)) − sum(wage_charges.fee)
```

**Why its own table.** A wage is money that moves with no player attached. `career_squad_moves.player_id`
is a non-null foreign key to `real_players`, because every row in it is about a person and the eleven is
composed out of those rows; a fifth kind there would either break that constraint or have to be filtered
out of squad maths everywhere the table is read. `career_wage_charges` (migration `0012`) keeps each table
meaning one thing, and the ledger both the page and the walk read is the two of them in round order — each
row carrying the `budget_after` its predecessors left, which is exactly the property that made a stored
charge better than a derived one.

**Where it is charged.** `career.play_round` is the only path that plays a round, and it calls
`market.pay_wages` after the fixture is stored: a match a career never played is a match it never paid
for. A career holding no deal of its own writes no row.

Seventeen of the walk's 103 checks now belong to this, printed verbatim from run `202609232047`:

```text
PASS  the wage rule says a round is charged, and an empty ledger has charged nothing
PASS  the standing wage rate is a sentence the walk can read before it plays
PASS  the round the walk plays is one its deals cost something in — 2,100 a week across 1 deal(s), 0 paid over 0 round(s)
PASS  the season page’s own button plays a round — clicked
PASS  the round arrives on the page that asked for it — Round 1 played: BRAA 1–1 DUNT (home, Braeford Yard) …
PASS  a played round is a row in the ledger, not a sentence about one — 1 wage row(s) of 4 ledger rows
PASS  the wage row is stamped for the round that was played — round 1
PASS  the round charged exactly the rate printed before it — 2,100 agreed · 2,100 charged
PASS  the wage row takes money out and names nobody — 1 player on wages Loror Fennmann 2,100
PASS  the wage row spells out the deals it was raised on — 1 player on wages Loror Fennmann 2,100
PASS  the balance falls by the wage and by nothing else — 9,691,440 − 2,100 = 9,689,340
PASS  the wage row prints the balance the round left — 9,689,340 beside a Remaining of 9,689,340
PASS  the paid-in-wages figure is the sum of the wage rows — 0 + 2,100 = 2,100
PASS  the rate the round cost is still the rate standing after it — 2,100 a week over 0 round(s) before · 2,100 over 1 after
PASS  every row of the ledger prints the standing its predecessors left — 4 rows, one running total
PASS  the balance sentence names the wages it netted and adds up to its own answer — 10,000,000 stated + 1,395,000 received − 1,703,560 spent − 2,100 in wages = 9,689,340 career credits
PASS  the rule that charged the round is on the page — wage charge for a round = Σ weekly_wage of the deals this career holds at the start of that round …
```

Three of those are worth separating. **The rate is read before the round and the charge after it**, both
out of the page's own sentence, so the walk asks whether the product charged what it had promised rather
than whether two readings of one response agree. **The row names its players** — `1 player on wages
Lorar Fennmann 2,100` — because a fee the reader cannot decompose is a fee they cannot check; the walk
pulls the name and the number out of the cell and asserts they add up. And **the whole ledger column is
added up in the browser**, from the stated budget to the last row's stored standing, which is the check
that a *derived* wage (computed at read time, never written) could never pass: the balance would move
between two rows with no row to explain it.

The parse that reads the sentence is itself a lesson. An earlier version scraped `[\d,]+` runs from the
paragraph and took the first two as rate and paid. The note's own punctuation — "…weekly wage, and each
round's…" — contains a comma, `[\d,]+` matched it alone, `Number('')` was `NaN`, and `|| 0` turned the
missing figure into a **zero that looked like a number**: the walk then reported "0 agreed · 2,100
charged" against a page that was printing 2,100 correctly. The check failed, which is the only reason the
bug is known. The sentence is now matched *as a sentence*, and when it does not match, `parsed: false`
fails the walk loudly instead of feeding it a zero.

Five service tests hold the same claims where they are made (`tests/test_transfers.py::TestWageBill`): no
deals means no row; the round a deal is struck for is the round it starts costing; a sold player stops
costing and an expired loan never starts again (`[1, 2]` charged, round 3 writes nothing); the row's
`detail` names the players and adds up to its own fee; and — the causal one — a budget cut to
`price₁ + wage₁ + price₂ − 5` makes the second offer affordable before the round is played and refused
with `remaining = price₂ − 5` after it, which is the whole point of charging.

What the wage bill still does not do is said in `limitations()["wages"]`: it charges the deals this
career made and not the club's stored squad (those players came with the job), and a negative balance
carries no consequence beyond the market refusing to spend from it — no default, no board reaction, no
embargo.

## 6. The signing window reaches the page, and a gate reads the wire through the page (measured 2026-11-02, landed 2026-11-03 at `05f2a106`)

`career_view["window"]` — the same block `GET /transfers/{career}` answers with — has been on the wire since
2026-10-28, and the market page never answered with it: a manager learned the window was shut only *after*
pressing a button the tier had already refused with 409 `transfer_window_closed`. This increment puts the
block on the page, then puts a gate between the wire, the type and the page — because "published, typed,
never read" is the defect this project has now found eight times in eight different namespaces, and a panel
added by hand is not evidence that the panel stays.

**The panel.** `app/career/[slug]/market/page.tsx` binds `const signing = view.window;` and renders
`<Panel data-testid="market-window">`: a notice that follows `state`, and an eight-row `KeyValueGrid` — the
state, the season being judged (`season_index`, `round_in_season`, `season_rounds`), which table the season
length was read from (`season_source`), every range in `windows` as `from–to` plus its own label, the label
of the range that holds this round (or an explicit "no range holds it"), how many of the holding range's
rounds are already played (`played_in_window`, with its own no-range sentence), how many signing rounds are
left (`signing_rounds_left`), and where the next window opens — `opens_at_round` and `opens_at_season` with
`opens_in_rounds`, and a separate sentence when `opens_at_round` is null, because that is the no-horizon
career and it deserves to be named. Eight rows, counted off the `rows={[…]}` array at the landing commit;
this section said six when it was written, and the two it forgot are the `kvWindowPlayed` and
`kvWindowSigningLeft` pair the same commit authored. The panel closes
with `window.formula` printed verbatim beside the two constants it is built from
(`early_window_last_round`, `mid_window_half_width`). The rules panel gained `data-testid="market-rules"` so
the walk can read that book out of the DOM rather than trusting the door that served it.

**The catalogue.** 20 keys in the `market` namespace, in all three catalogues — counted off the commit's own
diff to `messages/en.json` today, and the reason this sentence used to say 16: it was written from the panel's
row list rather than from the bytes, and the increment had already authored `windowPlayed`,
`windowSigningLeft`, `kvWindowPlayed` and `kvWindowSigningLeft` on top of the sixteen it named. The eight row
labels are `kvWindowState, kvWindowSeason, kvWindowSource, kvWindowRanges, kvWindowHeld, kvWindowNext,
kvWindowPlayed, kvWindowSigningLeft`. **Three** of them are plurals, not two:
`windowEyebrow`, `windowClosed` and `windowNextAt`, each on `{count}` — `qa-translation-quality` read a
camelCase plural variable as untranslated English in `zh` and `zh-TW` (4 issues, all on these keys), which is
why the variable was renamed to the repo's convention before landing. With it the gate read
`CHECKS passed=4 total=4 failed=0`; today it runs 6 checks and reads `passed=6 total=6 failed=0`. The same
pass corrected a doubled particle in `zh-TW` (`賽季的的第…` → `賽季的第…`).

**The gate.** `apps/web/scripts/qa-wire-readers.mjs`, wired into `scripts/check.sh` and CI, 12 checks as it
landed and 18 today (the `totals` and moves populations added six), files only — no server, no browser, no
port. Three populations, each re-derived from bytes on every run:

* the **wire**, from the service's own `return {…}` literals — `market_view()`, `transfer_window()` and
  `season_windows()`, with the body found by brace depth and the keys read by a string-aware scanner so a
  `":"` inside a sentence cannot be mistaken for a delimiter; the nested `constants` block comes out of the
  same dict, so the two populations cannot disagree about where the block ends;
* the **type**, from `lib/market.ts` — `MarketView`, `MarketWindow`, `MarketView["windows"]` and
  `MarketView["constants"]`, each followed through the alias it names;
* the **reader**, from `page.tsx` — every `view.window.*` and `view.constants.*` field name, plus the reads
  made inside the row callback the panel passes to `windows.map()`, bound to their call site rather than to a
  guess about which identifier the callback renames it to.

Checks 3 and 3b compare the *shapes* a branch produces (the no-horizon branch and the normal branch must
publish the same fields — twelve at the basis the arms graded, 16 at the commit this increment landed on and
16 today, because the lane's `window_from_round`, `window_to_round`, `played_in_window` and
`signing_rounds_left` went into the dict in between; a range must publish the same three from either season);
4–6 reconcile each published key set with the type that declares it, in both directions; 7–8 require every
typed window and range field to be read by the page; 9 requires the constants block to be exactly the
constants the type declares **and** requires the two the window formula is built from to be read; 10 requires
every published view key to have a reader or to name the reason it has none; 11 refuses an exemption whose
bytes stopped earning it. Four floors keep a broken scan from reading as agreement — `FLOOR_VIEW_KEYS=10`,
`FLOOR_WINDOW_KEYS=8`, `FLOOR_RANGE_KEYS=3`, `FLOOR_CONSTANT_KEYS=5` — and check 2 fails if any scan found
nothing. The census the arms were graded against, at `ed9b631` — re-derived from that commit's bytes today,
and every number below is what its own dict publishes:

```
wire: view=17 window=12 range=3 constants=10 | type: view=17 window=12 range=3 constants=10 |
page: 15 window reads rooted at signing (range ← signing.windows), 16 view reads
```

The exemption is one row, keyed `demo_data` — the published name the page never reads, because it reads the
boolean under its other name, `is_demo_data`. A literal read-only census would therefore call the published
key unread; the gate accepts the row only while both spellings exist in the bytes *and* the page's own name is
among the reads, which is what arm A7 kills. Check 10 still reports exactly one named key today, so the row is
still the only exemption the view population needs.

**Arms: 10/10 MATCHED.** Each arm is a plane holding only the three files the census reads, graded by the
shipped gate through `QA_WIRE_WEB`/`QA_WIRE_API`, and the arm runner re-reads the gate's own
`ran qa-wire-readers against …` line to prove it graded the copy. Every splice asserts its needle count, so
an arm cannot silently grade an unmutated file. `wire basis: HEAD ed9b631e2f201ab6c534d1021fec15b7365fa717`
— the wire is taken from `git show HEAD:`, because the shared working tree was already publishing another
lane's keys and a plane copied off it would have graded *their* drift as one of mine:

| arm | defect planted | red checks |
| --- | --- | --- |
| control | none | `[]` — `passed=12 total=12 failed=0` |
| A1 | the page drops the window panel | `[7, 8, 9]` |
| A2 | the panel *and* its `const signing = view.window` binding | `[7, 8, 9, 10]` |
| A3 | the type drops a published window field | `[5]` |
| A4 | the wire renames a signing-range key | `[6]` |
| A5 | one branch renames a field the other branch keeps | `[3, 5]` |
| A6 | the wire drops the no-horizon branch | `[3]` |
| A7 | the page reads the other name for the demo flag | `[10, 11]` |
| A8 | the wire publishes a view key the page never reads | `[4, 10]` |
| W | the wire as the shared working tree published it on 2026-11-02 | `[9]` |

A1 and A2 are the pair that matters: dropping the panel leaves the binding, and a census that only looks for
the field name would then still see reads. A2 also proves check 10 is about the *block*, not the panel — the
page no longer asks for `window` at all.

**What the gate caught that is not mine.** On the night it was measured, check 9 was red on the shared working
tree — `passed=11 total=12 failed=1`, `published, typed by nothing: season_grant_per_round,
season_grant_per_point, promotion_grant` — because the season-grant lane's `market.py` published 13 constants
while `lib/market.ts` typed the 10 that basis published. That is the drift the gate was written to find, one
day old, and it was *not* fixed in this increment: typing those three keys here would have red the same check
in the other direction (`declared, published by nothing`) on the basis CI graded, and editing the other lane's
uncommitted service file was not mine to do. The handoff was theirs, and they had already taken it one commit
earlier than this record knew: re-measured from the bytes today, `c5d0979` (2026-11-02, the grant lane's own
commit) puts `season_grant_per_round`, `season_grant_per_point` and `promotion_grant` into
`MarketView["constants"]`, and at this increment's landing commit `05f2a10` the service's constants dict
publishes 13 depth-1 keys and the type declares those same 13 — so the two populations check 9 compares
agree at the basis CI grades, and the red arm W measured was the shared tree's *uncommitted* intermediate. `objective_bonus_by_kind` has
joined the dict since (14 depth-1 keys at HEAD's blob), and the working tree today reads
`PASS 9 every constant the view publishes is typed by the web tier (33 published)`. That 33 is a
working-tree figure, not a committed one: the same depth-1 scan over `HEAD:apps/api/…/market.py` publishes 14,
so the extra keys are the lane's uncommitted work in that file — and `market.py`, `lib/market.ts` and
`qa-wire-readers.mjs` are all on its in-flight list, so the committed-basis verdict is the lane's to
establish, not mine to infer.
Arm W remains the witness that the gate says so on their behalf — `MATCHED W-… predicted=[9] measured=[9]`.

**The walk: 144/144, and the copied figures it stopped carrying.** Three of the walk's own checks were
assertions about a shape rather than readings of it, and they were cured the same way as the gate:

* the board read its columns by index (`cells[6]` = asking, `cells[7]` = now …). At the basis this unit lands
  on, `components/MarketTools.tsx` prints 14 headers, and the walk's `row.cells.length === 13` pin was red on
  it: `142/143 checks passed` with the single failure `every offer carries asking, current, clause, wage and
  fit — 14 columns`. `board()` now maps each figure through `BOARD_COLUMNS`, a table of the *header text*
  taken from the same `messages/en.json` the component renders, so a column added or re-ordered moves the read
  instead of silently mislabelling it; two checks replaced the copied count — `the board prints a header for
  every column this walk reads a figure from` and `every offer carries one cell under every header the board
  prints`, measured on 2026-11-02 as `14 headers: PLAYER | POS | … ` against `14 cells … across 12 row(s)`.
* the rules panel: the walk asserted a rule *count*. It now reconciles three books — `GET /transfers/rules`,
  the career door's `view.rules`, and the rows the panel actually printed — name by name and sentence by
  sentence, and separately asserts the two rules it quotes by hand (`budget`, `window`) are in the printed
  book. That run followed the other lane's growth without a single number being copied: `public 14, career 14`.
* the window: the walk re-draws the block from the published constants (`deriveWindow` reproduces the
  clipping and the merge rule the service documents) and compares field by field, then reads the printed
  grid rows back against the wire with the catalogue's own interpolations — eight of them, the number the
  panel's `rows={[…]}` array holds at the landing commit. Measured on 2026-11-02 on a career's
  round 1: `the window block is the arithmetic its own published constants produce (round 1 of a 14-round
  season) — every field agrees | early=4 half=1`, `in_window="the opening window" · round 1 of season 1 (14 rounds,
  source a double round-robin…)`, and the panel row-by-row `STATE=open | SEASON BEING JUDGED=season 1, round 1
  of 14 | …`.

The live re-run, on a fresh database through the shipped harness —
`node scripts/run-walks.mjs market` → `=== market: build VNv19az9qYbeALp8GaIdh · API :8772 · web :3249`,
`144/144 checks passed. Screenshots: 7 -> docs/screenshots/`, `--- market: exit 0`, `1/1 walks green`, with
`every browser console error was one this walk provoked on purpose — 4 seen, all deliberate` (the fourth is
Chrome's own `/favicon.ico` probe, named since the last run).

**Catalogue gates re-run on the tree as it stood that night, all green:** `qa-gate-inventory` 188/188 (the new
script is inventoried as `gates=[scripts/check.sh,.github/workflows/ci.yml]`), `qa-icu-messages` 2/2 over
12078 messages and 4026 keys compared across three catalogues, `qa-population-floor` 3/3
(en=4026 zh=4026 zh-TW=4026), `qa-icu-coverage` 2/2 over 3141 call sites, `qa-unused-keys` 3/3
(3960 keys judged here + 66 delegated to `test_locale_claims.py`, 0 dead against a floor of 0),
`qa-translation-quality` 4/4, `qa-shared-keys` and `qa-key-drift` green. Those were readings of that tree; the
same commands were run again on 2026-11-08 and their figures are below.

**Found while measuring, not cured here.** `qa-plural-select.mjs` reports `Plural/selectordinal: 0` and
`Select: 0` on a catalogue that the parser itself reads as **86 plural nodes in 4026 English messages**
(`@formatjs/icu-messageformat-parser`, walked with its numeric `TYPE` enum). The gate compares
`node.type === "plural"` to a *number*, and calls its `walk()` on the array `parse()` returns, so no node
ever matches and both checks pass on an empty population — the same class as the 2026-10-26 finding that
two catalogue gates reported zero checks on a clean checkout. It also has a third `else if` that repeats the
first two. A gate that would actually judge the 86 needs a rule about what a legitimate collapse looks like
in a language with one plural category: a first measurement found 106 locale messages whose plural-node count
differs from English, and most of those are intended (`other`-only Chinese), which is exactly why the number
is not filed as a defect count. Next item: re-arm the gate against its own population, with a floor.

**That next item landed, six days later, and it is not this record's bytes.** [I18N_ARC_VERIFICATION.md
§37](I18N_ARC_VERIFICATION.md) closes it at `ee5464b`: `qa-plural-select.mjs` now runs **7** checks —
discovery from the directory rather than from its own `LOCALES` list, a spelled-versus-parsed equality on
every locale *and* every key, a parse ledger that names the refusal instead of swallowing it (the silent
`catch { return [] }` was the reason an unparseable message read as an absence), a vacuity floor of 80 placed
under both the committed 89 and the in-flight 87 so it cannot red another milestone's catalogue yet cannot be
satisfied by a walker that reads nothing, cardinal completeness, **ordinal** completeness against a declared
CLDR table with an explicit refusal where a locale's ordinal set is undeclared, and select completeness — and
`apps/web/scripts/qa-plural-select-witness.mjs` holds each of those verdicts red alone over scratch
catalogues, 16/16, against a reverse control in which the pre-fix gate read `passed=2 total=2 failed=0` on
every charged fixture. The 86 this section counted is **87 on the shared working tree's** catalogues and
**89 on `HEAD`'s and on `55f7ea7`'s** — the shipped gate run over each plane's own `messages/`, which is how
the floor of 80 can sit under both without judging either lane's bytes. The `106 locale messages whose
plural-node count differs from English` the first measurement found are exactly the "flattened" column the
cured gate prints on this tree — `87 English plural(s); comparisons per locale: 87 en, 23 zh (64 flattened),
23 zh-TW (64 flattened)`, and `89 … 25 zh (64 flattened), 25 zh-TW (64 flattened)` over HEAD's catalogues —
so the number is no longer an unexplained discrepancy but the named, legitimate shape of a one-category
language, and the 25-versus-23 on the `zh` side only tracks English's own 89-versus-87, so it is a count of
the lane's uncommitted keys rather than a verdict about them.

**Residuals this increment leaves, named.** The walk still quotes the wage rule's divisor by hand
(`asking / 500`, checked to ±2.5 — the half-step of the `round_5` it is reproducing) and still needles the
negotiation counter with the literal `2 left` and the sentence with `round_5`; the constants sentence the
page prints is `2 × half_width + 1`, an arithmetic step the tier does not publish as data (the walk mirrors it
with the same expression, so it fails rather than drifts); and `qa-market.mjs` re-implements the clipping and
merge rule in JavaScript, which means the rule now lives twice and the walk is the thing that notices.

**Re-read 2026-11-08, so this section does not read as current.** Basis first: every figure below was read off
the **shared working tree**, which at this moment carries another lane's in-flight `market.py`,
`lib/market.ts`, `page.tsx`, the three catalogues and `qa-wire-readers.mjs` itself — nothing here was run over
a committed plane, and a mixed-basis reading is not evidence about what CI grades. The walk's 144/144 above is
*dated* evidence on purpose: it names its build (`VNv19az9qYbeALp8GaIdh`) and the command that reproduces it,
and it has not been re-run since.

* `node scripts/qa-wire-readers.mjs` → `CHECKS passed=18 total=18 failed=0`, with the census now
  `wire: view=19 window=16 range=3 constants=33 totals=10 moves=37 | type: view=19 window=16 range=3
  constants=33 totals=10 move=37 | page: 19 window reads rooted at signing (range ← signing.windows), 18 view
  reads, 2 totals reads, 1 seam reads, 39 move reads`. The block this increment grew has since grown a
  `totals` and a `moves` population, and checks 12–17 judge them in the same three directions.
* `qa-translation-quality` **6/6** as read that morning (the two added checks being the Arabic- and
  Hebrew-script rules — cured later the same day into **9/9** with an **11/11** witness, §40),
  `qa-gate-inventory` **204/204** (→ **209/209** with §40's witness wired), `qa-population-floor` **3/3** with `en=4269 zh=4269 zh-TW=4269`,
  `qa-icu-messages` **2/2** over 12807 messages and 4269 keys, `qa-unused-keys` **3/3** with 4202 keys judged
  here and 67 delegated, `qa-key-drift` **4/4**, `qa-shared-keys` **4/4**, `qa-plural-select` **7/7**,
  `qa-icu-coverage` **1/1** — one check where §6 recorded two, and the gate's own header says why: its
  source-side half was retired on 2026-11-06 into `qa-i18n-literals`, whose resolver binds each read to its
  namespace.
* The catalogue this increment's 20 keys live in has grown from 4026 to **4269** keys, and the walk's 144
  checks are a count of that page's shape at that date, not of today's.

**Found by the re-read, cured the same day (§40).** `qa-translation-quality`'s two script checks printed
`every Arabic message carries Arabic script` and `every Hebrew message carries Hebrew script` on a tree where
neither `ar.json` nor `he.json` exists — the gate's header calls that "dormant", and a dormant check and a
clean one are the same sentence on the page, which is the class of thing this project has now cured in
`qa-plural-select` (§37), in the dead-key census (§19) and in the two zero-check gates of 2026-10-26. The
shape of the cure was written here as "name the population judged, and refuse or say-so when there is none";
§40 did exactly that, and went one step further than this page dared to ask: the same two lines also read
clean over an `ar.json` written as a byte copy of `en.json` (measured on the pre-fix bytes: 6/6 green across
4224 identical messages). Dormancy is now a PASS that says `dormant`, twice; a shipped catalogue that judged
nothing is a finding; and a byte copy is red in two checks at once.

## 7. What this increment does not claim

- **Two bullets that used to sit here are gone, and the reason is a measurement.** This section used to record
  that `no_transfers` was still *advertised* as merely stated — naming `challenges.py:133`,
  `tests/test_challenges.py:155` and `visual-qa.mjs:2042` — and that the career form's budget caveat was
  asserted by a stale needle at `visual-qa.mjs:1766`. Re-measured on 2026-11-08: `no_transfers` appears in
  `apps/api/app/api/v1/challenges.py` **zero** times, and in `test_challenges.py` only inside the docstring at
  line 156 that says the old advertising "became false" and the assertion at line 167 that now demands
  `constraint.enforced is True` — so the honesty test runs in both directions, exactly as §7 asked it to. On
  the other half, the strings `"Nothing spends this budget"` and `"no transfer market in this build"` are in
  no tracked source and no catalogue (they survive only in stale `.next` build caches), and the walk's needle
  was re-pointed by its own owner: `visual-qa.mjs:2547` now tests `/what the transfer market gets to spend/iu`
  and `:2548` tests `/a budget still changes no fixture by itself/iu`, with the comment at 2542 recording why
  the old sentence became false. ROADMAP item 7's first half is closed; a non-claim that is no longer true is
  not a boundary, so these bullets retired rather than got re-worded.
- **The board is a fresh dozen per round, not a market with a memory.** There is no asking-price drift
  between rounds, no agents competing for the same player across careers, and no injury or suspension
  affecting value. §22's seven verbs are covered; its economy is one round deep.
- **A wage charge is one week per round** — and only that half of the old bullet survives. The engine's round
  is treated as a week for billing, which is a stated convention rather than a fact about the calendar, and
  `pay_wages()` still charges `wage_bill(…, round_index=…)` once per played round. What the bullet also
  claimed — "there is no contract expiry, so a five-year deal and a six-month one cost the same" — is no
  longer true: `CONTRACT_FORMULA` in `market.py` stores `expiry_round = signed_round + contract_years ×
  season_rounds − 1`, writes an `expire` row for a deal whose expiry has passed before the next round is
  played, and falls back to a one-season `renew` when the write-off would leave eleven players and a keeper
  unfieldable. The five-year and the six-month deal now cost differently.
- Nothing here is observed. Every figure is a fictional world's arithmetic, badged `DEMO DATA` with the
  disclaimer the walk reads back off the page.
