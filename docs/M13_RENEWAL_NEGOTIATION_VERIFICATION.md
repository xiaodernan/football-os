# M13 Phase 8 item 31 — renewals that negotiate

**Status: done 2026-11-03.** Item 26 gave the manager a renewal button: a flat 5% fee and the
valuation wage, accepted every time. That is a price list, not a conversation. This item makes the
term cost what it is worth, makes the player's demand follow the minutes he has actually played and
the tier he plays in, and lets him refuse an offer below it.

## The rule

* **The fee scales with the term.** `fee_per_year = round_5(asking × 5%)`, and
  `fee = fee_per_year × years`. A five-year commitment costs five times a one-year one because the club
  is buying five seasons of the registration.
* **The demand is measured, not copied from the valuation.**
  `demand = round_5(valuation wage × tier_factor × minutes_factor)`.
  `tier_factor` is **1.15** in tier 1, **1.00** in tier 2 and **0.90** in a cup (`tier = 0`).
  `minutes_factor = 0.90 + 0.20 × share`, where
  `share = career appearance minutes ÷ (rounds_played × 90)`, clamped to 0–1. A regular asks 1.10×;
  an unused player asks 0.90×. The quote publishes `demand_wage`, `fee_per_year`, `minutes_share`,
  `tier_factor` and `minutes_factor`, so the number is checkable.
* **The player can refuse.** `POST /transfers/{ident}/renew` accepts an optional `wage`. An offer at or
  above `demand_wage` is accepted at the offered figure; a lower one is refused with
  `409 renewal_refused`, naming `demanded_wage`, `offered_wage`, the share and both factors. An omitted
  `wage` means “pay the demand”, which keeps item 26's one-click path.
* **The existing guards still apply**: the fee must fit the balance, the bill after replacing the old
  wage must fit the board's ceiling, the term is 1–5 seasons, and the deal must be permanent (`buy`,
  `youth` or an earlier `renew`). A loan still cannot be renewed here.

## What a reader sees

* `contract_book`'s renewal block prints the demand wage and the per-year fee, so the page can show
  what the button will pay and what the player asks.
* `ContractRenewal.tsx` now renders a **weekly wage offer** input beside the button; the offer is sent
  with the years. A refusal is printed with the API's own code and demand.
* `RULES["renewal"]` and `RENEWAL_FORMULA` spell out the term and demand arithmetic.

## Tests

`TestRenewals` gains 2 cases: a three-year fee is exactly three times the one-year fee, a wage 5 below
the demand is refused with both numbers and the demand is accepted on the retry; an appearance of 90
minutes over one round makes `minutes_share = 1.0` and `minutes_factor = 1.1`, and the demand rises
above the zero-minute baseline. `TestContractRenewal` gains a wire case for the same refusal and
acceptance, and its existing fee assertions now use `fee_per_year × years`.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_transfers_api.py -q -k "Renewal or renewal"
# 10 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_transfers.py apps/api/tests/test_career.py apps/api/tests/test_transfers_api.py apps/api/tests/test_ageing.py -q
# 176 passed
```

`scripts/export_openapi.py` regenerated the contract for the new `wage` field and
`test_openapi_contract_currency.py` passed 4/4. ruff, mypy (163 files), tsc, ESLint,
`qa-i18n-literals` (9/9), `qa-unused-keys` (3/3), `qa-token-drift` (2/2) and `qa-wire-readers`
(12/12) are green.

## The live walk

`.scratch/walk-renew.py` signed a tier-2 player and read the quotes: **64,575** for one year and
**193,725** for three. The demand was **2,325** a week (valuation wage × 1.00 tier × 0.90 minutes).
An offer of **2,320** was refused with `renewal_refused`; accepting at **2,325** for two years charged
**129,150** and stored expiry **28**. Balance **7,062,750 → 6,933,600**.

```
"one_year_fee": 64575,
"three_year_fee": 193725,
"demand_wage": 2325,
"refused": {"code": "renewal_refused", "demanded_wage": 2325, "offered_wage": 2320},
"accepted_fee": 129150,
"expiry_round": 28,
VERDICT PASS
```

## Open

* The demand uses career appearances only; a player who has not played has no other signal, so every
  unused signing asks exactly 0.90× the valuation wage.
* Tier factors are authored bands (1 / 2 / cup), not a fitted curve.
* The player has no memory: a refused offer is not remembered and there is no multi-round bargaining.
* No production-build browser pass yet; the wage input is type-checked and linted, not walked.
