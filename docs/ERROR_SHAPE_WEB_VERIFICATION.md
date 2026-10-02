# §74's other half, gated: the shipped reader fed by the answers this API actually produces

**Closes open item 2 of 3 in `docs/SECURITY_AUTHORIZATION_VERIFICATION.md` §9, as `7aa6e91` published it** — that
section documents `2d3673e`, §74's API half, and the bullet is still open word-for-word in `50efc5e`'s own copy
of the file. The quote below is sliced out of `7aa6e91`'s blob by the script that writes this record, because a
first draft of it cited `2d3673e` for the sentence and *that* commit's copy has eight sections and no such
line — §9 and its open-items list arrived one commit later:

> The web half is ungated: `normalizeError`'s two branches are the reason the second shape stayed invisible, and
> `apps/web/**` is the concurrent run's. The API now answers where that reader looks; no test asserts the reader.

That sentence was true when it was written and is the reason this file exists. §74 changed the API's answer shape;
nothing in the repository asserted anything about the code that *reads* the answer — and that code is the reason the
wrong shape survived as long as it did.

## What the reader is, and what it must never do again

`normalizeError` in `apps/web/lib/api.ts` (85 lines, blob `04a4531` at the
plane this unit was measured against) is reached on every failed call the browser makes:
`browserFetch` → `if (!response.ok)` → `readError(response)` → `normalizeError(status, payload)`. It has four
decisions, and each one is a way a user can be handed a fallback string instead of the sentence the API already
wrote: unwrap a `detail` key or treat the whole payload as the refusal; answer a *string* detail as the message;
refuse an *array* detail rather than stringify it; and carry the keys that sit beside `code`/`message` (a fee, a
remaining count, a field list) through to the page.

## What landed

* `apps/web/fixtures/refusals.json` — 10 answer bodies, 3 from the installer's handlers,
  3 from named doors, 4 reader-tolerance payloads that no backend produces
  (each carries a `why`). The producer entries are not this file's inventions:
  `apps/api/tests/test_error_answer_shape.py` holds each one against the backend's own bytes — a handler entry is
  compared to `errors._answer(code, message, details)` verbatim, a door entry is found in the AST of the module it
  names (constant code + constant message, the same key-name set, and the status resolved from that call site).
* `apps/web/scripts/qa-error-shape.mjs` — 54 checks, 54 passing. It reads the shipped `apps/web/lib/api.ts` bytes, transpiles
  them with this repo's own `typescript`, imports the result through a `data:` URL, and compares the loaded export
  list with the `export` declarations parsed out of the same text, so "the reader was loaded" cannot mean "some
  reader was loaded". For every producer entry what the page must receive is *derived* from the payload (its code,
  its sentence, its figure keys) rather than written beside it. Only the tolerance entries carry an expected answer,
  because for those there is no backend source to derive from.
* `apps/api/tests/test_error_answer_shape.py` — +3 cases (`test_a_handler_fixture_is_what_the_wrapper_answers`, `test_a_door_fixture_is_a_literal_the_named_module_raises`, `test_the_two_halves_still_point_at_each_other`), collected as 13 inside
  a file of 11 test functions because one of 50efc5e's own cases is parametrized over the handler census.
  The third binds the two halves to
  each other: the web gate must still name the fixture and the reader, the reader must still unwrap a `detail` key
  and still route a failure through `readError`, and the tolerance entries must stay a small minority with a stated
  reason each. Without that case, either half can be rewritten out from under the other and stay green.

## Measured

