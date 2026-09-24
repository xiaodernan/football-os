# M7 item 23 — a request in prose, and the pool it cuts

§23 asks for an "AI Scout" that can be told *find me a left-footed under-22 who can play inverted
full-back, budget €20m* and answer with players. The interesting half of that sentence is not the players;
it is what the system does with the words it does not have. This module is the whole of the answer up to
"here are the rows, and here is the exact sequence of cuts that produced them" — a vocabulary, a parser,
and a search that walks a pool down one stated phrase at a time.

Backend: `apps/api/app/services/scouting/{requirements,search}.py` (new) with `app/api/v1/scout.py`
(wired into `app/main.py`), and one capability block at `/api/v1/capabilities` in `app/api/v1/meta.py`.
No migration and no model change: §23 reads `players`, `attributes`, `player_positions` and §22's
`market` module, and writes nothing.
Tests: `apps/api/tests/test_scout_search.py` — 100 test items (64 functions, one third of them
parametrized) in nine classes.
Surface: none yet. `/scout` is the next module; this one is the API tier it will read from.

---

## 1. What the spec's own sentence produced

The example request from §23 was run verbatim against a freshly generated world (300 players over 20
clubs), and this is what came back:

```
request:  找一个 22 岁以下、左脚、能踢 Inverted Fullback、预算 €20m 的球员
parsed    age_max    22          from '22 岁以下'      [parsed]
parsed    foot       left        from '左脚'           [parsed]
parsed    fee_max    20000000    from '预算 €20m'      [parsed]
refused   not_in_vocabulary      'Inverted Fullback' -> ['role LB', 'role LW', 'role RB']
assumed   the fee '预算 €20m' was read as 20,000,000 career credits
connectors = ['找一个', '能踢', '的', '球员']    unaccounted = []

waterfall  300 -> 88  '22 岁以下'
            88 -> 29  '左脚'
            29 -> 29  '预算 €20m'
asked_for  3 filters, 1 refused phrase, 5 candidates returned of 29 matches
```

Three things in that output are the module's contract rather than its incidental behaviour.

The refusal is **carried in the same response as the candidates**, not returned instead of them: a user
who asked for one thing and got another should see both the other thing and the words that say which part
was missing. `test_the_refused_phrase_survives_the_search_that_ignored_it` holds it there.

`unaccounted = []` is the parser's own audit. Every span of the request is either a requirement, a
connector this vocabulary knows, or *unaccounted* — and an unaccounted span is a bug report, not a shrug.
Sixteen sentences are parametrized against that assertion — §23's own example in both of this project's
languages, and fifteen more that each reach a different family of the vocabulary (roles, bands, sorts,
Chinese fee phrasing, the two-language foot shapes) — so "the parser silently ignored a clause" cannot be
added without a red test.

The `assumed` line exists because a bare number next to 预算 is not self-describing: €20m and 20,000,000
are the same figure here only because every budget in this project is career credits, and the parser says
that out loud instead of letting the equality be inferred from a screenshot.

## 2. Two rules this module holds to

* **A phrase is refused with the vocabulary beside it, never guessed at.** `Inverted Fullback` is not a
  role in this build, and the parser does not pick the nearest one — `not_in_vocabulary` names the phrase,
  and `suggests` lists what the vocabulary does hold (`role LB`, `role LW`, `role RB`, by shared token).
  The same rule holds for a misspelt attribute (`dribble at least 70` → `unknown_attribute`, suggests
  `dribbling`) and for a code nobody staffs (`RM` → `unstaffed_position`, because `ROLE_POSITIONS` has no
  rows for it and the `BAND_NAMES_READ_AS_POSITIONS` guard would otherwise let it read as a band).
* **A number in the response is a number a reader can recompute.** The waterfall's `rows_in`/`rows_out`
  per step, the `cut` derived from them, the `valuation` printed beside a candidate, the `mean_gap` inside
  `role_fit`, and the `fit` inside a career-dependent search are all published with the rule that made
  them (`waterfall_rule`, `RANK_RULE`, `FIT_FORMULA`, per-step `rule`). So every one of them is tested
  against a *second, different* reading: the age and foot steps are checked against a SQL `COUNT` over
  `players`; the band step against a plain ORM predicate walk; `valuation` against `market.valuation(row)`
  re-run per candidate; `role_fit` against `roles.ROLE_DEMANDS` and the stored attributes with `gap`
  recomputed; `tactical_fit` against `market.tactical_fit` called directly on the same rows. None of them
  is checked by asking the module to explain itself.

