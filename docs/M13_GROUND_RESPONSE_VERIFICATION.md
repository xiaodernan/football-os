# M13 Phase 8 item 33 - a ground that responds

**Status: done 2026-11-03.** Item 27 gave a home round a gate, but the gate read two constants a career
could never change: the world's stored capacity and the stored attendance. A promoted club sold the same
seats as a second-tier one, and a five-match winning run sold exactly what a five-match losing run sold.
This item makes the gate a consequence of the career.

## The rule

* `gate_capacity(club, tier)` returns an **effective** capacity and the factor it applied:
  `stored capacity x 1.25` in tier 1, `x 1.10` in tier 2, `x 1.00` otherwise. The shared `teams.capacity`
  row is never written: two careers can run in one world, and one manager's promotion is not the other's
  stadium. The factor is published with the figure that used it.
* `gate_form(session, career, before_round)` reads the career's own last five results before the round
  (W = 1, D = 0.5, L = 0), newest first, and publishes `played`, `form`, `results` and
  `factor = 0.90 + 0.20 x form`. No history reads as form 0.5 (factor 1.00) rather than as an empty ground:
  a career is not punished for a match it has not played.
* `attendance = min(effective_capacity, base x form_factor)` where `base` is the world fixture's stored
  attendance when the round is the generated fixture, or `effective_capacity x (62 + seed mod 38)%` on the
  career's own rotation. The cap is the effective capacity, so a hot run cannot sell seats that do not exist.
* `ticket_price` is unchanged (3 for tier 1, 2 for tier 2 or a cup), so the amount is still
  `attendance x ticket_price`, and `basis` now names the tier factor and the form window it used:
  `... (80% of the 53,002-seat Braeford Yard (tier 2 capacity x1.10); form 1.00 over 5 round(s) x 1.10)`.
* `GATE_FORMULA` publishes every constant and the two new steps; the three constants
  (`GATE_TIER_CAPACITY`, `GATE_FORM_WINDOW`, `GATE_FORM_SHARE`) are module-level so a balance pass moves
  one number.

## What a reader sees

* A receipt's `attendance` is the figure after both factors, and its `basis` says which factor did what.
  A reader adding the seats up against the stadium's stored capacity sees the effective cap named in words.
* Nothing else changes shape: the ledger row, `received_gate`, `gate_rows`, the timeline entry and the
  `kind = "gate"` market row are the ones item 27 shipped.

## Tests

`tests/test_transfers.py::TestGateReceipts` grows two cases (7 in the class):

* `test_a_winning_run_fills_more_of_the_ground_than_a_losing_one` - the same career, the same round seed,
  the same ground: five wins read 46,641 seats and five losses 38,161, and each basis prints its own form
  figure.
* `test_a_top_flight_ground_sells_more_seats_than_its_stored_capacity` - a tier-1 career's effective
  capacity is 1.25x the stored row while the row itself is untouched.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py -q -k GateReceipts
# 7 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_career.py apps/api/tests/test_transfers_api.py apps/api/tests/test_ageing.py apps/api/tests/test_affordability.py -q
# 187 passed
```

`ruff` clean; `mypy app` clean over 163 files; `tsc --noEmit` clean; `next lint` clean. No migration: this
item reads rows the world already stores.

## Live walk

`.scratch/walk-gate-form.py` on the configured Postgres database, two careers at the same club, the same
round seed and the same home ground, one with five wins behind it and one with five losses:

```
{
  "club": "Braeford Athletic",
  "stored_capacity": 48184,
  "tier_two_capacity": 53002,
  "tier_one_capacity": 60230,
  "winning": {"outcome": "W", "attendance": 46641, "amount": 93282,
              "basis": "... (80% of the 53,002-seat Braeford Yard (tier 2 capacity x1.10); form 1.00 over 5 round(s) x 1.10)"},
  "losing":  {"outcome": "L", "attendance": 38161, "amount": 76322,
              "basis": "... (80% of the 53,002-seat Braeford Yard (tier 2 capacity x1.10); form 0.00 over 5 round(s) x 0.90)"}
}
VERDICT PASS
```

The two careers differ by 8,480 seats and 16,960 credits on the same fixture, which is the whole claim:
form and tier are now money.

## What is still open

* Capacity grows with the tier *factor*, not with a stadium upgrade a manager buys; there is no building
  project, no ticket price a manager sets, and no away support.
* Form is the career's own last five results in any competition; cup ties (item 32) do not count until
  they are recorded as fixtures.
* The world's stored attendance still sets the base for a generated fixture, so a world that drew a quiet
  crowd can only be lifted by 10% of the form share.
* No production-build browser pass yet; the figure is visible only through the finance timeline's basis
  string, which the walk prints.