| what | reading |
|------|---------|
| gate, in the working copy | `CHECKS passed=54 total=54 failed=0`, exit 0 |
| `apps/api/tests/test_error_answer_shape.py` in the whole-suite leg(s) | 13 cases, 0 failures, on each engine |
| ruff, `check.sh`'s own target (no path arguments), on plane `D:\足球项目\.scratch\plane_checksh_053134` (`50efc5e`) | exit 1 in **both** states with 19 findings in both, and none of them inside `apps/api/tests/test_error_answer_shape.py` — HEAD is not ruff-clean on its own (another lane's in-flight work), so what this unit claims is only the delta, and the delta is 0 |
| mypy `app`, same plane | exit 1 (114 files checked), **1** finding(s) in both states — `app\services\simulation\aggregates.py:325: error: Name "careers" is not defined  [name-defined]` is another lane's code and this unit does not touch it, so the identical counts are the claim, not a clean run |

**Mutation probe — 6 arms + control on `D:\足球项目\.scratch\plane_webshape_053120`** (`git archive 50efc5e`, so `lib/api.ts` is at its committed
bytes; artifact `.scratch/r76_web_arms.out`, predictions written into the launcher before the first arm ran). The
check population stayed 54 in all seven runs, which is what makes "N red" a
measurement rather than a crash:

| arm | predicted red | observed | verdict |
|-----|---------------|----------|---------|
| `control` | 0 | 0 | CONTROL-GREEN |
| `A1_unwrap_gone` | 20 | 20 | CAUGHT |
| `A2_figures_gone` | 2 | 2 | CAUGHT |
| `A3_code_forced_error` | 13 | 13 | CAUGHT |
| `A4_array_guard_gone` | 1 | 1 | CAUGHT |
| `A5_network_status` | 1 | 1 | CAUGHT |
| `A6_never_reads_body` | 26 | 26 | CAUGHT |

Each arm keeps the *text* the gate pins and breaks the *behaviour*: `A1_unwrap_gone` leaves `"detail" in payload`
in the file while making the unwrap return the whole payload, so the 20 checks it turns red are behavioural. What
the arms say about the fixture, not just about the reader:

* `A2_figures_gone` is the informative one — dropping the figures-carrying clause reddens `door-422-careers`
  (`see`) and the flat refusal (`remaining`, `requested`), and **leaves `handler-422` green**, because that body's
  figure is a key literally called `details`, which the reader reaches by name anyway. A check that passes for the
  wrong reason is exactly what the two arms with distinct figure spellings are for.
* `A4_array_guard_gone` reddens one case, and it is the case that only exists as a tolerance entry: an uninstalled
  422 answers `detail` as a list, and without the guard the page would stringify a list of objects into
  `[object Object]` instead of answering `Request failed with status 422`.
* `A5_network_status` is the transport leg, which no fixture can reach because a fixture is an *answer* — the gate
  stubs `fetch` itself to reject for that one case.

**Does it fail a build?** `D:\足球项目\.scratch\plane_r76exit_053116`: control exit=0 (predicted 0); A4_array_guard exit=1 (predicted 1).
The arms above are judged from the `CHECKS` line, which is not what CI reads.

**Whole-suite legs over `50efc5e` + this unit**, plane `D:\足球项目\.scratch\plane_r76full_045020`, each tallied from its own `--junitxml`; the population was
derived, not assumed — `pytest -q --collect-only` sums to
1430 with this unit's file overlaid on 50efc5e's, and to 1427 with 50efc5e's own copy of that
file in place. The three cases the swap adds, read off the file's own syntax tree: `test_a_handler_fixture_is_what_the_wrapper_answers`, `test_a_door_fixture_is_a_literal_the_named_module_raises`, `test_the_two_halves_still_point_at_each_other`.

| engine | tests | failures | errors | skipped | junit time |
|--------|-------|----------|--------|---------|------------|
| SQLite | 1430 | 27 | 0 | 2 | 957.062s |
| PostgreSQL + pgvector | 1430 | 27 | 0 | 2 | 1703.097s |

