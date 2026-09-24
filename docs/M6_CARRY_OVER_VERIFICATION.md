# M6 §20 — a played round leaves a trace, and the next round reads it

Backend tier. Added 2026-09-24. Everything below was run on this machine against the code in this
commit; nothing here is a plan or an aspiration.

## 1. The defect this closes

Career Mode decided every round from the same two things: the club's stored squad rows and each
player's stored `form`, which the world generator wrote once when the world was built and nothing
after that ever updated. So

* a career that had played eight matches fielded a side exactly as fresh as one that had played none;
* the 100 rows in `real_training_sessions`, each carrying a `load_units` figure, reached nothing but a
  player's own page — the engine never looked at them;
* spec §20's "squad and training status carry over between matches" was, up to now, unimplemented in
  the one place it matters: the numbers the engine plays with.

## 2. Three rules, and why each is a rule rather than a number

1. **The trace is a row, not a re-derivation.** `career_appearances` (migration `0013`) holds one row
   per player the engine selected for a career's side, per round, with the minutes he was on the pitch
   for. The alternative — recomputing load out of `sim_matches.report` on request — would make the load
   vanish the moment its owner deleted the match, and the API already allows that. A round's minutes are
   the match length it was played at because the engine selects an eleven and models no substitutions:
   no row here claims a minute count the engine never decided.
2. **Load is a window with a decay, and the arithmetic is published.** The three rounds before the one
   being played count, each at half the weight of the round before it, so the figure is dominated by the
   last fixture — which is what "carry over between matches" is about — without forgetting the two
   before it. A full window holds `90 × (1 + 0.5 + 0.25) = 157.5` load units and that, not one match, is
   the denominator: a saturated starter reads as 1.0 of the scale rather than as 1.75 of a match.
3. **Training is a reserve, not a bonus track.** A player's own sessions in `real_training_sessions` give
   back part of the load his minutes put on him — at most 0.15 of condition, complete at 1200 load units
   on file. A player the world holds no session for is at 0 reserve, which is his minutes alone rather
   than a penalty for living in a world nobody trained him in.

`condition = 1 − 0.45·(load ÷ 157.5) + reserve`, clipped to 0.60–1.00. The clipping is not decorative: an
untrained starter with a full window is at 0.55 raw and the floor lifts him to 0.60, while the same
starter with a complete reserve is at 0.70, inside both bounds.

## 3. How a condition figure reaches an engine whose digests are frozen

This was the design constraint, and it is worth stating plainly because it decided the shape of the
feature. `report["model"]["coefficients"]` and every side's `factors` are hashed into
`sim_matches.digest`. Adding a coefficient, or editing a published expression in `FACTOR_EXPRESSIONS`,
would make every match already stored in every database fail `replay_is_identical` — the engine would
appear to have changed when only its reporting changed.

So carry-over enters through a door that already exists:

* `SquadOverlay` — the same object that applies a career's transfers to a club's squad rows — gained a
  `condition: Mapping[str, float]`. `squad_as_of` fills it from `carry_over.condition_map` for the round
  being built.
* `team_profile` folds it into the side's **form index**: each selected player's stored form is
  rescaled as before, then weighted by `0.5 + 0.5·condition`, and the eleven's mean is taken. The
  engine's fatigue term already reads that index ("a lower-form side fades further"), so a tired side is
  not given a new multiplier — it is measured as what the model already says a lower form is.
* **Identity when there is no trace.** With an empty condition map every weight is 1 and the mean is the
  number this function has always returned, bit for bit. That covers every club nobody manages, a
  career's first round, and every match stored before this feature existed.
* The two new Metrics (`condition_index`, `players_carrying_load`) are emitted **only** for a side that
  actually carries load, so no previously stored factor list is rewritten.

`SideProfile.selected` — the eleven with its player ids, slugs, positions and bands — is new and
deliberately absent from `to_dict()`. The report's `lineup` stays names because that is what a stored
digest covers; the ids are for the caller that has to write one row per player rather than match a
surname out of a report, and surnames repeat in a generated world.

## 4. The refusal that keeps the history honest

Two guards in `play_round` and `replay_is_identical` exist because this feature writes rows derived from
a report:

* **Attribution is checked before it is stored.** After a round is played, the career layer rebuilds the
  profile it used and compares `selected`'s names against the names in that match's own report. On any
  disagreement it records nothing for that round. A mis-attributed trace would blame the wrong eleven
  for the load, and no page can tell that after the fact.
* **A round whose trace is gone is a refusal, not a re-derivation.** `replay_is_identical` already
  refused when the rebuilt eleven differed from the one the report names. It now also compares each of
  the six indices the report printed against the rebuilt side, and refuses with both figures named
  (`form index (0.937 on file, 0.874 rebuilt)`) when they move. Without this, deleting a round's trace
  rows would make the *next* round's replay come out differently and the digest mismatch would be
  reported as though the engine disagreed with itself.

The reason text names the two things that can move an index — a training applied after the match, a
trace row deleted since — without claiming either happened, because the replay cannot tell them apart.

## 5. What the API now publishes

`career_view` carries a `carry_over` block, summed from `career_appearances` and
`real_training_sessions` on the request, in the same discipline as the record and the budget:

| field | what it is |
| --- | --- |
| `rounds_played`, `rounds_traced`, `untraced_rounds` | a round the career played but left no rows for is named as a hole, not counted as a rest |
| `appearances`, `players_traced`, `last_traced_round` | the size of the ledger |
| `window_rounds`, `decay_per_round`, `condition_floor` | the window and bound the arithmetic used |
| `carrying_load`, `mean_condition_of_last_xi`, `training_records_found` | what the next round will read |
| `most_loaded[]` | up to eleven players with `load_units`, `training_load_units` and `condition`, ranked by load |
| `rows[]` | the last thirty trace rows, each with its round, side, minutes and opponent |
| `load_formula`, `reserve_formula`, `condition_formula`, `form_formula` | the four expressions, in the same words the engine's factors print |

