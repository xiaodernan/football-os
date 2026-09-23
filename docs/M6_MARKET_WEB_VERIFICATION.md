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
(The walk ran first at 86 checks, on the page alone; §5 below is the wage increment that took it to 103.)

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

## 6. What this increment does not claim

- **`no_transfers` now binds but is still advertised as merely stated.** `transferable()` refuses every
  move for a career whose scenario carries the rule and says `enforced: true` in the refusal;
  `challenges.py:133`, `tests/test_challenges.py:155` and `visual-qa.mjs:2042` still say otherwise and
  have to move together. ROADMAP item 7.
- **The career form's budget caveat moved, and one gate has not caught up.** The form used to print
  "Nothing spends this budget yet — there is no transfer market in this build". That sentence became
  false when §22 landed and `components/CareerForm.tsx` now states what the budget does. `visual-qa.mjs`
  asserts the old wording at line 1766; its owner has to re-point that needle, which this run did not do
  from under them.
- **The board is a fresh dozen per round, not a market with a memory.** There is no asking-price drift
  between rounds, no agents competing for the same player across careers, and no injury or suspension
  affecting value. §22's seven verbs are covered; its economy is one round deep.
- **A wage charge is one week per round.** The engine's round is treated as a week for billing, which is
  a stated convention rather than a fact about the calendar; there is no contract expiry, so a five-year
  deal and a six-month one cost the same until the player is sold or released.
- Nothing here is observed. Every figure is a fictional world's arithmetic, badged `DEMO DATA` with the
  disclaimer the walk reads back off the page.