`sort` is refused the same way a phrase is. `need_fit` asks which band the club is weakest in, which is a
question about a squad a *career* owns; with no `career_slug` in the body it raises
`need_fit_needs_career` rather than sorting by something else and calling it need fit. With a career it is
measured: `{attack 0.293, defence 0.275, keeper 0.285, midfield 0.247}` says that club's midfield is its
thinnest band, and the candidates come back ranked by how well they fill exactly that gap, with the
formula riding along.

## 3. Where two vocabularies disagree, both are printed

This project has two band word-lists and they do not match: `simulation/profile.BANDS` keys the four bands
the match engine measures (`keeper, defence, midfield, attack`) while `tactics/roles.BANDS` keys the
board's zones (`goalkeeper, defensive, midfield, attacking`). §23's `band` requirement is the profile's,
because that is the vocabulary the pool is actually filterable by — and a role's own board zone is
published separately as `role_fit.board_band`, so a reader who came for the tactics meaning of "midfield"
is not quietly given the engine's.

The same care goes to the words that could belong to two kinds. `left back` is a position (`LB`), not a
foot, and the region-priority rule that resolves it is tested directly (`number ten` → `position CAM`,
`test_a_shared_word_resolves_to_the_narrower_claim_and_says_so`). Foot detection runs before
position detection precisely because `两只脚` contains a foot word; and `two-footed` — which was being
refused until the test suite asked for it — now reads as `foot = both`, since `both` is a stored value.

`role_fit` never cuts. A candidate who is short in 2 of 3 of a role's tactical demands is still listed for
that role, with `verdict` and `shortfalls` naming the gap, because "can they be listed for RWB" and "are
they good at RWB" are different questions and only the first one is a filter in this build.

## 4. What the tests corrected in the code, not in themselves

Three of the failures below were real defects that the first version of the module shipped with, found by
writing the assertion a reader would want rather than by matching the implementation:

| Symptom | Cause | Fix |
| --- | --- | --- |
| `two-footed` came back `not_in_vocabulary` | `_foot_value` tested `both`/`两只脚`/`双脚`/`两脚` and no English two-footed phrasing | `two` joins the set, so `foot = both` |
| `source: "parsed"` on every requirement from a JSON body of stated fields | the builders hard-coded the label they needed for sentence parsing | a `source` parameter threaded from `stated_requirements`, and a test that pins `["stated"] * n` against `["parsed"] * n` |
| `positions: ["CF"]` did not raise | it is not supposed to — `CF` is an authored alias of `ST`; the genuinely unstaffed codes are `LM`/`RM` | the test moved to where the real rule is, and the `CF → ST` alias got its own named test |

Two more were caught by the gates rather than the suite: `Step.detail` was annotated `field: str` inside a
dataclass and so shadowed the imported `dataclasses.field` (mypy: *`"str" not callable`), and the
`need_fit` sort key closed over a `need` that mypy could only see as `dict | None` at the call site — both
fixed at the source instead of with a cast.

`ruff check tests` was also red at `HEAD` in a file this module inherited (`test_carry_over.py`: an unused
import, a bare `zip`, and an unused local). Those three are fixed here too, since the house gate is
`ruff check app tests seed.py migrations` and a milestone that leaves it red has not landed.

## 5. §23's own flow, and where this tier stops

§23 draws the pipeline as `Search → Filter → Retrieve → Compare → Tactical Fit → Generate Scout Report`.
Four of those six run here, and the response says which four by naming each stage's arithmetic:

| stage | where it is answered | what is published |
| --- | --- | --- |
| Search | `parse_requirements` / `stated_requirements` | one requirement per understood phrase, each with the phrase that produced it |
| Filter | the waterfall in `search` | `rows_in`, `rows_out`, `cut` and the `rule` per step, in the order the request stated them |
| Retrieve | `pool` + `_meets` | every stored player is examined (`rows_examined`), and each returned candidate carries the measurement that answered each phrase |
| Tactical Fit | `role_fit`, and `market.tactical_fit` for a career's `need_fit` | the role's board demands against stored attributes; the club's weakest band and the fit formula beside the ranking |
| Compare | not here | the seven published sortings put candidates next to each other, but no two-player comparison is made |
| Generate Scout Report | not here | §24's twelve structured fields, and they are the next module |

`Compare` and `Generate Scout Report` are deliberately absent rather than stubbed: a report whose Risk,
Cost and Recommendation lines were prose written by this build would be the "没有依据的天赋" the spec
forbids, which is the same reason `search()` refuses to invent a band when asked for `need_fit` without a
career.

## 6. The three doors, and which questions each may answer