Both legs' red population is 26+1: 26 of each leg's 27 reds are `50efc5e`'s own, and that is measured rather than inferred: a fresh `git archive 50efc5e` plane that never contains this unit's file (`.scratch/r76_head_only_reds.out`, 84 s, interpreter bound to `D:\足球项目\.scratch\plane_r76headonly_052455\apps\api\app\__init__.py`) runs exactly the modules the leg found red and reports the same 26 — `test_knowledge_graph_api`, `test_simulation_aggregates` — with HEAD's own copy of `apps/api/tests/test_error_answer_shape.py` green at 10 cases. The mechanism is a mount, not a missing feature: `50efc5e`'s `app/main.py` carries 22 `include_router` calls where the shared working copy carries 24, and the 2 it does not mount (`graph`, `simulation_aggregates`) are precisely the modules those reds live in, while both router files exist at `50efc5e`. So the doors are implemented and tested but unreachable on the committed tree — which is what a `404` and a body missing its declared keys look like — and this unit's delta over that plane is **+3 cases, +0 red**. The remaining red is the portfolio schema-pin case caused by `7f481c2`'s fifth `ForeignKey("user_players.id")` clause — `video_assets` carries ForeignKey("user_players.id", ondelete="SET NULL") at `50efc5e`, while `50efc5e`'s `USER_PLAYER_TABLES` (its 4 names: `attribute_changes`, `training_plans`, `training_sessions`, `xp_events`) still does not list that table. The pin states its own claim (“the printed sentence counts these tables; a new one moves both”). pytest reports the length difference by naming the longer tuple's sorted tail (`Left contains one more item: ‘xp_events’`), which is not the added table — the carrier is the aligned diff's left side at index 3, so the red names its carrier rather than a coincidence, and it was re-confirmed on this plane inside the leg above, in a file this unit does not touch. The population is 1427 as `50efc5e` collects it on this plane, plus exactly the +3
cases of this unit — the same plane, the same swap, measured twice (`.scratch/r76_collect_measure.py`). The leg skips 2 cases, each named by the junit: `tests.test_scout_search.TestPublishedArithmetic::test_each_sorting_orders_the_survivors_by_its_published_key[need_fit]` is the long-standing scout ranking case; `tests.test_simulation_aggregates.TestSimulationAggregates::test_player_aggregate_returns_structured_data` sits in another lane's in-flight module (`test_simulation_aggregates.py`, untouched here).
§9 published 1373 tests / 1 red over `2d3673e` and this table publishes
1430 / 27 over `50efc5e`: the +57 between those populations is 13
commits of other lanes' work plus this unit's 3, the one red §9 blamed on the portfolio pin is the same
case named here, and the other 26 belong to finding 3 below.

## Three findings this unit had to work around, and did not cause

