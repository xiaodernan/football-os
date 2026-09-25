# M7 item 27 — a pair compared over ten dimensions, with no number allowed to decide it

§27 asks for `Compare Player A vs Player B` across ten named dimensions and then prints the one thing not to
do: 避免单一 Overall 分数决定一切 — avoid a single overall rating deciding everything. That second half is the
harder requirement, because a comparison payload is the natural home for a summary number: a reader asks
"who is better", and a server that wants to be helpful answers in one field. This tier answers differently.
`app/services/scouting/compare.py` forms **47 measures across 10 dimensions** and returns no field that ranks
the pair as a whole. `POST /api/v1/scout/compare` is the door; `GET /api/v1/scout/rules` carries the shape and
the integrity check.

## 1. The ten dimensions, and where each measure is read from

| dimension | measures | read from | what the measures are |
|---|---|---|---|
| `technical` | 9 | `real_players.attributes` | one measure per key `app.models.ATTRIBUTES["technical"]` lists |
| `physical` | 6 | the same row | one per key in that group |
| `mental` | 6 | the same row | one per key in that group |
| `tactical` | 6 | the same row | one per key in that group |
| `production` | 3 | `real_player_match_stats` | goals, assists and shots on target per 90 minutes of the lines behind the pair |
| `possession` | 2 | the same lines | `sum(passes_accurate) / sum(passes)`, and key passes per 90 |
| `defensive` | 3 | the same lines | tackles, interceptions and duels won per 90 |
| `progression` | 4 | row **and** lines | `long_passing`, `passing`, `vision`, plus key passes per 90 |
| `age` | 4 | the same row | `age` (unranked), `potential - overall`, §22's `age_curve`, `years_past_peak` |
| `context` | 4 | row, club, competition | club `overall`, competition name (unranked), competition tier, starts per appearance |

