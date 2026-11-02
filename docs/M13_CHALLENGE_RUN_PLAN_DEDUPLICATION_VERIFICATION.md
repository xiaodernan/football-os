# Challenge run detail: the next fixture is planned once

**Roadmap item:** performance follow-up (item 14). **Scope:** the two challenge routes that return a
whole run. **Date:** 2026-11-02.

## 1. What was wrong

`apps/api/app/api/v1/challenges.py` had two responses built like this:

```python
return {"next_fixture": next_fixture_plan(db, career), **run_view(db, career)}      # read_run
...
return {"started": True, "club_choice": choice,
        "next_fixture": next_fixture_plan(db, career), **run_view(db, career)}      # start
```

`run_view()` calls `career_view(include_fixtures=True)`, and `career_view` computes the plan itself and
writes `view["next_fixture"]` (`apps/api/app/services/simulation/career.py`, the `if include_fixtures:`
block). Because the `**run_view(...)` spread is applied *after* the literal key, the later mapping wins the
duplicate key. So each request planned the next fixture twice — once in the route, once in the view — and
discarded the route's plan without ever reading it.

`next_fixture_plan()` is not a pure formality: it reads the season bounds, the competition's clubs, the
calendar fixtures and the opponent's `Team` row, then projects the rotation. Paying for that twice on
every run open and every run detail was dead work.

## 2. What changed

Two files, and no response shape:

- `apps/api/app/api/v1/challenges.py`
  - `from app.services.simulation.career import next_fixture_plan` removed (the module used it nowhere
    else; no other module imported it through this namespace — checked with a repository-wide grep).
  - `start`: the literal `"next_fixture"` entry removed. `run_view` still supplies it, which the existing
    `start` tests already assert (`body["next_fixture"]["available"] is True`).
  - `read_run`: `return {"next_fixture": ..., **run_view(...)}` became `return run_view(db, career)`.
- `apps/api/tests/test_challenges.py`
  - New `test_a_run_plans_the_next_fixture_once_per_request`: it wraps
    `app.services.simulation.career.next_fixture_plan` with a counter through `monkeypatch`, opens a run
    and asserts exactly **1** call, then clears the counter, reads `/api/v1/challenges/runs/{slug}` and
    asserts exactly **1** call again. It also asserts the detail response's `next_fixture` is *equal* to
    the plan the start response published, since nothing was played between the two reads. That pins both
    the call count and the value a caller sees: removing the route's copy cannot change the answer.

## 3. Why the counter, not just the output

The output was already correct before this change — the route's plan was overwritten, so every test that
compared `next_fixture` field by field passed while the request still paid twice. A value assertion could
therefore never catch this. The counter observes the duplicate itself, and it fails on the old code with
`start planned the next fixture 2 times`.

## 4. Measured after the change

| Check | Command | Result |
| --- | --- | --- |
| Challenge API tests | `python -m pytest tests/test_challenges.py -q` | **34 passed** |
| Career routes next to the change | `python -m pytest tests/test_career.py tests/test_career_api.py -q` | **84 passed** |
| Lint (changed files) | `python -m ruff check app/api/v1/challenges.py tests/test_challenges.py` | All checks passed |
| Types (whole app) | `python -m mypy app` | Success: no issues found in **161** source files |

`ruff format --check tests/test_challenges.py` still reports one pre-existing block at
`test_the_catalogue_and_the_market_agree_about_whether_a_rule_binds` (line ~221); the same block fails on
`git show HEAD:apps/api/tests/test_challenges.py`, and the project gate (`scripts/lint.sh`) runs
`ruff check`, not `ruff format`. The new test block is formatter-clean — the only diff ruff proposes is
the header block that predates this change.

## 5. Limits of this verification

- No HTTP-level timing is published. The claim is narrower and measured directly: one fewer
  `next_fixture_plan` call per request on the two routes. This file does not claim a wall-clock saving.
- `run_view` may be called with `include_fixtures=False` (the run list); that path has no
  `next_fixture` and this change does not touch it.
- The working tree carries another lane's uncommitted market/contract work. This unit committed only the
  three paths above; `git show --stat` on the commit is the record.