1. **The suite did not collect from an archive when this unit began; it does now, and that is why the numbers above
   can be published at all.** `a7cf9c6` committed `app/services/knowledge_graph/project.py` and
   `tests/test_knowledge_graph_api.py`, both of which import `app.services.knowledge_graph.verbs`, while no commit
   carried `verbs.py` or the package's `__init__.py` — at that moment `git log --all --
   apps/api/app/services/knowledge_graph/verbs.py` printed nothing, and both files lived only in a working copy.
   `pytest --collect-only` over `git archive HEAD` therefore ended with
   `ImportError while importing test module .../test_knowledge_graph_api.py` and `Interrupted: 1 error during
   collection`, and `python -m mypy app` printed its one finding in `project.py` for the same reason. The legs could
   only run on the last commit whose archive collects, which is why the record's baseline was `2d3673e` and not the
   head of the day.
   That hole has since been closed by `30e9d37`, which added the module. Re-measured here on
   `git archive 50efc5e`: 42 modules collect into 1427 cases with no import error, and
   mypy's single remaining finding is `app\services\simulation\aggregates.py:325: error: Name "careers" is not defined  [name-defined]` — another lane's file, not a missing one. The legs
   above therefore run over the current head `50efc5e`, and this landing refuses to write itself if either collect
   artifact grows an `ImportError` again, so the sentence cannot go stale quietly inside a later copy of this record.
   The class of defect still stands, and is worth naming on its own: a green suite in one working copy is not a
   green repository.
2. **`apps/web` has no unit-test runner.** Its gates are `tsc`, `next lint`, `next build`, and `node scripts/*.mjs`
   walks. A `.mjs` is invisible to all three of the first group — `apps/web/tsconfig.json` lists
   `exclude: ["node_modules", "scripts"]`, and `next lint`'s directories do not include `scripts/` — so a reader
   gate nobody invokes is a report, not a gate. This landing therefore adds the invocation to both runners the
   project recognises: `scripts/check.sh` (its own comment is that the CI job and the local gate must not disagree
   about the population) and the `web` job of `.github/workflows/ci.yml`, where it runs after `npm ci` and before
   `Types`.
3. **`50efc5e` answers 404 for two tiers its own tests walk.** The committed tree makes 22 `include_router` calls; the shared working copy makes 24, and the 2 that differ (`app/api/v1/graph.py`, `app/api/v1/simulation_aggregates.py`) are exactly the modules the pure-HEAD reds live in. Both router files are in the tree at `50efc5e` (`git show 50efc5e:apps/api/app/api/v1/<mod>.py` is non-empty for each), so the two candidate readings split on measurement: "tests written ahead of code" is false, "doors implemented but not mounted on the committed tree" is what the plane shows without any of this unit's bytes. This unit mounts nothing and edits none of those tests — `apps/api/app/main.py` is on this run's do-not-stage list, and the two lines belong in the lanes' own next commits. Until they land, the whole-suite figures published above carry 26 reds that are not this unit's, and say so in every place they are quoted. Like finding 1, the class is worth naming: a suite that is green in the working copy where it is developed can be red in the commit it is supposed to describe.

## How this unit's `ROADMAP.md` row landed beside another run's edit

`ROADMAP.md`'s working copy held an uncommitted edit that is not this unit's — `git diff --numstat -- ROADMAP.md`
read `3	2	ROADMAP.md` just before the commit. Two ordinary moves were both wrong here: rebuilding the file from
`git show HEAD:ROADMAP.md` plus this row would delete their edit, and `git add` + a pathspec commit takes the
*working copy*, so it would put their hunk under this unit's message. `git add` is per-file, which is exactly why a
shared dirty file makes "stage my work" and "commit someone else's work-in-progress" one action.

So the row went in through the index alone: the script wrote `HEAD's bytes + row` as a blob
(`git hash-object -w --stdin`), staged it with `git update-index --cacheinfo`, and then appended the same row to
*their* bytes in the working copy. HEAD's `ROADMAP.md` is asserted to be the hash it staged, the working copy is
asserted to be its own prior bytes with this row appended, and the residual `git diff --numstat -- ROADMAP.md` after
the commit is asserted to equal `3	2	ROADMAP.md` — their hunk, unchanged, and nothing of mine in it.

## Reproduce

```
cd apps/web && node scripts/qa-error-shape.mjs            # CHECKS passed=54 total=54 failed=0
TS_ENTRY=$PWD/node_modules/typescript/lib/typescript.js \
  node scripts/qa-error-shape.mjs                          # the same, from an archive plane
cd apps/api && python -m pytest tests/test_error_answer_shape.py -q   # 13 cases
python .scratch/r76_web_arms.py                            # 6 arms + control, predictions in the launcher
```

The arms ran against a CRLF rendering of `apps/web/lib/api.ts`: `git archive` applies this host's `core.autocrlf=true`, so the
plane's copy is 4082 bytes holding 85 CRLF pairs where the working copy and the blob are
both 3997 — the same 85 lines modulo the `b'\r'`s, verified by re-encoding the working
copy's bytes and comparing against the plane's file rather than by arithmetic. Every mutation string and every source
pin in the gate is single-line, which is why that difference is harmless here; a multi-line arm would have had to ask
the plane what its own line endings are first.
