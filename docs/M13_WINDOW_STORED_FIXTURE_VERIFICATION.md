# M13 Phase 8 item 30 — a window measured against stored fixtures

**Status: done 2026-11-03.** The signing window was policed entirely from `career.rounds_played`. That is
usually the same number as the stored fixture list, because `play_round` writes both in one transaction
— but an imported or repaired career can hold a fixture whose round the counter has not reached, and
nothing refused a squad move booked into that round. This item makes the stored rows the fact the window
reads.

## The rule

* **A move cannot be booked into a round that has a fixture.** `transferable` computes the round the move
  would use (`rounds_played + 1`) and refuses with `round_already_played`, `constraint =
  "stored_fixture"`, the `round`, the stored-row count and `latest_stored_round`. Every move
  (`buy`, `loan`, `sell`, `release`, `renew`, `negotiate`) and `open_market` answer through this verdict,
  so the refusal cannot be bypassed by one endpoint.
* **The window counts stored rounds.** `transfer_window` reads `career_fixtures.round_index` and counts
  the rows inside the current window's lifetime range. `played_in_window` is the larger of that count and
  the counter's own count, so neither a lagging counter nor an imported row can hide a round.
  `signing_rounds_left` subtracts stored fixtures at or after the next round: a round that already has a
  fixture is not a signing round.
* **The career view reuses its fixture list.** `_window` hands the rows `career_view` already fetched to
  `transfer_window`, so the new measurement adds no second read of `career_fixtures` on the page (the
  read-efficiency test still holds). API endpoints that ask the window on its own read the table once.
* **The formula says so.** `WINDOW_FORMULA` now names stored rows as the fact that decides, not the
  calendar alone.

## Tests

`tests/test_transfers.py::TestTransferWindow` gains 2 cases: a fixture stored at round 1 refuses
`transferable`, `open_market`'s verdict and a `buy`, and the same career signs once the fixture is
removed; two stored rows with a zero counter make `played_in_window = 2` and `signing_rounds_left = 2`
(the first window is rounds 1–4), which the old counter-only arithmetic would have reported as 0 and 4.

The existing query-count and fixture-read-once tests in `test_career.py` still pass: the career view
does not read `career_fixtures` twice.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py -q -k TestTransferWindow
# 11 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_career.py apps/api/tests/test_transfers_api.py apps/api/tests/test_ageing.py -q
# 173 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_openapi_contract_currency.py -q
# 4 passed
```

ruff, mypy (163 files), tsc, ESLint and the four i18n/wire gates are green.

## The live walk

`.scratch/walk-window.py` played round 1, then rewound `career.rounds_played` to 0 — a counter that
lags a stored fixture. `transferable` answered `round_already_played` for round **1** with
`latest_stored_round = 1`; the window reported `played_in_window = 1` and `signing_rounds_left = 3`
(rounds 2–4), where the old counter-only read would have said 0 and 4. Restoring the counter made the
same career transferable again.

```
"refusal_code": "round_already_played",
"window_played_in_window": 1,
"window_signing_rounds_left": 3,
"restored_ok": true,
VERDICT PASS
```

## Open

* `play_round` still does not refuse when a fixture already exists at its planned round; the stored-row
  defect that creates this state is imported data, and a duplicate fixture would need its own guard.
* The refusal is evaluated against the next round only. A stored fixture far ahead does not block a move
  now, because the move is not booked into it.
* No production-build browser pass; the change is in the API's verdict and window arithmetic, and the
  wire shape is unchanged.
