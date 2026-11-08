# The gate has a price (M13 Phase 10 item 44)

`career_gate_receipts` has stored an attendance and a price since item 27, and item 33 made the crowd
respond to tier and form. The price itself was an authored constant: every tier-2 seat cost 2 credits
and every tier-1 seat 3, for every career, every round. A manager could buy more seats (item 37) but
could not decide what one cost. This unit makes the price the second thing a manager owns, and the first
that trades one figure against another.

## What is stored

- `careers.ticket_price_pct` — the manager's setting, 100 = the competition's own price. Migration
  `0055` adds it with a server default of 100, so a career opened before the column keeps item 33's
  gate exactly.
- `career_gate_receipts.price_pct` and `demand_pct` — copied onto the receipt when the gate is paid.
  A later change to the career's setting cannot rewrite a crowd already in the bank; the receipt is
  the row the balance counts.

## The curve

One pure function, `demand_pct_for`, is read by both the preview and the gate:

```
d = (price_pct − 100) / 100
demand_factor = max(0.20, 1 − 0.50·d − 0.50·d²)
attendance = min(effective_capacity, base × form_factor × demand_factor)
gate_receipt = round(attendance × ticket_price × price_pct / 100)
```

The setting moves in steps of five between 50% and 200%. The curve is downward-sloping and steepens
away from neutral: 120% draws 88% of the neutral crowd, 200% draws the floor of 20%. Revenue therefore
peaks around **120%** (index **106**), while a dearer seat still sells fewer — the trade the panel
prints rather than hides. The curve is authored from football's short-run demand, not fitted to a data
set; `what is not modeled` below says what that leaves out.

## Service and wire

- `market.ticket_price_view` publishes the setting, bounds, base price, demand, revenue index, the
  revenue-maximising setting and the formula. `career_view["tickets"]` and `market_view["tickets"]`
  both carry it; `RULES["ticket_price"]` states the arithmetic once.
- `market.set_ticket_price` validates the range and the step, then stores the setting. Refusals:
  `career_retired` (409), `challenge_budget` (409), `no_club` (404), `bad_ticket_price` (422, with
  `price_pct`, `min_pct`, `max_pct`, `step_pct`).
- `GET /api/v1/careers/{ident}/tickets` and `PUT /api/v1/careers/{ident}/tickets` expose the view and
  the decision. The OpenAPI contract moves to **222 paths / 285 operations**.
- `gate_row` publishes `price_pct` and `demand_pct`; the receipt's `basis` states both, and the ledger
  row the market page renders prints them beneath the detail.

## Web

`components/CareerTickets.tsx` is a panel on `/career/{slug}`: the current setting, the competition's
base price, the crowd and revenue indices, the best setting, a stepped input with a client-side
off-step warning, and the server's formula. Applying posts to the endpoint and re-reads the page, so
the finance panel and timeline below are the stored rows. The market page prints the same figures
beside the ground, and every gate row states the price and demand it was paid on.

## Evidence

**Directed tests.** `apps/api/tests/test_tickets.py` — 7 cases: the curve falls with price and names
120%/106; 80% fills more and 140% sells less; a neutral receipt is item 33's arithmetic exactly; a
120% receipt stores `price_pct = 120`, `demand_pct = 88` and pays
`round(attendance × base × 1.2)`; a later change to 150% leaves the paid receipt unchanged; 33/117/205
raise `bad_ticket_price` with the bounds; a challenge and a retired career are refused.
`TestTicketsWire` in `apps/api/tests/test_career_api.py` — 2 cases: PUT 120 returns 88/106 and the read
paths agree; 117 answers 422 `bad_ticket_price`, an outsider answers 404.

The directed regression over `test_tickets`, `test_transfers`, `test_transfers_api`, `test_career`,
`test_career_api`, `test_cup` and `test_affordability` passed. `alembic upgrade head` moved `0054` →
`0055` and `alembic check` answered **no new upgrade operations**. `ruff` clean; `mypy app` clean over
**164** files; `tsc --noEmit` and `npm run lint` clean.

**Web gates.** `qa-wire-readers` **18/18** (view 19, window 16, range 3, constants 26, totals 10,
moves 32); `qa-i18n-literals` **9/9** over 4,228 key calls; `qa-unused-keys` **3/3**;
`qa-token-drift` **2/2**; `qa-locale-tokens` **5/5** at **4,181 keys / 4,136 translated / 45 tokens**.
`test_locale_claims` and `test_answer_census` 13 passed.

**Live walk** (`.scratch/walk-tickets.py`, PostgreSQL `127.0.0.1:54321/football_os`, Braeford
Athletic, tier 2):

| Round | Price | Demand | Attendance | Gate |
| --- | --- | --- | --- | --- |
| 1 | 100% | 100% | 38,725 | 77,450 |
| 3 | 120% | 88% | 33,806 | 81,134 |

The dearer round sold **4,919 fewer seats** and earned **3,684 more**. The first receipt still read
100% / 77,450 after the career was moved to 150%; the timeline's closing balance equalled
`budget_position` at **1,158,584** with **0 disagreements**; the market ledger carried both gate rows
with their own `price_pct` / `demand_pct`. The current 150% setting indexes at **93** — the panel's
own best-setting line is what tells the manager the revenue peak is 120%, not 150%.

## What is not modeled

- The demand curve is authored, not estimated from attendance history. It responds to price, form and
  the ground, not to opponent, competition prestige, weather or kick-off time.
- One price applies to every seat: no concessions, hospitality tiers or season tickets. A season-ticket
  product that takes money up front and fixes part of the crowd for the year is the next natural unit.
- Changing the price affects future receipts only. There is no refund, no waiting list and no
  supporter-satisfaction consequence beyond the crowd itself.
- The crowd does not change the engine: a fuller ground does not raise home advantage, because the
  engine's `what_it_does_not_model` still names home advantage as unmodeled.
