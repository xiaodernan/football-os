# M13 Phase 8 item 32 — cup runs and prize money

**Status: done 2026-11-03.** Item 27 gave a home round a gate and item 24 gave a season a grant, so a
career's income was its league. The generated world has always held a knockout cup — eight entrants,
four quarter-finals, two semi-finals and a final, each with a stored opponent, side and venue — and a
career never touched it. This item turns that bracket into a run the career plays, and pays a prize for
every round it wins.

## The rule

* **The bracket is the world's, not invented.** A career is *entered* in a cup when the world's own rows
  for that season put its club in one: `real_matches` for a `kind = "cup"` competition whose
  `home_team_id` or `away_team_id` is this club. The quarter-final it plays is that row, with that row's
  opponent, side and venue.
* **Advancing replaces a slot, it does not redraw.** Win the quarter-final and the semi-final the world
  drew for that half is next; the opponent is the other club in that row and the side is the side the
  club it beat occupied (or its own side when the world's own simulation already sent it through). The
  same rule carries the final, which is played at a neutral venue. A club the world's own simulation
  knocked out therefore still has a route: its own result takes the slot.
* **The tie is decided by the engine.** `play_cup_tie` calls the same `run_simulation` a league round
  uses, with the career's own squad overlay (so a signing reaches the cup) and a seed from
  `career id + season + cup + stage`. A tie cannot end level: a draw is separated on penalties by the
  match digest (even for the club, odd for the opponent), stored in `decided_by` and `penalty_note`.
* **A tie is not a round.** It does not advance `career.rounds_played`, score league points or belong to
  the double round-robin. `career_cup_ties.round_index` is the league round it was played after, which is
  where its prize lands in the ledger's round order.
* **A round won pays a prize into the ledger.** `career_budget_awards` gains `kind = "cup_prize"`:
  **40,000** for a quarter-final, **90,000** for a semi-final, **220,000** for the final — 350,000 for a
  cup won. There is no fifth ledger table; `budget_position`, `budget_timeline` and `market_view` sum the
  same rows they already summed.
* **One prize per round.** `uq_cup_tie_stage` allows one tie per cup stage per season, and
  `uq_career_award_stage` (career, season, kind, `stage`) allows one award per round — so a replay cannot
  pay twice, and a season's grant (`stage = ""`) is still one row per season.
* **A challenge career enters no cup.** Its budget is an authored constraint printed when the run starts,
  and a prize would silently raise the figure the scenario stated — the same exclusion the gate and the
  grant make. The block says so.

`RULES["cup_prize"]` publishes the three figures and the rule, and `market_view["constants"]` carries
`cup_prize_by_stage` so the page can promise the prize beside the button.

## What a reader sees

* `career_view["cup"]` is a new block: whether the career is entered at all and why not, one run per cup
  it is in (cup, region, stage, status `live` / `eliminated` / `won` / `unavailable`, record, prizes, the
  formula), the next tie with its opponent, side, venue and bracket basis, and every tie already played
  with its score, how it was settled and what it paid.
* `budget_position` and `affordability_view` gain `received_cup`, `cup_rows`, `cup_detail` and
  `award_rows`; `granted`/`grant_rows` now mean the board's grant only, so a cup prize can never be
  printed as a season's judgment. `received` is sales + gates + cup prizes.
* `budget_timeline` labels a cup prize `cup prize, <cup>:<stage>` and keeps comparing every stored
  `budget_after` with the running total; `market_view` puts it on the one ledger (`cash = "in"`) and
  counts `totals.cup_prize_rows`.
* `CareerCup.tsx` is the panel: the run's state, the next tie, a **Play the cup tie** button that posts to
  `/careers/{slug}/cup` and re-reads the page, the ties table and the per-stage prizes.
  `CareerFinance.tsx` prints "Cup prizes so far" when the career has won one.
* `seasons_view` reads its grant per season from `kind = "season_grant"` only, so the award table's second
  kind cannot appear as a season's money.

## Tests

`apps/api/tests/test_cup.py` (13 cases):

* `TestCupBracket` — the view lists the world's own quarter-final (opponent, side, basis); a forged win
  points at the semi-final the world drew for that half and names the other club in it; a forged loss
  ends the run and `play_cup_tie` refuses `cup_run_over`; three wins win the cup and leave nothing to play.
* `TestCupPrizes` — a won tie pays its stage's prize into `career_budget_awards` (kind, stage, amount,
  basis, `budget_after`, `received_cup`, timeline label, ledger row); the same round cannot pay twice
  (`IntegrityError`); the three figures are published and add to 350,000.