| route | auth | reads rows | what a caller learns |
| --- | --- | --- | --- |
| `GET /api/v1/scout/rules` | public | counts only | the whole vocabulary, both band word-lists, the money reading, the seven sortings, the limits, the six limitation sentences, one worked `example_parse`, and an `integrity` block that publishes the parser's self-agreement checks (`clean: true`) instead of keeping them in a test file |
| `POST /api/v1/scout/parse` | public | none | what a sentence *would* do: `search_would_apply` counts the filters, `search_would_rank_by` the sorting, and when nothing was filtered the note says a search over it would only rank the pool |
| `POST /api/v1/scout/search` | account | every stored player | the waterfall, the candidates, the refusals, `asked_for`, and `duplicate_fields` |

Two of those columns are load-bearing rather than incidental.

`/parse` is public because it is pure — no row is touched, so a page can show a manager what their words
would cut before they sign in — and a test asserts that the search table really is not read there. The
split is checked from the other side too: `/search` answers 401 without an account.

`duplicate_fields` is the answer to a request where the sentence and the stated body speak about the same
kind (`query: "under 22"` with `max_age: 19`). Nothing is resolved silently: both cuts apply, the pool
narrows, and the response names both phrases with the rule that says why neither one overrules the other
(`test_a_stated_field_and_a_sentence_both_cut_and_say_so`). A career that is not the caller's answers 404
like every other foreign row in this project — never 403, which would confirm the slug exists — and a
career whose club cannot be resolved answers 404 with `no_club` while any other market refusal is a 409,
because "this club is not on the market" and "this club has no squad to search against" are different
kinds of dead end.

## 7. Measured

* 100 test items (64 functions; the sentence table and the sorting table are parametrized) in nine classes.
* The scout module on its own: `python -m pytest tests/test_scout_search.py` → **99 passed, 1 skipped in
  48.00s**. The skip is `test_a_probe_with_no_rows_says_so_instead_of_passing`, which runs against a pool
  emptied by a `monkeypatch` and asserts the module notices the emptiness instead of passing on it.
* API gates: `ruff check app tests seed.py migrations` (All checks passed!), `mypy app` (no issues in 82
  source files), `ruff format` (83 files left unchanged), `alembic check` — no new upgrade operations,
  because §23 writes nothing and needs no table.
* OpenAPI: `docs/api/openapi.json` regenerated from a private uvicorn on port 8737 over a throwaway SQLite
  file: **281 lines added, 0 removed**, and the additions are exactly `GET /api/v1/scout/rules`,
  `POST /api/v1/scout/parse`, `POST /api/v1/scout/search`. The server was killed after the export.
* The figures in §1 and §2 come from two throwaway probes run against a freshly generated world on a
  temporary database (`.scratch/probe_scout.py`, `.scratch/probe_parse.py`), and are deleted at the end of
  the milestone, so the tables above are the record.

### 7.1 Full API suite, both engines

| leg | result | wall |
| --- | --- | --- |
| SQLite | **597 passed, 1 skipped** | 1518.49s |
| PostgreSQL | **597 passed, 1 skipped** | 2505.88s |

Both legs were run against the same working tree, one after the other, and gave the same counts item for
item — which is the point of running them separately: a search that sorted differently on the two engines,
or read a JSON column differently, would have shown up as a difference in these two numbers.

The baseline before this module was 498 passed. The difference is §23's 100 items plus two test functions a
sibling session has added to `test_challenges.py` and `test_world.py` and not yet committed — they are in
the working tree these runs read. That is stated rather than smoothed over: the figure above is the tree as
it stands, not the commit as it lands.

### 7.2 Defects planted, and what each one made red

Not measured yet, and this section says so rather than guessing. The probe is written (`.scratch/mutate_scout.py`:
one exact-string edit at a time, the file restored and its sha re-verified after each run, the failing test names
printed), and it plants these five:

| defect | the claim it would test |
| --- | --- |
| a waterfall step reports its own cut as zero | §1's `300 → 88 → 29 → 29` is recomputable, so a step that lies about its own output must make a test red |
| the foot filter stops cutting the pool | the left-foot cut in §1 actually removes rows rather than being decoration |
| the refused phrases are dropped from the payload | §6's rule that a search never hides what it could not understand |
| an `age ≤ 22` cut excludes the players who are exactly 22 | the boundary of §23's own example sentence |
| a stated position is published as if it came from the sentence | the stated/parsed labelling §4 records as a defect this project already corrected |

The first run of the first mutation was starved by a loaded machine — the suite had not finished when the probe
was stopped twelve minutes in — so no mutation produced a result, and the mutated line was restored by hand and
the file re-audited against all five anchors before this document was committed. The numbers belong here once the
run completes; until then the honest reading is that §7.2 is a plan, not an experiment.



