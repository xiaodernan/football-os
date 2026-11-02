# M13 verification — development written back to the career's eleven

M13 Phase 1 item 4 shipped the minute-based curve as a **projection**: `development_view` recomputed
the developed attributes from `career_appearances` on every read, printed them beside the stored
ones, and never reached the engine. A career's ninth fixture was therefore decided by the same
attributes as its first. This half closes the loop: a played round writes one row per selected
player into a career-owned table, and the *next* round's eleven reads it. The world's
`real_players` rows are never rewritten.

Date: 2026-11-02.

## 1. The table

`apps/api/app/models/__init__.py` adds `CareerDevelopment`; migration
`apps/api/migrations/versions/0048_career_developments.py` creates it (revision `0048`,
`down_revision` `0047`). Nineteen columns:

| Column | Meaning |
| --- | --- |
| `id` | `cdv…` public id |
| `career_id` | the career that played the round (FK `careers.id`, CASCADE) |
| `round_index` | the round that earned the snapshot |
| `player_id` | the selected player (FK `real_players.id`, CASCADE) |
| `player_slug`, `player_name`, `position` | the name the report printed, kept so the row reads after the world is re-synced |
| `minutes_total` | that player's summed `career_appearances.minutes` through this round, inclusive |
| `training_units` | the world's training load for the player at write time |
| `effective_minutes` | `minutes_total + 0.5·training_units` |
| `potential` | the player's stored potential at write time |
| `overall_before` | the previous round's `overall_after`, or the stored overall on a first row |
| `overall_after` | the scalar curve's value |
| `attributes` | the full developed attribute set (all 27 keys) |
| `note` | a sentence naming the round, minutes and potential, and the world's untouched row |
| `data_origin`, `is_demo_data` | `simulation` / `true`, as every career row carries |
| `created_at`, `updated_at` | `TimestampMixin` |

`UniqueConstraint(career_id, round_index, player_id)` (`uq_career_development_round_player`) makes a
round's rows idempotent; `ix_development_career_round` serves the per-career ordered read and
`ix_development_player` the per-player audit. No backfill: rounds played before this migration wrote
no row, and the projection still recomputes their curve from appearances.

## 2. What writes, and what reads

* **Write.** `career._write_developments` runs inside `_trace_round`, after `record_appearances`,
  for the same eleven the report recorded. It reads the career's cumulative appearance minutes and
  the world's `training_loads`, recomputes `development_summary` **from the stored baseline** (not
  from last round's row) and commits one row per selected player. Existing rows for the round are
  returned unchanged, matching `record_appearances`' idempotence.
* **Read.** `squad.developments_as_of(session, career_id, round_index)` returns the latest row per
  player from rounds **strictly before** `round_index`; `squad_as_of` folds the attribute dict and
  the developed overall into `SquadOverlay.developed` / `.developed_overall`.
  `select_starting_xi`, `_band_index` and `team_profile` rank and measure the eleven from those
  values, and the profile gains a `developed_players` factor naming how many of its own eleven carry
  a row. `overlay.empty` keeps its old meaning (transfers only) so existing transfer tests read the
  same; `SquadOverlay.summary` and `carries_development` name the new half.
* **Replay.** Round N's row is written after N is stored and applies from N+1. `replay_is_identical`
  on round N rebuilds the overlay as of N, which cannot see N's own row, so the digest is unchanged
  by construction — not by a stored counter that happens to agree.
* **Academy.** `academy_view` passes the same `developed_overall` into its band selection and class
  ranking, so "the eleven the engine would select" stays the eleven the engine does select.
* **View.** `development_view` keeps the projection and adds `applied_rows`, `applied_players`,
  `last_applied_round`, `applies_from_round`, and per row `applied_round`, `overall_before`,
  `overall_after`. `limitations()["carry_over"]` names both continuations (condition and
  development) and says the world's rows are unchanged; `limitations()["projections"]` now says the
  development block prints applied rows rather than pretending to be read-only.

## 3. What the page prints

