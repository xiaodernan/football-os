# M13 Phase 7 item 27 — gate receipts

**Status: done 2026-11-02.** The ledger had three tables and one recurring income: the board's season
grant. A career still paid its wages out of savings and a home fixture earned nothing, even though the
world already stored how many people were at the ground. This item makes the home round pay.

## The rule

* One `career_gate_receipts` row per **home** round, unique on `(career_id, round_index)`. An away round
  writes no row: in this model the home club takes the gate.
* A career opened from a **challenge** writes no gate at all. A challenge's budget is an authored
  constraint printed when the run starts, and its window pays no season grant for the same reason: a
  gate would silently raise the figure the scenario stated. The exclusion is in `pay_gate_receipt` and
  pinned by a test.
* `attendance` is the world fixture's stored `stats.attendance` when the round is the generated fixture.
  A round played on the career's own rotation (after the world calendar runs out) sells
  `capacity × (62 + seed mod 38)%` of the home ground, the same 62–99% band the world builder uses.
* `ticket_price` is authored by competition tier: **3** for a tier-1 league, **2** for a tier-2 league
  or a cup (`tier = 0`). The amount is `attendance × ticket_price`.
* The row stores `basis` in words, the `budget_after` it produced, and its own units. A home ground with
  no capacity, or an attendance of zero, writes no row rather than a zero one.
* The receipt is written in `play_round` **after** the fixture is stored and **before** the wage charge,
  so the wage row's stored `budget_after` includes the gate the same round earned. That is the order
  the timeline reads: moves → gate → wage → boundary grant.

The formula is public in `RULES["gate"]`, and the four constants are published in the market view's
`constants` block.

## What a reader sees

* `budget_position` gains `received_sales`, `received_gate`, `gate_rows` and `gate_detail`. `received`
  is now every cent that arrived (sales + gates), and `BUDGET_FORMULA` spells the extra term out.
* `budget_timeline` gains a `gate` entry with a `+amount` delta, ranked between a round's moves and its
  wage charge; every stored `budget_after` is still compared with the running total.
* `market_view` puts the gate on the one ledger (`kind = "gate"`, `cash = "in"`, attendance and ticket
  price beside the amount), and `totals.gate_rows` counts it.
* `affordability_view` publishes `received_gate`, `gate_rows` and `gate_detail`; `CareerFinance.tsx`
  prints "Gate receipts so far" when the career has earned one.
* The market ledger's contract column treats a gate like a wage or a grant — an em-dash, not "0 years".

## Tests

`tests/test_transfers.py::TestGateReceipts` (5 cases): only home rounds earn a gate and each one is its
own row; the rotation attendance is `capacity × the seeded share`; an away round writes nothing; a
tier-1 home round charges 3 per seat; a challenge window pays nothing and its stated budget stays put.
`tests/test_transfers_api.py::TestGateReceiptsWire` reads the
same gate on both doors — the market ledger and the career's finance timeline — and checks the row's
own `fee == attendance × ticket_price`.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_career.py apps/api/tests/test_transfers.py apps/api/tests/test_transfers_api.py -q
# 164 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_affordability.py -q
# 9 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_openapi_contract_currency.py -q
# 4 passed, after scripts/export_openapi.py regenerated the contract for the new routes
```

`ruff` clean; `mypy app` clean over 161 files; `tsc --noEmit` clean; `next lint` clean;
`qa-i18n-literals` 9/9 over 4,110 calls; `qa-unused-keys` 3/3; `qa-token-drift` 2/2;
`qa-wire-readers` 12/12 with 17 constants (the four gate constants are typed and the market page reads
the tier comparison). `alembic check` clean after `0049 → 0050`.

## Live walk

`.scratch/walk-gate-receipt.py` on a fresh `alembic upgrade head` SQLite database, playing two rounds
of the weakest club's career:

```
{
  "career": "gate-walk-braa",
  "club": "Braeford Athletic",
  "capacity": 48184,
  "rounds": [
    {"round": 1, "side": "home", "venue": "Braeford Yard", "attendance": 38725, "ticket_price": 2, "amount": 77450},
    {"round": 2, "side": "away", "venue": "Ostdera Ridge", "attendance": 0, "ticket_price": 0, "amount": 0}
  ],
  "gate_rows_on_ledger": 1,
  "received_gate": 77450,
  "received_sales": 0,
  "remaining": 1077450,
  "opening_budget": 1000000,
  "timeline_kinds": ["gate"],
  "timeline_disagreements": 0,
  "timeline_closing": 1077450
}
VERDICT PASS
```

## Economy note

The gate is sized to be recurring income, not a windfall: a second-tier home round at this club's
ground pays 77,450, and a 14-round season with seven home games pays roughly 542,000 before wages. The
authored top-flight price of 3 raises the same ground's gate by half. The numbers are published so a
later balance pass can move one constant rather than reverse-engineer a formula.

## What is still open

* No production-build browser pass yet for the new finance row and the gate ledger row.
* Away clubs earn nothing, and no cup prize money or broadcast money exists.
* Capacity never grows; a stadium upgrade and attendance response to results are not modelled.
* Gate money is paid even when the match is a heavy defeat; attendance is the world's stored figure and
  does not react to form.
