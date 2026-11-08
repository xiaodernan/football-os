# M13 Phase 7 item 26 — manager-chosen renewals

**Status: done 2026-11-02.** Item 25 made a contract's stored last round decide the squad. This item
gives the manager the other half of that decision: extend a deal this career already holds, at a
price the contract book quotes before the click, without waiting for a signing window.

> **Updated 2026-11-03 (item 31).** The flat 5% fee and the valuation wage described below were
> superseded: the fee now scales with the term, the player's demand weighs minutes and competition
> tier, and a low offer can be refused. The route shape is unchanged and `wage` is an optional new
> field. See [M13_RENEWAL_NEGOTIATION_VERIFICATION.md](M13_RENEWAL_NEGOTIATION_VERIFICATION.md).

## The gap

After item 25 a permanent deal expired, the player left and the wage stopped — but the only renewal
the engine could write was the authored rescue (`renew` at the same wage when a departure would leave
fewer than eleven players or no keeper). A manager who wanted to keep a player had no door: waiting
for expiry meant losing them, and `buy`/`loan` address the world market rather than the career's own
book. A long career therefore leaked players with no way to plan a squad.

## What landed

Migration `0049` already carries `career_squad_moves.expiry_round`; this item writes the same column
from a manager's renewal rather than a signing.

* `POST /api/v1/transfers/{ident}/renew`, body `{ player, years? }`, `years` 1–5 and defaulting to
  the player's current valuation term. It does **not** require an open transfer window: the player is
  already this career's, and the window governs arrivals from other clubs.
* The renewal is only for a permanent deal this career holds and whose effective kind is `buy`
  (`renew` rows are the same). A loan answers `409 loan_cannot_be_renewed`; a squad player with no
  stored deal answers `409 no_contract_to_renew`.
* `renewal_fee = 5% of the player's current asking fee, rounded to 5` (`RENEWAL_FORMULA`, published
  through `RULES["renewal"]`). The new weekly wage is the player's **current valuation**, not the
  wage the old deal carried — a renewal re-prices the player rather than extending stale terms.
* `expiry_round = the round the renewal is signed before + years × season_rounds − 1`, computed once
  from the season length in force and stored on the row exactly as a signing's is.
* Two refusals are arithmetic, and both carry their figures: `insufficient_budget` (`fee`,
  `remaining`) and `wage_ceiling_exceeded` (`wage_bill_before`, `proposed_weekly_wage`,
  `wage_bill_after`, `wage_ceiling`, `headroom`).
* `contract_book` adds a `renewal` block to every held permanent row: `years`, `weekly_wage`, `fee`,
  `balance_after_fee`, `wage_bill_after`, `wage_ceiling`, the two affordability flags, `can_renew`
  and `formula`. The page prints the quote; it does not recompute it.
* `components/ContractRenewal.tsx` renders that quote inside the deal book's new **Renewal** column,
  prints the blocking reason when the quote cannot be taken, posts the player and years, and then
  refreshes the page so the expiry column and the ledger show what the server stored.
* `move_row` now publishes `expiry_round` as well, so a `renew` row in the market ledger and the
  deal book cannot disagree about the term the server wrote.

## Wire and tests

`tests/test_transfers.py` grew four service cases (`TestRenewals`): the arithmetic and stored
expiry, the loan refusal, the no-deal refusal, and both arithmetic refusals. `tests/test_transfers_api.py`
grew five wire cases (`TestContractRenewal`): the quote's fee is the published rounding, the POST
returns the same fee and expiry the deal book then reads, the quote's formula is `RULES["renewal"]`,
a loan is refused, a squad player with no stored deal is refused by name, and the budget and ceiling
refusals carry their numbers — then the same renewal succeeds once the ceiling is raised.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py -q
# 66 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_transfers_api.py -q
# 89 passed
```

`ruff check` clean; `mypy app` from `apps/api` clean over 161 files; `tsc --noEmit` clean; `next lint`
clean; `qa-i18n-literals` 9/9 over 4,109 key calls; `qa-unused-keys` 3/3; `qa-token-drift` 2/2;
`qa-wire-readers` 12/12.

## Live walk

`.scratch/walk-contract-renewal.py` runs through the service layer against a fresh
`alembic upgrade head` SQLite database. It signed one player, read the contract book's own quote,
renewed for two seasons, re-read the book, then played the round:

```
{
  "career": "renewal-walk-braa",
  "player": "Zeek Drosttis",
  "signed_expiry_round": 14,
  "renewal_fee": 30040,
  "quoted_fee": 30040,
  "new_weekly_wage": 1200,
  "old_weekly_wage": 1200,
  "renewed_round": 1,
  "stored_expiry_round": 28,
  "expected_expiry_round": 28,
  "season_rounds": 14,
  "balance_before": 9098875,
  "balance_after": 9068835,
  "recent_kind": "renew",
  "played_round": 1,
  "wage_charged": 1200
}
VERDICT PASS
```

The walk asserts, rather than prints only: the fee equals the quote, the stored expiry equals
`round + 2 × season_rounds − 1`, the balance after is the balance before minus exactly that fee, the
deal book's newest ending is `renew`, and the round's wage charge is the renewed wage.

## What is still open

* No production-build browser pass yet. The panel and the button are wired and typechecked, but the
  last browser walk of the contracts panel predates the renewal column.
* The renewal fee does not scale with the chosen term: one season and five seasons cost the same 5%
  of the asking fee. That is a deliberate authored rule for now, not a negotiation.
* A renewal cannot be refused by the player, and no signing bonus or agent fee is modelled.
* Pre-`0049` rows still project their expiry until re-signed; a renewal writes the stored column and
  therefore closes that row's projection from then on.
