# M13 Phase 9 item 34 - a cup tie earns a gate and leaves minutes

**Status: done 2026-11-03.** Item 32 made the cup a run a career plays, but the tie ended at the score:
the ground was a string in the row, the gate was never paid, and the eleven that played it left no trace,
so a cup minute did not tire a player or develop him. Both tables keyed their rows by the *league round*,
and a tie played after round 7 shares round 7 - the one-gate-per-round and one-trace-per-player-per-round
uniques refused it outright. This item gives the tie its own key and pays what it earns.

## The rule

* `career_gate_receipts.tie_id` and `career_appearances.tie_id` are nullable: NULL is a league round, a
  value is that cup tie. The league uniques become partial indexes over `tie_id IS NULL`, and two new
  unique indexes name the tie (`uq_career_gate_tie`, `uq_career_appearance_tie_player`). A league round
  still has exactly one gate and one trace per player; a cup tie has one of each of its own, and can share
  a round index with the league round it followed.
* `pay_cup_gate(tie)` pays only a **home** tie, and never a **final**: the neutral venue's gate is the
  competition's. The crowd is built from capacity rather than the world's stored attendance, because the
  bracket row a later tie replaces was played by other clubs - its crowd is not this tie's. Everything
  else is the same arithmetic as a league gate: `effective capacity`, `62 + seed mod 38` percent of it,
  the stored form factor, capped at the effective capacity, times the competition's ticket price.
* The form window for a tie is `before_round = tie.round_index + 1`: the tie is played *after* the round
  its index names, so that round's result is part of the form the crowd responds to (`form 1.00 over 1
  round(s) x 1.10` in the walk below). A league gate is still taken before the round it names.
* `_trace_tie` rebuilds the eleven from the same rows the engine played with, checks it against the match
  report exactly as `_trace_round` does, and writes `career_appearances` with `tie_id` set. Those minutes
  reach `carry_over` (condition) and `development_view` (the curve) because both sum the appearance table;
  no `career_developments` row is written for a tie, because that table is keyed by league round and the
  tie's minutes reach the curve at the next round's write, in the cumulative total.
* A cup gate and a cup prize are written after the round they follow, so the timeline sorts them at tier 4
  - after that round's grant - instead of sharing the league gate's slot. `ledger_of` and
  `budget_timeline` share `_ledger_tier`, so the market page and the account page cannot order them
  differently. The gate is written before the prize, so the prize's stored `budget_after` includes it.

## What a reader sees

* A played tie carries `gate` (`amount`, `units`, `attendance`, `ticket_price`, `budget_after`, `basis`)
  or `null` for an away tie and a final; the run carries `gates: {total, rows}`, and
  `career_view["cup"]["totals"]["gates"]` adds the runs up.
* `budget_position` grows `received_gate_cup` and `gate_cup_rows` beside the unchanged `received_gate`
  total, and `gate_detail` names a cup row `cup tie after round N` so two rows at one round index are
  legible.
* The market ledger's cup gate row is `kind = "cup_gate"` with the label `cup gate receipts, N seats`, and
  the career's carry-over grows `cup_appearances` (and marks each trace row `competition = "cup"`).
  `rounds_traced` counts league rounds only - a tie is not a round.
* The cup panel prints a gate column on the tie table, a gate total beside the prize total, and a note
  that a home tie pays a gate while the final's belongs to the competition (four keys, three locales).

## Tests

`apps/api/tests/test_cup.py::TestCupGateAndMinutes` (3 cases; the file is 16) proves:

* a home tie after a played league round pays one receipt whose `tie_id` is the tie, whose amount is
  `attendance x ticket_price`, and whose trace is eleven players at 90 minutes under the tie - while the
  league round's eleven rows are untouched, which is the collision the old uniques refused;
* the run, `budget_position` and the timeline agree with that receipt (`received_gate_cup`,
  `gate_cup_rows`, a `cup_gate` timeline row, `disagreements == 0`), and `carry_over` reports
  `cup_appearances == 11` with `rounds_traced` still 1;
* an away tie and a final each pay no gate, and a hand-written second receipt for the same tie is refused
  by the unique index.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cup.py -q
# 16 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cup.py apps/api/tests/test_career.py apps/api/tests/test_transfers.py -q
# 163 passed
```

`alembic upgrade head` moved `0051 -> 0052` and `alembic check` is clean; ruff clean; `mypy app` clean
over 164 files; `tsc --noEmit` clean; `next lint` clean; `qa-i18n-literals` 9/9 over 4,154 calls;
`qa-unused-keys` 3/3; `qa-token-drift` 2/2; `qa-wire-readers` 12/12; `qa-locale-tokens` 5/5 with
`4119` keys and `4074` translated in each Chinese catalogue.

## Live walk

`.scratch/walk-cup-gate.py` on the configured Postgres database at `0052`, Corgard Town in the Haldhurst
Invitation Cup, one league round played first so the tie and the round share an index:

* the quarter-final was at home and lost 0-1; the receipt is **64,624 seats x 2 = 129,248**, from
  `92% of the 64,624-seat Corgard Field (tier 2 capacity x1.10); form 1.00 over 1 round(s) x 1.10` -
  the form factor wanted 65,399 seats and the effective capacity capped it;
* `new_gate_rows = 1`, `league_appearances = 11`, `cup_appearances = 11`, `cup_minutes = [90]`;
* `carry_over`: `rounds_traced = 1`, `cup_appearances = 11`, `appearances = 22`, `carrying_load = 11`;
* balance `1,115,030 -> 1,244,278`, a delta of exactly the run's `gates.total + prizes.total`
  (129,248 + 0); `rounds_played` still 1; timeline kinds `["gate", "cup_gate"]`,
  `timeline_disagreements = 0`, closing balance equals `budget_position.remaining`.

## What it still does not do

* A final pays no gate to either club; the competition keeps it. That is a stated rule, not a computed
  split.
* A cup tie writes no `career_developments` row of its own. Its minutes are in the appearance table and
  therefore in every later projection, but the round-by-round development row for that night does not
  exist.
* A transfer made after a league round and before the cup tie played after it sits at round `r + 1` in the
  timeline while the tie sits at round `r`, so the stored `budget_after` chain can count a disagreement
  in that narrow sequence. The tie's own rows are internally ordered and the walk exercises the normal
  sequence.