27 of those 47 measures are attribute keys, taken one at a time and **never averaged into a group score for
the pair** — the group mean is §24's job inside a single-player report, and using it here would have turned the
four attribute dimensions back into four numbers that a reader adds up in their head. Every event measure names
the SQL that formed it (`sum(goals) * 90 / sum(minutes)` over each side's lines) inside its own `source` field,
so a figure and its recipe travel together.

## 2. The no-single-score rule, and the two first-class non-answers

`NO_WINNER_NOTE` is shipped inside every payload rather than living in this file, because the first thing a
reader does with a comparison is look for the winner:

> this payload has no overall rating, no winner score and no weighted index: each dimension is called `left`,
> `right`, `even`, `split` or `unresolved` from the measures printed under it, and a reader who wants one number
> to decide the pair has to bring that number themselves

Three mechanisms keep that sentence true:

* **a measure decides its own direction.** `direction` is `higher_is_greater`, `lower_is_greater` or `none`.
  Competition tier is `lower_is_greater` because 1 is the top; `years_past_peak` likewise. Two measures print
  `direction: none` — `age` and `competition_name` — and a measure that says it cannot be ranked is published
  with `leader: not_scorable` and `delta: null`. A two-year gap deciding a pair by itself is exactly the single
  score §27 rejects, wearing a different hat.
* **a dimension has to answer for its measures.** `left` or `right` only when that side wins *every* scorable
  measure; `even` when all tie; **`split`** when the two sides win different measures; **`unresolved`** when
  none is scorable. `split` is not a failure to find an answer — it is the answer, and it is the most common
  one in this world (see §7).
* **nothing in the payload is a verdict.** `overall_line` prints the two stored `overall` columns side by side
  with their difference, and its `note` says plainly that this is not the payload's verdict. `counts` reports
  how many measures and dimensions fell to each leader — a tally of the shape of the answer, not a score. There
  is no `winner`, `score`, `index`, `rating` or `combined` key, and the shipped gate fails if one appears.

An unknown is a fact about a row, not a zero: an attribute key a row does not carry lists which side is
missing it, and any rate for a side with no stored minutes is `unknown`. `_per_90` returns `None` rather than
`0.0` when the denominator is absent, which is the same refusal §24 applies to a group mean.

## 3. Three refusals, and the difference between them

| situation | answer | why it answers that way |
|---|---|---|
| `{"left": "not-a-player", "right": ...}` | `404` `{"code":"no_such_player", ...,"players_in_pool":N}` | the row genuinely is not in the pool; the count beside it tells the caller whether the pool itself is empty |
| `{"left": x, "right": x}` (same row, by slug or by id) | `422` `{"code":"same_player", ...}` | every measure would print an `even` line, which is a payload that looks measured and says nothing |
| `{"left": 12}` (missing field, or an over-long string) | `422` house envelope `{"error":{"code":"validation_error",...}}` | the request body itself was not well-formed, which is a different layer from a domain refusal |
| no account | `401` | the route reads the stored player table, so it sits behind the same wall as §23's search and §24's report |

A pair can be given by slug or by id, and both are resolved against the **same pool list** the search built —
there is no second read of `real_players` that could disagree with the first.

## 4. What the tests corrected in the code, not in themselves

Two findings here were not test failures but *gate* failures, and both went into the shipped module:

* **the integrity gate was auditing itself.** `comparison_problems` first recomputed each dimension's leader by
  calling `_leader_for` — the function under audit. Two mutation-style tests that rewrote a `leader` value after
  the figures were formed passed anyway, because `counts`, the dimension leader and the per-measure leader were
  all derived from the same column, so a rewritten value moved all three together. The fix walks the ladder
  **again inside the gate**, and adds a second, independent copy of the answer to check against: `delta` is
  printed per measure, and a non-zero delta points at a side all by itself. `leads left while the delta it
  prints points right` is now a sentence the gate can emit. The two tests were then rewritten to say honestly
  which check is load-bearing (a `direction: none` measure that ranks is caught by the direction rule, not by
  the ladder).
* **a fixture assumption that measurement falsified.** The tests originally derived an "unobserved" side from
  the database, assuming the seeded world contains players with no stat lines. It does not: `players_without_lines`
  is **0**, every one of the 300 stored players has lines. A test built on that assumption would have been
  describing a world this project does not have. It was replaced by (a) a test that records the real fact — the
  seeded world writes a line for every player — and (b) two tests that patch `_stat_totals` with production's
  exact shape to produce `unknown` and `unresolved`, which is the only honest way to reach those branches here.

One more was a harness bug rather than a design bug: running `TestComparisonIntegrityGate` alone failed with
"the stored player pool has fewer than two rows", because the module-scoped `world` fixture was never requested
by that subset. Both scout test files now take `def session(world)`, so a subset run seeds first.

## 5. §27's own flow, and where this tier stops

§27's list also asks for a saved shortlist and for a comparison that feeds a transfer decision. The second is not
here, and the first is not here *in this tier* — both gaps are stated rather than hidden:

* **this tier stores nothing.** §27 adds no table and no migration; a comparison is computed from two stored rows
  on the request that asks for one. §23's shortlist — the saved list §27's flow points at — landed beside it in
  migration `0015`, and it stores membership and the manager's words rather than any of these measures
  ([docs/M7_SHORTLIST_VERIFICATION.md](M7_SHORTLIST_VERIFICATION.md)).
* **no offer is made.** A comparison reads §22's valuation through `asking_fee` on each brief, but it does not
  touch the market: no listing is created, no budget moves. `limitations()` says so.
* **Progression is thinner than the other three event dimensions, and says which parts came from where.** This
  world's stat lines carry no progressive carries or field-progression events, so inventing a "progression
  score" from passes alone would have been the unevidenced number §24 forbids. `PROGRESSION_RULE` is published
  in the payload and names the four measures and their two sources.
* **no model call.** No prose, no opinion, no "character" reading — the same line §24 draws, restated in
  `limitations()` because a feature called AI Comparison invites the expectation.

## 6. The gate that ships with the route

`comparison_problems(session)` builds a real pair out of the stored pool and checks the payload against §27's
own claims before `/api/v1/scout/rules` is allowed to report `clean: true`:

* the ten dimensions are present **in the order the spec prints them**, and none is empty;
* each dimension's published `counts` equal a recount over its printed measures;
* each dimension's `leader` equals the ladder walked **again** over those measures — not the value the module
  computed for itself;
* every measure's `leader` is inside the published `LEADERS` set; a `direction: none` measure must be
  `not_scorable`; a measure with both sides present may not call itself `unknown`;
* every `delta` equals its own `left - right`, and a non-zero delta must point at the same side the measure
  claims to lead;
* the payload has no `winner` / `score` / `overall_score` / `index` / `rating` / `combined` key;
* `counts.measures` equals the measures actually printed;
* asking for a player against themself raises `same_player` rather than returning a table of `even` lines.

`comparison_ready(db)` and `comparison_counts(db)` ride on `GET /api/v1/capabilities` under
`m7_player_comparison` — ready means *two* rows exist, because one is not a pair. The dimension-level gate
stays on `/scout/rules`, which is the page a reader consults about shape, not the route every page hits on
load.

## 7. Measured

Figures below come from the seeded dev world (300 stored players) on this tree, plus the two test legs.

* **47 measures per pair** (9 + 6 + 6 + 6 attributes, 3 + 2 + 3 event rates, 4 progression, 4 age, 4 context);
  `measures_total` printed by the payload matches the sum over its own dimensions, which the gate asserts.
* **`split` is the ordinary answer, not the exception.** Across 50 pairs (10 dimensions each, 500 dimension
  verdicts) the leaders distributed: `split` 209, `left` 144, `right` 137, `even` 10, `unresolved` 0. Two of
  ten dimensions (`defensive`, `progression`) split on more than half those pairs, and `technical` split on 26
  of 50 — the attribute groups disagree one key at a time far more often than one side wins all nine keys. No
  dimension in that sample reached `unresolved`, because a pair with lines always leaves something scorable —
  `unresolved` is reached in tests by patching the line totals away.
* **`totals_check.agree` is `true` for both sides** in every pair sampled: the stored season columns equal the
  sum of that player's `real_player_match_stats` lines, so the per-90 rates rest on lines that reconcile.
* **gate cost.** `comparison_problems` runs two `build_comparison` calls plus the recount ladder: 113.7 ms on
  this tree's dev world against `report_problems` at 78.2 ms. `GET /api/v1/scout/rules` therefore carries
  roughly 190 ms of integrity work on top of the search and vocabulary checks; it is rate-limited to 60 calls a
  minute and is not on a page load path.
* **tests.** `apps/api/tests/test_scout_compare.py` — 73 items covering the ten dimensions, the no-single-score
  rule, every figure re-derived by its own SQL, the three refusals, the gate itself, the route, and the round
  trip that flips a pair (every delta changes sign, every leader swaps side). Suite totals for both legs are in
  `docs/M7_SCOUT_REPORT_VERIFICATION.md` §7–§8, which covers the same commit, and the panel that renders these
  ten dimensions is walked in `docs/M7_SCOUT_WEB_VERIFICATION.md`.
