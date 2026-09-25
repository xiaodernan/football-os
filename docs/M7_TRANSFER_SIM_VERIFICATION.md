# M7 — the transfer simulation: what would change, computed and written nowhere

Spec line: M7's list closes with **Transfer simulation**. §22 already has the door that moves a player
(`POST /transfers/{career}/buy`), and §23/§24/§27 have the screen that shows him. What was missing is the question
between them: *if this career signed this player, what would actually be different?* This document certifies the
answer that route gives — `POST /api/v1/scout/simulate-transfer`, `app/services/scouting/transfer_sim.py`, and the
panel on `/scout` that prints it.

## 1. The claim, and the shape that keeps it honest

A projection is easy to fake: run the real market call, read the rows it wrote, then describe them. That is not
this. The module calls no market writer, adds no row, and decrements no balance — it composes four read-only
functions the project already publishes and prints the arithmetic between them:

| Question | Read from | Why that, and not a copy |
| --- | --- | --- |
| what would he cost | `market.valuation` on the player's row, against `market.budget_position` and `market.wage_bill` | the fee a seller would ask and the wage a season would pay are §22's formulas, evaluated on the row as it stands |
| would the side change | `profile.team_profile`, run twice — the squad at that round, and that squad with one row added | it is the selector the engine plays, so a player who would bench is shown benching, not shown starting because a scout liked him |
| which fixtures | `career.next_fixture_plan(…, round_index=n)` | the rotation is a pure function of the round number; reading ahead needed a seam, not a fake `rounds_played` |
| what happens in them | `engine.simulate_match`, the pure step, twice **at the same seed** | persisting the projection would be a transaction wearing a lab coat; the engine's step reads nothing and stores nothing |

The seam in the planner is the one change to another module: `next_fixture_plan` now takes an optional
`round_index`, defaulting to the round after the last one played. A test pins that the default answers exactly as
it did before, and that reading twelve rounds ahead leaves the career's `rounds_played` and budget untouched.

## 2. The answer a reader gets

Each projected round prints its seed once and both lines' seeds separately, with the digest each produced:

```text
round 1  vs Dunmoor Town   seed 1582546099   without 0-1 L  poss 0.307  digest 157e35e1…
                                       with the signing 0-4 L  poss 0.354  digest 0c5ad818…
```

Same seed, two elevens, two digests — so the difference cannot be attributed to the dice having been rolled twice.
Beside the fixtures the panel prints the pre-dice part of the answer, which is the part that is not luck: the
band indices before and after, and who moves in the eleven.

Measured on the development world, for a career whose first search result was offered up as a signing:

* squad `15 → 16`, a legal side fieldable before and after;
* the eleven **did** change — `in: Fariel Toban (CDM) · out: Unin Marnova (CDM)`, one name for one name;
* fee `1,336,500` against `6,000,000` left, so affordable on the fee, with headroom `4,663,500` after it and
  `1,743` rounds that the leftovers would carry his printed weekly wage of `2,675` (`× 52 = 139,100` a season);
* the walk re-added every one of those numbers out of the page rather than reading them from a response;
* and over the two projected fixtures the signing **lost the career a point**: `2-3 · 1 point` without him,
  `0-6 · 0 points` with him. A separate shape probe over the strongest player outside the club's own books measured
  the pre-dice half of the same question — defence index `+0.077`, press `+0.025`, overall `+0.02`.

That last line is the one this tier exists to be able to say. A recruitment tool that only ever printed
encouragement would be a brochure; the projection above recommends against the deal it was asked about, with the
arithmetic that led it there on screen.

## 3. Refusals, each with its figures

| Code | Answer | Measured |
| --- | --- | --- |
| `no_such_player` | 404 | `no stored player answers to 'definitely-not-here', so there is nothing here to simulate signing` |
| `already_at_this_club` | 404 | refusing to report a no-op as a signing; names the player and the club |
| `no_opponent` | 404 | the career has no fixture left to project |
| `retired_career` | 422 | a retired career has no future round, and this route will not invent one |
| `window_closed` | 409 | §21's window has closed, so the next fixture will not be played |
| `bad_rounds` | 422 | `a projection covers between 1 and 6 future fixtures, and 99 was asked for` — printed with `{"rounds":99,"min":1,"max":6}` |

