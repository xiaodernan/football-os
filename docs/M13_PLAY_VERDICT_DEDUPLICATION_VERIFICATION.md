# The play response's verdict no longer builds a second career view

**Roadmap item:** performance follow-up (item 14). **Scope:** `POST /api/v1/careers/{ident}/play`.
**Date:** 2026-11-02.

## 1. What was wrong

The play endpoint returns the whole career view after playing a round:

```python
return {"played": True, "fixture_id": ..., "match": {...}, **career_view(db, career),
        "challenge_verdict": _challenge_verdict(db, career)}
```

`_challenge_verdict` answered the last key by calling `run_view(db, career, include_fixtures=False)`
and keeping `["verdict"]`. `run_view` is built on `career_view`, so the endpoint built **two** career
views per play: the one it returned, and a second one whose only surviving byte was the verdict. The
second view re-read the appearance table, the training table, the squad moves, the ledger, the season
boundary, the board and the contract book — every table the first view had just read.

## 2. What changed

- `apps/api/app/services/simulation/challenges.py`
  - New `verdict_of(session, career)`: `None` for a career with no scenario (or one whose scenario is
    no longer in the catalogue — the same `None` `run_view` publishes), otherwise
    `verdict_for(challenge, career, fixtures_of(session, career))`. The verdict is a pure judgment of
    `career_fixtures` rows, so that one SELECT is its whole cost.
- `apps/api/app/api/v1/careers.py`
  - The import of `run_view` as `challenge_run_view` is replaced by `verdict_of`.
  - `_challenge_verdict` now returns `verdict_of(db, career)` instead of indexing a second view.
- `apps/api/tests/test_challenges.py`
  - New `test_a_run_verdict_costs_one_fixture_read_and_one_helper_call` with three arms:
    1. the play route calls `verdict_of` exactly **once** per request (counter installed on the route
       module's name, so a revert to `run_view` fails the test);
    2. `verdict_of` itself issues exactly **one** SELECT, and it is `from career_fixtures`;
    3. after two played rounds the play response's `challenge_verdict` equals the run detail route's
       `verdict` field for field, so the cheap path and the full view cannot drift.
    It also covers the two `None` branches (no scenario, unknown scenario) without issuing a query.

## 3. Measured after the change

| Check | Command | Result |
| --- | --- | --- |
| Challenge tests (incl. the two new arms) | `python -m pytest tests/test_challenges.py -q` | **35 passed** |
| Career API tests (the route's own module) | `python -m pytest tests/test_career_api.py -q` | **14 passed** |
| Lint (changed files) | `python -m ruff check app/api/v1/careers.py app/api/v1/challenges.py app/services/simulation/challenges.py tests/test_challenges.py` | All checks passed |
| Types (whole app) | `python -m mypy app` | Success: no issues found in **161** source files |

The SELECT count is the witness: it was measured at **1** for `verdict_of` on a two-round run. The
previous path built a whole `career_view` for the same dictionary; `test_career.py::TestReadEfficiency`
already pins that view at one read each of appearances and training, so the second view was a second
read of both plus its other tables. No wall-clock figure is claimed here; the measured claim is the
statement count and the number of helper calls.

## 4. Limits of this verification

- Only the play route's verdict was changed. `GET /challenges/runs/{ident}` still builds the full run
  view, because it returns the run in full; the verdict there is part of that one view and costs nothing
  extra.
- The service test calls `verdict_of` directly; the route arm proves the endpoint reaches it. The two
  arms are deliberately separate so a route refactor cannot make the service test vacuous.
- The working tree carries another lane's uncommitted contract-expiry work, which adds a call inside
  `play_round`. The tests above were run on that tree; this unit committed only
  `app/api/v1/careers.py`, `app/services/simulation/challenges.py`, `tests/test_challenges.py` and this
  file. `git show --stat` on the commit is the record.
