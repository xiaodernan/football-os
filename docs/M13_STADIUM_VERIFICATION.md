# M13 Phase 9 item 37 - a stadium a manager buys

**Status: done 2026-11-05.** Item 33 made the gate respond to the career through a tier factor and a
form factor, but the ground itself was still the world's `teams.capacity`, shared by every career at
that club: a manager could win five rounds and sell more seats, yet could never *build* one. This item
turns the constant into a decision with a published price.

## The rule

* A purchase is **500-20,000 seats at 120 credits each**, one row in `career_stadium_works`. The row
  stores the seats, the unit price, the amount, the ground either side of it and the `budget_after` it
  produced, so the finance page can replay it against the running balance.
* The ground is `teams.capacity + sum(bought seats)`. The gate sells **the tier-factor capacity plus
  every bought seat**:

  ```
  gate_capacity = round(stored capacity x tier factor) + bought seats
  ```

  A career that has bought nothing reads exactly item 33's figure. Every bought seat is therefore one
  more seat the next home gate can sell, and a stand stays concrete rather than being multiplied by a
  later promotion; the club's own ground still scales with the tier, as before.
* The only path that spends on the ground is `market.buy_seats`, and it refuses with a registered code:
  `career_retired`, `challenge_budget` (a challenge's budget is an authored constraint, so it owns no
  ground), `bad_seats` (422), `no_club`, `insufficient_budget` (409, carrying the price and balance). A
  refusal writes no row.
* The purchase is a **ledger row of its own**, kind `stadium`, with no player. It shares the round's
  first timeline slot with squad moves and is ordered against them by the time it was written, then the
  gate, the wage charge, the boundary's grant and the cup money follow. `budget_position` subtracts
  `stadium_spent`, `market_view` merges the row into its ledger, and `career_view["stadium"]` publishes
  the ground, its history and what one more seat costs.

## The wire and the page

* `POST /api/v1/careers/{ident}/stadium` takes `{"seats": 500}` and answers `built: true`, the stored
  `work` row and the re-derived career view (so the balance, the timeline and the stadium block move
  together).
* `GET /api/v1/careers/{ident}` carries `stadium`; `GET /api/v1/transfers/{ident}` carries the same block
  plus `stadium` rows in `moves` and `totals.stadium_rows`.
* `CareerStadium.tsx` prints stored seats, bought seats, built capacity, gate capacity, the published
  price, the available balance, a seat count with a live cost preview and the purchase history. The
  finance panel gains its "Spent on the ground" row. `en`, `zh` and `zh-TW` carry the 37 new keys.

## Tests

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_stadium.py -q
# 4 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_career_api.py::TestStadiumWire -q
# 2 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py -q -k "budget or gate or timeline"
# 9 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_answer_census.py apps/api/tests/test_locale_claims.py -q
# 13 passed
```

The service cases pin the published price and the one-seat-to-one-seat gate increase, two purchases
accumulating to 1,500 seats after a played round with a zero-disagreement timeline, the market page's
stadium block and ledger row, and every refusal leaving the table empty. The wire cases pin the stored
work row, the balance and timeline on the response, the next read's gate capacity, the 422 for a stand
below 500, and the 404 an outsider gets.

`alembic check` is clean at `0054`; `ruff` is clean; `mypy app` reports no issues in 164 files; `tsc
--noEmit`, ESLint and the i18n gates are green (`qa-i18n-literals` 9/9 over 4,197 key calls,
`qa-unused-keys` 3/3, `qa-token-drift` 2/2, `qa-locale-tokens` 5/5 with 4,161 keys / 4,116 translated /
45 named tokens). The contract was regenerated from the tree to **221 paths / 283 operations**; the
currency gate reads `HEAD` by design, so it reds on this uncommitted checkout against the older blob
until the route and the contract are committed together.

## Live walk

`.scratch/walk-stadium.py` on the configured PostgreSQL database, at `0054`, Braeford Athletic (tier 2):

```
capacity before          53,002   (48,184 stored x1.10)
buy 500 + 1,000          +1,500
capacity after           54,502
works                    500 seats / 60,000 ; 1,000 seats / 120,000
round 1, home            attendance 38,725, gate 77,450
budget                   stadium_spent 180,000
                         remaining 897,450 = timeline closing 897,450
                         timeline disagreements 0 ; stadium rows 2
market view              bought 1,500 ; ledger stadium rows 2
```

The arithmetic is exact: `1,000,000 - 180,000 + 77,450 = 897,450`, and both stadium rows replay in the
timeline against their stored `budget_after`.

## What it still does not do

* Seats are bought for the world's club row, so two careers at the same club see the same stored
  capacity as their base; their *bought* seats are private to each career, which is the same rule item
  33 used for the tier factor.
* There is no construction time, capacity decay or maintenance cost: the stand is available to the next
  home gate as soon as the row is committed.
* A cup final still pays no gate because the competition takes it, and a challenge career still owns no
  ground at all.
