# M13 verification — both boundary lines crossed, live on the wire

ROADMAP Phase 2 item 8, the live half. Date: 2026-11-02.

The write half of item 8 closed a career's season and stored a verdict; the verification beside it
recorded a limitation: every walked season landed between the two published lines, so promotion and
relegation existed only as unit tests. This walk is the other evidence. Two clubs played whole seasons
through the HTTP API, each crossed one line, and every claim the response makes about the move was read
back from another response: the league the verdict names, the tier of that league, the next fixture's
club, the moved competition, and the grant's arithmetic.

## 1. Two grids first, so the walk is not a lucky guess

`.scratch/probe-promotion-grid.py` and `.scratch/probe-relegation-grid.py` play one whole season for every
club of the tier being tested, through the same `create_career` / `play_round` / `career_view` calls the
endpoints use, on a migrated scratch database (`.scratch/walk-promotion.db`, upgraded to the tree's
schema):

| grid | clubs | crossed | best / worst |
| --- | --- | --- | --- |
| tier-2 promotion | 16 | 1 | Corgard Town, 28 points in 14 rounds (2.000 per round, line 1.8) |
| tier-1 relegation | 16 | 4 | Elnwick Athletic 10 (0.714), Obrhaven Union 12, Thorndera Town 12, Quernmoor Town 13; line 1.0 |

The other 15 tier-2 clubs finished between 10 and 25 points, all `stayed`; the other 12 tier-1 clubs
finished between 16 and 28, all `stayed`. Both branches therefore exist in the simulator with a real
grid beneath them, not one hand-picked career.

## 2. The tree and the database the walk runs on

The walk does not run against the working tree, because that tree carries feature work from other
lanes that is not part of this commit. It extracts the tree this commit points at:

```
git archive --format=tar HEAD -o .scratch/head.tar
tar -xf .scratch/head.tar -C .scratch/head-tree
```

and boots `.scratch/head-tree/apps/api` with a fresh SQLite database built by `alembic upgrade head`
(head `0048` in that tree), `ENV=development`, `APP_SECRET=pyramid-walk-secret`, on `:8784`. The world is
seeded by the application's own startup sync. A new account is registered through `/auth/register`, and
each career is opened with `budget: 0` so the season's grant is the whole balance and cannot be confused
with money the career already had.

## 3. The promotion walk

Corgard Town (overall 67) in Ravhurst First Tier (tier 2), `POST /careers` then fourteen
`POST /careers/{slug}/play` calls. The attempt counter is `1`: the first whole season promoted, so the
walk's retry path — delete a season that stays inside the lines and report it as an attempt — was never
needed, and nothing here is cherry-picked from a stored row.

| read | value |
| --- | --- |
| season | 14 rounds, 10-1-3, 31 points, GF 14, GA 4 |
| fixtures re-summed from the response | 14 played, 31 points, 10 wins — equal to `record` in the closed block |
| pace | 2.214 per round, above the published line 1.8 |
| verdict / rule | `promoted` / `promotion`, `recheck` says the fixtures still say what the stored verdict said |
| league it names | Thornford Superleague, read back at **tier 1** from `/world/competitions/{id}` |
| career's competition after the boundary | Thornford Superleague — `career.competition_name` equals `next_competition.name` |
| current season | season 2, 0 rounds played, competition Thornford Superleague (tier 1) |
| next fixture | round 15 of season 2, home, Cordale Town, `source: career_rotation`; Cordale Town's team detail puts it in Thornford Superleague |
| grant | **339,500** = 14 × 8,000 + 31 × 2,500 + 150,000; `promotion: 150,000`; `budget_after` equals the balance |
| lifetime record | 14 played, 31 points — the same season, because only one has been played |

## 4. The relegation walk

Elnwick Athletic (overall 48) in Lyndera Superleague (tier 1), same shape, also on attempt `1`:

| read | value |
| --- | --- |
| season | 14 rounds, 2-7-5, 13 points, GF 4, GA 10 |
| fixtures re-summed from the response | 14 played, 13 points, 2 wins — equal to the closed block |
| pace | 0.929 per round, below the published line 1.0 |
| verdict / rule | `relegated` / `relegation`, `recheck` agrees |
| league it names | Braehaven Elite League, read back at **tier 2** |
| career's competition after the boundary | Braehaven Elite League |
| current season | season 2, 0 rounds played, tier 2 |
| next fixture | round 15 of season 2, home, Braeford Athletic; team detail puts it in Braehaven Elite League |
| grant | **144,500** = 14 × 8,000 + 13 × 2,500, `promotion: 0`, `budget_after` equals the balance |

## 5. What each walk asserts

Seventeen checks, the same list in both directions, all true in both runs (`PASS: true`, saved to
`.scratch/pyramid-walk.json`):

1. the closed season's `record` sums to `rounds` fixtures and its points to the stored record;
2. the pace equals `points ÷ played` and equals `points_per_round`;
3. the verdict is the expected one and the line is the published constant for that rule;
4. the pace is on the other side of that line;
5. `recheck` reports agreement rather than a rewritten figure;
6. `next_competition`'s world row has the other tier;
7. the career's competition name is that league's name;
8. season 2 is the new league, at 0 rounds played;
9. the next fixture exists, is round 15 of season 2;
10. the next fixture's opponent belongs to that league;
11. the grant is `played × 8,000 + points × 2,500 + bonus`, with the bonus exactly 150,000 for the
   promotion and exactly 0 for the relegation;
12. `grant.budget_after` equals the amount equals the career view's `remaining` (the career opened with
    zero, so no other money can explain it);
13. the lifetime record equals the season, because exactly one season has been played.

## 6. Scope, stated rather than implied

- This is the **career's** boundary, not the generated world's. Item 9's `_apply_promotion_relegation`
  moves clubs between leagues when the world is regenerated; this walk moves the career's own
  `competition_id` and leaves the world's membership alone, which `close_season`'s docstring already
  states. The two can disagree, and that is by design.
- The new season is proved by its first projected fixture and by its competition, not by playing it. A
  second full season in the new league is a different unit (its calendar, its table, its own boundary).
- The web page was not walked for this unit. The working tree carries feature work from other lanes,
  and a build over it would not be this commit; the API is where every figure above is published, and
  the page consumes those same blocks.

## 7. Gates, as run on the extracted tree

| gate | result |
| --- | --- |
| `pytest tests/test_career.py tests/test_career_api.py` (in `.scratch/head-tree/apps/api`) | **84 passed**, rc 0 |
| `ruff check app` (same tree) | All checks passed |
| `.scratch/walk-pyramid.py` | **PYRAMID WALK OK**, exit 0, 17/17 checks twice |
| `.scratch/probe-promotion-grid.py` | 16 clubs, 1 promoted |
| `.scratch/probe-relegation-grid.py` | 16 clubs, 4 relegated |

## 8. What remains open in item 8

The line is crossable and the move is published, but the consequences of the move inside the career
remain thin: the new season starts on the career's own rotation because the world has no calendar for
the new league in the new season label, and gate receipts, prize money and cup runs are not modelled.
Those are Phase 7 items 24 and the pending market items, not this one.