`GET /api/v1/careers/{slug}` returns it; the match report carries the two new factors on any side that
had load. `limitations()["carry_over"]` states what this still does not do.

## 6. Not claimed

* **Growth does not carry over.** `progression.py` can rewrite a player's stored `form` after a training
  session, and that reaches the next round only because it changes the row, not because this module
  moves it. A career's own progression is a separate rule (§20's "player growth" clause stays open).
* **Nothing rests a tired player.** No manager action can drop or rest a player; the engine selects the
  eleven from the squad and load cannot change that choice. A tired side is a lower form index, nothing
  more.
* **No half-times, no substitutions.** Minutes are the fixture's length for every selected player
  because that is the only thing the engine actually decided.
* **An unmanaged club is untouched.** Its condition map is empty by construction; a career playing
  *against* a club does not tire that club's players for their own matches — the trace is keyed to the
  career that wrote it.
* **Selections made by a challenge or a scout are outside this**: the trace records who was selected,
  not why.

## 7. Reproduce

```bash
cd apps/api
python -m ruff format app tests && python -m ruff check app
python -m mypy app                      # 75 files
alembic upgrade head && alembic check   # 0013 is the head; no new operations
python -m pytest -q tests/test_carry_over.py
python -m pytest -q                                       # SQLite leg
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest -q                                     # PostgreSQL leg, its own per-run database
```

The new module's tests are the ones to read first: `tests/test_carry_over.py` is 17 tests in four
classes — the ledger's rows, the condition reaching the next round, the published arithmetic against the
numbers, and the view's own sums — and the last class includes the two refusals in §4, each reached by
deleting a round's trace and asking the engine what it makes of it now.

## 8. The panel on the season page, walked in a browser

`apps/web/app/career/[slug]/page.tsx` renders the §5 block as a panel between the fixture list and the
table: the rounds-played/rounds-traced pair, the window and its capacity, the mean condition of the last
eleven and the trace count, then one row per player carrying load — position, rounds in the window,
minutes with their unit, `load_units`, `training_load_units`, and `condition` to three places, badged
`at the floor` when it sits on the published bound. Below it the module's own limiter and the condition
disclaimer. The match report at `/simulate/{slug}` shows the two factors §3 emitted, and the walk
checks that the report's two formula sentences are the *same strings* the season page printed — a
reader who follows the link should not meet a second dialect.

`apps/web/scripts/qa-carry.mjs` drives it against a production build, 45/45 on 2026-09-24:

| what the walk insists on | what it found |
| --- | --- |
| it plays both rounds through the page's own button, never through `POST /play` | round 1 and round 2 each announce themselves, and the fixture list grows |
| the eleven rows the API traces are the eleven rows the page prints | 11 rows after one round, 22 trace rows for the same 11 players after two |
| every printed condition is re-derived from the constants the page itself publishes | `depth 0.45 · window 157.5 · reserve 0.15/1200 · floor 0.6` scraped out of the sentence, then `0.743 vs 0.7429` row by row |
| the window decays rather than doubles | `load 90 → 135`, `condition 0.7429 → 0.614`, nobody on the floor after one match |
| the panel's mean is the table's own mean | `mean_condition_of_last_xi = 0.7489` against the eleven derived rows |
| the units are the server's, not the page's | `match minutes`, compared with `rows[].minutes_units` |
| a phone still gets the table | 11 rows and its headers at 375×812 |
| nothing is blamed on the engine when the ledger has a hole | `untraced_rounds = []`, and the server's own re-check sentence is printed verbatim (`2 of 2 … all agree`) |

**Three of the walk's first failures were the walk's, not the page's**, and they are worth writing down
because each is a way a browser check can lie while the code is correct:

* `careers/options` publishes no competition field, so the walk's first club filter tested a property
  that does not exist and found nothing. It now opens careers from the weakest club upward and asks the
  career view whether a round is actually scheduled — the honest question — and it takes the budget off
  `budget_ceiling` rather than hard-coding 50,000,000, which that ceiling (10,000,000) would have
  refused.
* `CareerTools` calls `router.refresh()` *after* the play response lands, so scraping at the
  `Round 1 played:` line read the pre-round server render: no load rows, `0 / 0`. The row-wise checks
  that walked over an empty scrape **passed vacuously** — `every(...)` is true of nothing — which is the
  same fake green a `sum` over an empty list gives. The walk now waits for `Next up: round 2`, a
  sentence only a re-render can produce, and each per-row check carries its own row count in its
  condition.
* eyebrows and table headers are upper-cased by the stylesheet, and `innerText` reports what is painted
  rather than what was written. `has(body, 'carry load into round 2')` and the `dt` label lookup were
  comparing against text the browser never displays; both now match with the case taken out.

One figure is deliberately *not* corrected: the report prints the traced-player count as `11.00 count`.
Every metric on this platform goes through one formatter, three other `count` metrics predate this
module, and their labels are frozen into `sim_matches.digest` — so the walk asserts the string the page
prints instead of asking for a number it would have to special-case to get.

```bash
cd apps/web
NEXT_DIST_DIR=.next-carry npm run build                     # the walk runs a production build
NEXT_DIST_DIR=.next-carry API_INTERNAL_URL=http://127.0.0.1:8734 npx next start -p 3214
QA_BASE=http://127.0.0.1:3214 node scripts/qa-carry.mjs     # 45/45; PNGs to docs/screenshots/
```

Do not run this at the same time as `pytest`: both write careers into the same development database.
