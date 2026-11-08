# M13 Phase 10 item 46 — season tickets

**Status:** done 2026-11-06. A season ticket is money now for seats later: before the first round a
manager sells a block of seats that covers every home league round at 85% of the walk-up price. The
seats are then in the ground every home round and are not charged again at the gate.

## The rule

- `unit_price = round(home_rounds × base_price × 85%)`, where `home_rounds = season rounds // 2` and
  `base_price` is the competition's authored price (3 in tier 1, 2 in tier 2) — the same constant the
  gate uses, so the two prices cannot drift.
- The block is **100–50% of the ground**, in steps of 100 seats; the cap is `capacity × 50%` rounded
  down to a whole block. Half the ground is the most that can be pre-sold, so walk-up demand still
  exists for the gate price to price.
- The money is written once, before the season's first round, as a row of its own. One row per season
  is a schema property (`uq_career_season_ticket_season`), so a second sale is refused rather than
  double-paid.
- A season-ticket seat is **not charged again**: the league gate's `paid_attendance` is
  `attendance − season_ticket_seats`, while the receipt stores both figures so the crowd and the
  charge can be read apart. A cup tie is not a league home round and passes zero season seats.
- A challenge career sells none (its budget is an authored constraint), a retired career sells none,
  and a club with no ground sells none.

## Data and API

- `careers.season_ticket_sales` relationship; `career_gate_receipts.season_ticket_seats` stores the
  seats a receipt did not charge. Migration `0057_career_season_tickets.py` adds the table
  `career_season_tickets` (career, season index and label, sale round, seats, home rounds, unit price,
  amount, capacity, basis, `budget_after`, provenance) and the receipt column.
- `BUDGET_FORMULA` adds `sum(season_tickets.amount)` on the income side; `budget_position` publishes
  `season_ticket_income`, `season_ticket_rows` and `season_ticket_detail`; `budget_timeline` places
  the sale at tier 0, before every round's gate, because the money arrived before the season.
- `market_view` merges the sale as ledger kind `season_tickets` with `season_index`;
  `affordability_view` carries the income; `career_view["season_tickets"]` is the offer.
- `GET /api/v1/careers/{ident}/season-tickets` reads the offer, the sale (or `null`), every sale row
  and the income. `POST` the same path with `{"seats": N}` sells one block and answers
  `{"sold": true, "sale": …, **career_view}`.
- Refusals: `bad_season_ticket_seats` (422, off-step or out of bounds), `season_ticket_window_closed`
  (409, the season has started), `season_tickets_already_sold` (409), `season_ticket_unavailable`
  (409, challenge/retired/no ground/too small), `challenge_budget` and `career_retired` (409).

## Web

`CareerSeasonTickets.tsx` prints the season, the sales window, the home rounds covered, the unit and
walk-up prices, the ground cap and the income; it sells the block the manager types and re-reads the
page. `CareerFinance` adds a season-ticket income row, the market ledger prints the sale and the gate
row names the seats that were not charged again. 24 keys per locale were added.

## Evidence

- **Service:** `apps/api/tests/test_season_tickets.py` — 7 cases: offer arithmetic, a sale that pays
  now and lands in the ledger/timeline, season seats filling the ground while only paid seats are
  charged, second sale, closed window, off-step/oversized blocks, challenge/retired refusals.
- **Wire:** `TestSeasonTicketsWire` in `apps/api/tests/test_career_api.py` — 2 cases: a block sold and
  read back through both routes and the career view; 422 + 409 + outsider 404.
- **Schema:** `alembic upgrade head` 0056 → 0057 and `alembic check` → *No new upgrade operations
  detected*.
- **Contracts:** `docs/api/openapi.json` regenerated from the tree — 223 paths / 287 operations.
- **Web gates:** `qa-wire-readers` 18/18 (constants 30, moves 35), `qa-i18n-literals` 9/9 (4,259
  calls), `qa-unused-keys` 3/3, `qa-key-drift` 4/4, `qa-token-drift` 2/2, `qa-locale-tokens` 5/5 at
  4,209 keys / 4,164 translated, `qa-locale-completeness` 2/2, `qa-icu-messages` 2/2; `tsc --noEmit`
  and `next lint` clean.

### Live walk

`.scratch/walk-season-tickets.py` on PostgreSQL, Braeford Athletic (48,184 seats, 7 home rounds):

| figure | value |
| --- | --- |
| offer | 7 home rounds · walk-up 14 · season 12 per seat · cap 24,000 |
| sale | 1,000 seats → 12,000 credits, stored `budget_after` 1,012,000 = the balance |
| first home round | 38,725 in the ground, 1,000 season seats, 37,725 paid |
| gate | 75,450 (= 37,725 × 2), the arithmetic the receipt stores |
| timeline | closing 1,075,404 = `budget_position.remaining`, 0 disagreements |
| ledger | `season_tickets` → `gate` → `upkeep` |
| after the start | offer closed, second sale refused `season_tickets_already_sold` |

## Traps recorded

- **Order of refusals.** `buy_season_tickets` checks `sold` before the window and the window before
  `available`, because `available` is false for an already-sold season too; checking it first would
  report a sold allocation as a closed window. `season_ticket_unavailable` therefore only answers for
  the reasons that are not a sale or a date.
- **The gate's paid seats.** `_gate_terms` now returns an eighth value, `season_seats`; every caller
  unpacks eight. `pay_gate_receipt` subtracts it before charging, while the stored `attendance` stays
  the full crowd — a receipt that stored only paid seats would understate the gate.
- **The sale round is the first round.** The ledger sorts the sale at the season's `first_round`, not
  at the round the manager happened to open the page on, because the money is paid before the season.
