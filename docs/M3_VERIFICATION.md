# M3 Football World — backend verification

Date: 2026-09-21 (UTC). Scope: the synthetic world **backend** — models, migration, generator,
unified search, `/api/v1/world/*`, the `/capabilities` flag. The public web pages at the §80 routes
are the next increment (`ROADMAP.md` → M3 web surface) and are **not** claimed here.

Spec anchors: §4 data model · §7 entities · §25 news schema · §26 fact/analysis/speculation ·
§54 match centre · §55 player page · §56 one search box · §62/§88 provenance labelling ·
§65 the M3 gate · §80 canonical web paths.

## 1. What is in place

| Piece | File | Notes |
| --- | --- | --- |
| Tables | `apps/api/app/models/__init__.py` | `Competition`, `Team`, `RealPlayer`, `RealMatch`, `RealPlayerMatchStat`, `NewsArticle`, `NewsArticleLink` — each row carries `data_origin` / `is_demo_data` |
| Migration | `apps/api/migrations/versions/0003_football_world.py` | `alembic upgrade head` applied on PostgreSQL+pgvector; `alembic check` reports no drift |
| Pure plan | `app/services/world/plan.py` | `Planned` rows keyed by natural key, `content_hash` over visible columns only, `WorldPlan.fingerprint()` as the determinism witness, plus the §80 `SEO_ROUTES` / `web_path()` table |
| Generator | `app/services/world/builder.py` (927 lines) | `WorldRng` (SplitMix64) → fictional name tables (`names.py`) → clubs, squads, fixtures, per-match stat lines. `plan_world(seed, sizes)` is cached and side-effect free |
| Newsroom | `app/services/world/news.py` | 500 articles, each quoting only numbers that exist in the stat tables; `claim_class` ∈ fact/analysis/speculation; byline is a desk, `source_name='synthetic-world'` |
| Sync | `app/services/world/sync.py` | plan → upsert by natural key, `_validate()` refuses a row that does not fit the column, deletions cascade, `GATE` floors, `world_counts` / `world_ready` / `world_tables_present` |
| Search | `app/services/world/search.py` | one query, typed ranked hits over all five entity types, explainable term-overlap scoring, no provider call |
| HTTP | `app/api/v1/world.py` (12 routes) | registered in `app/main.py`; every payload wrapped in `data_origin` + `is_demo_data` + `disclaimer` |
| Capability | `app/api/v1/meta.py` | `m3_football_world = world_ready(db)`, so the flag follows the data, not the code |

## 2. The gate (spec §65)

`GET /api/v1/world/status` against the pgvector database after `WORLD_AUTO_SYNC`:

| Entity | Required | Present |
| --- | --- | --- |
| competitions | — | 10 |
| teams | 20 | 20 |
| players | 300 | 300 |
| matches | 100 | 130 (122 completed + 8 scheduled) |
| articles | 500 | 500 |
| stat lines | — | 3,172 |
| article↔entity links | — | 9,058 |

`world_ready()` is `True`; the planned total is 13,190 rows across seven tables.

## 3. Determinism and idempotence

* `plan_world(3)` rebuilt after `cache_clear()` yields an identical `fingerprint()`; seed 4 differs —
  `TestPlan::test_same_seed_rebuilds_the_identical_world`.
* A second `sync_world()` on an already-built world reports `changed=0` and
  `unchanged == rows` — no timestamp churn, no duplicate keys.
* Slug safety is asserted per entity: `^[a-z0-9]+(-[a-z0-9]+)*$`, `slug == slugify(slug)`,
  ≤ 200 chars, and `unquote(quote(url, safe="/")) == url` for all 500 article URLs.

## 4. Honesty invariants

* A fixture with `status='scheduled'` returns `home_goals=None`, `away_goals=None`,
  `score="Data unavailable"`, `available=False`, `stat_lines=[]` — the API cannot print a result
  for a match that has not been played.
* Standings are aggregated from `real_matches` on each request, never stored, so the league page
  and the fixture list cannot drift apart. A cup returns `standings: []` with a `format_note`
  saying why, and its entrants come from the drawn fixtures rather than a membership column.
