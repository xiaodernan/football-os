# Contract expiry enforced (M13 Phase 7 item 25)

Written 2026-11-02. This is the evidence record for the item that turns the deal book from a projection
into a consequence.

## The gap

`career_squad_moves` stored a deal's `contract_years`, and `contract_book` projected an expiry from it on
every read, but nothing enforced that date. A signed player stayed in the squad forever, the wage bill
never shrank, and `limitations()["projections"]` said so in as many words: "a deal book whose projected
expiry nothing enforces". The season grant (item 24) had just given a career a second income; it could
still only spend it on players it could never lose.

## The shape

- **The date is stored when the deal is signed.** Migration `0049_career_contract_expiry` adds
  `career_squad_moves.expiry_round`, fixed as `signed_round + contract_years x the season length then in
  force - 1`. A later promotion changes the length of future seasons, and a contract already agreed must
  not stretch with it. Rows written before the migration hold `0`; they are projected from their stored
  terms until they are re-signed, and the contract book says which basis it read.
- **The write-off happens before the next round, on the only path that advances a career.**  
  `expire_contracts()` runs at the start of `play_round`, after the next fixture is planned and before
  `squad_as_of` reads the eleven. A permanent deal whose stored last round has passed is written with an
  `expire` move at that round: the player leaves the overlay, and `held_deals` stops charging the wage.
- **No money moves for a contract ending.** The `expire` row carries `fee = 0` and the standing
  `budget_after`, so the ledger still adds up; the wage stops on the next round rather than being
  refunded.
- **One authored exception keeps a career playable.** If letting the deal lapse would leave the club
  below eleven players or without a keeper, the deal is extended by one season at the same stored wage
  with a `renew` move. The result names the fielding figures that decided it; the extension is not
  silent.

Both new kinds are part of `MOVE_KINDS`/`MOVE_EFFECT`, and `IN_KINDS`/`OUT_KINDS` carry `renew`/`expire`
so the squad overlay, the market pool, the wage bill and the ledger all read one vocabulary.

## What the reader sees

- `career_view["contracts"]` gains `recent` - the last five `expire`/`renew` rows with the player, kind,
  effective round, expiry round, wage and the API's own effect sentence.
- `components/CareerContracts.tsx` prints that block on `/career/{slug}` after the held deals: player,
  outcome, effective round, expiry round and weekly wage. The held-deal column now reads "Expiry round"
  rather than "Projected expiry round", and the formula label is "The contract's arithmetic".
- The market ledger already prints every move row, so an `expire` or `renew` row appears there with no new
  panel; both carry a zero fee and the unchanged balance.
- `limitations()["projections"]` no longer claims that no contract expires. It names the enforcement and
  the one-season extension, and keeps the read-only list to the blocks that really are read-only.

## Evidence

**Schema.** `alembic upgrade head` on a fresh SQLite file ran `0048 -> 0049`; `alembic check` answered
"No new upgrade operations detected."

**Service tests.** `tests/test_transfers.py`: **62 passed**. The two new cases hold the two paths:

- `test_a_deal_whose_stored_last_round_has_passed_leaves_the_squad`: the expiry row is written before
  `expiry + 1`, its fee is 0, the balance is unchanged, the player is out of `current_squad`, the wage
  bill for the next round is 0, and the book's `recent[0]` is the `expire` row.
- `test_a_deal_that_would_leave_no_side_is_extended`: the fixture releases base players until the squad is
  exactly eleven, then expires the one signing; the result is a `renew` row, the squad stays at eleven,
  the player stays, and the new expiry is `expiry + 1 + RENEWAL_SEASONS x season_rounds - 1`.
- `test_a_signing_projects_its_expiry_from_the_stored_terms` now asserts the stored `expiry_round` is the
  row's expiry, not a re-derivation.

**Career and wire tests.** `tests/test_career.py` + `tests/test_transfers_api.py`: **88 passed**. The public
`/transfers/rules` answer now publishes `expire` and `renew` in `move_effects`; the test reads
`MOVE_KINDS` rather than a second hand-written list.

**Static gates.** `ruff` clean on every touched Python file; `mypy app` clean over **161** source files;
`tsc --noEmit` clean. The web gates on the same tree: `qa-i18n-literals` **9/9** over **4,098** key calls,
`qa-unused-keys` **3/3** at floor 0, `qa-token-drift` **2/2**, `qa-wire-readers` **12/12** (the market
window's 16 published fields are now typed and read; the four round-count fields the gate named were
missing from `MarketWindow` and are now read by the panel).

**Live service walk.** `.scratch/walk-contract-expiry.py` against a fresh alembic-built SQLite database
(`.scratch/contract-expiry.db`):

```
signed_player          Corand Ruceek
signed_round           1
contract_years         5
stored_expiry_round    70
played_round           71
expire_row_round       71
expire_row_fee         0
squad_after            15
player_still_in_squad  false
remaining_before       7,675,000
remaining_after        7,675,000
deals_after            0
recent_kind            expire
wage_after             0
VERDICT                PASS
```

The walk signs through `market.buy`, moves the career to the deal's own stored last round, plays the
next round through `career_service.play_round`, and reads the squad, the ledger, the contract book and
the wage bill back. The expiry round is the one the signing wrote, not one fabricated for the walk.

## What this does not claim

- **No browser pass yet.** The panel, its three locales and its type/read gates are green, but no
  production build has been walked against a career whose contract just expired. That is the next
  verification step, and this record does not pretend otherwise.
- **No renewal UI and no compensation.** A renewal is the authored emergency exception, not a manager's
  choice; an expired player returns to the world club and no fee arrives. Contract negotiation at expiry
  is a future item.
- **No aging or retirement.** The age profile still reads the world's stored ages; expiry is a contract
  date, not a career arc.
- **Legacy rows are projected, not backfilled.** A row written before `0049` has no stored date and keeps
  the old formula until it is re-signed. The book labels that basis.