* `TestCupEntries` — a season the world drew no cup for says so; a challenge career enters no cup; a
  retired career plays no tie.
* `TestCupTie` — a played tie is the engine's own result (same digest, same goals, same opponent and
  side) and does not advance the league round; its prize lands at the round it was played after; a drawn
  tie is separated by the digest, even for the club.

`apps/api/tests/test_career_api.py::TestCupWire` (3 cases) proves the wire: `POST /careers/{slug}/cup`
returns the tie and the re-derived career view (the cup block, `rounds_played` unchanged, the prize and
`received_cup` agreeing), a run that is over answers `409 cup_run_over` with the cup block beside it, and
another account gets a 404.

Targeted runs:

```
.venv\Scripts\python.exe -m pytest apps/api/tests/test_cup.py -q
# 13 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_career.py apps/api/tests/test_transfers.py apps/api/tests/test_transfers_api.py apps/api/tests/test_cup.py apps/api/tests/test_ageing.py apps/api/tests/test_affordability.py -q
# 200 passed
.venv\Scripts\python.exe -m pytest apps/api/tests/test_openapi_contract_currency.py -q
# 4 passed, after scripts/export_openapi.py regenerated the contract for the new route
```

`alembic check` clean after `0050 → 0051`; ruff clean; `mypy app` clean over 164 files; `tsc --noEmit`
clean; `next lint` clean; `qa-i18n-literals` 9/9 over 4,151 calls; `qa-unused-keys` 3/3;
`qa-token-drift` 2/2; `qa-wire-readers` **12/12** with 18 constants (the new `cup_prize_by_stage` is typed
by `lib/market.ts`).

## Live walk

`.scratch/walk-cup-prize.py` on the configured Postgres database at `0051`, playing the Haldhurst
Invitation Cup for Corgard Town. A tie's seed comes from the career's own id, so the walk creates careers
until one wins a round — the claim being demonstrated is the prize:

```
{
  "club": "Corgard Town", "cup": "Haldhurst Invitation Cup", "attempts": 4,
  "ties": [
    {"stage": "Quarter-final", "side": "home", "opponent": "Ostford Wanderers", "score": "0-0", "outcome": "W", "decided_by": "penalties"},
    {"stage": "Semi-final",     "side": "home", "opponent": "Braeford Athletic", "score": "1-0", "outcome": "W", "decided_by": "goals"},
    {"stage": "Final",          "side": "home", "opponent": "Cordale Town",     "score": "0-1", "outcome": "L", "decided_by": "goals"}
  ],
  "status": "eliminated", "won": 2,
  "prize_rows": [
    {"stage": "haldhurst-invitation-cup:Quarter-final", "amount": 40000, "budget_after": 1040000},
    {"stage": "haldhurst-invitation-cup:Semi-final",    "amount": 90000, "budget_after": 1130000}
  ],
  "received_cup": 130000, "granted": 0, "cup_rows": 2,
  "remaining": 1130000, "opening_budget": 1000000,
  "rounds_played": 0, "timeline_kinds": ["cup_prize", "cup_prize"],
  "timeline_disagreements": 0, "timeline_closing": 1130000
}
VERDICT PASS
```

Three ties, two rows, 130,000 credits, one balance that adds up — and the league round counter never
moved, which is the difference between a cup and a round.

## Economy note

A cup won pays 350,000. A 14-round season's grant at a mid-table pace is about 147,000 and seven home
gates about 540,000, so a cup run is a good season's *extra* income rather than a substitute for the
league: it rewards a manager who is still in the competition at the end of it. The three stage figures are
authored constants in `market.py`; a balance pass moves one number.

## What is still open

* A cup tie pays **no gate** — `career_gate_receipts` is unique per league round, and a second gate for the
  same round would need a separate key. The prize is the cup's income for now.
* A cup tie charges no **extra** wage and writes no **appearance** row: the week's wage covers it, and
  `career_appearances` is keyed by league round. Development therefore does not see cup minutes.
* Cups exist only for the season the world generated (`2026`); a career in its second season reads "the
  world's 2027 season drew no cup bracket this club entered". The world builder does not draw next
  season's cup.
* The world can enter one club in several cups in the same season; each is its own run, and the panel
  prints them all. `POST /careers/{slug}/cup` plays the first live run unless a `cup` is named.
* No production-build browser pass yet; the panel was checked by `tsc`, ESLint and the four i18n/wire
  gates, not in a rendered page.
