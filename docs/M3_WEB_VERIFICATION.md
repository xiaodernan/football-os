# M3 Football World — web surface verification (spec §54, §55, §56, §62, §65, §80)

Date: 2026-09-22 · Tier: `apps/web` · Evidence run: `202609212343` (**110/110 browser assertions**, 46 PNGs in `docs/screenshots/`,
zero browser console errors) against a **production build** served on `:3211`, API on `:8731` (pgvector).
Backend evidence: [`M3_VERIFICATION.md`](M3_VERIFICATION.md).

The backend half of M3 was already verified. This record covers the public pages that consume it: the twelve
routes below, the §80 crawl surface they create, and the four things these pages are required *not* to do.

## 1. What landed

| Route | File | Reads | Refuses to show |
| --- | --- | --- | --- |
| `/world` | `app/world/page.tsx` | `/world/status` + four list routes | a placeholder row when a table is empty; a gate claimed rather than counted |
| `/world/competitions` `/teams` `/players` `/matches` `/news` | `app/world/*/page.tsx` | the five list routes, with `kind` / `nation` / `position` + `sort` + `order` / `status` / `category` + `claim_class` | a filter's results re-labelled as the whole set |
| `/world/search` | `app/world/search/page.tsx` | `/world/search` (`q`, `types`, `limit_rows`) | an empty query faked as "everything"; itself indexed (`robots: noindex, follow`) |
| `/competition/{slug}` | `app/competition/[slug]/page.tsx` | `/world/competitions/{ident}` | a points table for a knockout (`standings: []` + `format_note`) |
| `/team/{slug}` | `app/team/[slug]/page.tsx` | `/world/teams/{ident}` | a crest or logo image (initials + the row's own `brand_color`, validated hex only) |
| `/player/{slug}` | `app/player/[slug]/page.tsx` | `/world/players/{ident}` | a total that its stat lines do not add up to (the page prints the API's `consistency_check` verdict) |
| `/match/{slug}` | `app/match/[slug]/page.tsx` | `/world/matches/{ident}` | a score for an unplayed fixture |
| `/news/{slug}` | `app/news/[slug]/page.tsx` | `/world/news/{ident}` | an external citation — `source_name` is `synthetic-world` and the page says so |

The five §80 entity routes are mounted at exactly the paths `SEO_ROUTES`/`web_path()` hand out in
`apps/api/app/services/world/plan.py`. Pages link through the API's own `path` fields; nothing in the web tier
concatenates `"/team/" + slug`. Two fields were added to the API to keep that true (`match_path` on a stat line and
on a `recent_form` row), each covered by a test that walks every `*path` string in a detail payload.

Supporting code: `lib/types.ts` (the whole world wire shape, nullability copied from the SQLAlchemy columns),
`lib/world.ts` (`cleanParams` / `buildHref` / `readWorld` / `pageOf` / `brandColor`), `components/world.tsx`
(`OriginBadge`, `Provenance`, `WorldHead`, `MatchRow`, `WorldPager`, `FilterChips`, `RefLink`, `ClaimChip`, `Crest`,
`KeyValueGrid`, `formatDay`/`formatMoment`), `styles/world.css`.

## 2. Honesty rules these pages enforce in code

- **Provenance is a wire field, not a caption.** Every payload carries `data_origin`, `is_demo_data` and
  `disclaimer`; `OriginBadge` renders `DEMO DATA` from those, so a row from a licensed provider would flip the badge
  by itself. `/world` prints the disclaimer verbatim.
- **No score before a kick-off.** `status='scheduled'` rows are NULL in the database; the scoreline renders
  "no score yet", the row lists render "Not played · Data unavailable", and `stats` are absent rather than zeroed.
- **No table for a knockout.** `/competition/{slug}` shows `format_note` and the bracket; the cup page asserts the
  absence of a standings claim rather than filling one in.
- **Aggregation says where it came from.** A league table is computed per request from stored completed fixtures,
  and the panel prints the API's own `Table aggregated from the stored completed fixtures on this request.`
- **Reconciles in public.** The match centre shows `goals in score` against `goals in lines` and labels the pair
  `RECONCILES` / `DOES NOT RECONCILE`; the player page prints the API's `consistency_check` string.
- **Claim class is visible.** Every generated report declares `fact` / `analysis` / `speculation` next to its title.

## 3. The §80 crawl surface

| Check | Result |
| --- | --- |
| `sitemap.xml` `<loc>` entries | **983** — 500 news + 300 players + 130 matches + 20 teams + 10 competitions + 6 world pages + 17 knowledge documents |
| Coverage vs the API's own counts | asserted equal per entity type, so the sitemap cannot under- or over-report the tables |
| Every advertised `<loc>` answers 200 | 983/983, probed through the harness with a bounded 8-worker pool (an unbounded `Promise.all` of 983 fetches made the tier refuse its own crawler) |
| Per-route canonical + OpenGraph | asserted on `/knowledge`, `/world`, and every detail route sampled; canonical is per route, never inherited from the layout |
| Structured data | `Dataset` on `/world`, `SportsOrganization` on a competition, `SportsTeam` on a club, `Athlete` on a player, `SportsEvent` (with `homeTeam`/`awayTeam`/`startDate`/`eventStatus`) on a match, `NewsArticle` on a report, `WebSite` + `SearchAction` on search |
| `/world/search` | `noindex, follow` and absent from the sitemap — a query shell is not content |
| `robots.txt` | unchanged: session-gated areas disallowed, `Sitemap:` line dynamic (`docs/SEO_VERIFICATION.md` §4) |

Sitemap `lastModified` comes from the rows themselves (`kickoff_at`, `published_at`), never a build timestamp.
Filter URLs (`?kind=cup`, `?position=ST`) keep the unfiltered canonical, so a crawler is not told they are distinct pages.

## 4. What the browser walk proves (110 assertions)

Beyond the pre-existing 68, the 42 new world checks cover: the proxy serving the world API to a signed-out visitor;
the sitemap's per-type coverage; the counted-contents table and gate state on `/world`; the search box; `noindex` on
the query page; the no-score state on a scheduled fixture; score reconciliation and `SportsEvent` on a played match;
full squad rendering and `SportsTeam` on a club; `consistency_check`, inline-SVG radar and per-line row counts on a
player; points ordering and the aggregation note on a league table; the absent table on a knockout; claim class,
source and `NewsArticle` on a report; 12 entity cross-links resolving 200; pagination changing rows; a position
filter holding on every rendered row; an ascending sort really ordering its column; and an unknown slug answering
404 rather than an invented record. World surfaces are also walked at 375px with zero horizontal overflow.

## 5. Defects found and fixed during this increment

1. **A component prop named `ref`.** `RefLink({ ref })` compiled, type-checked and built, then killed every request
   that rendered it: React refuses refs in server components ("Refs cannot be used in Server Components"), which is a
   500 for `/world/news` and `/news/{slug}` — and it took the `next start` process down with it. Renamed to `target`.
   Twelve routes had rendered fine; only the two that used it failed, which is why the walk visits every route.
2. **The sitemap probe DoSed our own tier.** 983 concurrent `fetch`es made the run abort with `fetch failed` after
   the probe was widened from 17 URLs to 983. `probeStatuses()` now uses a bounded pool and turns a refused
   connection into a failed check instead of an exception that hides the other 90 assertions.
3. **Text assertions against uppercased CSS.** `.eyebrow { text-transform: uppercase }` means `innerText` reports
   `7 ROWS …`, so a `includes('7 rows')` assertion failed against a page that was correct. Replaced with a DOM row
   count, which is what the check meant anyway.
4. **Two `f`-string prefixes without placeholders** in `migrations/versions/0002_knowledge_base.py` kept
   `ruff check .` (the whole API directory, not just `app/`) red. Removed; the emitted SQL is byte-identical.
5. **A dead `MatchStats` import and six missing `key` props** in `KeyValueGrid` rows were the only `npm run lint`
   findings; the gate is clean again. (`npx eslint .` is not the gate — it sweeps `.next*` output and reports thousands
   of problems the `next lint` configuration deliberately excludes.)
6. **Two QA runs aborted at the second step with a 60s wait.** The cause was the harness, not the pages: Git Bash's
   `$!` is an MSYS pid, so the cleanup `Stop-Process` had killed nothing, a `next start` from an earlier run kept
   owning `:3211`, and the fresh run's own server died on `EADDRINUSE` while the walk drove the **stale** build whose
   chunks had been deleted — visible only as HTTP 400s for `/_next/static/chunks/*.js`.
   `apps/web/scripts/verify-production.sh` now owns that sequence: it releases the port by looking the listener up and
   matching its command line, refuses to run unless the served chunk hash equals the hash present in `.next-ci`, and
   the walk reports an unhandled abort as a failed check plus an `abort-state` screenshot instead of one log line.

## 6. Reproduce

```bash
# one command: typecheck + lint + build, serve on :3211, prove the served build is the fresh one,
# run the walk, release the port
cd apps/web && bash scripts/verify-production.sh          # 110/110, exit 0

# what it runs underneath
npx tsc --noEmit && npm run lint                          # 0 errors
NEXT_DIST_DIR=.next-ci SITE_URL=http://127.0.0.1:3211 npx next build
NEXT_DIST_DIR=.next-ci SITE_URL=http://127.0.0.1:3211 npx next start -p 3211 &
QA_BASE=http://127.0.0.1:3211 node scripts/visual-qa.mjs  # 110/110, exit 0
curl -s http://127.0.0.1:3211/sitemap.xml | grep -c "<loc>"   # 983

# backend invariants the pages lean on
cd ../api && python -m ruff check . && python -m mypy app && python -m pytest -q   # 89 passed (SQLite)
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" python -m pytest -q
```

## 7. What this does not claim

- The world is **generated**, not sourced: no provider, no feed, no scrape (§45's real-provider path stays unbuilt, and
  `DEMO MODE` in the nav refers to the absent AI key).
- Seasons do not progress. `2027` fixtures exist as scheduled rows; nothing plays them forward, and no page pretends otherwise.
- `/training/{slug}` is still session-gated, so it is not in the sitemap even though §80 lists the route shape; making it
  public is a product decision, not an SEO one.
- §81 i18n: the **mechanism** is built as of 2026-10-06 — `middleware.ts` resolves `fo_locale`/`Accept-Language`,
  the nav carries the switcher, both Chinese catalogues carry the full key set (`zh` 287/288, `zh-TW` 288/288
  written as Traditional), and `/capabilities` publishes `locales: ["en","zh","zh-TW"]`, held there in both
  directions by `tests/test_locale_claims.py`. The page **bodies** are still English literals — only `Nav.tsx`
  and `LocaleSwitcher.tsx` read a catalogue, and wiring them is `PLAN.md` item 2c. Evidence:
  `node scripts/visual-qa-locale.mjs` against the production build at commit `56d524c` — **249/249 checks
  passed**, including choosing 简体中文 and reading the repainted shell, the choice surviving a reload, switching
  back, and settings listing exactly the shipped locales with no pending chips.
- The 46 PNGs under `docs/screenshots/` are gitignored (the pre-commit hook rejects them), so they are evidence for a
  human on this machine, not artefacts in the repository.
