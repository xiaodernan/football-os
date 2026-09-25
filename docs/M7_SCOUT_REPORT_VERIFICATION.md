# M7 item 24 — a scouting report that names the row behind every line

Spec §24 asks for a structured AI scout report with thirteen named fields — `Player`, `Current Level`,
`Potential`, `Technical`, `Physical`, `Mental`, `Tactical`, `Role Fit`, `Team Fit`, `Risk`, `Cost`,
`Comparison`, `Recommendation` — and then draws the line under it:

> 不要输出没有依据的"天赋"

This increment is the route tier over the report service: `POST /api/v1/scout/report`, one door that takes a
player slug and answers §24's thirteen fields, plus the integrity gate that keeps the answer shaped like the
question. The service tier (`app/services/scouting/report.py`) was written while §23 was still being verified;
what landed here is the HTTP surface, the published rule set, and the tests that read the payload back.

## 1. The thirteen fields, and what each one is allowed to be answered with

| §24 field | Answered by | Recomputed from |
| --- | --- | --- |
| `player` | identity, age, position(s), band, club, `observed` | the `real_players` row and the `teams` row it points at |
| `current_level` | stored `overall`, `compute_overall` for the same attributes, percentile in pool and in band | `app.services.attributes`, plus two SQL `COUNT`s |
| `potential` | `potential - overall` beside §22's `age_curve` for the stored age | the row, and `market.age_curve` |
| `technical` / `physical` / `mental` / `tactical` | mean over the attribute keys the row actually carries | `app.models.ATTRIBUTES` groupings, per key |
| `role_fit` | §23's role fit, same function the search called | `ROLES[role].demands` |
| `team_fit` | §22's `tactical_fit` for the band the career is thinnest in | `market.club_need` + `market.tactical_fit` |
| `risk` | a list of named factors, each with the figure that raised it | age, appearances, wage-to-fee share, squad count in band |
| `cost` | `market.valuation`, plus the fee beside the career's stored budget | §22's valuation formula |
| `comparison` | deltas per group against one other stored row | both rows, read the same way |
| `recommendation` | a verdict from `RECOMMENDATION_RULE`, with the two deciding figures beside it | the figures above, in this payload |

A group whose keys the row does not carry is not averaged as zero: `measured` counts what was there and
`missing` names the rest. `comparison` is `null` when no second player was asked for, and `team_fit` is `null`
when no career was — §24 lists both fields, and answering them with a plausible-looking figure over nothing
would be the unevidenced claim the spec forbids.

## 2. Two refusals, and the difference between them

`POST /api/v1/scout/report` refuses in three distinguishable ways:

* **404 `no_such_player`** — the row is not in the pool this report reads. The response carries the ident and
  `players_in_pool`, and there is no empty report returned to suggest a player was found and had nothing to say.
* **422 `unknown_role`** — the word is not in the role catalogue, so the response prints `roles` (the fifteen
  board codes this project actually holds). This is a refusal about *vocabulary*, and the vocabulary is ours to
  correct, so it comes back with the alternatives.
* **422 `validation_error`** — the house envelope, for a request body that never reached the service: an empty
  or 200-character `player`, a `round_index` outside `0..380`. A domain refusal keeps a flat `detail`; a
  schema refusal is wrapped in `error.code`, which is why the two are tested separately.

The player is looked up **before** the role. A wrong slug and a wrong role in one request is a question about
the world and a question about our vocabulary at once, and the world answer is the one that does not change
when this project adds a role.

## 3. A career is optional, and its absence stays visible

`team_fit` needs a club to fit into. Asked without a career, the report prints `team_fit: null` and the risk
list carries one factor fewer — `band_is_already_crowded` cannot be evaluated, so it is absent rather than
guessed. Asked with one, `cost.against_career_budget` puts the asking fee beside §22's stored budget for that
career and says whether it fits without selling:

```json
{"budget": 18400000, "units": "EUR", "share_of_budget": 0.3421, "fits_without_selling": true}
```

A career that belongs to someone else answers **404**, not 403 — the same shape every owner-gated route in
this project uses, so a probe cannot tell "exists but not yours" from "does not exist".

## 4. What the tests corrected in the code, not in themselves

**The role-fit sign.** The recommendation ladder originally negated `role_fit.mean_gap` on its way in. Because
`mean_gap` is `have - demanded`, a player short in two of three role demands was read as a positive fit and
told to `sign now` — while the same payload printed `mean_gap: -16.0` beside `decided_by: ["fit 16.0"]`. The
test that caught it asserts the *rule*, not the run: it asks for a role the row is short for, asserts the gap
is negative, and asserts every `decided_by` figure that names `mean_gap` ends with the same signed number
the `role_fit` line printed. A payload that contradicts itself in one response is the failure this module is
actually vulnerable to, and no amount of re-running the implementation would have shown it.