The `rounds` cap deliberately lives in the service and not in pydantic: a transport 422 names a field and a
rule, while the service's refusal names the number it was handed and the window it fell outside. A browser that
asks for 99 fixtures gets the second kind, and the panel keeps the last good projection on screen while it says so.

## 4. The mutation probe, and the bound it caught this time

Six defects were planted one at a time in the module, with the tier's suite run between planting and restoring
(`.scratch/mutate_transfer_sim.py`); the file was byte-identical afterwards (`sha 4dcdb1c0…` on both sides).

| Defect planted | Suite answer |
| --- | --- |
| the signing's line replayed at a re-rolled seed | `1 failed, 34 passed` — `test_every_projected_round_carries_one_seed_for_both_lines` |
| the squad reported the same size after a signing | `2 failed, 33 passed` — the same-rows-plus-one test and the bench test |
| the aggregate stops counting points | `1 failed, 34 passed` — `test_totals_and_verdict_counters_equal_the_rounds_printed` |
| the hypothesis never adds the player to the overlay | `1 failed, 34 passed` — `test_a_player_good_enough_to_start_is_the_one_who_moves_the_eleven` |
| a player already on the books is allowed through | `1 failed, 34 passed` — `test_a_player_already_on_the_club_s_books_is_refused_by_name` |
| the **lower** rounds bound stops being checked | **survived** the first pass — `35 passed`, no red |

The survivor was the same class of hole as §24's: a boundary tested from one side only. `rounds=0` does not raise,
it returns an empty projection — no rounds, totals of zero, and a `points_delta` of `0` that reads like a finding.
`test_zero_and_negative_rounds_are_refused_rather_than_projecting_nothing` and
`test_a_projection_always_carries_at_least_one_round` close it; re-planting that defect by hand now gives
`1 failed, 34 passed`, red on the new test, and the file is restored to the same hash.

## 5. Verified

* `alembic check`-equivalent: this tier adds no schema — nothing to migrate, and the head stays at `0015`.
* **Tests:** `apps/api/tests/test_scout_transfer_sim.py` — **35 items**, and the two full legs on this tree:
  **814 passed, 1 skipped on SQLite in 458.47 s** and **814 passed, 1 skipped on PostgreSQL in 886.10 s**
  (780 items before this increment, 815 with it).
* **Walk:** `apps/web/scripts/qa-scout.mjs` → **124/124 checks** on a production build (uvicorn `8734`,
  `next start -p 3213`), 2026-09-25 at 03:47 local. The 27 added checks open a career of their own, run a
  projection, re-add the printed arithmetic from the DOM (season wage against the printed weekly figure, headroom
  against the printed balance and fee, rounds-pay-for against the leftovers, the totals against the difference),
  require both lines of every round to carry one seed, refuse 99 fixtures with its figures, confirm the refusal
  does not erase the answer before it, and delete the career they opened. Two console errors in the whole run,
  both provoked on purpose and both named in the walk's allowance.
* **Contract:** regenerated from this tree — **91 paths, 106 operations**, including
  `POST /api/v1/scout/simulate-transfer`.

## 6. Where this tier stops

* **Nothing is stored or committed.** No `SimulationMatch`, no `CareerSquadMove`, no wage charge, no budget
  movement, no listing, no offer. Asking is not a transaction, and the five lines saying so are in the payload.
* **A fixture is one sample of a stochastic model.** One better scoreline is not a better side; that is why the
  rounds are printed individually, with the indices and possession share beside them.
* **It projects the career as it stands**: its current system, no other ins and outs, no renewal, no injury in
  between. A real window moves several players and each one changes the eleven.
* **The price is a valuation, not a negotiation.** No seller has been asked, and a clause, a rival or a
  counter-offer can move the number §22 would really take.
* **No model is consulted.** No prose, no rating of "fit" beyond the published formula, no advice. The page says
  what it computed and which formula computed it, and the manager decides.