`apps/web/components/CareerDevelopment.tsx` now leads with the applied count, prints
`applied players / players with appearances`, the last applied round, a **Round** column (each
row's `applied_round`), and the per-row before/after overall pair. The panel title is "Applied
development". No catalogue key was added: the new column reuses `careerDetail.thRound`. The four
existing values were reworded in all three locales (`en`, `zh`, `zh-TW`); the population stayed at
**4028 keys** in every file, which `qa-population-floor.mjs` and `qa-locale-completeness.mjs`
re-derived (see §5).

## 4. Tests

`apps/api/tests/test_career.py::TestDevelopment` grew seven cases beside the two projection cases:

| Case | Claim |
| --- | --- |
| `test_a_fresh_career_has_applied_nothing_and_names_the_round_it_would` | a career with no appearances reports zero applied rows and an `applies_from_round` of 1 |
| `test_every_played_round_writes_one_row_per_selected_player` | one round writes 11 rows for the same 11 traced players; each carries the fixture's full minutes, a non-decreasing overall, the full 27-attribute after-state, and never crosses potential from below (an attribute already above stays) |
| `test_the_next_round_plays_the_eleven_the_last_round_developed` | `squad_as_of(…, 2)` carries development, and `team_profile` names how many of its selected eleven do |
| `test_a_round_never_reads_the_development_it_writes` | `squad_as_of(…, 1)` is `None` after round 1; round 2 is the first reader |
| `test_replaying_a_stored_round_keeps_its_digest_after_later_rounds` | both rounds replay identically after round 2 is stored, so late rows never move an old digest |
| `test_the_worlds_stored_rows_are_never_rewritten` | two played rounds leave every club `RealPlayer` attribute and overall byte-for-byte what the generator wrote |
| `test_the_view_reports_the_rows_it_applied_and_the_round_they_apply_from` | two rounds report 22 rows, 11 distinct players, `last_applied_round=2`, `applies_from_round=3`, and each entry's applied round is 1 or 2 |

The existing projection cases still pass unchanged: the fresh note still carries "fixture-minutes"
and the played note still carries "stored", and the curve identity (`after − before = delta`,
`after ≤ max(before, potential)`) is re-checked over the rows.

## 5. Gates

| Gate | Result |
| --- | --- |
| targeted pytest (`test_career`, `test_carry_over`, `test_transfers`, `test_academy_outcomes`, `test_development`, `test_career_api`) | 176 passed |
| full pytest | every test passed except three: the audit case still reads HEAD's 47 migrations (it is re-run after this commit and answers 48), and the two `test_ci_trigger` cases that spawn `scripts/lint.sh` through Git bash without `dirname` on this Windows host |
| `ruff check app tests` | all checks passed |
| `mypy app` | 161 files, no issues |
| `alembic upgrade head` + `alembic check` on a throwaway SQLite | head `0048`, no new upgrade operations |
| `npm run typecheck` | 0 errors |
| `npm run lint` | no warnings or errors |
| `npm run build` | clean |
| `qa-icu-messages`, `qa-unused-keys`, `qa-population-floor`, `qa-locale-completeness`, `qa-locale-content`, `qa-shared-keys` | all passed; 4028 keys in `en`/`zh`/`zh-TW`, 0 unused, shared-key ceiling held at 234 |

The audit's migration census moved from 47 to **48** in `docs/SPEC_COVERAGE_AUDIT.md` and in
`ROADMAP.md`'s quoted triple, which `apps/api/tests/test_spec_audit_currency.py` C1/C2 recompute
from the committed tree after this commit.

## 6. Disclosures

* **No live page walk in this unit.** The wire fields are printed by a server component and the
  build/typecheck/lint gates are green, but the rendered HTML was not walked against a running API
  here; the panel's presentation of the applied fields (and the reworded three-locale values) is
  covered by the gates above, not by a browser walk. A later live-tier walk can pin the rendered
  strings the way `docs/M13_DEVELOPMENT_PANEL_VERIFICATION.md` did for the projection.
* **History is not backfilled.** A career played before `0048` has no rows; its next round starts
  from the stored baseline and cumulative minutes, which is the same arithmetic the projection
  prints. This is deliberate: inventing per-round snapshots for matches already stored would claim
  a history those rounds did not have.
* **Path independence is a choice.** Recomputing `after` from the stored baseline on every round
  keeps the row and the projection identical for the same minutes; it means a row is not "last
  round plus this round's gain" in the attribute dict. `overall_before` is the legible
  round-to-round scalar (previous `overall_after`), and `overall_after` is the pure curve.
* **One new factor, only when it applies.** `team_profile` prints `developed_players` only when a
  selected player carries development, so a career with no market, no carry-over and no played
  round reads exactly as before.

## 7. Reproduce

```bash
cd apps/api && python -m pytest tests/test_career.py::TestDevelopment -q
cd apps/api && python -m ruff check app tests && python -m mypy app
cd apps/api && rm -f _check.db && DATABASE_URL="sqlite:///./_check.db" python -m alembic upgrade head \
  && DATABASE_URL="sqlite:///./_check.db" python -m alembic check && rm -f _check.db
cd apps/web && npm run typecheck && npm run lint && npm run build
cd apps/web && node scripts/qa-icu-messages.mjs && node scripts/qa-unused-keys.mjs \
  && node scripts/qa-population-floor.mjs && node scripts/qa-locale-completeness.mjs
```