**A parametrized verdict test that mirrored the implementation.** `test_the_verdict_follows_from_the_figures_
this_report_published` walks `RECOMMENDATION_RULE`'s ladder in the test and compares — which is only worth
anything if the ladder in the test is written from the published rule string rather than from the code. It is
kept honest by two companions: `test_the_verdict_moves_when_the_level_it_reads_moves`, which replaces the
percentile function and requires the verdict to change with it (a verdict that could not move is not derived
from anything), and the pool-wide check below, which asks no question about the implementation at all.

**A universal over the stored pool, with a non-vacuity guard.** `test_no_row_in_the_pool_is_told_to_sign_now_
while_short_for_the_role_asked` walks every twentieth player for two roles and asserts that no player with a
negative `mean_gap` is ever told `sign now`. It fails if the rule drifts back, and it also fails if the world
changes so that no short player is in the sample — the guard `assert short >= 3` is there because a universal
over an empty sample is a green light, not a proof.

## 5. §24's own flow, and where this tier stops

The report reads: the stored player pool, §23's requirements vocabulary and role fit, §22's valuation, club
need and tactical fit. It does not: call a model, write a sentence about a player's character, rank
unmeasured capacity, or attempt a transfer. `limitations()` prints six lines saying exactly that, inside every
report, and `recommendation.note` states that no model was asked what it thinks.

The §24-adjacent web step has since landed: `/scout` renders these thirteen fields from this route rather than
restating them, and its own evidence walk is [docs/M7_SCOUT_WEB_VERIFICATION.md](M7_SCOUT_WEB_VERIFICATION.md).

## 6. The gate that ships with the route

`GET /api/v1/scout/rules` now answers a `report` block — the thirteen fields, the six companion keys, the four
verdicts, the ready flag, the counts, the limitations and the two refusal codes — and its `integrity.problems`
list is the report's own structure gate run live against the stored pool:

* every §24 field present, and no top-level key that is neither a §24 field nor a published companion;
* the report's `fields` line equal to `REPORT_FIELDS`;
* for each of the four groups, the printed `mean` equal to the mean of the `attributes` map printed beside it
  (within 0.01), and `measured` equal to the number of keys printed;
* the verdict inside the published `VERDICTS`, with a non-empty `decided_by`.

The group checks re-average from the payload's own figures, which is what makes the gate worth publishing:
a renamed line or a mean that drifted from the attributes it claims to summarize becomes a sentence a caller
can read, in the response, rather than a passing test.

`GET /api/v1/capabilities` carries `m7_scout_report` — ready, the field list and the counts. The structure
gate deliberately is not recomputed there: `/capabilities` is hit by pages on load, while `/scout/rules` is
where a reader is about to type.

## 7. Measured

Figures from the seeded dev world (300 stored players) on this tree.

* **the ladder answers, and the answer is not one verdict.** 120 randomly sampled players (fixed seed):
  *with no role asked* — `sign now` 67, `pass` 40, `develop` 13, `monitor` 0. *With `role="RW"` asked* —
  `monitor` 50, `pass` 40, `develop` 30, `sign now` 0. The second row is the interesting one: naming a role
  moved 67 "sign now" answers to `monitor` and `develop`, because `role_fit.mean_gap` became negative for
  players short in one of the three demands. A report that printed a verdict independent of the figures above
  it could not change its mind that completely on one extra input. (`monitor` is absent without a role because
  the ladder only reaches it when a fit was asked for and is negative; `sign now` is absent with a role because
  a winger-shaped demand set is not met by most of a 300-player pool.)
* **cost per call.** `build_report` over the pool runs at ~46 ms per player, including a fresh `pool()` read per
  call. `report_problems` — one full report plus the re-derivation checks — is 78 ms; `GET /scout/rules` also
  runs §27's `comparison_problems` at 114 ms, so the rules endpoint carries ~190 ms of integrity work plus the
  search and vocabulary checks. It is rate-limited to 60 calls a minute and is not on a page-load path.
* **agreement between the report and the store.** For the player sampled, `current_level.agrees_with_stored` is
  true — `compute_overall` over the row's own attributes equals the stored `overall` column — and the group
  means equal an independent Python average over `ATTRIBUTES` in every sampled report; `missing` is empty for
  every generated row, since `ATTRIBUTES` lists twenty-seven keys across the four groups (9 technical, 6
  physical, 6 mental, 6 tactical) and every sampled generated row carries all twenty-seven.
* **tests.** `apps/api/tests/test_scout_report.py` — **60 items**, all 60 green on both database legs (the
  totals are in §8). The web tier that renders these thirteen fields is
  [docs/M7_SCOUT_WEB_VERIFICATION.md](M7_SCOUT_WEB_VERIFICATION.md).

## 8. Six defects planted, and what it took to catch the sixth

