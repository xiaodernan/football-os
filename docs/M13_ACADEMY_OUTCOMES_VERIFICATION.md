# M13 verification — the youth academy outcomes block (career domain)

Roadmap item 7 asked for academy trainees graduating into the squad with attributes derived from
their stored load. Two honest constraints, both discovered before a line was written and both now
published on the wire, shaped what landed:

* **There is no organisation-to-career link, and this unit did not invent one.** M8's academy tier
  (development plans, assessments, sessions) hangs off user-created `organizations`
  (`app/services/club/organizations.py:406` is the only constructor; the demo world seeds none) and shares no rows with
  careers. Bridging the tiers would require an invented org↔career link — new data nobody's door
  writes. So the block reads the load the career domain actually stores: the world's own training
  sessions (`carry_over.training_loads`) and the career's own appearance rows — the same two sources
  the `development` block projects from.
* **The graduation is deliberately not a dice roll.** The roadmap's wording was "a deterministic
  roll" — a contradiction the engine cannot honour: a roll makes a stored match's replay report a
  squad the one that played never used, and replay identity is the career mode's own tested claim
  (the M13 Phase 2 determinism guard exists for exactly this). Graduation is therefore **measured,
  not drawn**: the formation picks the eleven from the career's current squad exactly as
  `team_profile` does before every played round, and a trainee at or under the age ceiling is
  `selected` in that eleven, `next_in_line` as the first reserve of his band (band rank = seats + 1),
  or `off_the_pace` at his band rank.

Date: 2026-10-28. Status: API half done and pinned on both database legs; the career page's panel is
the next unit (see §7).

## 1. What landed

