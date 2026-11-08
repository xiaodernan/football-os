# M13 Phase 8 item 28 — a career clock that ages and retires players

**Status: done 2026-11-03.** The contract book printed an age profile and a retirement risk list, and
the profile said in words that nothing in the build aged a player or retired one. This item gives the
career its own clock: a player's effective age is the world's stored age plus the seasons this career
has closed, and the season boundary writes a `retire` move at the threshold.

## The rule

* **The clock is career-scoped.** `real_players.age` is shared by every career in the world, so ageing
  it would age another manager's squad and a world re-sync would undo it. `ageing.effective_age(player,
  closed)` returns `stored age + closed`, and `closed_seasons(session, career)` counts the career's own
  `career_seasons` rows. Nothing here writes a player row.
* **The threshold is 40.** `ageing.RETIREMENT_AGE = 40` decides a retirement; `market.RETIREMENT_AGE =
  35` remains the age-profile *flag* that warns a manager about a player. The contract book prints the
  boundary age (`retirement_age = 40`) and keeps the 35+ list as the risk flag, because carrying a
  37-year-old and choosing to renew him is a decision the build allows.
* **The boundary retires.** `close_season` writes its `CareerSeason` row and then calls
  `retire_at_boundary(..., round_index=last_round + 1, closed=season_index)`. The retirement binds
  from the next season's first round: the player played the season that just closed and is gone from
  the squad overlay when the next eleven is picked. The row stores `fee = 0`, the wage it was being
  paid and `expiry_round = 0`; retiring is neither a sale nor a payment.
* **A side must remain.** Candidates are walked oldest first. A candidate is *retained* when retiring
  them would leave fewer than eleven players or no goalkeeper (`can_field_side`); the boundary result
  names the retained player, their age and the count that refused. This is the same rule that guards a
  sale, a release and a contract expiry.
* **A challenge retires nobody.** A challenge career has one season and no boundary after its window,
  so `retire_at_boundary` returns `checked = 0` with the reason. The window's authored budget is not
  disturbed.
* **Every age read is the same age.** `valuation(player, age=...)`, `open_market`'s listing rows,
  `buy`, `loan`, `sell`, `release`, `renew`, `_record_move`'s stored contract terms and
  `contract_book`'s age profile, `market_view`'s squad rows and the academy class all use the career
  clock. A test pins the contract book's profile, the market squad rows and every trainee's printed age
  to the stored age plus the closed count, so a page cannot print two ages for one player.

## What a reader sees

* `CareerSquadMove.kind` gains `retire`; `MOVE_EFFECT` names it, `OUT_KINDS` treats it as a departure,
  and `contract_book.recent` lists it with the other endings.
* `CareerContracts.tsx` renders it through `contractsKindRetired` ("retired at the boundary") in all
  three catalogues. No new column: `recent` is the panel that already names endings.
* The age profile's `retirement_age` now prints the threshold that actually ends a career (40), while
  `retirement_risk` remains the 35+ warning list.

## Tests

`tests/test_ageing.py` (4 cases): the effective age is the stored age plus the closed count and a
negative offset does not make a player younger; a signed player one year short of the threshold is
retired by the boundary, his `retire` row is written at the next season's first round, the overlay
drops him, the wage bill falls by his stored wage and `recent` names him; a squad aged wholesale to
the threshold keeps eleven players and a keeper, with the retained candidates named; a challenge
window retires nobody.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_ageing.py -q
# 4 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_career.py apps/api/tests/test_transfers_api.py -q
# 165 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_openapi_contract_currency.py -q
# 4 passed
```

`alembic check` reports no new upgrade operations (the item adds no column: `retire` is a value of the
existing `career_squad_moves.kind`). ruff, mypy (162 files), tsc, ESLint, `qa-i18n-literals` (9/9),
`qa-unused-keys` (3/3), `qa-token-drift` (2/2) and `qa-wire-readers` (12/12) are green.

## The live walk

`.scratch/walk-ageing.py` closed one season on a fresh career against the configured database. The
signed player's stored age was 27; the walk forced it to 39 so the boundary would turn him 40. The
season ran 14 rounds, the `retire` row landed at round 15, the squad fell to 15 players, the wage bill
moved **3,100 → 0**, and the contract book's `recent` read `retire / Corand Ruceek` with
`retirement_age = 40`.

```
"effective_age_at_boundary": 40,
"retire_round": 15,
"retire_weekly_wage": 3100,
"still_in_squad": false,
"wage_bill_before": 3100,
"wage_bill_after": 0,
VERDICT PASS
```

## Open

* No production-build browser pass yet; the `recent` label is catalogue-checked but not seen in a
  browser.
* The retirement decision does not weigh the player's remaining contract, his role or his wage: 40 is
  the only rule. A player under contract is retired as readily as one on an expiring deal.
* The clock advances only when a season closes, so an imported mid-season career starts at stored age
  for its first season.
* Youth intake (item 29) is what replaces the retirees; it now runs at the same boundary and is
  recorded in [M13_YOUTH_INTAKE_VERIFICATION.md](M13_YOUTH_INTAKE_VERIFICATION.md).
