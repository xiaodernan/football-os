# M13 Phase 11 item 47 — the training ground

**Status:** done 2026-11-06. Item 4's development curve already read the world's training sessions, but
every club trained on the same ground. A career now buys facility levels; each level makes every later
training session count 10% more toward development, up to +50% at level 5.

## The rule

- Level 0 is the club's inherited facility and reads exactly the old curve: `training_minutes(units, 0)
  = round(0.5 × units)`. Existing careers and every earlier test therefore keep their figures.
- Level `L` (1–5) costs `150,000 × (L + 1)` credits to leave; buying several levels in one call writes
  one ledger row per level, each with its own `budget_after`.
- `effective_minutes = match_minutes + 0.5 × load_units × (100 + 10L)/100`. Level 0 turns 400 units
  into 200 minutes; level 2 into 240; level 5 into 300.
- The bonus is applied where a round's development is **written** and where it is **projected**, both
  through the one `training_minutes` helper, so the stored row and the page cannot disagree.
- A challenge career, a retired career, a career with no club, an empty balance and a maxed ground are
  each refused with their own code.

## Data and API

- `careers.training_level` (0–5) and `career_training_works` (migration
  `0058_career_training_works.py`): round, level before/after, `bonus_pct_before`/`after`, amount,
  `budget_after`, basis and provenance. The bonus is stored on the row so a later constant change
  cannot rewrite what an upgrade actually bought.
- `BUDGET_FORMULA` subtracts `sum(training_works.amount)`; `budget_position` publishes
  `training_spent`, `training_rows`, `training_detail`; `budget_timeline` places each level at its
  purchase round before that round's moves; `market_view` merges rows as kind `training`;
  `affordability_view` carries the totals.
- `GET /api/v1/careers/{ident}/training` reads the level, the bonus, the next price, the history and
  the formula. `POST` the same path with `{"levels": N}` buys N levels and answers
  `{"built": true, "levels": [...], **career_view}`.
- Refusals: `bad_training_levels` (422, 0 or beyond the room left), `training_maxed` (409),
  `insufficient_budget` (409), `challenge_budget` and `career_retired` (409), `no_club` (404).

## Web

`CareerTraining.tsx` prints the level, the session bonus, the next price, the ground's spending and
every upgrade; it buys the number of levels the manager types and re-reads the page.
`CareerFinance` adds a training-ground spending row, and the market ledger prints each level and its
bonus. 22 keys per locale were added.

## Evidence

- **Service:** `apps/api/tests/test_training.py` — 8 cases: the curve at levels 0/1/5 and the same
  curve applied to an attribute set, a bought level's row and balance, two levels chaining the
  balance, maxed ground, out-of-range purchase, unaffordable balance, challenge/retired refusals.
- **Wire:** `TestTrainingWire` in `apps/api/tests/test_career_api.py` — 2 cases: two levels bought and
  read back through both routes and the career view; 422 + 409 + outsider 404.
- **Schema:** `alembic upgrade head` 0057 → 0058 and `alembic check` → *No new upgrade operations
  detected*.
- **Contracts:** `docs/api/openapi.json` regenerated from the tree — 224 paths / 289 operations.
- **Web gates:** `qa-wire-readers` 18/18 (constants 33, moves 37; the union now names all seven row
  functions), `qa-i18n-literals` 9/9 (4,283 calls), `qa-unused-keys` 3/3, `qa-key-drift` 4/4,
  `qa-token-drift` 2/2, `qa-locale-tokens` 5/5 at 4,231 keys / 4,186 translated,
  `qa-locale-completeness` 2/2, `qa-icu-messages` 2/2; `tsc --noEmit` and `next lint` clean.

### Live walk

`.scratch/walk-training.py` on PostgreSQL, Braeford Athletic (budget 1,000,000):

| figure | value |
| --- | --- |
| purchase | level 1 for 150,000 + level 2 for 300,000 = 450,000 |
| ground after | level 2, +20%, next level 450,000 |
| one player | 90 match minutes + 400 training units |
| effective before | 290 minutes (level 0) |
| effective after | 330 minutes (level 2) — exact expected value |
| timeline | closing 615,404 = `budget_position.remaining`, 0 disagreements |
| ledger | `gate` → `upkeep` → `training` → `training` |

The walk writes one temporary `real_training_sessions` row for the measured player because the
lowest-rated club has no world sessions of its own, and deletes it before exiting.

## Traps recorded

- **Level 0 is the old curve.** `training_minutes` returns the same rounded figure the old expression
  did at level 0, so item 4's writeback and every projection keep their existing numbers and a career
  that never upgrades is not silently rebalanced.
- **One helper, two call sites.** The writeback (`_record_development`) and the projection
  (`development_view`) both call `training_minutes`; a level read from `career.training_level` at only
  one of them would make the page promise minutes the stored row did not use.
- **The ledger's row union.** `qa-wire-readers` builds the Move type from the union of row functions;
  adding `training_ledger_row` revealed that `season_ticket_ledger_row` had never been named, so both
  are now in the union and a new key on any row is red until the type declares it.
