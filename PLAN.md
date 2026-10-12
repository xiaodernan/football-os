# PLAN — the work that is left, in the order it should be done

`ROADMAP.md` says which milestone is open and what has been proven. This file says what to build **next**, in
order, with the evidence each item has to produce before it counts as done. It is written to be picked up cold:
every item names the files it touches, the gate it must pass, and the thing that would make it a lie.

Rule inherited from spec §96 and this project's own practice: **an item is done when its claim is measured, not
when its code exists.** A number in a document that no command reproduces is not evidence.

Last updated 2026-10-12.

---

## Done, and what it cost

| Item | Landed | Evidence |
| --- | --- | --- |
| **0. one gate, not three** | ✅ 2026-09-30 | `scripts/check.sh` and CI both run `python -m ruff check` with no path arguments. Proven by planting an unused import in `evals/`: invisible to the old target, caught by the new one, and the script exits 1. |
| **1. §13's 3D pitch** | ✅ 2026-09-30 | `components/pitch.tsx` projects the board's own metres isometrically; `237/237` walk checks on a production build, with a check that recomputes every dot from its metres and another that holds the projected lawn inside its `viewBox`. `docs/M4_WEB_VERIFICATION.md` §8. |
| **2a. §81's `locales` claim** | ✅ 2026-10-01 | `tests/test_locale_claims.py` binds `locales` to the catalogues in both directions. Found that `zh.json`/`zh-TW.json` are 278/278 copies of English, so the field stays `["en"]` — and now cannot be moved without a translation or left unmoved with one. |
| **2b. §81's translations + the switcher** | ✅ 2026-10-06 | `LocaleSwitcher` writes the `fo_locale` cookie middleware has always read; `locales` moved to `["en","zh","zh-TW"]`; both Chinese catalogues are now **complete** — `zh` 392/394 translated (fallbacks: `scout.placeholder` already Chinese in the English file, `settings.apiBadge` = 'API {status}'), `zh-TW` 393/394 (`settings.apiBadge` only), `zh-TW` written as Traditional rather than converted. `test_locale_claims.py` 4/4; the locale walk drives the real switcher and reads the repainted shell. |
| **2c. the catalogue is reachable from the content pages** | 🟡 2026-10-11 | **Development is wired** — a 54-key `progress` namespace written from the page's own strings (metadata, four group names, five stat labels + hints, the XP bar, both panel footers, four day buttons, two empty states, the achievements panel, the closing notice). Coach before it (78 keys, three files); scout/career/world were wired from keys that already existed — and `8feda9a` closed `world`'s seventeen **attribute** labels the same way, no new key: 16 wired, one named a sense skip, two of the files (`/player/{slug}` and the signed-in aggregate) reading no catalogue at all before it. **15 files now read a catalogue**, walk **140/142** on a production build — all three of this page's checks green, and the run stopping at 142 rather than ~199 because the video section aborted it again (see the video row below; the three checks are placed in front of it for exactly that reason). **Tactics is wired (2026-10-11)** — a 173-key `tactics` namespace written from the six pages' own strings (index, `[slug]` with its counterfactual/3D/analysis/roles/demands panels, compare, boards index, board edit with two `t.rich` link embeds, shared token) plus the shared furniture (`BandLegend`, `MetricTable`, `Verdicts`, `ChangeNav`, `SystemCard`); English values are byte-identical to the literals they replaced, walk assertions untouched. `agents` (36 keys) before it. **`Panel` now forwards `data-*` props** — the aggregates walk checks' `data-testid` hooks never reached the DOM (they were `Panel` props this component dropped on the floor), so those two checks had never once passed. **History is wired (2026-10-11)** — 47 keys for `/history`, walk **178/181** with all three of its checks green. It had been **half-wired**: it already read `common` for `previousPage`/`nextPage`, which is the shape that hides work — a page that reads *some* catalogue looks finished in a grep for `useTranslations` while its own copy is still literals. **Twice now**, so it is a pattern, not a coincidence: grep for `useTranslations` is not a measure of coverage, because a page reading one catalogue looks done. The measure is a page's *own* copy and it has to be read. **Training is wired (2026-10-12)** — 108 keys across four files, the largest yet (index, `[slug]` with its eight panels, `AddSession`, `SessionLogger`), walk **212/214**, the furthest any run has got. Two shape notes worth carrying forward: `ratingLabel` was a `Record<string,string[]>` of fifteen sentiment words read in two contexts, so the fifteen keys had to resolve **inside the component** rather than be baked into one concatenated sentence; and two `<Panel title="…">` props became keys, which means **"no literals in the JSX" is not the whole check either** — translated text can arrive as a prop. **Shape D's back links are wired (2026-10-12, `c7e9f4c`)** — seven pages now take `nav.home` / `nav.myFootball` from the catalogue, and reaching two of them to prove it required fixing the door's exemption semantics first (the row on the share link). **Shape D's document titles are wired (2026-10-12, `dd8618c`)** — nine `export const metadata` titles became `generateMetadata`, each taking **the key that page's own heading already reads**, so a tab cannot drift from its h1; witness 65/0 over 9 sites, arms 7/7 (the seventh is a control: move only the `<Panel>` title beside the h1 and the witness must stay green), live read **135/0** over 9 routes × 3 locales on a fresh bundle. **The rule is a shipped gate now (2026-10-13, `ef0ff8b` + `5ef05eb`)** — `apps/web/scripts/qa-metadata-title.mjs` reads it off all 59 pages, registered in `scripts/check.sh` and `ci.yml`: **94/94** on a clean plane, witness **12/12 arms**, live read **34/0** with a still-literal page as the control, and `/knowledge`'s tab wired to the orphan `knowledge.metaTitle` its own writer had left unread, which is the last of the eleven byte-exact metadata sites this arc counted. Two lessons from the read being wrong first: its `og:title` claim was written as one promise for nine pages and went red on three, because those three carry no `openGraph` block and fall back to the layout's `title.default` — *at HEAD too*, so nothing had moved; the claim is now derived per site from HEAD's own bytes, with a floor that refuses the run if no route carries its own preview title. And `/my-football` came back **307 → `/onboarding`**, which is the product correctly refusing a user with no player: the read was measuring the door, not the page, so the session is now onboarded through `POST /players` with the option values the onboarding form itself lists. **One lint red is at HEAD and is not this slice's** — `app/knowledge/[slug]/page.tsx:38 'tc' is assigned a value but never used`, landed by `5aa8926`; eslint over the nine files above alone exits 0, so read the gate with the plane's sha. **That red is still at `5ef05eb`** — the whole-app `next lint` that exited 0 on 2026-10-13 did so because the worktree holds someone else's *uncommitted* one-line fix for it (`git diff` shows `- const tc = await getTranslations("common");`), and the machine-wide pre-commit hook grades the worktree, not the commit. The way to grade a lint claim at a ref without disturbing a shared tree is `git show HEAD:<path> | npx eslint --stdin --stdin-filename <path>`, which re-prints the `tc` error at line 38. Still literals: club, community, video, simulate, market, challenges (another session is wiring club/community/graph/portfolio/simulate in parallel — count the callers, do not assume). **Knowledge is wired (2026-10-12)** — 96 keys across four files, walk **215/217**. **It was the third half-wired page**: all three top-level files already read `common` (the "all" chip, the Search eyebrow, the DEMO MODE badge, `open` in the citation link) while everything else was literals — history and training arrived the same way, so **three of five**. PLAN now states plainly that `grep useTranslations` is not a coverage measure. Three shape notes for the next person: a small server component sharing the page's file needed `getTranslations`, **not** the client hook `useTranslations`; when one file reads *two* namespaces, `t` means a different catalogue depending on which half you are in (the build catches it); and a lede with a conditional prefix became **three keys** (`ledeCounts`/`ledeNoCounts`/`ledeRest`) — the first sentence in this batch that had to be split. `validation` (8 keys) waits for a form that shows custom messages. |
| **— `common` is 97 keys and 3 are read** | ⚠️ not the next step | Measured 2026-10-09. `common` is generic UI vocabulary (`save`, `cancel`, `loading`, `yes`, `no`, `or`, `of`) and **three keys are read** — `language`, `demoMode`, `demoModeTitle`, all from `Nav`/`LocaleSwitcher`. Of its 97 English values, 16 appear as a literal anywhere in `app/`+`components/` and 80 appear nowhere: there is no `Loading…` string in the project at all. The app's real vocabulary is domain words (Player, Age, Position, Club, Expected goals, Fixture) which belong to pages, not a shared namespace. So the plan's "wire `common` next" had nothing to wire; the next work is a page, and `coach` was the next page a reader meets. |
| **4. §61 account erasure end to end** | ✅ 2026-10-06 | `GET/DELETE /auth/account`: preview inventories every row and byte, one confirmed transaction, media containment refused before any write, last-owner blocking (409), §60's third 403 code (`invalid_password`) registered. 4 tests including the escaping-storage-key case a planted-defect probe demanded. |
| **§38/§60 portfolio share + PDF** | ✅ 2026-10-06 | `POST/GET/DELETE /portfolio/share[/{token}]`, `/portfolio/cv.pdf` (reportlab), robots keeps both off crawlers. Committed with the two above because all three share one contract file. |
| **— migration `0026`** | ✅ 2026-10-07 | Not on the plan. `alembic upgrade head` did not run at all: `0026` and `2e197f085070` both revised `0025`, so the graph had **two heads** and every fresh database, gate run and deploy failed at the first step — invisible because `python -m seed` builds its schema from the models. Behind that: `sa.Index` inside `create_table` (invalid SQL), `now()` (not a SQLite function), and a table declaring `id INTEGER` where the model says `String(40)`, with no `updated_at`. Verified: `0025 → 2e197f085070 → 0026`, `rc=0`, `alembic check` clean. |
| **— every commit is refused on this host** | ⚠️ environment | Found 2026-10-09. The global `pre-commit` hook (`~/.codex/git-hooks/pre-commit`) ends with `trap 'rm -f "$FILES_TMP"' EXIT`, and `FILES_TMP="${TMPDIR:-/tmp}/codex-global-pre-commit-files.$$"`. This host exports `TMPDIR=C:\Users\18414\AppData\Local\Temp`, so the path becomes `C:\Users\...\Temp/codex-global-pre-commit-files.958` — mixed separators — and the safe-delete shim refuses it: `[safe-delete][SAFE_DELETE_INVALID_PATH] embedded drive prefix is not allowed`. The trap's failure becomes the hook's exit status, so the hook prints *passed* and then fails the commit. **The checks are not the problem and the hook is not wrong to run**: `TMPDIR=/tmp git commit …` commits normally. Worth fixing in the hook (use `mktemp`, or strip the drive) rather than in every caller. |
| **— the middleware's prefix list had drifted from the pages that gate themselves** | ✅ 2026-10-11 | Found by walk run 3: the silent refresh only runs for `PROTECTED_PREFIXES`, and `/simulation` (plus `/agents`, `/club`, `/community`, `/creator`, `/graph`, `/portfolio`, `/scout`, `/simulate`) was missing — a signed-in reader whose 15-minute access token died mid-visit was bounced to /login by the page's own `currentUser()` instead of being refreshed. `/club/rules` is exempt (`PUBLIC_EXCEPTIONS`) because the rulebook is the one /club page a signed-out visitor may read. The walk's own session proves it: the aggregates section, last in the run, went from 307 to 200. |
| **— the same door's *exemption* list could only ever fire on one page** | ✅ 2026-10-12 | Found by the shape-D live read, not by the walk: `GET /video/shared/e90273…` answered **307 → /login** in all three locales while `/tactics/shared/<token>` answered 200. Cause: `isProtected()` matched `PUBLIC_EXCEPTIONS` by **exact pathname** (`pathname === "/club/rules"`) while matching `PROTECTED_PREFIXES` by prefix — so an exemption could never reach a segment below it, and `/portfolio/shared` had never been listed at all. Both lists now share prefix semantics and both share doors are exempted. `apps/web/scripts/qa-middleware-gating.mjs` is the shipped gate: it slices the decision out of `middleware.ts`, transpiles it with the repo's own TypeScript and **calls `isProtected`** instead of paraphrasing it, then reads every page under `app/` — today 59 pages, 38 that read or redirect to a session, 34 gated by the door — with checks for a private page the door misses, a public page the door still catches, and a stale exemption. It runs **red on HEAD before the fix** (the reverse control), which is what makes it a gate rather than a description. Registering it in `scripts/check.sh` and `ci.yml` needed a `fileURLToPath` fix first: `new URL("..", import.meta.url).pathname` percent-encodes this repo's CJK path and the read dies with ENOENT. Un-gating the clip page exposed a **second defect behind the first**: it typed the owner's `VideoReport` against the shared door's flat summary, so it rendered a 500 (`TypeError … 'frame_count'`) the moment it was reachable. The page was rewritten to disclose what the door actually answers — ten record fields, and it now says that the clip's bytes, frames and detections stay with the account that uploaded them — rather than widening the API to hand analysis bytes to a token-holder. That widening is a decision about what a share link *means* and is left open in `docs/MIDDLEWARE_GATING_VERIFICATION.md`. Live read: 18 green / 6 red → **24 / 0**. |
| **— the video section aborts the walk about half the time** | ⚠️ open | `"No clips yet" never appeared at /video/vid_…` after the walk clicks *Delete clip and file*. The API answers the `DELETE` **204** (confirmed in the uvicorn log), so the delete works — what fails is the client. `VideoTools.call` does `router.push("/video")` then `router.refresh()`, and the page never leaves the report URL. The walk's own media-detach step removes `<video>`/`<img>` elements that React owns, which is the prime suspect: pulling nodes out from under React can break the tree that the subsequent `push` needs. It also leaves a `GET /file?_rsc=…` prefetch (404) that the detach does not cover. Consequence: **every check after the video section does not run**, so a green-looking run is really 142 checks, not 199 — see 2c for why the language checks were moved in front of it. |
| **— the walk's stopping point moves between runs** | ⚠️ open | On 2026-10-11 a run got past the video section and then died in the **§12j career block** instead: `retiring the season stops the rounds and says so on the page — copy false · button found true · play disabled false`, then `no button containing "Take charge again"`, stopping at 181 checks. So a run reporting ~140, ~181 or ~199 is not three qualities of result — it is one walk stopping in three different places, and **the fraction alone does not say which checks ran**. Read the failed-checks block, not the number. |
| **— `/simulation/aggregates/player/{slug}` answers 404** | ⚠️ open | Twice in a row (2026-10-11, 2026-10-12) the walk has stopped here: `"corand-ruceek" never appeared at /simulation/aggregates/player/corand-ruceek`, with the console showing `HTTP 404 /simulation/aggregates/player/corand-ruceek`. The route is advertised by the walk and by the sitemap but the server returns 404 for it — so either the route is not mounted or it lands on a different path. This is now the walk's *usual* stopping point, ahead of the video abort. |
| **— `/agents` was linked but deleted** | ✅ 2026-10-11 | Rebuilt as the M11 console: `app/agents/page.tsx` + `AgentConsole.tsx` read a 36-key `agents` namespace (all three catalogues, parity-verified), render the roster from `GET /agents/list` (the registry's own answer, not a TS copy), run single agents through `/agents/run` and composite tasks through `/agents/composite`, and show the session's stored memories via `/agents/context` with a per-visit session id. Walk section `06b` (placed before the video section, which still aborts about half its runs): 5/5 green — shell, orchestrator label, run with confidence, agent attribution, composite steps. The dead link's 404 console error is gone. |
| **— this host cannot run `next build` twice** | ⚠️ environment | Not on the plan. The Recycle Bin rejects the operation (`Unknown { description: "Some operations were aborted" }`), so the safe-delete shim times out on the delete Next performs against a **pre-existing** dist directory. The build compiles, then dies before writing `prerender-manifest.json`, leaving output that cannot be served. Building with the directory absent works. `scripts/check.sh` runs `npm run build` once, but any second run in a row fails here, and `rm -rf`-style cleanup of a build directory hangs. |
| **— migration `2e197f085070`** | ✅ 2026-09-30 | Not on the plan; found by trying to run the SQLite leg it broke. Unadjusted autogenerate, PostgreSQL-only DDL, a `downgrade()` that could not run anywhere, and each new column indexed twice. |
| **— the aggregates ledger had no index, and its back links were dead doors** | ✅ 2026-10-11 | `/simulation/aggregates/league` and `/simulation/aggregates` (both back-link targets) answered 404 — the walk's console gate recorded them as unprovoked errors every run. `app/simulation/aggregates/page.tsx` is the index: one panel listing every competition from `/world/competitions` (the path is `/world/competitions` — the first draft used `/competitions` and rendered the unavailable branch, caught live before landing), one explaining the player door, one printing the rules door's vocabulary. The league page's back label moved with it, and the walk's anchors were repointed to what the success body actually renders (the competition name; the player slug chip) — the old anchors lived in metadata or a back-link label, which is how repointing one link broke a wait. |
| **— the OpenAPI contract and autocrlf** | ✅ 2026-10-06 | Not on the plan. The working copy of `docs/api/openapi.json` had been checked out CRLF while `scripts/export_openapi.py` writes LF, so the byte gate failed with *equal byte counts* — a host newline policy, not an artifact defect. Regenerated from the tree (162 paths / 208 operations, LF). Windows checkouts of this repo will do this again; the remedy is the exporter, never hand-editing. |

**The pattern worth naming.** Three of the four items above were *claims that had drifted from their evidence*,
not missing features: a gate three targets wide, a `locales` field nobody checked, a migration that had never
been run on the engine the docs tell you to use. The features in this project are in good shape. The documents
and the fields are where the work is.

---

## What is actually open

| Area | State | Where the truth is |
| --- | --- | --- |
| M0–M7 | ✅ verified | `ROADMAP.md` gate table |
| M8 Club OS | ✅ verified 2026-09-28 — only §42's **payments** open, and spec §42 says not to rush them | `docs/M8_CLUB_OS_VERIFICATION.md` |
| M9 Community | 🟡 §35 (posts, reactions, follows, feed) landed 2026-09-28; §36/§37 verbs still absent | `docs/M9_COMMUNITY_VERIFICATION.md` |
| M10 Creator Economy | 🟡 §38 portfolio landed, share links + CV PDF landed 2026-10-06 | `docs/M10_PORTFOLIO_VERIFICATION.md` |
| M11 Multi-Agent | 🟡 all six agents + `FootballOrchestrator` landed — the orchestrator replaced the keyword router, and §30's graph has its own joint-retrieval evidence | `docs/M11_AGENT_BENCHMARK_VERIFICATION.md` |
| M12 Hardening | 🟡 §61 erasure landed 2026-10-06; structured logging, cache, latency percentiles, cost advisor, governance + backup docs landed 2026-10-09; **the spend cap gates the coach door at the call** 2026-10-11 (/coach/ask skips only the LLM phrasing when today is spent, so the arithmetic still ships; /knowledge/ask still refuses 429); **OpenTelemetry tracing landed 2026-10-11** (packages pinned, span path measured through an in-memory exporter, no collector on this host) and **the restore drill was executed 2026-10-11** — `pg_dump` → `pg_restore` inside the project's own container, 58/69 tables byte-identical, and it found the one defect no gate could see: the long-lived container still carried `2e197f085070`'s duplicate indexes, closed by migration `0027`. What has *not* landed is listed in the verification doc's "does not claim" (no authenticated Redis tier (the layer landed; 6379 here needs a password), no trace backend, no off-host backup; **the load ceiling is now published for one worker** (90.80 req/s at c10 on this shared host, and 52.54 at c50 — saturation, not scaling), and four workers were measured against one: +29% at concurrency 10, +6% at 50, and the 15s max outlier fell to 656ms once a second process existed — the figures are a floor — `scripts/bench_api.py` and the run found a defect in the harness first: it reported 0.00 ms latency for every non-2xx response, so a door that always answers 401 measured as instantaneous) | `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md` |
| §81 i18n | 🟡 catalogues full, switcher works, shell switches; **58 files bind a translator (83 bindings), counted on HEAD blobs at `844216d`** — nav/auth/scout/career/settings/world/progress plus `common`'s verbs, nouns and its attribute labels; `agents` (36 keys) exists only in a writer's uncommitted catalogue. Still English literals: the content-page namespaces whose keys do not exist yet (tactics, training, club, community, video, simulate, market, challenges). | the grep that counts `useTranslations`/`getTranslations` callers on HEAD blobs; the label census re-run **with a TSX parser over all eleven HEAD dictionaries** (`census-ast.mjs`, 105 files, 0 parse diagnostics). At `8feda9a` it read **A 24 sites, B 168, C 54 — 245 distinct sites**; re-run at `844216d` after the `nav` group it reads **A 24, B 168, C 40 — 231 distinct sites**, plus **E 3** (a label in a component's default parameter, which no earlier shape could see). `world`'s C group closed at `8feda9a` (17 found, 16 wired, 1 named sense skip), `common`'s at the two shape-C landings (11 wired + 1 skip) and `nav`'s at `844216d` (21 rows: 15 wired, 4 reachable only case-insensitively so wiring them would rewrite `en`, 2 left as key-ownership questions with the reason named). The union fell by 14 for 15 wired attributes, and the one is not a missing label: `tactics/[slug]/page.tsx` `title="Tactical system"` survived its own file's edit but moved from `:79` to `:81`, so a census keyed on `file:line` re-counts a site when a line *above* it is written. That is why every figure in this arc names the ref it was measured at. The parser also **withdrew the older "shape A 0"**: `common`/`world` words do stand as bare JSX text — 7 A sites and 76 B sites carry one of their values, every one of them still a sense question rather than a wiring. | A **fourth shape** is now measured and partly closed: a label inside an object literal, e.g. `back={{ label: "Back to Football World" }}` or `metadata = { title: "Community" }`, which no JSX-shaped census can see. `census-d.mjs` parses every HEAD `.tsx` (108 files, 1331 object literals) and read **14 D sites**, of which **10 were byte-exact against `en`** — all ten are `export const metadata` titles, so wiring them needs `generateMetadata`, not a prop — and **4 are case-only** (`label: "Career mode"` vs `nav.career` = "career"), which stay open because wiring them would rewrite English's bytes. Re-run at `2348ed1` it read **15 rows / 11 byte-exact**: the knowledge landing surfaced an eleventh site, `/knowledge`'s own metadata title. **The metadata half is now wired for nine of those eleven (`dd8618c`)**, and the census re-run at `dd8618c` reads **6 rows / 2 byte-exact**. The rule the slice states, because it is what makes a literal title safe to delete: *a page's document title takes the key its own heading already reads* — no new catalogue keys (all three message files were dirty from concurrent work, and a key written there would ride along in someone else's commit). The two that stayed, stayed for named reasons: `/community`'s h1 says "Community wall" while `nav.community` says "Community", so wiring its tab would couple two copies that do not agree; `/knowledge` was the file another writer is standing on. **That one is now wired** (`ef0ff8b`, reading the orphan `knowledge.metaTitle` its own writer had authored), so the census re-run at `ef0ff8b` reads **5 rows / 1 byte-exact** — the survivor being `/community`'s metadata title — and the pair the gate's ledger carries is `/community` ("Community" over "Community wall") and `/club` ("My clubs" over "Club tenancies"), two copies that differ in English where choosing between them is a sense decision, not a wiring. One case-only row moved line but not shape (`app/scout/page.tsx` :41 → :46) — the census is `file:line`-keyed, which is why every figure above names its ref. **Two open items this slice disclosed rather than fixed**: three pages (`/portfolio`, `/scout`, `/my-football`) carry a bare metadata object with no `openGraph` block, so their link-preview title is the layout's `title.default`, and **nine pages' `description` meta is still an English literal** — `generateMetadata` reads a catalogue for the title only. The permanent form **is** written and shipped now (`ef0ff8b` + `5ef05eb`): `apps/web/scripts/qa-metadata-title.mjs` states the rule over the whole page population instead of one change's diff — every `app/**/page.tsx` must declare its tab in exactly one form, **may not** hold a load-time literal on a page whose heading reads a key (check 4, DRIFT), **may not** read a key on a page whose headings are all literals (check 11, MIRROR — the same mismatch in the other direction, empty today so it refuses rather than ratchets), and where both are literals they must be the same copy unless a ledger row whose predicate is re-read from that file's bytes on every run says otherwise (checks 5/6). Plus the population floor, a per-file parse-diagnostic floor, a heading-carrier floor, one-namespace-per-binder, per-key resolvability in all three catalogues, a differs-from-English test on every tab key, an orphan clause on `<ns>.metaTitle`, and a descending ceiling on literal-titled pages — every count derived from the same walk that finds the pages, so a narrowing scan goes red instead of quietly shrinking what is protected. At `ef0ff8b` on a clean plane it reads **population 59, tabs keyed 25 / literal 24 / dynamic 10, heading carriers 45 (keyed 25, literal 13, dynamic-only 21), CHECKS 94/94**; the same script over the dirty worktree reads 101/101 with keyed 27 / literal 22, because a concurrent writer has since wired two more pages — the ceiling is a ratchet, so the fall is what the gate wants. Witness **12/12 planes matched** (`arms-meta.mjs`): reverse control to the pre-wiring blob, stale exemption, an added disagreeing page, a tab pointed at the h1's own key, a deleted zh value, a zh value copied from English, an added agreeing page, `app/` deleted, a heading carrier retyped as a `Panel`, a page declaring both metadata forms, and a keyed tab over a literal heading; each red judged by its clause id **and the file it names**, never by a count. Two lessons the writing taught, both recorded here because they are not obvious from the file: (i) the "2 remaining sites" this row carried for a whole slice was a **D-census** number being read as a **page-population** number — the population holds 24 literal-titled pages, of which exactly 2 disagree with their own heading and 1 more (`/knowledge`) was drifting from a keyed heading; and (ii) the rule is **not** "the tab reads the key its heading reads". `/knowledge`'s tab names the surface ("Football Knowledge") while its h1 names the corpus ("The football knowledge base"), exactly as `agents`, `coach` and `settings` already do — so the gate forbids the two directions of *mismatch*, not a difference of copy. A census written earlier in this arc (`meta-census.mjs`) printed a bucket labelled `title-keyed-heading-literal` reading 7 and looked like a population the gate ignored; all 7 are keyed headings under a different key or dynamic ones (`board.name` twice) — the label described the census's equality test, not the heading's kind. Cross-checking two scans is what found both, and `/knowledge` closed without new copy: its own writer had already authored `knowledge.metaTitle` and left it with **no reader** (7 `metaTitle` keys, 6 read), so the drift page and the orphan key were one fact seen from two sides. Live read **34/0** over `/knowledge` × 3 locales with `/world/search` as the still-literal control: the wired tab repaints ("Football Knowledge" / "足球知识库" / "足球知識庫", `og:title` with it) while the control does not move, and every description stayed the page's own bytes. `dmeta-check.mjs` and `knowledge-meta-check.mjs` remain as change-time instruments for the next wiring slice; the shipped rule no longer depends on them. The **back-link half of shape D is closed** (`c7e9f4c`, seven pages: `/club`, `/community`, `/graph`, `/portfolio`, the portfolio share page, `/simulate`, `/video` now read `nav.home` / `nav.myFootball`), which is what found the middleware defect in the row above: the live read could not reach two of those pages at all. Six `/world/*` pages still carry `back={{ label: "Back to Football World" }}`, a label with **no key** — the value is `"Back to " + en[nav.world]`, so it needs either a new key or an interpolated one, and the sense rule for it is not written yet. A **fifth** shape is measured (shape E, 3 sites) and open for a different reason: one of its strings is used as data by a page that compares against it. |

Three cross-cutting defects have now been found and fixed **three separate times** (M4's `tactics/sync.py`, M7's
scouting modules, M8's academy tier): *the committed tree does not pass the gate its own documents quote.* The
cause is always the same — `ruff` is run against a narrower target than CI uses. Item 0 exists so this stops
recurring instead of being rediscovered.

---

## Item 0 — make the local gate the same gate as CI

**Why first.** `scripts/check.sh` runs `ruff check app tests seed.py migrations`. CI runs
`ruff check app tests evals seed.py migrations`. The documents quote `ruff check app tests`. Three targets, one
of them enforced. A green local run is therefore not evidence that the commit is green, and the difference has
already cost three repair passes.

**Do.** Give `scripts/check.sh` and CI one shared target — a single line both read, so they cannot drift again.
Update every document that quotes a narrower command to quote the shared one. Add the missing `evals` leg to
`check.sh`'s local run.

**Evidence.** `bash scripts/check.sh` exits non-zero on a tree that CI would reject — demonstrated by planting a
lint error in `evals/` (a file neither the old script nor the old docs covered) and showing the script catch it.

**Files.** `scripts/check.sh`, `.github/workflows/ci.yml`, `CONTRIBUTING.md`, the verification documents that
quote the command.

---

## Item 1 — §13's 3D pitch, as an isometric projection of the same metres

**Why.** Spec §13 asks for 2D **and** 3D. M4 shipped the 2D pitch, drawn as SVG from the metres the
measurements come from, and the ROADMAP has carried "3D pitch" as an open item since. It is the only M4 item that
is neither blocked on another milestone nor a policy question.

**Do.** Add a third view to `/tactics/{slug}` — alongside the existing 2D and the drag-to-arrange board — that
projects each of the eleven from the same `x_metres`/`y_metres` the 2D view reads, through a stated isometric
transform, and draws it as SVG. No new dependency: a 3D view that renders from the same numbers is a *projection*,
and a projection is arithmetic, not a renderer. Print the projection formula on the page beside the view, the way
every other figure on this project prints its own.

**The claim that has to hold.** A point at a known metre coordinate lands at the projected pixel the printed
formula gives for it. That is checkable without a screenshot and is the difference between a 3D view and a picture
that looks 3D.

**Evidence.** A walk check that reads one player's projected coordinates out of the DOM and compares them with the
formula recomputed in the browser from that player's own printed metres — plus the toggle asserted to leave the
underlying metres unchanged, so the 3D view cannot quietly become a second source of truth.

**Files.** `apps/web/app/tactics/[slug]/page.tsx`, `apps/web/components/**` (a new pitch component),
`apps/web/scripts/visual-qa.mjs`.

---

## Item 2a — §81 i18n: the claim, before the translation

**Why.** The cross-cutting gate says the UI is English-only and `GET /capabilities` reports `locales: ["en"]` with
`locales_planned` beside it. That is honest, and it is also the only field in the project that nothing checked.

**Done 2026-10-01.** The catalogues exist with the full key set; `tests/test_locale_claims.py` now binds `locales`
to them in both directions, so the field cannot be over-claimed or left stale. See the table above.

**What it found.** The catalogues are copies, so the honest answer stays `["en"]` and the switch is now a
mechanism rather than a note to a future reader. The translating itself is item 2b.

**Files.** `apps/web/messages/*.json`, `apps/web/lib/i18n.ts`, `apps/web/app/settings/**`,
`apps/api/app/api/v1/meta.py`.

---

## Item 2b — §81's actual translations

**Done 2026-10-06 (two commits: `2671102` mechanism, `56d524c` words).** The switcher writes the cookie,
middleware answers in it, and both Chinese catalogues carry the full key set — `zh` 287/288 (the search example
sentence is Chinese in the English file already, so its one fallback is the honest state), `zh-TW` 288/288
written as Traditional with Taiwan usage, not converted. `test_locale_claims.py` 4/4 on the new catalogues; the
full locale walk (`node scripts/visual-qa-locale.mjs`, production build at `56d524c`) passed **249/249**, including
driving the switcher, surviving a reload and reading the repainted shell. The claims in `meta.py`,
`messages/README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md` and `M3_WEB_VERIFICATION.md` were corrected in the same
commit as the words.

## Item 2c — §81's remaining half: wire the pages to the catalogues

**Done (auth batch) 2026-10-06.** The nav stopped being the only reader: `app/login/page.tsx`,
`app/register/page.tsx` and both forms now read `auth.*` (the register form reuses `settings.displayName`
rather than duplicating it), and `metadata` became `generateMetadata` so even the tab titles follow the cookie.
31 keys were added across the three files for this. The locale walk gained five assertions that open the auth
pages and read their `h1` in both languages — `登录` / `创建你的账号` — and passed **254/254** on the production
build (was 249), including a screenshot of the Chinese login page. `test_locale_claims.py` 4/4, `tsc` clean.

**Why next.** A complete catalogue that two components read is a library, not an interface. After the auth batch,
`grep -r "useTranslations\|getTranslations" apps/web --include=*.tsx` still returns mostly `Nav.tsx`,
`LocaleSwitcher.tsx` and the four auth files — every other page body still renders English literals, so the
switcher repaints the nav bar above a page that cannot change. The catalogue is now the *easy* part; this item is
the long tail.

**Do.** One namespace at a time, in the order a reader meets them: ~~`auth`~~ done, ~~`scout`~~ done, ~~`career`~~ done, ~~`disclaimer`~~ done (2/3 keys — `demoData` + `aiEstimate`; `fictionalResults` has no reader), ~~`settings`~~ done (86 keys — page + PrivacyPanel fully wired), ~~`world`~~ done (54 keys — /world page fully wired with metadata, search, panels, table headers, badges, generation labels, browse section), ~~`common`~~ done on both scanned label shapes (2026-10-09 and 2026-10-10 records below; attribute-position labels are a third shape, unclosed).
The rest are **content-page** namespaces that do not exist yet — `tactics`, `training`, `progress`, `coach`, `club`,
`community`, `video`, `simulate`, `market`, `challenges` each need new keys in all three catalogues before a page can
be wired, because their copy is page-specific rather than a shared word. The `validation` namespace (8 keys) waits for a form that
displays custom error messages — no component uses these yet. Each page wired is a page the walk can read
in Chinese — extend `scripts/visual-qa.mjs` to assert one translated string per wired page rather than
trusting the absence of literals.

**Done (common batch) 2026-10-09, twelve commits `1b206a5`..`db34fec`.** Twelve files now read
`useTranslations("common")`. `Nav.tsx` and `LocaleSwitcher.tsx` already did; the ten that joined are
`ScoutShortlistPanel`, `CareerTools`, `VideoTools`, `SimTools`, `BoardEditor`, `SessionReportTools`, `BoardsNew`,
`PortfolioSharePanel`, `ClubTools` (both `TenantTools` and `InvitationTools`) and `CreatorWorkbench`. What gets wired is
the shared **verb**, not page copy, counted by grepping each verb back to the files that read it: `delete` in five files
(`BoardEditor`, `CareerTools`, `ScoutShortlistPanel`, `SimTools`, `VideoTools`), `save`, `close`, `open` and
`accept`/`decline` in two files or two uses each — `save` (`BoardEditor`, `SessionReportTools`), `close` (`ClubTools`,
`PortfolioSharePanel`), `open` (`CreatorWorkbench`, `ScoutShortlistPanel`), `accept`+`decline` (`ClubTools`' invitation
row) — and `create`, `apply`, `remove`, `view` in one each. `Nav.tsx` and `LocaleSwitcher.tsx` read the namespace for
its nouns and labels rather than its verbs, which is why the file count (12) is above the number of files this batch
touched (10). Two keys the namespace did not carry were added in all three catalogues at once (`accept`, `decline`),
because the parity rule below refuses to let one locale hold a key another lacks. A busy state appends `…` to the base
verb rather than declaring a progressive form: the catalogue has none, and `deleting`/`saving` per locale would be
maintenance debt for a word the button already shows.

**Attribution — `db34fec` carries work that is not §81's.** Its message says "added two new keys"; its numstat says 82
lines per catalogue file. `messages/{en,zh,zh-TW}.json` were **already modified** when this run started — a concurrent
writer was mid-`coach` (`app/coach/page.tsx`, `CoachAsk.tsx`, `PlanBuilder.tsx`, `scripts/visual-qa.mjs` are still
uncommitted) — and whole-path `git add` swept that writer's 80-key `coach` namespace into my commit. The keys are
theirs; the commit is mine, and this record is the correction rather than a rewrite: moving a commit another writer may
be building on is not reversible. HEAD is not broken by the extra namespace, measured not assumed — `test_locale_claims.py`
is **4/4**, and `git show HEAD:apps/web/app/coach/page.tsx` reads no namespace at all, so those 80 keys sit unreferenced
until that writer's components land. Worth naming: the parity gate compares the catalogues *to each other*, so it can
never see a key no component reads. "Catalogue complete" and "catalogue wired" remain different claims. The rule this run
adopts: any file dirty **before** this run touched it is staged hunk-wise (`git apply --cached` on my own hunks), never
with `git add <path>`.

**Done (common batch, continued) 2026-10-09, three commits `e7567d7`..`a9f43a1`.** Seventeen files now read
`common` (`grep -rl 'Translations("common")' apps/web/components apps/web/app`), counted per verb by grepping the
call back to its carriers: `open` six (`AcademyTools`, `ChallengeStartForm`, `CreatorWorkbench`,
`ScoutShortlistPanel`, `app/knowledge/KnowledgeAsk`, `app/page`), `delete` six (`BoardEditor`, `CareerTools`,
`ClubTools`, `ScoutShortlistPanel`, `SimTools`, `VideoTools`), `close`/`save`/`create` two each, and
`apply`/`remove`/`view`/`accept`/`decline`/`goTo`/`previousPage`/`nextPage` one each. Three of these landed on
**Server Components**, and two findings came out of doing it:

- `useTranslations` works in a **non-async** Server Component. `components/world.tsx`'s `WorldPager` is one, and it
  rendered the reader's locale with no provider change. The async rule below is about `async` components only —
  converting `WorldPager` to `getTranslations` would have meant awaiting it in every `/world` page.
- A shared verb can be **wrong in the other language**. `common.previous`/`common.next` carry 上一步/下一步 — step
  words — so the pager could not reuse them; `previousPage`/`nextPage` were added (en keeps "Previous"/"Next" so the
  fallback locale's HTML is unchanged, zh 上一页/下一页, zh-TW 上一頁/下一頁), in all three catalogues in one commit
  because the parity gate compares the catalogues to *each other*. `previous`/`next` stay, unreferenced, for the
  stepper that will want them.

Because a build cannot see a locale, each of these three commits was verified by **asking the running app in each
locale**: production `next start` on a fresh port, `GET` with the `fo_locale` cookie set, and read the label out of
the response (`← 上一页 / 下一页 →` on `/world/players?page=2`; the landing hero CTA `前往 我的足球` signed in, after
registering a throwaway account and player through the shipped cookie proxy — the same route `visual-qa` takes).
`test_locale_claims.py` 4/4 on every new key.

**Done (common batch, closed on the labels) 2026-10-10, three commits `db5fc27`, `dab8449`, `78da148`.**
`db5fc27` moved the training-log pager and the landing hero CTA. `dab8449` deleted the last **standalone**
`common` literal in the tree — census **8 to 0** — and named the two shapes the rest of this item is measured by,
both derived from the catalogue's own values rather than from a hand-typed word list, walking the 105 `.tsx` files
under `app/` and `components/`: shape A is a JSX line whose `trim()` *is* a `common` value (0 left), shape B is an
inline text child `>Label<` (14 before `78da148`, **4 after**). `78da148` took the table headers and the badge quote:
`Status` on `/career`, `/club`, `/club/{ident}` and inside the client component `ClubTools.TenantTools`, `Name` on
`/team/{slug}` and `/world/players`, `Name` on `/world/competitions`, `Open` on `/graph/nodes/{kind}` and on the
creator guides header row, plus the `DEMO MODE` the prose at `knowledge/[slug]` quotes.

- **A literal equal to a catalogue value is not automatically the same sense.** `common.name` = 名称 (a thing's name)
  and a person's name are different words in Chinese, so `personName` (姓名) was added for `/team` and `/world/players`
  while `/world/competitions` kept `name` — and the two locales then disagreed on screen in exactly the way the
  senses do, which is the read that proves the split rather than the dictionary entry. The four labels left literal
  are the same finding in reverse: `CreatorWorkbench`'s two `Moved` headers sit over numeric cells (`common.moved`
  is 已移动, a sentence, not a count), its `Published` sits over `guide.published_on`, a date, and `NoticeBoardTools`'
  `Notice` names an announcement row while `common.notice` = 提示 is a UI hint box. `AI-ranked` and `Erase` stay
  English for the same reason — domain state words with no key of that sense.
- **One of these was a real inconsistency, not a skip**: the creator guides column's *button* already read `t("open")`
  while its own *header* carried the literal. The census found it because it scans for the value, not for the key.
- **A client-fetched table is invisible to `curl`.** The creator shelf loads after hydration, so the SSR bytes hold
  no such row — the headless read went through `puppeteer-core` (already a devDependency) with the locale and
  `fo_access` cookies set, and the header matched its own column's button in all three locales. The in-app browser
  timed out on every operation, so that leg was replaced rather than reported as done.
- **Shared tree, measured not assumed**: the three catalogues also carried a concurrent writer's uncommitted
  `progress` namespace (55 lines each, plus `app/progress/page.tsx` and `scripts/visual-qa.mjs`). The catalogues were
  staged as HEAD-blob + my one line through `hash-object`/`update-index` — never `git add <path>` — each asserted
  `+1/-0`, and the staged set was asserted equal to my thirteen paths with a refuse branch. The refuse fired on the
  first attempt: the script split the worktree on the **string** `"\r?\n"` instead of the regex, so the file looked
  like one line, the anchor matched nothing, and the index was untouched. Post-commit, `HEAD:<path>` equalled the
  recorded index hash for all 13, and `git show HEAD:…en.json` still had no `progress` block.
- **A build cannot see a locale, and a running server can be stale.** One live read disagreed with the source and
  the cause was my own: the build had silently not run (a mangled parallel command), so the server answered from old
  `.next` bytes. The order is now enforced — rebuild into a log in the repo, assert `Compiled successfully` and
  exit 0, start on a **new** port, then read. `next start` prints `Error: ENVIRONMENT_FALLBACK` once at boot;
  attributed as boot-only (the log did not grow across four route reads, all 200) but its source is unidentified.
- `common` is now closed on all three scanned shapes. Shape C — a label in an **attribute**, which is neither a line
  that IS a label nor a `>Label<` child — is measured and wired in `286c71a`, recorded below.

**Done (shape C: attribute labels) 2026-10-11, `286c71a`.** The hand-picked spelling list was the first thing to go
wrong: grepping the four names I thought of (`aria-label`, `placeholder`, `title`, `alt`) found **1** attribute label
equal to a `common` value. Enumerating instead what the tree actually writes — 58 attribute names carry a plain string
over the same 105 files, of which 13 are label-bearing (`aria-label` 96, `label` 37, `eyebrow` 97, `placeholder` 45,
`title` 330, `hint` 4, `lede` 26, `message` 13, `body` 13, `fallback` 3, `detail` 2, `what` 2, `caption` 1 = **669
carriers**) — found **12**. Eleven wired, one named as a sense skip:

- `eyebrow="Filter"` ×9 (`/world/players`, `competitions`, `matches`, `news` ×2, `teams`, `training`, `/tactics` ×2)
  → `common.filter`; `eyebrow="Search"` on `/knowledge` → `common.search`, the same file that already read
  `t("search")` at line 144 while its own section heading stayed a literal — the header/button disagreement again,
  one shape over. `aria-label="Summary"` → `common.summary`.
- Four pages (`world/matches`, `news`, `teams`, `training`) bound `getTranslations("common")` for the first time;
  before this they read no catalogue at all.
- **Sense skip, named:** `app/career/[slug]/market/page.tsx` `label="Received"` is a money figure sitting beside
  three page-copy siblings, while `common.received` is 已接收 — a delivery status. Wiring one label of a four-label
  row to a dictionary whose sense is wrong would trade an English literal for a Chinese lie.

Two claims this slice nearly made without evidence, and the control that stopped each:

- **Composites are invisible to an exact-value scan.** `placeholder="Summary (optional)"` is two catalogue words
  (`summary`, `optional`) joined by punctuation, so it matched nothing. A decomposition detector was written for it
  and first reported **0 on HEAD's own bytes** — a belt that cannot fire is not a measurement, so the detector was
  run against the pre-edit blob as a reverse control: it was comparing case-sensitively and could not see the
  catalogue's `Optional` inside `(optional)`. Fixed, it finds that one composite at `HEAD:…CreatorWorkbench.tsx:207`
  and **0** now.
- **A build cannot see a locale, and `tsc` cannot see a rendered string.** The first composition interpolated
  `t("optional")` as-is, so the fallback locale printed `Summary (Optional)` where HEAD prints `Summary (optional)` —
  green typecheck, green build, green parity gate, wrong bytes for the default locale. The puppeteer read of `/creator`
  is what caught it; the hint word is now lower-cased inside the sentence and the en DOM is byte-identical to HEAD.
  Same leg also caught a **bare `//` comment left in JSX child position**, which React renders as page text: the
  witness asked for the sentence in `document.body.innerText` and got `true` in all three locales, `{/* */}` and a
  rebuild take it to `false`. Neither tsc, lint, the build nor the parity gate can see either defect.

**Verification.** Production build, `next start` on `127.0.0.1:8815`, 24 reads (8 pages × `zh`/`zh-TW`/`en`) all 200:
`筛选` / `篩選` / `Filter` and `搜索` / `搜尋` / `Search`, the English rows unchanged from HEAD. `/creator` is
client-fetched, so its read goes through `puppeteer-core` with a freshly registered throwaway account and a published
creator profile: `aria-label` 摘要 / 摘要 / Summary and `placeholder` 摘要 (可选) / 摘要 (選填) / Summary (optional).
`test_locale_claims.py` 4/4, `tsc` and `npm run lint` clean, `staged == mine: 9 paths`, `HEAD:<path>` equal to the
recorded index hash for 9/9. No catalogue line was needed — every key already existed — so this slice never touched
the three files the concurrent writers keep editing.

**Not closed by this, and why it is a different question.** The same attribute scan against *every* namespace finds
labels whose key exists but is read by nothing. `world`'s group was the one where the stored key plainly *is* the
page's own word, and it closed in `8feda9a` (recorded below). The rest, re-run on the TSX parser at `8feda9a`:
**`nav` 21, `scout` 14, `coach` 6, `progress` 4, `world` 2, `career` 2, `common` 1, `auth` 1, plus 3 sites two
dictionaries both hold** — and `nav`'s 21 are mostly one repeated find: nine sites reading "Tactical Lab" across the
six `/tactics` page files (seven `eyebrow`, two `title`; the earlier wording here said "pairs" and "five pages", both
of which under-counted — corrected when `844216d` wired them and listed each row), three `title="Football CV"` on
`/portfolio`, three
`title="Community"` on `/community`. The three single hits are the named sense skips (`label="Received"`,
`eyebrow="Get started"`, `title="Table"`), not open work. The plane is named because it moves the number: the
census reads **105 HEAD `.tsx` blobs**, where a worktree walk reads 107 — the two extra files, and the `agents`
dictionary their single hit comes from, are a writer's uncommitted work. What is left is key-**ownership**
decisions — which namespace a page label belongs to (e.g. `/club/{ident}/plans/{plan}` `title="Progress"`, or
"Tactical Lab" living in `nav` while the tactics pages have no namespace of their own) — not a value lookup, and
answering them by importing whichever dictionary happens to contain the word would make the catalogue the author of
the UI. Also unclosed: attribute labels with no key anywhere, `CreatorWorkbench`'s `Headline` / `Biography` /
`Guide title` / `Section` / `Visibility`, which need new keys the way the content-page namespaces do.

**Done (the `world` section headings, 2026-10-11, `8feda9a`).** Sixteen labels whose text was already in the
catalogue, wired without authoring a key — the same no-contention route that made shape C safe to land while three
writers kept editing `messages/*.json`. Six `eyebrow="Football World"`, the six `WorldHead title`s (Competitions,
Fixtures & results, Reports & notes, Players ×2, Clubs, Training log), `label="State"` on the matches filter, and the
two pages that had borrowed a world word from outside `/world/*`: `app/player/{slug}` `title="Training log"` and the
signed-in `app/simulation/aggregates/player/{slug}` `title="Players"`. Those two files read **no catalogue at all**
before this; every key they now use already had a reader on `app/world/page.tsx`, which is what makes borrowing
legitimate rather than convenient.

- **Sense skip, named:** `/competition/{slug}` `title="Table"` sits over a standings table
  (`{standings.length} clubs with at least one played fixture`) while `world.tableHeaderTable` is the column header of
  a *database* table — 表格. Same three letters, different word. The scan surfaced a second one while this record was
  being written: `/training/{slug}` `eyebrow="Get started"` sits over "Add this drill to today", while
  `auth.getStarted` = 开始使用 is the register-CTA sense of the same two words. Naming it is the whole action — a
  drill-scheduling eyebrow reading the `auth` dictionary would be wrong twice over.
- **A fourth shape, still open.** `back={{ href: "/world", label: "Back to Football World" }}` is a label inside an
  object literal in a JSX *expression*: neither the bare-quoted nor the `={ "…" }` attribute spelling matches it, so
  the census reports 0 for it while six pages carry it. Recorded as unclosed rather than wired blind — it needs its
  own key first.
- **The fallback locale's bytes are the risk in a wiring commit, and this time a derived check reads the diff.**
  `world-parity.mjs` zips each hunk's removed literals against the `tw("key")` calls added in the same hunk and asserts
  `en.world[key] === removedLiteral`: 16 pairs, 0 mismatches, so `en` renders what it rendered before. Its first run
  **refused** — the diff header `--- a/x` was being counted as a deleted line. The refusal firing on my own parser is
  the proof the branch works; a check that cannot refuse is not a check.
- **The live read got a reverse control.** Judging the same `zh` bytes against the *English* value goes red while the
  `zh` value stays green (arm A, three pages); no English literal survives in the wired element on any of the six
  world pages (arm B); and `/world/matches` `zh` carries **exactly one** filter label, `状态`, printed beside the
  still-literal `By state` panel eyebrow, so the `tableHeaderState` claim names its own element (arm C).
  `world-read.mjs` 24/24 over `zh`/`zh-TW`/`en` on port `8816`, the authenticated aggregate page included.

**Census basis, corrected.** The status row read "51 files bind a translator (70 bindings)". That walk ran over the
*worktree*, which then held a foreign writer's uncommitted `app/agents/` pages — 2 files, 3 bindings. On HEAD blobs
the same walk reads **49 files / 67 bindings** at `fe7685d` and **51 / 75** at `8feda9a` (+2 files, +8 bindings: this
slice's two new pages and their eight `world` bindings). The file counts coincide; the numbers are not the same
measurement, and a walk over a plane that mixes two writers' work cannot be compared to one that does not.

The corrected walk became a tool, and the first tool was wrong. `census-head.mjs` matched lines, and it admitted
**two** `app/login/LoginForm.tsx` rows as shape-A labels (`:47`, `:63`, both the line `required`) — the HTML boolean
attribute name, not a label. Re-running it confirms the defect is still there rather than a transcription of an old
output: line scan gives A 27 sites / B 110 / C 54. Line scanning cannot tell JSX structure from JSX text, so the
census was re-run with the actual TSX parser (`census-ast.mjs`: `typescript` 5.7.3 as required through
`apps/web/package.json`, `createSourceFile(…, ScriptKind.TSX)` over the 105 HEAD `.tsx` blobs, **0 parse
diagnostics**, walking `JsxText` nodes for A/B and `JsxAttribute` nodes whose name matches the label list for C).
Its verdict: **A 24 sites, B 172 rows / 168 sites, C 57 rows / 54 sites — 245 distinct sites**, where A is a label
alone on its line and B the same label inline. Comparing the two artifacts site by site: **A 24 ⊂ 27** — the three
the parser refuses are exactly false positives, `LoginForm.tsx:47` and `:63` (the attribute name `required`) and
`app/page.tsx:95` (the identifier `capabilities`, a ternary operand inside a `{ … }` expression that renders no
label at all); **B 110 ⊂ 168** — every line-scan B site survives the parser, which adds 58 more, because
`>text<` on one line cannot see a label the formatter put on its own line, nor text sitting after an expression as
in `{objective.actual} of {objective.target}`; and **C is identical, 54 sites on both**. That agreement matters
more than the disagreement: C is the shape every landing of this arc has worked, so a heuristic and a parser
reading the same population reach the same 54 — while the JSX-text shapes were never measured honestly until now.
Shape C splits by dictionary: **nav 21, scout 14, coach 6, progress 4, world 2, career 2, common 1, auth 1**, plus
3 sites two dictionaries both claim. The finds the earlier `common`-only scans could not see:
`components/world.tsx:243` renders a bare `all` chip in the same `FilterChips` whose label this slice wired;
`app/not-found.tsx:18,21` prints `My Football` and `Training` while `nav` holds both; `ScoutShortlistPanel` carries
**eight** shape-A cells — seven equal a `scout` value (`Room` `Age` `Overall` `Potential` `Headroom` `Asking fee`
`Off`) and the eighth, `Players` at `:158`, equals two `world` keys, which is a naming collision rather than a
borrow. Each still needs the sense test before it needs the call — `open`, `all`, `With` / `Without` are the
kind of short words that equal a catalogue value in one dictionary and mean something else in the sentence they sit
in. And the parser overturned a claim of this arc's own: `common` and `world` were recorded as census-closed on
every shape because the line scanner found **0** shape-A labels for them; the AST finds seven (`all`, `Open` ×2,
`With`, `Without`, `Seed`, `Players`, and the `Room` header beside `Players`), and each of them is a sense skip
before it is a wiring. Zero rows was the tool's blindness, not the tree's.

**One death left unattributed, on purpose.** The first server of this slice (`8811`) died mid-batch with
`ECONNRESET` immediately after the boot block it printed. That block — `Error: ENVIRONMENT_FALLBACK` — appears
identically in **6 of 6** server logs from this arc, including ones started before this slice existed, and the log
does not grow with route reads, so it is boot-time and pre-existing; the restart answered every page. The death is
therefore not charged to it, and not explained either.

**Done (the `nav` section headings, 2026-10-11, `844216d`).** Fifteen attribute labels, eight files, no new key and
no catalogue line: seven `eyebrow="Tactical Lab"` and two `title="Tactical Lab"` over the six `/tactics` page files,
three `title="Community"`, three `title="Football CV"`. Every one is a page's own section heading, which is what
`nav` holds, so the ownership question the previous paragraph left open did not arise here — it arises for the two
sites this slice deliberately did **not** take (below). `nav`'s 21 reconcile exactly, once the census's
lower-cased bucketing is undone: **17 byte-exact against `en` + 4 case-only** (the parser matches
`value.toLowerCase()`, so `title="My football"`, `eyebrow="Video analysis"` ×2 and `title="Transfer market"` are
reported as `nav` hits while `en` says *My Football*, *Video Analysis*, *Transfer Market* — wiring those four would
rewrite the fallback locale's bytes, which is the one thing a wiring commit must never do). The 17 split **15 wired +
2 left**: `club/{ident}/plans/{plan}` `title="Progress"` (a panel over review arithmetic, whose eyebrow says so —
`nav.progress` is the app's *section*, so this is ownership, not a lookup) and `training/{slug}` `eyebrow="Video"`
(a drill's demonstration clip, while `nav.videoShort` names the video-analysis section). Both are recorded as open
work with the reason, not quietly dropped.

- **The live read asserts three things per row, and the middle one was not enough.** `nav-read.mjs` sends one cookie
  and reads one element, so its first run reported **eight zh-TW reds that were its own**: the harness sent
  `fo_locale=TW`, which is not a locale the middleware knows, so the app correctly fell back and answered English.
  Each row now also pins the page's own claim — `<html lang>` must equal the tag the row asked for — so a cookie that
  selects nothing is a refusal naming the harness instead of a phantom translation gap. The second defect was in the
  same file's arithmetic: the mismatch branch printed `RED …` without incrementing `red`, so the run summary read
  **"16 green, 0 red of 24"** beside eight printed reds. A tally that loses rows cannot gate anything; the branch now
  counts, and the run refuses unless `green + red` equals the row count. With both fixed: **24/24** over
  zh/zh-TW/en — 8 paths × 3 locales, on a fresh build (`Compiled successfully`, exit 0) served on `8817` against the
  running API and on `8818` against a stub that replays a *captured* `/auth/me` and refuses every other read, which
  is the only way the `WorldUnavailable` branches holding most of these labels render for real.
- **Green here is decisive without a second build, because `want` did not exist in HEAD's bytes for that element.**
  `战术实验室` / `社群` / `足球履歷` can only come from the wired call; the same element pre-slice held an English literal,
  so a stale bundle prints RED. And a per-row `keep` pins a literal this slice left alone on the same page —
  `Tactical system`, `Compare two systems`, `My tactical boards`, `Shared tactical board`, and on `/community` and
  `/portfolio` the surviving string is `WorldUnavailable`'s own default `eyebrow`, `"Football World"`. That last pair
  is the whole point of the `keep`: it proves the neighbour moved while this element stayed English, which a wholesale
  locale fallback cannot produce.
- **Shape E: a default parameter is a label no caller can translate.** The parser's new shape found three sites, in
  three different components: `components/world.tsx:272` `eyebrow = "Football World"` (equal to both `nav.world` and
  `world.title`), `components/AttributeRadar.tsx:6` `label = "Attribute profile"` (`progress.metricAttributeProfile`)
  and `components/ui.tsx:94` `title = "Why this was chosen"` (`coach.whyChosen`). Every caller that omits the prop
  renders English whatever the cookie says, which is why `/community` and `/portfolio` now show 社区 under an English
  eyebrow. `WorldUnavailable`'s sibling default, `title = "Data unavailable"` at `:273`, is the same hazard pointing
  the other way: no dictionary holds those bytes, so it is not a wiring candidate — and it is *also* data, because
  `app/training/[slug]/page.tsx:98` invents that exact string as a sentinel and `:212` branches on
  `video !== "Data unavailable"`, where `video &&` can never be false since the sentinel is never empty. A shape-E
  landing therefore has to move the sentinel's comparison in the same commit, or it changes behaviour while looking
  like a translation.
- **The census moved, and the arithmetic asked a question.** Re-running `census-ast.mjs` at `844216d` reads
  **C 42 rows / 40 sites** where the walk recorded at `1b4cf2d` — whose `apps/web` bytes are `8feda9a`'s, since that
  commit wrote only this document — read 57/54. Rows fell by exactly the 15 wirings while *sites* fell by 14. Diffing the two artifacts site by site names the extra one: `tactics/[slug]/page.tsx:79` carried **two** C rows
  (`eyebrow="Tactical Lab"` and `title="Tactical system"`), the first was wired, and the second survives at `:81` —
  same label, same element, a line number that moved because the slice wrote an import above it. A site identity
  keyed on `file:line` therefore re-counts a site that was never touched, which is why the union
  (**245 → 231 distinct sites**, 248 → 234 counting shape E) is quoted with its ref every time it appears.
- **A witness must grade the plane that lands.** `parity.mjs` passed before staging and then crashed on re-run: it
  read `git diff` (empty once the slice is staged — *nothing graded* is not *a pass*, so it now throws on an empty
  diff) and it read `messages/en.json` off disk, which three concurrent writers keep editing. It now takes each
  source file from the index (`git show :path`) and `en` from HEAD, and prints, for every namespace the slice reads,
  whether HEAD and the worktree catalogue agree before making any claim that depends on that agreement (`nav` and
  `common`: they do). Its refusal branch was proved by rewiring one site to `nav.training` — it named the key, its
  `en` value and every literal in the hunk, exit 1; the file came back byte-identical and the run went green.

`tsc --noEmit` and `npm run lint` clean, `staged == mine: 8 paths`, and `HEAD`'s numstat is the 8 files +30/−15 the
derived expectation computed before staging.

**Evidence.** The locale walk's per-page assertions: switch to `zh`, read a string that used to be a literal,
assert it equals the catalogue's value. The `useTranslations` caller count moves with each landing.

**Watch for.** `middleware.ts` resolves the locale server-side; a client component reading `useTranslations`
needs the locale in its provider — `app/layout.tsx` already passes it. The trap is `getTranslations` on **async**
Server Components (`app/page.tsx`, `app/settings/page.tsx`): a hook cannot be called after an `await`, so those
pages bind their translators in one `Promise.all` up front. Non-async Server Components take `useTranslations`
directly — measured at `f5460d5`, where `WorldPager` answered in the cookie's locale. `Nav.tsx` is the client-side
worked example. Found during
the auth batch: a long walk can outlive a `next start` process on this machine — mid-walk `ERR_CONNECTION_REFUSED`
means restart the web process and rerun, not debug the page.

---

## Item 3 — §35's pointer promise (landed 2026-10-09, `d18d4c1` was the paper; the tier's own landing is the community resolver)

**The claim as written was false.** "§36/§37's remaining community verbs" read §35's module numbers as one list and asked
for verbs that do not exist. §35 is the community wall — landed 2026-09-28 at M9
(`docs/M9_COMMUNITY_VERIFICATION.md`; the audit's §35 row reads "moderation, reporting and blocking are not in this
build", and this spec has no other place that asks for them). §36 is the **creator** system — landed
2026-09-28 at M10 (`docs/M10_CREATOR_VERIFICATION.md`; the audit's §36 row records `services/creator/publishing.py`,
7 paths / 11 operations under `/api/v1/creator`, all landed 2026-09-28). §37 is the **gamification** module — `services/
achievements.py`, `progression.py`, `/api/v1/progress/*`, `/progress`, landed at M1. Neither spec module asks for a
community verb, and the M9 done-set's content nouns are all landed; there is no moderation, reporting or blocking
work in this spec at all.

**What was actually open** is the promise the wall's nouns make. §35's Tactical Boards, Training Plans and Video
Highlights are already landed as the wall's `my_tactic`/`my_training`/`my_analysis` kinds — pointer, never a copy —
so there was no missing table and no missing door. What no door held was the tier's own sentence: *the kinds a user
may publish all point at artifacts that are the author's own to share*. An address was checked for **shape** and not
for its **referent**, so a public post naming another account's clip published the existence of a private row.

**Landed.** `create_post` resolves the address before the row is stored: five kinds read the author's own rows
(`my_match` → `sim_matches`, `my_tactic` → `tactic_boards`, `my_analysis` → `video_assets`, `my_career` → `careers`,
`my_goal` → the *windowed* career the run prefix names) and `my_training` reads the project's drill catalogue. Both
failures answer one code (`post_artifact`, 404, in the tier's `NOT_FOUND_CODES`), with the author's own words as
figures — a sentence that told a guessed address apart from someone else's row would be an oracle, which is the
disclosure `ownership_or_admin` refuses with a 404. Evidence: five new cases in `tests/test_community.py` (50 in the
file), a green file on the SQLite leg, and one probe arm whose reds are named in
`docs/M9_COMMUNITY_VERIFICATION.md` — along with the finding that `scripts/probe_m9.py`, cited by that same file, is
not in the tree.

---

## Item 4 — M12's first slice: account-level erasure end to end

**Done 2026-10-06 (`2671102`, found as a finished uncommitted tree from 10-03, verified then committed).**
`GET /auth/account` previews the full inventory; `DELETE /auth/account` takes the phrase and the password,
erases in one transaction, refuses an escaping storage key **before** any write (503 `private_media_not_erased`),
and blocks a last owner with other active members (409). Rows that must survive (`SET NULL` model calls) do; the
audit row names no erased identity. The census gained its third 403 code (`invalid_password`) and an erased
account answers 401 `unauthenticated` again rather than 403 describing somebody who is not there. Evidence:
`tests/test_account_deletion.py` (4 cases, including the escape probe), full suite green except the contract
byte gate this same landing fixed.

---

## Item 5 — M11's first composite task

**Why.** It is the last unopened milestone that is not hardening, and §30 Knowledge Graph is blocked behind it by
an explicit decision.

**Do.** Do not start with eight agents. Start with §33's smallest composite task end to end — an orchestrator, one
specialist, one tool call and a stored trace — and measure it against §64's benchmark before adding a second
agent. A multi-agent system with no benchmark is a diagram.

**Evidence.** The benchmark run, its score, and the trace of the run that produced it.

---

## How to work an item

1. Read the milestone's existing verification document first. It will name the trap that was already hit.
2. Write the check before the feature when the check is expressible — several of this project's best findings
   came from a check that existed before the thing it checked.
3. Run `bash scripts/check.sh`. If it fails on files you did not touch, that is a finding, not an obstacle:
   record it and fix it in its own commit, the way the last three passes did.
4. Verify in a browser when the change is visible. `scripts/verify-production.sh` builds, serves on a throwaway
   port, proves the port is serving *that* build, then walks. Do not quote a walk figure you did not run.
5. Write the evidence into the milestone's verification document with the command that reproduces it.
6. If a claim turns out to be false, correct the claim in the same commit that corrects the code. Several of this
   project's documents currently say what was true at the step they were written, and say so.