A mutation probe is the only honest answer to "do these tests test the arithmetic, or do they test that the
module ran?". `.scratch/mutate_report.py` plants one defect at a time in `report.py` — a single exact-string
edit, each anchored to appear exactly once — runs the module's own suite, then restores the file and checks the
text came back. Six defects, measured on this tree on 2026-09-25; five were caught on the first pass and the
sixth was not.

| Defect planted | Suite answer |
| --- | --- |
| a key the row does not carry is averaged as a zero | `1 failed, 58 passed` — `TestGroupScores::test_a_key_the_row_does_not_carry_is_named_rather_than_averaged_as_zero` |
| the percentile count drops the players sitting exactly on this row | `1 failed, 58 passed` — `TestCurrentLevel::test_the_percentile_is_a_count_taken_from_the_database` |
| the recommendation negates the role gap it quotes | `2 failed, 57 passed` — `test_no_row_in_the_pool_is_told_to_sign_now_while_short_for_the_role_asked`, on both the `[AM]` and `[RWB]` role pairs |
| `develop` fires for a past-peak age | `1 failed, 58 passed` — `test_the_verdict_follows_from_the_figures_this_report_published[quietest]` |
| the comparison deltas are `other - this` | `1 failed, 58 passed` — `TestComparison::test_the_deltas_are_this_minus_other_for_every_group` |
| the crowded-band factor needs nine players instead of four | **`59 passed` — survived** |

`report.py` was byte-identical to its own starting text after the run (`restored: True` on all six, and the
probe's closing line says the file is unchanged).

**The survivor is a coverage hole, not bad luck.** §24's `band_is_already_crowded` factor fires when the club a
career manages already stores at least four players in the band the candidate fills. Raising that to nine changed
nothing any test could see, for two reasons that compound: every risk assertion in the module builds its report
**without** a career — where `team_fit` is null, so the factor cannot fire on either side of the mutation — and the
three tests that do pass a career assert the need, the fit and the band *count*, never the factor list beside it.
The ladder-walking test compares the factors that fired against the ones it expects from the same row, and a row
with no career expects none. A threshold that no assertion reads is not a tested threshold, however many figures
around it are re-derived.

`TestRiskFactors::test_the_crowded_band_factor_turns_on_at_four_rows_in_the_band` closes it by sweeping counts
`0…8` through `_risk` with a `team_fit` built for the purpose, and asserting the factor turns on at exactly four
— plus that it names the count that raised it, that the sentence it prints says *four*, and that no team fit
asked for is no crowded band claimed. Re-running the surviving defect by hand against the new test: `1 passed`
in 39 s on the clean module, `1 failed` with `>= 9` planted, and the file back to `sha256 a3d1041a…` afterwards.

**Suite totals for this tree, measured 2026-09-25, both database legs:**

| leg | result |
| --- | --- |
| SQLite (default `python -m pytest`) | **729 passed, 1 skipped in 811.58 s** |
| PostgreSQL (`FOOTBALL_OS_TEST_DATABASE_URL=…54321/football_os_pytest`) | **729 passed, 1 skipped in 1045.72 s** |

730 items in all, of which the scout tier holds 233: `test_scout_search.py` 100 (§23's vocabulary, parser and
waterfall), `test_scout_report.py` 60 (§24, including the swept threshold this probe added), and
`test_scout_compare.py` 73 (§27). The contract in `docs/api/openapi.json` was compared against the running
server rather than trusted: 86 paths / 98 operations, byte-identical to the committed file.

**One red the PostgreSQL leg found on the way here, in this repo's own older work.** The first full PG run of this
tree printed `1 failed, 728 passed` — `tests/test_sim_ledger.py::TestTotalsAreTheRows::test_every_club_total_is_what_a_direct_count_of_the_rows_gives`
raised `KeyError: 'goal'`. Two fixtures at the sampled club had produced no goal, and the line indexed
`view["by_type"]["goal"]` outright while `by_type` is built only from the kinds that have rows. SQLite passed the
same run because its sampled club did score — a leg-dependent fact the test had silently assumed. The line now
asserts the pairing instead: the key appears exactly when the rows count it, and its figure is that count
(`("goal" in by_type) is (counted["goal"] > 0)`), which is both weaker than a claim about the world and stronger
as a claim about the ledger. That fix is committed separately from the scouting tiers.

**One tooling lesson, because it cost two dead runs.** `-o addopts=""` passed inside a *list* argv hands pytest
the two-character value `""`, which it reads as an empty path argument that matches every file: the module's
items became the whole suite's 729, and the first two probes looked like they had hung at 900 s when they had
only collected far more than they meant to. In a shell the quotes are eaten before pytest sees them; in a
subprocess argv they have to be absent in the first place (`-o addopts=`), and the probe now writes its output
to a file so a partial run is still readable.
