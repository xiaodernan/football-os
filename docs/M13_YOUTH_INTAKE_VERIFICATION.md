# M13 Phase 8 item 29 — a boundary youth intake

**Status: done 2026-11-03.** Item 28 made a long career shrink: every boundary could retire a player and
nothing replaced him. This item adds the other half — at the same boundary, the club promotes young
world players into the squad on free contracts, chosen by the academy's own ranks. No player row is
invented: the intake reads `real_players` and writes career moves.

## The rule

* **Who is eligible.** A candidate is a world player at or under **21 on the career's clock**
  (`effective_age = stored age + closed seasons`), outside this career's current squad. The pool is
  sorted by the band a retiree vacated first, then overall, potential and slug, and the first 80 are
  judged.
* **The academy decides.** `academy.judge_candidates` appends the pool to the club's squad and runs the
  same `academy_class` the academy page uses, against the same eleven and band seats. Only a candidate
  whose verdict is `selected` or `next_in_line` can be signed; `off_the_pace` is refused. The verdict
  and band rank are printed in the result.
* **How many.** At most one per retiree, capped at `MAX_YOUTH_INTAKE = 4`. A boundary with no
  retirement signs nobody, and a challenge career (one season, no later boundary) signs nobody.
* **The contract.** Fee **0**; the wage and contract years come from `valuation` at the career-clock
  age, and `expiry_round = round_index + contract_years × season_rounds − 1` is stored on the row.
  The row is `kind = "youth"`, which `IN_KINDS`, `expire_contracts`, the contract book's renewal quote
  and `renew()` all treat as a permanent deal.
* **The wage ceiling still binds.** A promotion whose wage would push the bill past the board's ceiling
  is skipped and named in `skipped`; the intake does not silently break the rule the market enforces.

## What a reader sees

* The contract book lists a `youth` row with its stored expiry and the same renewal quote as a
  signing, labelled `contractsKindYouth` ("youth intake") in all three catalogues.
* The market ledger shows the promotion as an incoming move with `fee = 0`; the wage row that follows
  charges it.
* `close_season` runs retirement then intake in the same transaction, so a boundary either has both
  halves or neither.

## Tests

`tests/test_ageing.py` (6 cases) now covers the intake: a retirement is replaced by a `youth` row with a
stored expiry and the bill moves by the retiree's wage minus the intake's; a boundary with no
retirement signs nobody; a fabricated six-retiree boundary promotes at most four, every row free, every
expiry computed from its term; the empty-retired call answers with a reason rather than a signing.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_ageing.py -q
# 6 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_career.py apps/api/tests/test_transfers_api.py apps/api/tests/test_academy_outcomes.py -q
# 176 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_openapi_contract_currency.py -q
# 4 passed
```

`alembic check` is unaffected (no new column). ruff, mypy (163 files), tsc, ESLint, `qa-i18n-literals`
(9/9), `qa-unused-keys` (3/3), `qa-token-drift` (2/2) and `qa-wire-readers` (12/12) are green.

## The live walk

`.scratch/walk-ageing.py` now reads both halves. The 14-round boundary retired the forced 39-year-old
(wage **3,100**), then promoted **Noa Veitmann**, age **20**, on a **5-year** deal at **1,730** a week
with expiry **84** (= round 15 + 5 × 14 − 1). The squad was 15 after the retirement and **16** after
the intake; the bill ended at **1,730**, exactly the new deal.

```
"retire_round": 15,
"retire_weekly_wage": 3100,
"youth_intake": [{ "player_name": "Noa Veitmann", "age": 20, "contract_years": 5, "weekly_wage": 1730, "expiry_round": 84 }],
"wage_bill_after": 1730,
VERDICT PASS
```

## Open

* No production-build browser pass yet; the new label is catalogue-checked only.
* The intake is sized by the retirement count, not by a squad target: a club that sells players still
  shrinks, because only a boundary retirement opens a place.
* The candidate pool is the world's current young players; there is no separate academy roster, so the
  same world player can be promoted by two careers.
* A promoted player's development still follows the career's minutes; the intake does not grant a
  training bonus.
