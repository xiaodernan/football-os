# The ground costs money to run (M13 Phase 10 item 45)

Item 37 let a manager buy seats and item 44 let the manager price them. A stand was still free to
operate: the only cost of building was the once-off 120 credits a seat, which a full tier-2 house
repays in sixty home rounds — so the rational move was always to build. This unit adds the other half
of the trade: every home round pays for the seats it opens.

## The rate

```
upkeep = round(capacity × 25 / 100)
```

`capacity` is the physical ground — the club's stored seats plus every bought one — not the
tier-adjusted figure the gate sells, because the cost is the stand, not the league's permission to
sell it. A 48,184-seat ground costs **12,046** a home round; 500 more seats raise it by **125**. At a
tier-2 price a full house earns two credits a seat, so even a full ground nets 1.75 a seat; the rate is
deliberately below the cheapest ticket, which keeps a full ground profitable and makes an empty one a
real loss rather than a rounding error.

Only a home league round and a home cup tie pay. An away round, a neutral-venue final and a challenge
career pay nothing — the challenge's scenario already pays no gate, so charging it upkeep would change
the authored budget the run starts with.

## Storage and wire

- `career_upkeep_charges` (migration `0056`) stores one row per home round: the round and fixture (or
  tie), the capacity, the `seat_rate_pct` (25), the amount, the basis, and the `budget_after` it
  produced. Partial uniques keep one league row per round and one row per cup tie, beside the gate's
  own keys.
- `BUDGET_FORMULA` subtracts `sum(upkeep_charges.amount)`; `budget_position` publishes `upkeep_spent`,
  `upkeep_rows` and `upkeep_detail`; `budget_timeline` places the row immediately after its gate and
  before the round's wage charge, ordered by write time inside the same tier. A cup tie's upkeep sits
  in the cup tier after its gate and before its prize.
- `stadium_view` publishes `upkeep_per_seat_pct`, `upkeep_per_home_round` at the current ground,
  `upkeep_spent` and `upkeep_rows`; `RULES["upkeep"]` states the formula; the market constants carry
  the rate; `market_view` merges the rows into the ledger as kind `upkeep` / `cup_upkeep`, with
  `capacity` and `seat_rate_pct` on the row.
- `CareerFinance` prints the running total, `CareerStadium` prints the per-round rate and what has
  been paid, and the market page prints the rate beside the ground.

## Evidence

**Directed tests.** `apps/api/tests/test_upkeep.py` — 5 cases: a home round writes one row at
`round(capacity × 25%)`, its `budget_after` is the gate's less the cost, the balance and timeline
agree, and the timeline orders gate before upkeep; an away round writes none; a challenge career
writes none; buying 500 seats raises the rate by 125; the market ledger carries the row with its
capacity and rate. `test_cup.py` now asserts the home tie's `cup_upkeep` row and its place in the
timeline. The directed regression over `test_upkeep`, `test_stadium`, `test_tickets`, `test_transfers`,
`test_transfers_api`, `test_career`, `test_career_api`, `test_cup` and `test_affordability` passed.

`alembic upgrade head` moved `0055` → `0056` and `alembic check` answered **no new upgrade
operations**. `ruff` clean; `mypy app` clean over **164** files; `tsc --noEmit` and `npm run lint`
clean. Web gates: `qa-wire-readers` **18/18** (moves 34, 14 named), `qa-i18n-literals` **9/9** over
4,234 key calls, `qa-unused-keys` **3/3**, `qa-token-drift` **2/2**, `qa-locale-tokens` **5/5** at
**4,185 keys / 4,140 translated / 45 tokens**.

**Live walk** (`.scratch/walk-upkeep.py`, PostgreSQL `127.0.0.1:54321/football_os`, Braeford
Athletic, tier 2):

| Round | Capacity | Gate | Upkeep | Net |
| --- | --- | --- | --- | --- |
| 1 | 48,184 | 77,450 | 12,046 | 65,404 |
| 3 (after +500 seats) | 48,684 | 76,832 | 12,171 | 64,661 |

The first row stayed at 12,046 after the ground grew; the second cost exactly 125 more; the two rows
summed to 24,217 and the timeline closed at **1,070,065** against the same `budget_position` with
**0 disagreements**. The ledger read `gate, upkeep, stadium, gate, upkeep` — the order the money was
actually written in.

## What is not modeled

- The rate is one authored fraction of capacity, not an itemised bill: no stewards, utilities, pitch
  maintenance or staff, and no difference between an old stand and a new one.
- Cost does not rise with the crowd on the day, only with the seats opened. A 20% full ground and a
  full house cost the same to run, which is the intended pressure but not a full stadium P&L.
- There is no deferred maintenance or capital project: a stand never ages, closes or needs replacing.
- A cup final at a neutral venue pays no upkeep, matching the rule that it pays no gate; the neutral
  venue's own costs are outside the career's books.
