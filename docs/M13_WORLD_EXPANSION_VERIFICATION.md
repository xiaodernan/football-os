# M13 verification — the world grows to a two-tier pyramid, and the graph re-measures its ceiling

ROADMAP Phase 3 item 11 landed as commit `2f1119b` (2026-10-30) and was repaired by `8e28750`
before merging: the larger world broke two tests that had remembered the five-club shape, and one
of the breaks was a real product regression — the depth-2 graph walk had become a wall.

Date: 2026-10-30.

## 1. The shape

`WorldSizes` is now a pyramid: `tiers = (2, 2)`, `teams_per_league = 8`, `cups = 8`, squad 15,
seasons 2026/2027 — 12 competitions (4 leagues over two tiers + 8 cups), 32 clubs, 480 players,
288 matches (280 completed + 8 scheduled), 7,280 stat lines, 15,393 article↔entity links, 824
articles and 100 training sessions. The plan is 24,409 rows across eight tables, still a pure
function of the seed.

The previous world was 10 competitions · 20 clubs · 300 players · 130 matches · 500 articles.

§65's `GATE` floors are untouched and the world sits above every one:

| Entity | Floor | Present |
| --- | --- | --- |
| competitions | 10 | 12 |
| teams | 20 | 32 |
| players | 300 | 480 |
| matches | 100 | 288 (280 completed + 8 scheduled) |
| training sessions | 100 | 100 |
| articles | 500 | 824 |

Tier 1 clubs are drawn from the **0.52–0.95** strength band and tier-2 clubs from **0.30–0.66**;
the bands overlap, so the top flight is stronger by construction without making a promoted side
unable to compete. Tier 1 is the top flight (smaller number = higher level) and a cup carries
`tier = 0` because a cup sits outside the pyramid — the web prints a dash where a cup's tier would
be rather than calling it a division.

## 2. The newsroom grows with the world

A fixed 500-article budget would have left the twelve new clubs without a note, so the quotas are
now computed from the draft the generator is handed: one report per completed fixture, one preview
per scheduled fixture, three notes per club, two per competition, a spotlight for every second
player and a transfer line for every fifth. The tactical desk keeps its fixed budget of 80. The
`GATE` floors are unchanged; the article count is an output of the world's shape, not a constant.

## 3. What the larger world broke, and what was repaired

### 3a. The away half of a career moved

A career's rotation plays every opponent **at home in its first cycle and away in its second**
(`career.next_fixture_plan` publishes that sentence). With five clubs the away half began at round
5; with eight it begins at round 8. `test_an_away_round_contributes_the_clubs_events_from_the_away_side`
had played 6 rounds and asserted `away`, so it went red — a test remembering the old shape, not an
engine defect. It now derives the rounds from the career's own competition:

```python
opponents = career_service.competition_clubs(session, career.competition_id, exclude_id=career.club_id or "")
for _ in range(len(opponents) + 1):
    career_service.play_round(session, career)
```

### 3b. The depth-2 graph walk was a wall (a real regression)

`TestNeighborhoodDoor::test_the_walk_holds_its_word_at_the_ceiling` asks the five narrowest
articles for a depth-2 walk and requires at least one to **answer** inside the published caps —
the ceiling must be a ceiling, not a wall. In the 32-club world every one of the five refuses
`graph_too_broad` at the published 400 edges.

Measured over the seed-3 world (the union of the walk's own links, counted without a cap):

| Root | Depth-2 edges | Depth-2 nodes |
| --- | --- | --- |
| narrowest article (3 links) | 698 | 367 |
| next narrowest four (3 links) | 656–774 | 212–376 |
| a player | 1,155 | 233 |
| a team | 2,737 | 464 |

The narrowest roots are 64–94% over the cap because a competition is a hub: an article names a
competition, and the competition names eight clubs, its fixtures and its articles. The ceiling rose
to **800** — the smallest round number above the measured narrow roots — with the measurement
recorded beside the constant. A team's walk still reaches 2,737 edges and still refuses by name,
so the refusal path and its sibling test (`test_a_walk_that_breaches_the_edge_ceiling_refuses_rather_than_trimming`)
are unchanged in meaning.

The other ceiling constants are untouched: `MAX_DEPTH = 2`, `MAX_NODES = 600`.

## 4. Web

The cup's tier stopped being printed as a level: the competitions table, the home page's chips and
the competition page's eyebrow all print a dash (`—`) where a cup's tier would be, and keep the
number for a league. Verified in the browser against the movement branch (which carries this web
code unchanged): `/world/competitions` shows every cup with `—` and leagues with `1`/`2`, and a cup
page's «级别 —» sits beside a league page's «级别 2».

## 5. Evidence

| Check | Result |
| --- | --- |
| `pytest tests/test_world.py` (item 11 branch) | green — the pyramid test asserts `[1, 1, 2, 2]` for leagues, `[0] * 8` for cups and eight registered clubs per league |
| `pytest tests/test_sim_ledger.py tests/test_knowledge_graph_api.py` | green after 3a/3b |
| `pytest tests/test_world.py tests/test_openapi_contract_currency.py tests/test_locale_claims.py` (rebased onto master) | green — the contract reproduces the committed bytes after the rebase |
| live `GET /world/status`, seed 1 | competitions 12, teams 32, players 480, matches 288, stat lines 7,280, training 100, articles 824; gate 10/20/300/100/100/500 |
| graph depth-2 after the raise | the five narrowest articles answer (656–774 edges); a team root refuses at 800 |

The first full-suite run of the branch (before the rebase) ended **EXIT=1** with four reds:
`test_ci_trigger` (the branch is `world-pyramid`, not `master` — it is green on master),
`test_openapi_contract_currency` (the branch predated master's contract fix `f5ce28a`),
`test_sim_ledger` (3a) and `test_knowledge_graph_api` (3b). The latter three were fixed or became
non-issues by the rebase; the ci trigger is a property of running the suite on a feature branch.

## 6. What this does not claim

* **The floors are floors.** §65 asks for 20 clubs / 300 players / 100 matches / 500 articles; the
  world clears them, and the tests assert `>=`, not equality.
* **A tier is not a rank of quality measured in play.** The bands make tier 1 stronger on average
  by construction; a single promoted club can out-play its new tier, and promotion/relegation at
  the season boundary is item 9's own commit and record.
* **A cup has no level.** `tier = 0` is a sentinel the API publishes; the pages print `—` rather
  than inventing a division.
* **The 2027 calendar is two scheduled fixtures per league**, not a full next season; the world
  schedules ahead only what the generated calendar holds.
* **The graph cap is a load ceiling, not a completeness promise.** 800 edges is where the narrowest
  roots in this world fit; a busier root still refuses and says so with the same published number.

## 7. Reproduce

```bash
# the tests
cd apps/api && python -m pytest tests/test_world.py -q
cd apps/api && python -m pytest tests/test_sim_ledger.py tests/test_knowledge_graph_api.py -q

# a fresh world, seed 1
cd apps/api && DATABASE_URL="sqlite:///$TEMP/pyramid-walk.db" WORLD_SEED=1 KNOWLEDGE_AUTO_INGEST=0 \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 3300
curl -s http://127.0.0.1:3300/api/v1/world/status
curl -s "http://127.0.0.1:3300/api/v1/graph/rules"   # max_depth 2, max_edges 800, max_nodes 600
```