| File | What it adds |
| --- | --- |
| `app/services/simulation/academy.py` (new) | `academy_class` — the pure core: per-band pools sorted `(-overall, slug)` (the engine's own order), band ranks, per-band seat floors, one verdict row per under-ceiling player; `academy_view` — the career wire: squad-as-of-next-round with the transfer overlay applied, the formation from the career's system or the team's own, `select_starting_xi` seats counted by the eleven members' own bands |
| `app/services/simulation/development.py` | `developed_overall` — the same saturating curve applied to one scalar, left unrounded, so the overall projection and the attribute projection can never disagree (a pure test pins the equality) |
| `app/services/simulation/career.py` | `career_view["academy"]` wired after the `development` line, reusing the appearance rows and training loads the view already fetched; `limitations()["projections"]` names the new block among the read-only projections |
| `tests/test_academy_outcomes.py` (new) | 8 pure cases + 3 database-backed cases (§3) |

## 2. What the block publishes

| Field | Meaning |
| --- | --- |
| `available`, `reason` | False with the API's own reason on the empty branches (no club; no players to select from; nobody at or under the ceiling) |
| `youth_age_max` | 21 — the world generates outfielders at 17–34, so 21 names the genuine youth class |
| `class_size`, `selected_count`, `next_in_line_count`, `squad_size` | the class's shape and its verdict counts |
| `formation`, `system_slug` | the shape the eleven was picked with — the career's system's formation, or the team's own when no system is set |
| `trainees[]` | per trainee: identity, band, age, `stored_overall`/`stored_potential`, the load (`minutes`, `training_units`, `effective_minutes`), the projection (`projected_overall`, `potential_headroom`), the standing (`band_rank`, `band_size`, `seats_in_band`, `verdict`, `gap_to_last_seat`) |
| `tau`, `rate` | the curve's own constants (3000 minutes, 0.18) — the same projection the `development` block runs |
| `academy_formula`, `formulas`, `note` | the published sentence and per-figure derivations; the note states both re-scopes in the reader's words |
| `data_origin`, `is_demo_data` | as every career block carries |

Three verdicts, one closed set (`selected`, `next_in_line`, `off_the_pace`). `gap_to_last_seat` is
null for a selected trainee (he *is* a seat) and the weakest selected player of his band minus his
own stored overall otherwise — a positive gap means he sits behind the last seat today. The block
computes nothing it does not publish a formula for, writes nothing back, and borrows the career
view's already-fetched rows so the read adds no per-player queries beyond its one roster select and
the squad overlay's own reads.

## 3. The tests

`tests/test_academy_outcomes.py` — 11 cases, green on both database legs:

Pure (no database, engine helpers only):

1. `test_zero_minutes_leaves_the_overall_unchanged` — the scalar projection at 0 minutes is the identity.
2. `test_the_overall_projection_is_deterministic_and_saturating` — same inputs, same value; growth
   rises with minutes and slows as it approaches potential; 48000 minutes cannot cross potential.
3. `test_no_growth_when_already_at_potential` — an overall at potential stays there.
4. `test_the_overall_projection_matches_the_attribute_curve` — `round(developed_overall(...))` equals
   `developed_attributes(...)`'s finishing column at minutes 0/1500/3000/9000: the two projections
   share `_develop_one`, and the test pins that they share it *in behavior*, not just by import.
5. `test_an_adult_only_squad_is_an_empty_class` — no under-21 player, no rows.
6. `test_the_best_young_attacker_is_selected_by_the_engine_s_own_eleven` — the best young attacker is
   `selected`; a young CB behind four adult CBs *and* the adult reserve (band rank 6 of 6) is
   `off_the_pace` with `gap_to_last_seat` 7.0. The first draft of this case expected the rank-5 CB to
   be `off_the_pace` and the block correctly said `next_in_line` — rank 5 against 4 seats *is* the
   first reserve by the block's own published rule; the case gained an adult CB so the boundary it
   names is the one it tests (recorded here because the prediction error was mine, not the code's).
7. `test_the_first_reserve_of_a_band_is_next_in_line` — a slug tiebreak puts the kid ahead of the
   adult at equal overall; rank 5 against 4 seats reads `next_in_line`.
8. `test_the_projection_reads_the_load_the_caller_handed_in` — 1200 match minutes plus 400 training
   units project through `effective_minutes = 1200 + 0.5·400 = 1400`, asserted against the scalar
   curve at that figure.

Database-backed (`TestAcademyBlock`, the generated world; plays two rounds through the real
`play_round` so the rows are the career's own):

9. `test_the_class_is_the_squad_s_under_21_players_judged_by_the_engine_s_eleven` — class size equals
   the under-21 count of the career's own `current_squad`; verdicts are the closed set; every
   `selected` trainee is in the engine XI recomputed from the block's own `formation`.
10. `test_the_block_is_recomputed_from_the_rows_on_every_read` — two `career_view` reads are
    json-equal: no stored counter drifts, the block is a projection.
11. `test_each_trainee_s_figures_rederive_from_the_career_s_own_rows` — each trainee's `minutes`
    equals the sum of his appearance rows and `projected_overall` equals the scalar curve over the
    effective minutes rebuilt from the career's own loads (skipped, named, when the drawn club has
    no under-21 player).

## 4. Both legs

| Leg | Result |
| --- | --- |
| SQLite (per-run database, the CI shape) | academy file 11/11; `test_career.py` + `test_development.py` 38/38 — the career view's existing per-table query-count pins (one appearances read, one fixtures read, no per-round slug reads) hold with the block wired in |
| PostgreSQL + pgvector (local `football_os_db` on 54321, psycopg2 driver) | both files together 49/49 |
| `ruff check` + `ruff format --check` | clean on all four touched files |
| `scripts/lint.sh` | "All checks passed!" |
| `mypy app` | clean except the foreign lane's `market.py` (14 errors, lines 495–514 — §5) |

## 5. Disclosures

* **master's api CI job is red from the foreign market batch, not cured here** — `market.py`'s mypy
  errors, now **14** (was 13 when the development panel unit disclosed it; the file carries that
  lane's uncommitted edits in the shared worktree and grew one error this session). Verified via
  `mypy app` filtered on the file: no error exists outside it. This unit's four Python files type-check.
* **A live read first hit the wrong database, and the incident is the record.** The scratch walk set
  only `FOOTBALL_OS_TEST_DATABASE_URL` — a **conftest-only** convention — while
  `app/core/config.py`'s `_load_dotenv()` reads `apps/api/.env`, whose `DATABASE_URL` points at the
  local **PG dev database** (`football_os` on 54321). The walk therefore created its user, career and
  three played rounds there (a second run's `UniqueViolation` on the same email proved the first had
  persisted). Every row was then deleted by a cleanup that counted before deleting — 33 appearance
  rows, 53 `sim_events`, 3 `sim_matches`, 3 fixtures, the career, the user — and verified zero
  leftovers by re-selecting both ends. Any future off-suite read must override `DATABASE_URL`
  itself, as the reproduce block below does.
* **The M8-tenant bridge is a deliberate non-goal**, published in the block's `note`: development
  plans and assessments remain a tenant-scoped surface with no link to careers. If a link ever
  lands, it is a migration with its own door, not this block's assumption.
* `seats_in_band` counts borrowed players where they came from (a defender drafted into midfield
  fills a midfield seat) — the formula string says so; no test holds a borrowed case because
  `select_starting_xi`'s borrowing is already pinned in the engine's own tests, and the block reads
  seats off the selection's output rather than reimplementing it.

## 6. The live read

A three-round career (throwaway SQLite, `DATABASE_URL` overridden, world seeded, no tactical system
so the team's own 4-4-2 picks the eleven): squad 15, class **3**, all three `selected`,
`next_in_line_count` 0 — minutes 270 each (three rounds × 90), training units 0:

| Trainee | Pos | Age | Stored → projected | Band standing |
| --- | --- | --- | --- | --- |
| Balyn Qelmann | CAM | 20 | 49 → 49.2 (headroom 12.8) | midfield rank 2/4, 4 seats |
| Janek Tober | RW | 19 | 49 → 49.2 (headroom 12.8) | attack rank 2/4, 2 seats |
| Unin Marnova | CDM | 20 | 48 → 48.2 (headroom 13.8) | midfield rank 4/4, 4 seats |

The projection at 270 minutes is small (the τ=3000 curve closes ~8.6% of the headroom) — the figures
the page will print for a young season. The `selected` rows carry `gap_to_last_seat: null` on the
wire, as published. The full block (formulas, note, constants) was read off the wire and matched this
document's tables before the record was written.

## 7. Reproduce and what is next

```bash
# the block, live, on a throwaway database (DATABASE_URL must be overridden — see §5)
cd apps/api && DATABASE_URL="sqlite:///./.scratch-academy.db" ../../.venv/Scripts/python.exe \
  -c "<create user + career, play 3 rounds, print career_view['academy']>"

# the suite
../../.venv/Scripts/python.exe -m pytest tests/test_academy_outcomes.py -q            # SQLite, 11
DATABASE_URL="postgresql+psycopg2://football:***@127.0.0.1:54321/<per-run db>" \
  ../../.venv/Scripts/python.exe -m pytest tests/test_academy_outcomes.py tests/test_career.py tests/test_development.py -q
```

**Next unit (the web half):** type the block in `lib/types.ts`, render
`components/CareerAcademy.tsx` on `/career/{slug}` (the three verdicts, the standing columns, the
formulas/note, the empty branch), author the keys in all three locales holding the shared-keys
ceiling, and walk it on a shipped build — the M13 panel pattern the previous six units used.

## 8. Dev-database hygiene note for the next unit

`apps/api/.env` is loaded by `config._load_dotenv()` via `os.environ.setdefault`, so it wins whenever
the shell does not already define the key. Two conventions exist and only one is real in-process:
`DATABASE_URL` selects the database everywhere; `FOOTBALL_OS_TEST_DATABASE_URL` is read by
`tests/conftest.py` alone. A script that sets only the test variable talks to the dev database.