* Every list/detail/search payload repeats `data_origin: "synthetic"`, `is_demo_data: true`,
  `WORLD_DISCLAIMER`, and (for stats) `stat_method`, which names how rating and season totals were
  derived. News articles name their own desk and `source_name='synthetic-world'`, and the detail
  response states that no external citation exists because nothing was fetched.
* `/capabilities` now ships `locales: ["en"]` with `locales_planned: ["en","zh","zh-TW"]` beside it:
  §81 translations are not built, so the wire no longer advertises three languages.

## 5. §80 web paths the API hands out

`web_path()` is the single table (`SEO_ROUTES` in `plan.py`): `player → /player/{slug}`,
`team → /team/{slug}`, `competition → /competition/{slug}`, `match → /match/{slug}`,
`article|news → /news/{slug}`. Verified live on this run:

```
/world/teams   → /team/braeford-athletic
/world/players → /player/elum-eldtis
/world/matches → /match/2027-thornford-superleague-ildwick-athletic-ostford-wanderers-matchday-1-game-2
/world/news    → /news/preview-2027-thornford-superleague-ildwick-athletic-ostford-wanderers-matchday-1-game-2
/world/search  → /competition/braehaven-elite-league
```

The web tier must mount exactly these segments (task #10).

## 6. Defects found during this verification and fixed

1. **The router was never registered** — `app/api/v1/world.py` existed but `main.py` did not include
   it, so all 12 routes answered 404. Every read test failed until it was mounted.
2. **Article slugs contained spaces** (`transfer-ada-dolith-contract talk`), producing invalid
   canonical URLs. `_slug_key()` now runs through the shared `slugify()`; the re-sync rewrote 80
   articles and left 0 orphaned `news_article_links`.
3. **`/world/competitions` ignored `page_size`** — it hard-coded page 1 and returned everything. It
   now paginates like its sibling lists and reports a real `total`.
4. **Cup detail had no clubs** — participants were read from `Team.competition_id`, which points at a
   club's *league*, so `teams: []`, blank standings and null home/away briefs on every cup fixture.
   Knockout entrants are now derived from the fixtures.
5. **`world_counts`/`world_ready` were not exported** from `app.services.world`, so `meta.py` raised
   `ImportError` at boot; the package re-exports them (and `web_path`) now.
6. **Startup auto-sync reused the knowledge `report` variable** in `main.py`, logging the wrong
   summary. It has its own `world_report`.
7. **Nullable scores were cast through `int()`** in the builder and `**`-unpacking an optional dict
   in the router — mypy errors that hid real "unplayed match" paths; replaced with
   `_Fixture.score() -> tuple[int, int] | None`.

## 7. Reproduce

```bash
cd apps/api
python -m ruff check app tests            # All checks passed
python -m mypy app                        # no issues found in 45 source files
python -m alembic upgrade head && python -m alembic check
python -m pytest -q                                                  # 87 passed (SQLite)
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest -q                                               # 87 passed (pgvector)
python -m evals.run_rag_eval                                        # all gates passed (unchanged by M3)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8731 &
python ../../scripts/export_openapi.py   # 40 paths, 44 operations, incl. the 12 /world routes
curl -s localhost:8731/api/v1/world/status
```

`tests/test_world.py` is 39 tests in four classes: `TestPlan` (pure invariants), `TestSync`
(idempotence, gate floors, referential integrity), `TestReads` (HTTP envelope, pagination,
slug-vs-id resolution, 404s, search filters), `TestSearchService` (ranking, nonsense queries,
per-hit provenance).

## 8. Not claimed by this milestone

* Public `/player`, `/team`, `/match`, `/competition`, `/news` pages and the world index/search UI —
  next increment, including their sitemap entries.
* Any external data provider. `NEWS_API_KEY` / `FOOTBALL_DATA_API_KEY` remain unread; the world is
  generated locally and `source_name` says so (spec §45).
* Season progression: fixtures are generated once per seed from `SEASON_START`; nothing simulates a
  matchday moving the table forward (that is M6's engine).
* Multilingual rendering of world copy (§81).
