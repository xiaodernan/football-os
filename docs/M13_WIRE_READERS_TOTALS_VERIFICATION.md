# The wire-readers gate computes its totals census

**Status: done 2026-11-05.** Item 42 was filed against `qa-wire-readers.mjs`: its docstring advertised checks
12-14 over the `totals` block and a seam through `components/MarketTools.tsx`, but the shipped script
declared `TOOLS_TSX` and `FLOOR_TOTALS_KEYS` and read neither. The run answered 12/12, the eleven checks
and 3b it had before, so deleting a `totals` key from the wire left the gate green. The census was prose.

## The fix

The gate now derives the block from the same `scanDict` that reads the rest of `market_view`:
`publishedTotals = viewScan.shapes.flatMap((shape) => shape.children.totals ?? [])`, and the type side
follows `MarketView["totals"]` through the project's TypeScript. Three checks are real:

* **12** — the published totals keys and the declared keys are equal in both directions, naming every
  key that is published but untyped or declared but unpublished.
* **13** — every declared field is read by the page (`view.totals.x`) or through the seam
  (`totals.x` inside `MarketTools`), or is named in a ledger whose proof is re-measured on every run.
  The seam is not "the component mentions the prop": a `passesProp` AST clause requires the page's own
  JSX to pass `totals={view.totals}`, so a component that reads a prop nobody hands it is red.
* **14** — a ledger row whose proof stopped holding is stale and red. The seven counts that are not
  printed on their own (`moves`, `wage_rows`, `grant_rows`, `cup_prize_rows`, `bonus_rows`, `gate_rows`,
  `stadium_rows`) are excused only while the page still prints `view.moves` (or, for `wage_rows`, the
  budget block's same count), because a totals count is the length of that visible ledger.

Check 10 also became stricter as a side effect of the stadium block: the market page now reads
`view.stadium` and prints the ground summary, so a published view key cannot be added without a reader.

## The run

```
node scripts/qa-wire-readers.mjs
# CHECKS passed=18 total=18 failed=0
# wire view=18 window=16 range=3 constants=22 totals=10 moves=30
# type view=18 window=16 range=3 constants=22 totals=10 move=30
# page 17 view reads, 2 totals reads, 1 seam read, 33 move reads
```

The population is printed, not copied: the totals block has 10 keys on both sides, and the moves block
has 30.

## Mutation arms

Each arm copies the four files into a separate root and changes one thing; the untouched copy is the
control. Run with `QA_WIRE_WEB`/`QA_WIRE_API` pointing at the arm.

| arm | mutation | result |
| --- | --- | --- |
| baseline | none | 18/18, exit 0 |
| wire | remove `"stadium_rows": len(works)` from `market_view["totals"]` | 15/18: check 12 `wire 9 vs type 10 — declared, published by nothing: stadium_rows`; check 13 names the field; check 14 names the stale ledger row |
| type | remove `stadium_rows` from `MarketView["totals"]` | 17/18: check 12 `published, typed by nothing: stadium_rows` |
| seam | remove `totals={view.totals}` from the page's `MarketTools` call | 17/18: check 13 `the market page does not pass totals={view.totals} to MarketTools` |
| reader | replace `signed: view.totals.signed` with `signed: 0` | 17/18: check 13 `nothing asks: signed` |

The control proves the copy is gradeable; each mutation reds on exactly the clause its name states,
which is the property the item asked for. The `qa-wire-readers` docstring already lists checks 12-14 and
the five populations, so no prose was widened for this landing.

## What it still does not do

The ledger excuses a totals count by pointing at the visible `view.moves` rows; it does not prove the
count equals the filtered rows, because that is arithmetic and belongs to `qa-market.mjs`. The gate's
job is to refuse a missing reader, not to re-sum the API.
