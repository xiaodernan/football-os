# PLAN — the work that is left, in the order it should be done

`ROADMAP.md` says which milestone is open and what has been proven. This file says what to build **next**, in
order, with the evidence each item has to produce before it counts as done. It is written to be picked up cold:
every item names the files it touches, the gate it must pass, and the thing that would make it a lie.

Rule inherited from spec §96 and this project's own practice: **an item is done when its claim is measured, not
when its code exists.** A number in a document that no command reproduces is not evidence.

Last updated 2026-10-15.

---

## Done, and what it cost

| Item | Landed | Evidence |
| --- | --- | --- |
| **0. one gate, not three** | ✅ 2026-09-30, **completed 2026-10-20** | The 2026-09-30 row said `scripts/check.sh` and CI both run `python -m ruff check` with no path arguments, proven by planting an unused import in `evals/`. Both halves were true and the item was still open: run from inside `apps/api`, that command walks `apps/api` alone, so 4 committed `.py` files outside it — all in `scripts/` — were read by neither caller while this plan claimed the whole project was covered. The target is now written down once, in `scripts/lint.sh`, and both callers run that one file: all of `apps/api` plus every committed `.py` outside it, derived from `git ls-files` per run, with the population printed. Witnessed 6/6 on a worktree at `33bdd8c`, including the reverse control (the old command green while a planted defect sits in `scripts/`) and a newly `git add`ed file joining the target unaided. Item 0 says what was measured. |
| **1. §13's 3D pitch** | ✅ 2026-09-30 | `components/pitch.tsx` projects the board's own metres isometrically; `237/237` walk checks on a production build, with a check that recomputes every dot from its metres and another that holds the projected lawn inside its `viewBox`. `docs/M4_WEB_VERIFICATION.md` §8. |
| **2a. §81's `locales` claim** | ✅ 2026-10-01 | `tests/test_locale_claims.py` binds `locales` to the catalogues in both directions. Found that `zh.json`/`zh-TW.json` are 278/278 copies of English, so the field stays `["en"]` — and now cannot be moved without a translation or left unmoved with one. |
| **2b. §81's translations + the switcher** | ✅ 2026-10-06 | `LocaleSwitcher` writes the `fo_locale` cookie middleware has always read; `locales` moved to `["en","zh","zh-TW"]`; both Chinese catalogues are now **complete** — `zh` 392/394 translated (fallbacks: `scout.placeholder` already Chinese in the English file, `settings.apiBadge` = 'API {status}'), `zh-TW` 393/394 (`settings.apiBadge` only), `zh-TW` written as Traditional rather than converted. `test_locale_claims.py` 4/4; the locale walk drives the real switcher and reads the repainted shell. |
| **2c. the catalogue is reachable from the content pages** | 🟡 2026-10-11 | **Development is wired** — a 54-key `progress` namespace written from the page's own strings (metadata, four group names, five stat labels + hints, the XP bar, both panel footers, four day buttons, two empty states, the achievements panel, the closing notice). Coach before it (78 keys, three files); scout/career/world were wired from keys that already existed — and `8feda9a` closed `world`'s seventeen **attribute** labels the same way, no new key: 16 wired, one named a sense skip, two of the files (`/player/{slug}` and the signed-in aggregate) reading no catalogue at all before it. **15 files now read a catalogue**, walk **140/142** on a production build — all three of this page's checks green, and the run stopping at 142 rather than ~199 because the video section aborted it again (see the video row below; the three checks are placed in front of it for exactly that reason). **Tactics is wired (2026-10-11)** — a 173-key `tactics` namespace written from the six pages' own strings (index, `[slug]` with its counterfactual/3D/analysis/roles/demands panels, compare, boards index, board edit with two `t.rich` link embeds, shared token) plus the shared furniture (`BandLegend`, `MetricTable`, `Verdicts`, `ChangeNav`, `SystemCard`); English values are byte-identical to the literals they replaced, walk assertions untouched. `agents` (36 keys) before it. **`Panel` now forwards `data-*` props** — the aggregates walk checks' `data-testid` hooks never reached the DOM (they were `Panel` props this component dropped on the floor), so those two checks had never once passed. **History is wired (2026-10-11)** — 47 keys for `/history`, walk **178/181** with all three of its checks green. It had been **half-wired**: it already read `common` for `previousPage`/`nextPage`, which is the shape that hides work — a page that reads *some* catalogue looks finished in a grep for `useTranslations` while its own copy is still literals. **Twice now**, so it is a pattern, not a coincidence: grep for `useTranslations` is not a measure of coverage, because a page reading one catalogue looks done. The measure is a page's *own* copy and it has to be read. **Training is wired (2026-10-12)** — 108 keys across four files, the largest yet (index, `[slug]` with its eight panels, `AddSession`, `SessionLogger`), walk **212/214**, the furthest any run has got. Two shape notes worth carrying forward: `ratingLabel` was a `Record<string,string[]>` of fifteen sentiment words read in two contexts, so the fifteen keys had to resolve **inside the component** rather than be baked into one concatenated sentence; and two `<Panel title="…">` props became keys, which means **"no literals in the JSX" is not the whole check either** — translated text can arrive as a prop. **Shape D's back links are wired (2026-10-12, `c7e9f4c`)** — seven pages now take `nav.home` / `nav.myFootball` from the catalogue, and reaching two of them to prove it required fixing the door's exemption semantics first (the row on the share link). **Shape D's document titles are wired (2026-10-12, `dd8618c`)** — nine `export const metadata` titles became `generateMetadata`, each taking **the key that page's own heading already reads**, so a tab cannot drift from its h1; witness 65/0 over 9 sites, arms 7/7 (the seventh is a control: move only the `<Panel>` title beside the h1 and the witness must stay green), live read **135/0** over 9 routes × 3 locales on a fresh bundle. **The rule is a shipped gate now (2026-10-13, `ef0ff8b` + `5ef05eb`)** — `apps/web/scripts/qa-metadata-title.mjs` reads it off all 59 pages, registered in `scripts/check.sh` and `ci.yml`: **94/94** on a clean plane, witness **12/12 arms**, live read **34/0** with a still-literal page as the control, and `/knowledge`'s tab wired to the orphan `knowledge.metaTitle` its own writer had left unread, which is the last of the eleven byte-exact metadata sites this arc counted. Two lessons from the read being wrong first: its `og:title` claim was written as one promise for nine pages and went red on three, because those three carry no `openGraph` block and fall back to the layout's `title.default` — *at HEAD too*, so nothing had moved; the claim is now derived per site from HEAD's own bytes, with a floor that refuses the run if no route carries its own preview title. And `/my-football` came back **307 → `/onboarding`**, which is the product correctly refusing a user with no player: the read was measuring the door, not the page, so the session is now onboarded through `POST /players` with the option values the onboarding form itself lists. **One lint red is at HEAD and is not this slice's** — `app/knowledge/[slug]/page.tsx:38 'tc' is assigned a value but never used`, landed by `5aa8926`; eslint over the nine files above alone exits 0, so read the gate with the plane's sha. **That red is still at `5ef05eb`** — the whole-app `next lint` that exited 0 on 2026-10-13 did so because the worktree holds someone else's *uncommitted* one-line fix for it (`git diff` shows `- const tc = await getTranslations("common");`), and the machine-wide pre-commit hook grades the worktree, not the commit. The way to grade a lint claim at a ref without disturbing a shared tree is `git show HEAD:<path> | npx eslint --stdin --stdin-filename <path>`, which re-prints the `tc` error at line 38. Still literals: club, community, video, simulate (another session is wiring club/community/graph/portfolio/simulate in parallel — count the callers, do not assume). **Knowledge is wired (2026-10-12)** — 96 keys across four files, walk **215/217**. **It was the third half-wired page**: all three top-level files already read `common` (the "all" chip, the Search eyebrow, the DEMO MODE badge, `open` in the citation link) while everything else was literals — history and training arrived the same way, so **three of five**. PLAN now states plainly that `grep useTranslations` is not a coverage measure. Three shape notes for the next person: a small server component sharing the page's file needed `getTranslations`, **not** the client hook `useTranslations`; when one file reads *two* namespaces, `t` means a different catalogue depending on which half you are in (the build catches it); and a lede with a conditional prefix became **three keys** (`ledeCounts`/`ledeNoCounts`/`ledeRest`) — the first sentence in this batch that had to be split. `validation` (8 keys) waits for a form that shows custom messages. **Challenges is wired (2026-10-13)** — a **154-key** `challenges` namespace across four files: `/challenges`, `/challenges/runs/[slug]`, and the two client components that actually do the work (`ChallengeStartForm`, `ChallengeRunTools`). It is the first namespace written for a route with no shared furniture of its own, and the walk is **282/0** — a full run and the furthest any walk has gone, clearing both places a run used to stop (the video section and the `/simulation/aggregates` player detour), with the three challenges checks placed in front of them as always. English values are byte-identical to the literals they replaced, proven by diffing every value against the pre-wiring blobs: **110 verbatim**, **40 templated** with a placeholder, and **four that differ only by source form** — two carried an `&apos;` entity rather than a typographic apostrophe, and two were one sentence the JSX had split around a `<Link>` (`refPre`/`refLink`/`refPost`), all of which render identically. Three shape notes for the next person. First, **almost none of this page's copy was bare JSX text**: it arrives as `Panel eyebrow`/`title`, `WorldHead back={{label}}`, `<th>` text, `KeyValueGrid` rows and `<option>` labels, and every one of them is a key carrying a placeholder the number beside it fills (`{used} of {limit} used`, `Next up: round {round}, {side} {opponent}{venue}.`), which is what keeps the English bytes identical while the count moves. Second, **two client components sharing the page's namespace bind their own `t`**, and `ChallengeStartForm`'s `OpenedRun` binds **both** `challenges` and `common` in one function body — the `t`-means-two-catalogues trap the knowledge slice named, which typecheck caught once when a stale `t("open")` pointed at the wrong catalogue. Third, the route is **session-gated** (it starts a run and lists this account's verdicts), so its checks ride the session the walk already mints at registration; the walk separately proves the door (signed-out 307 to `/login?next=%2Fchallenges`, catalogue still public at 200) and the crawl exemption (robots disallows, sitemap absent). The knowledge slice's `tc` lint red named in this row is **closed**: the line is gone and the whole-app `npm run lint` that `verify-production.sh` runs at the top of every evidence run now exits 0. **The transfer market is wired (2026-10-15, `4f5c284`)** — a **153-key** `market` namespace across two files (`app/career/[slug]/market/page.tsx` and the client `MarketTools`), **44 call sites**. It arrived **half-done and nothing in the tree said so**: an earlier pass had written 150 keys into all three catalogues and wired only the page's top half — the same shape that hid history's and knowledge's work, because a catalogue key nothing reads is indistinguishable from one that works. Three keys no attribute-shaped scan could reach were added (`boardNeedPre`/`boardNeedPositions`/`boardNeedSquad`): the buying table's caption interleaves a `<strong>` with prose, so it was split one fragment per side of the element, the way the world's back links were. **The graded claim is not "it is translated" but "the English did not move"**, and it is checked rather than asserted: `.scratch/i18nprobe/market-parity.mjs` reads HEAD's two blobs and requires every literal fragment of every English value to appear in them, with whitespace collapsed and `&apos;` decoded so a line break or an entity cannot pass as a rewrite — **182 fragments, 180 verbatim**, and the two that are not are *declared in the script with their reason* (`dealsNote`'s two arms come from an inline conditional, which no text comparison can see through; HEAD carries both arms verbatim). The same run asserts **all 153 keys are read, 0 orphans**. Two nullable fields (`player_name`, `counterparty_name`) are passed through `String(...)` on purpose: the literals they replaced interpolated them straight into templates, so a null printed `null`, and ICU renders a null value as the empty string — `String` keeps the rendered bytes identical, and making the empty case read well is a separate change with its own evidence. **A new hole is closed for this namespace.** Nothing in the build reads a catalogue — `next-intl` resolves a key in the browser — so malformed ICU (a plural with no `other`, an argument name the parser rejects) compiles, typechecks, lints and 500s the page; `.scratch/i18nprobe/market-icu.mjs` parses and formats all **459 messages (153 × 3 locales) at count 1 and count 2**, so both plural branches execute rather than merely parse, against the app's own `@formatjs/icu-messageformat-parser` off `node_modules`. Gates: `tsc --noEmit` clean, `npm run lint` clean, `test_locale_claims.py` 4/4, identical key sets 153/153/153, and each catalogue diff a single pure 155-line insertion. **Not done, and named:** the live walk assertion. `scripts/qa-market.mjs` is this route's own walk but it asserts arithmetic, not locale, and `scripts/visual-qa.mjs` — where the per-page locale checks live — carried another lane's uncommitted hunk, so adding one there would have staged their work with mine. The three checks (Chinese renders / English gone / switch back) go in when that file is free. |
| **— `common` is 97 keys and 3 are read** | ⚠️ not the next step | Measured 2026-10-09. `common` is generic UI vocabulary (`save`, `cancel`, `loading`, `yes`, `no`, `or`, `of`) and **three keys are read** — `language`, `demoMode`, `demoModeTitle`, all from `Nav`/`LocaleSwitcher`. Of its 97 English values, 16 appear as a literal anywhere in `app/`+`components/` and 80 appear nowhere: there is no `Loading…` string in the project at all. The app's real vocabulary is domain words (Player, Age, Position, Club, Expected goals, Fixture) which belong to pages, not a shared namespace. So the plan's "wire `common` next" had nothing to wire; the next work is a page, and `coach` was the next page a reader meets. |
| **4. §61 account erasure end to end** | ✅ 2026-10-06 | `GET/DELETE /auth/account`: preview inventories every row and byte, one confirmed transaction, media containment refused before any write, last-owner blocking (409), §60's third 403 code (`invalid_password`) registered. 4 tests including the escaping-storage-key case a planted-defect probe demanded. |
| **§38/§60 portfolio share + PDF** | ✅ 2026-10-06 | `POST/GET/DELETE /portfolio/share[/{token}]`, `/portfolio/cv.pdf` (reportlab), robots keeps both off crawlers. Committed with the two above because all three share one contract file. |
| **— migration `0026`** | ✅ 2026-10-07 | Not on the plan. `alembic upgrade head` did not run at all: `0026` and `2e197f085070` both revised `0025`, so the graph had **two heads** and every fresh database, gate run and deploy failed at the first step — invisible because `python -m seed` builds its schema from the models. Behind that: `sa.Index` inside `create_table` (invalid SQL), `now()` (not a SQLite function), and a table declaring `id INTEGER` where the model says `String(40)`, with no `updated_at`. Verified: `0025 → 2e197f085070 → 0026`, `rc=0`, `alembic check` clean. |
| **— every commit is refused on this host** | ⚠️ environment | Found 2026-10-09. The global `pre-commit` hook (`~/.codex/git-hooks/pre-commit`) ends with `trap 'rm -f "$FILES_TMP"' EXIT`, and `FILES_TMP="${TMPDIR:-/tmp}/codex-global-pre-commit-files.$$"`. This host exports `TMPDIR=C:\Users\18414\AppData\Local\Temp`, so the path becomes `C:\Users\...\Temp/codex-global-pre-commit-files.958` — mixed separators — and the safe-delete shim refuses it: `[safe-delete][SAFE_DELETE_INVALID_PATH] embedded drive prefix is not allowed`. The trap's failure becomes the hook's exit status, so the hook prints *passed* and then fails the commit. **The checks are not the problem and the hook is not wrong to run**: `TMPDIR=/tmp git commit …` commits normally. Worth fixing in the hook (use `mktemp`, or strip the drive) rather than in every caller. |
| **— the middleware's prefix list had drifted from the pages that gate themselves** | ✅ 2026-10-11 | Found by walk run 3: the silent refresh only runs for `PROTECTED_PREFIXES`, and `/simulation` (plus `/agents`, `/club`, `/community`, `/creator`, `/graph`, `/portfolio`, `/scout`, `/simulate`) was missing — a signed-in reader whose 15-minute access token died mid-visit was bounced to /login by the page's own `currentUser()` instead of being refreshed. `/club/rules` is exempt (`PUBLIC_EXCEPTIONS`) because the rulebook is the one /club page a signed-out visitor may read. The walk's own session proves it: the aggregates section, last in the run, went from 307 to 200. |
| **— the same door's *exemption* list could only ever fire on one page** | ✅ 2026-10-12 | Found by the shape-D live read, not by the walk: `GET /video/shared/e90273…` answered **307 → /login** in all three locales while `/tactics/shared/<token>` answered 200. Cause: `isProtected()` matched `PUBLIC_EXCEPTIONS` by **exact pathname** (`pathname === "/club/rules"`) while matching `PROTECTED_PREFIXES` by prefix — so an exemption could never reach a segment below it, and `/portfolio/shared` had never been listed at all. Both lists now share prefix semantics and both share doors are exempted. `apps/web/scripts/qa-middleware-gating.mjs` is the shipped gate: it slices the decision out of `middleware.ts`, transpiles it with the repo's own TypeScript and **calls `isProtected`** instead of paraphrasing it, then reads every page under `app/` — today 59 pages, 38 that read or redirect to a session, 34 gated by the door — with checks for a private page the door misses, a public page the door still catches, and a stale exemption. It runs **red on HEAD before the fix** (the reverse control), which is what makes it a gate rather than a description. Registering it in `scripts/check.sh` and `ci.yml` needed a `fileURLToPath` fix first: `new URL("..", import.meta.url).pathname` percent-encodes this repo's CJK path and the read dies with ENOENT. Un-gating the clip page exposed a **second defect behind the first**: it typed the owner's `VideoReport` against the shared door's flat summary, so it rendered a 500 (`TypeError … 'frame_count'`) the moment it was reachable. The page was rewritten to disclose what the door actually answers — ten record fields, and it now says that the clip's bytes, frames and detections stay with the account that uploaded them — rather than widening the API to hand analysis bytes to a token-holder. That widening is a decision about what a share link *means* and is left open in `docs/MIDDLEWARE_GATING_VERIFICATION.md`. Live read: 18 green / 6 red → **24 / 0**. |
| **— the crawl policy was three files describing each other, and 8 gated pages were in no `Disallow`** | ✅ 2026-10-13 | Found by reconciling the files instead of reading their comments: `middleware.ts`, `app/robots.ts` and `app/sitemap.ts` split one decision and each only *described* the others in prose. Measured on the worktree (files only) — **59 pages, 34 gated by the door, 10 advertised, 30 declaring `robots:{index:false}`** — **8 of the 34 gated pages sat in no disallowed prefix**: `/agents`, the four `/graph` pages, the three `/simulation/aggregates` pages. Their own `noindex` is **inert**: a signed-out fetch answers **307**, a redirect carries no `<head>`, so the only crawler that would honour the declaration never reads it (all eight confirmed 307 on the served plane). `DISALLOWED` went **21 → 24**. `apps/web/scripts/qa-crawl-policy.mjs` is the shipped reconciliation — it transpiles and **calls** all three decisions and every page's own declaration, then runs 9 checks (floors/callability, gated⇒disallowed, advertised⇒not gated, an advertised path under a disallowed prefix needs a strictly longer `Allow` **and** that mechanism needs a live carrier, advertised⇒not self-`noindex`, stale `Allow`, orphan `Disallow` with `/api/` in a two-directional ledger, readable `robots:` declaration). **9/9** on the fixed tree, **8/9 with check 2 red naming exactly those 8 routes** on the parent's `robots.ts` (the reverse control), witness **13/13 planes matched** on `D:/m107-planes`, live read **24/0** on a fresh `NEXT_DIST_DIR=.next-m107` build served at `:8837` — served `Disallow:` set == the worktree's 24, the older pre-fix server's == HEAD's 21, served difference == file difference, so the read grades this build rather than a restart. Registered in `scripts/check.sh` and `ci.yml`. Two holes the arms found in the gate before they ran: `robots: SOME_IDENTIFIER` made nothing red anywhere (check 8 is that fix), and a CRLF plane — `git archive` emits **LF blobs**, but this host's tar produced 213 CRs in `middleware.ts`, so `\n`-terminated needles silently no-opped; the base plane is now LF-normalised. Two prediction misses where **the gate was right and my prediction was the hole**: deleting a page strands the `DISALLOWED` prefix that named it (check 7, arms A9/A10), and clause 4 is really 4a/4b, so the runner prints 9 checks, not 8. |
| **— the video section aborts the walk about half the time** | ✅ 2026-10-14 | Both suspects in the record were right, and both are fixed. The abort: the walk's own media-detach step called `video.remove()` on elements React owns, breaking the tree the delete button's `router.push('/video')` needed — the page never left the report URL. It now neutralises without detaching (`load()` with no src aborts the range request; a data-URI src cancels the img fetch). The unprovoked console error: the report's "open the file directly" was a Next `<Link>` to an API route, RSC-prefetched into a 404 every visit — it is an `<a>` now. **Measured**: walk run 6 took the video section 10/10 including the delete-and-return check, and reached the career section at check 186 — further than any run since the abort appeared. (Run 6's three career failures are another lane's live work on the simulation aggregates; they were green in run 5.) |
| **— the walk's stopping point moves between runs** | ⚠️ open | On 2026-10-11 a run got past the video section and then died in the **§12j career block** instead: `retiring the season stops the rounds and says so on the page — copy false · button found true · play disabled false`, then `no button containing "Take charge again"`, stopping at 181 checks. So a run reporting ~140, ~181 or ~199 is not three qualities of result — it is one walk stopping in three different places, and **the fraction alone does not say which checks ran**. Read the failed-checks block, not the number. |
| **— `/simulation/aggregates/player/{slug}` answers 404** | ✅ 2026-10-14 | The walk stopped here because of the *player it happened to pick*, not because the door is missing — and both claims this row carried were false. **(a)** "either the route is not mounted or it lands on a different path": `GET /api/v1/simulation/aggregates/player/corand-ruceek` answers **200 today with 6 careers**, the door has been mounted since `3651587` — a commit whose own message is "aggregates+graph: wire the tiers main.py never mounted", and `git show HEAD:apps/api/app/main.py` still carries `app.include_router(simulation_aggregates.router, prefix=api)` at line 344 — while the ref the old record legs ran over (`50efc5e`) mounts 22 routers where the tree mounts 24, which is exactly why that record saw these modules red. **(b)** "advertised by the walk *and by the sitemap*": `apps/web/app/sitemap.ts` emits no `/simulation` path at all and #107 put `/simulation` in `Disallow`, so #107's own probe — **1039/1039 sampled sitemap URLs answered 200, 1039 carried their own copy** — never contained this door. The only in-app pointer is the index page's prose. **The defect was the 404's subject.** The door resolved careers from `career_appearances.player_slug` and raised `not_found` when that list was empty: it refused a player the world serves for having played nobody's season. Its sibling league door resolves `Competition` first, 404s only when the entity is absent and otherwise answers zeros — and the aggregates index page promises exactly that behaviour for a competition ("A competition whose careers stored no events still answers — its totals are zero, and the page says so rather than pretending the season never happened", `app/simulation/aggregates/page.tsx:60`), while the player door refused the analogous case. Measured before any edit (worktree at `f75faf6`, `.env` PostgreSQL 127.0.0.1:54321, `.scratch/r108-namespaces.py`): `real_players` 300 rows / 300 distinct slugs, `career_appearances` 275 rows / **22** distinct slugs, `careers` 31 — **278 of 300 world players were refused**; and **0** appearance slugs lack a `real_players` row while the 22 pairs that exist agree with `real_players.slug` exactly, so resolving the subject from `real_players` is a strict superset of the answering set: **no player answered today is newly refused.** The fix is that resolution — the door 404s only when no `real_players` row carries the slug, the view takes the resolved player so a career-less ledger prints the world's name and position instead of the slug it was handed, and one derived field `career_notice` states why an empty ledger is empty (`""` the moment a career has played). It travels as API prose like `scope`/`source`/`consistency`/`formula`, because a page literal needs a catalogue key and `messages/*.json` are another lane's in-flight files (#106's blocker). **Read in both directions and pinned both ways**: 22→300 answering world slugs, and the refusal still reachable — control slug `definitely-not-a-player-108` answers `404 not_found`. Measured after: live door census `SAMPLE=20` **`200×6 / 404×14` → `200×20 / 404×0`** (`:8734` pre-fix build vs `:8741` this code — and `:8741` is a PostgreSQL read: `select 1` through the app's own engine, server `PostgreSQL 16.15`); suite legs on the worktree **1639 collected** where HEAD collects 1636 (+3): leg 1 `1 failed, 1636 passed, 2 skipped in 3368.94s` and leg 2 after the pin's fix **`1637 passed, 2 skipped, 0 failed, 0 errors in 4810.35s`**, both skips named by the junit (`test_redis_cache::test_redis_cache_real_integration`, `test_scout_search…[need_fit]`) and neither in this module; module **4 → 7 collected** (the deleted skip case passed a `POST /players` `user_players.id` to a `real_players.slug` door — two namespaces, so the skip reason "requires world with careers" was false and no integration could ever have made it answer); `ruff check` exit 0; `mypy app` green, 142 files, at HEAD *and* with the change; `npx tsc --noEmit` clean; contract gate 11 passed and `docs/api/openapi.json` regenerated with **exactly one changed node** — `…/player/{player_slug}/get/description`, because **FastAPI publishes the handler's docstring as the contract**, so rewriting prose moves bytes even with no response model; `qa-metadata-title.mjs` (population 59), `qa-crawl-policy.mjs` (59/34/10/30/24) and `qa-gate-inventory.mjs` unchanged and green — no page added, no new page literal (the sentence is data), no new script. The served plane: preview `:8839` on a `NEXT_DIST_DIR=.next-m108` build, career-less player 200 with `agg-career-notice` present and h1 `Loror Fennmann`, `corand-ruceek` 200 with no notice, unknown slug 404 — then **real Chrome through the shipped register form** (`.scratch/r108_browser_leg.mjs`; the in-app browser tool timed out on every navigate, so the leg is my own puppeteer script against `apps/web`'s vendored `puppeteer-core`, screenshots into `.scratch` because the shipped walk owns `docs/screenshots`): consent armed, `/onboarding` reached, cookies `fo_access/fo_refresh/fo_locale`, notice **painted 553×61**, career rows 0 on the career-less player and 6 on `corand-ruceek`, `verdict: the browser leg agrees with the served HTML`. **Four prediction misses, kept as misses.** (1) I predicted the contract bytes would not move; the docstring is contract, and the byte-identity case went red and named the node — the gate was right, my prediction was the hole. (2) I predicted collection 4→6; it is 4→7, because I wrote a fourth case and did not re-predict. (3) I predicted "+2 collected, 0 new reds" for the suite leg; it collected **+3** and went red **once, in my own case**: `…notice_is_blank_once_a_career_has_played` pinned the door's career list to this fixture's single career, but the suite shares one database and other modules have played rounds whose squads contain the same world player — a door that sums every career naming the slug is *correct* to list them all. The pin now derives the set from `career_appearances` and requires the fixture's career to be inside it. **A green module run is not a green suite run.** (4) I predicted the live census would keep `careers per answered player` at min=6/max=6; re-read after the legs it is **min=0 max=6 mean=1.80** (`.scratch/r108-census-final.txt`) — the answered set *grew* to include the career-less world players, so min=0 is the fix landing, and my clause would have graded a correct build as wrong because it was written about the players who have careers but stated as a census over everyone the door answers. Also retracted: my first `git archive HEAD apps/api \| tar -x` plane was silently **incomplete** (61 of 65 committed `test_*.py`, `tar` exit 0), and two readings taken from it are withdrawn — `1605 collected` (HEAD truly collects 1636) and "6 mypy errors in `app/core/redis_cache.py` at HEAD" (mypy is green at HEAD: `Success: no issues found in 142 source files`, which also retires that file's stale finding in `docs/ERROR_SHAPE_WEB_VERIFICATION.md` and the skip case it names). **That retraction is itself half right, and the other half is worth more than the reading it withdrew (2026-10-15).** The 6-error reading is *reproducible on the full tree* — the incomplete plane was only one of its two causes. `scripts/check.sh` and `ci.yml` both say `python -m mypy app`, and **which `python` is invoked decides the answer**: this host's system Python 3.11 carries `redis 5.2.1`, while `requirements.txt` pins `redis==8.1.0` and the repo's `.venv` has it. `C:/Program Files/Python311/python.exe -m mypy app` answers **6 errors in `app/core/redis_cache.py`** (that version's stub types `Redis.get`/`scan`/`info` as `Awaitable[Any] | Any`, so every synchronous call site reads as wrong), and `../../.venv/Scripts/python.exe -m mypy app` answers **clean over 142 files**. The venv is the gate — it is the version CI installs — so HEAD was green, and the withdrawn reading was charged to a plane when it should have been charged to an interpreter. The lesson is the one Item 0 exists for, one level down: **a gate that names a command but not a runtime is not a gate**, and "mypy is green" is a claim about an interpreter until the tree pins one. A plane is now verified against `git ls-tree -r HEAD --name-only` before any "pre-existing at HEAD" verdict is charged to it. **What this leaves open, named:** the Careers table prints `career.slug` in both the "Career" and the "Slug" column; `app/player/[slug]/page.tsx` still links nowhere to the door, so the index page's "the world's player pages are the way in" is a pointer with no arrow behind it, and an in-app link needs a `world.*` key (#106's blocked lane); and the row above this one — "the walk's stopping point moves between runs" — stays open on its own evidence, since #108 removes one stopping point rather than the walk's dependence on which row it picks. |
| **— the academy's `counts` was typed for a migrated host only** | ✅ 2026-10-17 | Landed `5e213db`, record in [docs/M8_ACADEMY_VERIFICATION.md](docs/M8_ACADEMY_VERIFICATION.md). #108 met a branch-divergent key set from the producer's side and answered by making one field unconditional; the next case in the class is the opposite shape — **the divergence is right and the promise is wrong**. `GET /club/academy/capabilities` composes `counts` from three producers (`app/api/v1/club_academy.py:219`): `academy_counts()` answers 12 keys on a migrated host and 8 on an unmigrated one, `session_counts`/`report_counts` answer `sessions`/`reports` on both, so the door publishes **14 / 10** — and the subset is a tested invariant this suite owns (`set(empty) < set(counts)`, "a reader cannot mistake it for a quiet academy"). `apps/web/lib/club.ts:226-239` at `f3c9f1d` declared **all twelve required and neither of the two always-published ones**: four figures the door may withhold promised, two it always sends un-declared. **Nothing in the toolchain can see it**: `mypy` reads the handler's own `dict[str, Any]`, `tsc` cannot because `lib/server.ts:44` returns `(await response.json()) as T` — the cast *is* the promise — and `docs/api/openapi.json` holds **0 occurrences of `"counts"`** (the word `sessions` appears 15 times, all paths and tags, not one property), contract byte-identical before and after (`sha256 1d6b5630…5dd8ec14`, 411051 bytes). Found from a census, not a guess: `.scratch/r110_divergent_keys.py` (ast, read-only, no server, no DB) over `apps/api/app/**/*.py` at `f3c9f1d` — **145 files, 1461 functions, 32 returning a dict literal on ≥2 paths**; `D1` divergent key sets 13, `D2` conditional insertions 8, `D3` literal-plus-non-literal 15 (44 rows), then a reader join (45 omitted keys, 15 name-matched to a required `lib/types.ts` field with a web reader) — **and the join over-counted**: four of the strongest sites are already honest, each differently (`market.ts` optional + `??`, `CareerNextFixture` optional + a `plan.get("available")` guard, `lib/scout.ts` optional + `?.length ?? 0`, and `AgentRunResponse` defaulting `from_cache=False` so the divergence is absorbed before the wire). A name matching a required field is not a contradiction; only the carrier's text is. **The fix is web-side deliberately** (`lib/club.ts` +14/−4, 23081 → 23768 bytes: ten required, four optional, comment free of numbers): the alternative — publish all twelve on both branches — would overturn the API's own tested invariant to satisfy a type. Reader census says no served byte moves (the four conditional names occur only in the type; the only typed page read of an academy figure is `{edu.counts.rule}` at `app/club/rules/page.tsx:271`, required on both branches), which is why no browser leg ran: a live read could only re-confirm the type. **The gate** (`tests/test_club_academy.py` +97) calls all three producers on both branches, parses the `counts` block out of the real bytes (bound to the type's header, because `lib/club.ts` carries three `counts:` blocks), pins the seam to one composition line naming all three, and reconciles in both directions: always-published ⇒ required, sometimes ⇒ optional, declared-but-never-published ⇒ red. Legs: module **84/84** exit 0 (per-ref `def test_` census 83 → 84, the +1 this case), whole suite **1668 tests / 4 failures / 0 errors / 2 skipped / 2132.595s** with this case green inside it, `mypy app` **145 files** clean on the venv interpreter, `npx tsc --noEmit` exit 0 (11-byte log), `qa-gate-inventory` **54/54**, `qa-metadata-title` **115/115**, `qa-crawl-policy` **9/9**. **All four suite reds attributed by case name and carrier, none this unit's**: three are the contract gate naming `boards/gallery/public`, `boards/gallery/public/{slug}`, `boards/{ident}/list-publicly` — routes that exist only in the gallery lane's **uncommitted** `boards.py` (`git show HEAD:` answers 0 of the three), so no clean plane reproduces them; the fourth is `test_timeutil.py::…test_no_module_takes_its_day_from_the_host_clock`, whose file is **untracked** and whose offender `planned_date=date.today().isoformat()` is committed at `app/api/v1/trainings.py:84`. Whole-project `ruff` exit 1 is the same untracked file's `F401`. **Two findings about the witness, both fixed in the product rather than by relaxing an expectation.** (1) **pytest renders a collection-valued assert message through its own repr and elides the middle**: `assert not problems, problems` printed **492 of 692 characters and dropped 3 of the 6 verdicts** — measured in `D:/r110-tiny` (no conftest, 0.09s, so it is a rewriting artifact, not a fixture or a timing one) and against plain Python (no elision); the shipped message is now joined, and the next verdict named all six keys in 770 characters. **#111 is the class gate over the 17 collection-shaped assert messages in `apps/api/tests`.** (2) **A reverse control keyed on `HEAD` stops meaning what it says at the commit that lands the fix**: the plane builder read its control from `HEAD` and refused afterwards with five `PREFLIGHT FAIL` lines — correctly. Both ends are pinned now (`f3c9f1d` the control, `5e213db` the gate and the fixed pair) and the tree is enumerated with `ls-tree <ref>`, never `ls-files`, because `ls-files` reads the shared **index**. Re-graded on the repaired planes: `-k` collector reads **6/90 selected, 84 deselected**, battery exit 0 (`R` red naming all six keys and both clauses, `A1`/`A2`/`A3` red on their own clause, `CTRL` green), and A4 — widening the unmigrated branch — still answers **2 failed** at plane lines 331 and 375. A third finding is the at-rest clause's own: it searched `plans_of_minors: 0,` for bytes that read `"plans_of_minors": 0,` and keyed on `endswith("academy.py")`, true of both the handler and the service, so it printed `0/4` about a file that had just been widened; it now measures the **delta** against the pinned bytes (plane B 4/4 new, plane A 0/4). **Left open:** this gate is one door's — 12 `D1`, 8 `D2`, 15 `D3` sites remain, and three of the four honest sites are honest only because *their* types mark those keys optional, which nothing enforces from the producer's side; and whether an unmigrated host should publish a capability object at all, rather than ten figures and a `rule` string implying an academy exists, is a product question this unit did not answer because the answer moves served bytes. |
| **— an `assert` message that pytest discards on the way to the screen (the class #110 named)** | ✅ 2026-10-20 | Landed as `183e3c3` (the two `test_boards.py` sites) + `e4b19c3` (the gate); both files entered HEAD under the shared identity rather than through this unit's own commit, so the landing was verified by `cmp` against `git show HEAD:<path>` — **byte-identical**, which is what makes the readings below legs of HEAD and not of a plane. Record: [docs/ASSERT_MESSAGE_VERIFICATION.md](docs/ASSERT_MESSAGE_VERIFICATION.md). Two mechanisms, both reproduced at the shipped command form (`.venv/Scripts/python.exe -m pytest <file> -q --tb=line -rf`): **a non-`str` message is printed through pytest's 240-character repr window** (head and tail kept, middle replaced by `...`) **in every traceback style**, so `assert not rows, (name, got, wanted)` is a red case whose answer was thrown away; and **a `str` message containing a newline is clipped to its first line by `--tb=line`**, the style three published leg commands use. Measured 12/40 and 1/40 verdict markers reaching the terminal, against 40/40 for a `!r` f-string and for a pipe-joined message — 4 shapes, 4 MATCH, re-measured 2026-10-18 from the script the record cites. Census over the committed tree (`git ls-tree -r HEAD` + `git show`, never the shared working copy): **40 offender sites in 15 files** at `fe32570` (29 tuple, 6 list comprehension, 1 set comprehension, 4 newline-joined), **0** now, with `apps/api/tests/test_assert_message_forms.py` (6 cases) refusing the two provable shapes. HEAD reads **214 committed `.py` files / 4859 asserts / 1411 carrying a message**, the buckets summing to the assert count exactly, and **707 of those 1411 are invisible to a syntax walk** (`UNPROVABLE:*` 385, `unknown-lines:*` 322 — `response.text` is a `str` at runtime and a hole to the scanner): counted and published, never refused, because a rule that refused them is a tax dressed as a proof. **Three findings about gates like this one.** (1) *The census includes the counter*: the repo-wide shape floors this gate first shipped (53 f-strings, 5 joins) were outrun by the gate's own text — its messages are inside the population it walks, so the join bucket reads 12 where the tree reads 5, and converting two of them back stayed green (battery 1, arm A3: **MISMATCH**). The claim is 18 per-carrier `(file, shape)` pins over the 15 converted carriers now, keyed on identity, never on `file:line` — which is why the gallery lane's `862079a` shifting `test_boards.py`'s two sites from 104/156 to 106/158 cost nothing. (2) *An empty exemption ledger makes its own agreement clause vacuous*: #114 converted the last two sites and emptied the ledger, so that case now runs `ledger_defects()` on a **three-way plant** (agreeing, stale, unledged) as well as on the tree, and arm A5 charges the outside direction. (3) *A missed prediction is a hole, not a number to widen*: battery 3 run 1 was 8 MATCH / 1 MISMATCH — A1 reverted one of `test_world.py`'s **two** pinned f-strings, so the carrier pin dropped 2 → 1 and `CERT` fired along with the predicted `BAD` and `LED`. The gate was right; run 2 is 9 arms 9 MATCH, both baselines green, 9 clean restores, exit 0. Reverse control, the shipped gate against the pre-cure ref: **5 failed, 1 passed in 28.25s** — 36 of 36 `BAD` unledged, 4 `CLIPPED`, 15 carriers no row names, 16 of the 18 pins unmet, and the population floor red too (213 files against a floor of 214), which makes this control stronger than the `4 failed, 2 passed` reading it replaces. Gate green where it lands: **6 passed** on the landing plane (`git archive` of `862079a` plus this unit's two files) and on real HEAD. Also closed here: the dated correction to `docs/M8_ACADEMY_VERIFICATION.md` §Reproduce — its two `--tb=line` legs printed the header sentence and none of the six verdict tags, because that message joined its verdicts with a newline at `fe32570` and joins them with a pipe now; the inserted text sits below the cited code fence, so lines 376-377 still point where the record says. **Found on the way, and needing separation**: `test_spec_audit_currency.py` is red at `e4b19c3` on a HEAD-basis reading of both sides (the audit table says 59 page routes where `git ls-tree -r HEAD` holds 61 `page.tsx`, and 6 `/tactics/*` where it holds 8) — a stale document, queued as #115. `test_openapi_contract_currency.py` is red **only in the shared working copy**: its `answers()` is `app.openapi()` imported off the disk and the traces routes live in this lane's uncommitted `app/api/v1/agents.py` (`git show HEAD:` counts 0 occurrences of `traces` there, the working copy 9, the contract 0), so no clean plane reproduces it — the same attribution #110 had to make for the gallery lane's `boards.py`. **Left open:** the whole-API-suite leg at this commit and the PostgreSQL leg (§7 of the record); the 707 messages the walk cannot see; and the class of claims no syntax gate can reach — a message that is a `str` and fits on one line but names nothing. |
| **— three of the audit's own figures had been outlived by the gallery lane** | ✅ 2026-10-20 | Found while landing the #114 record, cured as #116. `test_spec_audit_currency.py` is a HEAD-basis gate — it reads `docs/SPEC_COVERAGE_AUDIT.md` through `git show HEAD:` and counts the tree through `git ls-tree -r HEAD` — so what it refused was a document, not a behaviour: `AUDIT_FIGURES` published 59 page routes where the tree holds 61 `page.tsx`, the §A Tactical Lab row published 6 `/tactics/*` pages where it holds 8, and, one clause below the first red, 28 migrations where `apps/api/migrations/versions` holds 29. All three moved in one commit, the gallery lane's `862079a`: `/tactics/gallery`, `/tactics/gallery/[slug]` and `0028_board_gallery_consent.py`. **A first red is evidence about the clause that fired, not about the case**: that figures assertion checks contract paths, then page routes, then migrations, so the route refusal stopped it before the migration clause could run — the second stale figure only appeared once the corrected ledgers were re-run on a plane (`D:/r116-plane`, an extract of `fb5453b` with the two documents replaced by the repaired bytes): **9 passed in 25.54s, exit 0**, against **2 failed, 7 passed** for the same file read at `fb5453b`. Every replacement figure is read from the same walk the gate runs, never typed; the splice refuses a needle that appears other than exactly once, a line-count change, or a CR byte in a file whose blob is LF. The ROADMAP's parenthetical quote of the same three figures went red the moment the audit line moved, which is what quoting rather than restating buys. **Left open on purpose**: `test_openapi_contract_currency.py`, red only inside the shared working copy because the agents lane's `traces` routes are uncommitted — that one is theirs to reconcile at their landing, and a clean plane cannot reproduce it. |
| **— Item 0 closed the wrong end: the "one shared target" walked only `apps/api`** | ✅ 2026-10-20 | #117, found while scoping the legs the #114 record owes. `git ls-files '*.py'` counts 252 committed files, 248 of them under `apps/api`; the **4** outside it all live in `scripts/`, and neither `scripts/check.sh` nor CI read one of them, because both ran `python -m ruff check` **from inside `apps/api`** under a comment claiming "Ruff then walks the whole project, which is the target CI enforces" — true of the disagreement that sentence replaced, false of the tree it described. The target is written down once now, in `scripts/lint.sh`, which both callers invoke: all of `apps/api` plus the directories holding every committed `.py` outside it, derived from `git ls-files` on every run, with the population printed so a narrowing cannot be silent. **Two measurements before the first edit.** (a) The population: 4 files in 1 directory at `33bdd8c`. (b) The invocation decides the answer — `python -m ruff check --config apps/api/pyproject.toml .` from the repository root reports **71 I001** in files the project's own run calls clean, because one level up `app.*` stops being first-party. That artifact cost this unit a wrong "fix": the first pass `--fix`ed `scripts/qa_db.py` into the wrong import block, and it is now byte-identical to `33bdd8c` — it was never defective. The real figure for the population is **2**, not 3: `scripts/bench_api.py` UP041 (`except asyncio.TimeoutError`, an alias of the builtin since 3.11) and `scripts/schema_drift.py` I001. Both fixes are behaviour-neutral, proved by executing each script's body in-process, not by reading the diff. **Six arms on a worktree at `33bdd8c`** (`D:/r117-plane`, whose index is its own so `git add` there cannot touch the shared tree), **6/6 MATCH**, in `.scratch/r117_arms.txt`: at that ref the old command answers `All checks passed!` while the shared target names both defects — the reverse control run on HEAD's real files; a planted unused import in `scripts/qa_db.py` is caught by the shared target and stays invisible to the old command; a **newly added** `tools/probe.py` is in target the moment `git add` sees it, moving the printed population 4 → 5 files and 1 → 2 derived directories; a plant inside `apps/api` still goes red in both, so the widening is additive; the root-relative shape is recorded as the rejected alternative; and a derivation that finds no committed `.py` refuses with exit 2 instead of passing quietly. Two of the driver's own first-run reds were the driver's, not the gate's: `^`-anchored patterns without `re.M` read a 2-error report as zero, and this host resolves bare `bash` to a WSL relay that dies on `execvpe(/bin/bash)`. `scripts/check.sh` was proved against the gate that reads it — `qa-gate-inventory.mjs` still lists `scripts/check.sh` as the runner of all four static web gates. **Not verified: the CI job itself.** The step names `working-directory: ${{ github.workspace }}` plus `bash scripts/lint.sh`; only a push shows GitHub honouring a per-step override, and the local run of that same file is what stands behind it. `CONTRIBUTING.md` publishes the new command. The ~20 verification documents that quote `ruff check app tests` and its variants keep their quotations: those rows record what was run at their milestone, and a record of a narrow command is not a claim about today's gate. |
| **— the DR pair was described, never run: five defects in scripts nothing invoked** | ✅ 2026-10-20 | The 2026-10-11 "first live restore drill" (M12) ran `pg_dump`/`pg_restore`/`alembic` *inside the container*; it never ran `scripts/backup_db.sh` or `scripts/restore_db.sh`, and nothing in the repository did — a grep for both names finds the docs and the two files themselves, no caller. Running them found five defects, each measured: **(1)** `incremental` was a no-op returning 0 (0 artifacts, 0 `pg_dump` calls) with a success line; **(2)** both scripts typed `PGPORT=5432`/`PGUSER=football`/`PGDATABASE=football_os` while `infra/docker-compose.yml` publishes **54321**; **(3)** `restore_db.sh` defaulted to `football_os_restore` and ran `DROP DATABASE IF EXISTS $TARGET_DB` without consulting `scripts/qa_db.py`, which already owned the scratch-name policy; **(4)** `if [[ $? -eq 0 ]]` after `pg_restore` was dead under `set -euo pipefail`, so the failure branch could never run; **(5)** alembic ran from the repo root, which has no `alembic.ini` (only `apps/api/` carries it), and "Restore completed" required no measurement. Fix: `scripts/dr_lib.sh` derives the coordinates from compose, refusing rc=2 with the match count on 0 or 2 candidates; restore hands its target to `qa_db.py --assert-scratch`; `rc=$?` carries the status; alembic runs from `apps/api`; success is printed only after the restored table count is read; incremental asks `SHOW archive_mode`, reads `pg_stat_archiver` and (with `REPLICA_HOST`) the replay lag, refusing rc=2 on every non-answer. Gate `apps/api/tests/test_dr_scripts.py`: **14 cases** over the shipped scripts with stub binaries and no server, reading the compose and calling the shipped `dr_published_pg_port` and policy CLI instead of paraphrasing them — **14/14** on the fix, **13 failed / 1 passed** against HEAD's scripts on a `git archive` plane (528/528 files), the single green being the shell pre-flight and the 13 names matching the defect list (the reverse control). M12's bullets and its "now *executed*" sentence are corrected in place. |
| **— `/agents` was linked but deleted** | ✅ 2026-10-11 | Rebuilt as the M11 console: `app/agents/page.tsx` + `AgentConsole.tsx` read a 36-key `agents` namespace (all three catalogues, parity-verified), render the roster from `GET /agents/list` (the registry's own answer, not a TS copy), run single agents through `/agents/run` and composite tasks through `/agents/composite`, and show the session's stored memories via `/agents/context` with a per-visit session id. Walk section `06b` (placed before the video section, which still aborts about half its runs): 5/5 green — shell, orchestrator label, run with confidence, agent attribution, composite steps. The dead link's 404 console error is gone. |
| **— Windows reserved 54321 out from under the database container** | ⚠️ environment | Found 2026-10-14: the database container came back up (recreated without its port mapping) and could not rebind — `netsh interface ipv4 show excludedportrange` shows Hyper-V has reserved **54288–54387**, which contains the project's own 54321, and the bind fails with `ports are not available` until the reservation moves. `net stop winnat` clears it but needs an elevation this shell does not have (system error 5). The unblocking workaround, which touches no repo file: `docker run -d --name football_os_db_alt -v football-os_db-data:/var/lib/postgresql/data -p 54399:5432 pgvector/pgvector:pg16` reuses the named volume on a port outside the reservation, and the API takes `DATABASE_URL=postgresql+psycopg2://football:football@127.0.0.1:54399/football_os`. `infra/docker-compose.yml` stays canonical; the exclusion is dynamic and often clears on a host reboot, after which the compose container binds normally. |
| **— this host cannot run `next build` twice** | ⚠️ environment | Not on the plan. The Recycle Bin rejects the operation (`Unknown { description: "Some operations were aborted" }`), so the safe-delete shim times out on the delete Next performs against a **pre-existing** dist directory. The build compiles, then dies before writing `prerender-manifest.json`, leaving output that cannot be served. Building with the directory absent works. `scripts/check.sh` runs `npm run build` once, but any second run in a row fails here, and `rm -rf`-style cleanup of a build directory hangs. |
| **— migration `2e197f085070`** | ✅ 2026-09-30 | Not on the plan; found by trying to run the SQLite leg it broke. Unadjusted autogenerate, PostgreSQL-only DDL, a `downgrade()` that could not run anywhere, and each new column indexed twice. |
| **— the aggregates ledger had no index, and its back links were dead doors** | ✅ 2026-10-11 | `/simulation/aggregates/league` and `/simulation/aggregates` (both back-link targets) answered 404 — the walk's console gate recorded them as unprovoked errors every run. `app/simulation/aggregates/page.tsx` is the index: one panel listing every competition from `/world/competitions` (the path is `/world/competitions` — the first draft used `/competitions` and rendered the unavailable branch, caught live before landing), one explaining the player door, one printing the rules door's vocabulary. The league page's back label moved with it, and the walk's anchors were repointed to what the success body actually renders (the competition name; the player slug chip) — the old anchors lived in metadata or a back-link label, which is how repointing one link broke a wait. |
| **— Git Bash mangles leading-slash CLI arguments** | ⚠️ environment | Found 2026-10-13, the same host family as the TMPDIR/pre-commit entry: `python -m scripts.bench_api --endpoint /api/v1/healthz` from Git Bash silently rewrites the argument into `C:/Program Files/Git/api/v1/healthz`, so the benchmark measured 2,200–3,600 requests **all 404** and printed it as a healthy-looking throughput figure. The bench is fine; the harness is what lies. `MSYS_NO_PATHCONV=1` (or `MSYS2_ARG_CONV_EXCL="*"`) before the command stops it, and the bench prints the URL it will hit before it starts. The same conversion is why the restore drill's `docker exec … -f //tmp/…` needed doubled slashes. |
| **— the OpenAPI contract and autocrlf** | ✅ 2026-10-06 | Not on the plan. The working copy of `docs/api/openapi.json` had been checked out CRLF while `scripts/export_openapi.py` writes LF, so the byte gate failed with *equal byte counts* — a host newline policy, not an artifact defect. Regenerated from the tree (162 paths / 208 operations, LF). Windows checkouts of this repo will do this again; the remedy is the exporter, never hand-editing. |
| **— boards could be private or shared by token, never stand in a public place (M9's consent story, §13 follow-up)** | ✅ 2026-10-17 | `POST/DELETE /boards/{ident}/list-publicly` is a dedicated consent door whose payload carries the sentence it grants; `tactic_boards.listed_publicly` (migration `0028`, `server_default false`) is the predicate the gallery reads, so revocation is an **absence, not a delete** — the row survives, the read stops seeing it. Two server pages (`/tactics/gallery`, `/tactics/gallery/{slug}`, both `noindex` and `Disallow`ed) read a new `gallery` namespace (all three catalogues) plus ten `tactics` consent keys, with a `GalleryConsent` control on the owner's edit page. **Measured**: `test_boards.py` 23/23 (`TestPublicGallery` 6/6 — consent door, revocation-as-absence, owner-name-only leak check, arithmetic recomputed not replayed) on throwaway SQLite; `test_locale_claims` 4/4; `tsc` + `lint` + `next build` green; a live walk of a listed board reads the card, the owner's display name and the consent sentence at 200, the board page 200, an unlisted slug 404, and zh renders Chinese while every English literal drops then returns. Committed `862079a`. |
| **— the community wall and both simulation routes read their catalogues** | ✅ 2026-10-20 | §81 2c, three more content-page namespaces. `community` (86 keys, page + `CommunityTools`) landed `ef2595c`; `simulate` was extended across the index + `SimulatorForm` (`31c43ce`, 56 keys) and the `[slug]` report + the seven `simulation.tsx` server components + `SimTools` (`38e254c`, +96 keys → 150). Each: English byte-identical to HEAD (static substring; JSX-split/tagged sentences normalised, nullable figures `String()`-coerced so an absent one still prints as the template literal did), all three catalogues key-identical, and a signed-in walk of the route in en and zh (the English labels gone in zh). The report page's seven components were made `async` and read `getTranslations` themselves; two sentences with inline markup use `t.rich`; the COMPARED/EVENT label tables mapped to keys. Measured: tsc + scoped eslint clean, `test_locale_claims` 4/4, all 150 × 3 ICU messages parse. The shared production build/lint are transiently red **only** on a concurrent session's uncommitted club edit (`focus_items_max` on `PlanView`), which these commits do not touch and which is absent at HEAD — so each commit's tree is buildable — and the report route was walked on a `next dev` server that compiles routes on demand and never touches the club page. |
| **— the two owed suite legs read the same five reds on both engines** | ✅ 2026-10-20 | Recorded in [docs/ASSERT_MESSAGE_VERIFICATION.md](docs/ASSERT_MESSAGE_VERIFICATION.md) §7. Both legs ran on the same frozen plane, `D:/r119-legs` at `fb5453b` (verified with `git rev-parse`; the runner's binding probe printed `app/__init__.py` and `app/main.py` inside the plane): **1660 collected / 5 failed / 2 skipped on each**, SQLite `3965.73s`, PostgreSQL `3978.52s` on server 16.15 with a per-run database the conftest created and dropped. The reds are identical by name: three `test_openapi_contract_currency` cases refuse the three gallery routes (`/api/v1/boards/gallery/public`, `/api/v1/boards/gallery/public/{slug}`, `/api/v1/boards/{ident}/list-publicly`) and the committed contract's 411051 bytes against 416045 serialised; two `test_spec_audit_currency` cases refuse the stale 59-page and 6-`/tactics/*` figures, cured after the plane by #116 (`33bdd8c`). No other case failed. The two skips are the Redis integration case (no Redis) and the `[need_fit]` sorting case. This closes the two legs #114's record left owed. |
| **— a share link previewed the site, not the page, and every indexed page promised a picture that did not exist** | ✅ 2026-10-21 | Recorded in [docs/SHARE_PREVIEW_VERIFICATION.md](docs/SHARE_PREVIEW_VERIFICATION.md). `sharedMetadata()` now owns the two decisions a caller must not forget (`noindex`/`nofollow`, the parent canonical) and the three `/…/shared/<token>` pages build through it; `scripts/make_og_image.mjs` renders `public/og.png` (1200×630) from `app/icon.svg`, `lib/site.ts` and the stylesheet's tokens, so §89's ban on copied imagery still holds and the SEO doc's §3 exclusion is retired in place. `apps/web/scripts/qa-share-preview.mjs` grades it in **25 checks** by *transpiling and calling* the helpers rather than searching for strings, and `.scratch/share109-arms.mjs` proves each clause decisive: **17/17 arms matched a prediction written before the run**, R0 being the reverse control that re-grades HEAD's own two pages and answers `2, 2, 9, 9, 9b, 9b`. The live leg (`next build` + `next start` on port 3213, signed-out reads) reports `summary_large_image declared: 10, of those carrying an image: 10` — the promise is paid everywhere it is made, and `/club/rules`'s smaller `summary` card is the one page that owes no picture. **§109b, found while verifying:** a clean `git archive HEAD` plane does not type-check — `app/portfolio/shared/[token]/page.tsx(10,10): error TS2305: Module '"@/lib/site"' has no exported member 'sharedMetadata'`, one error, because `cc0ad34` wired that page and committed the page only. `check.sh:110` arms exactly this control and did not fail the commit because the gate was run against a dirty tree that held the helper. `lib/site.ts` lands here, retiring it; the same read also corrected `docs/SEO_VERIFICATION.md` §3, which had the root route's story backwards (`/` answers **200** to a signed-out reader — the two `redirect()`s sit inside `if (user)`). |

| **— the locale figures were named three times, and none of them could fail** | ✅ 2026-10-21 | On the day this closed, the same catalogue was published as **288** keys (`ARCHITECTURE.md`, `meta.py`), **393** (`apps/web/messages/README.md`) and **2890** (`en.json` itself), and the repository's front door still said *the translation layer is not built*. A figure in prose has no reader, so the cure is a reader: two cases in `apps/api/tests/test_locale_claims.py`. The first recomputes the README table — its population must equal `en.json`'s leaf count exactly, its numerator must not exceed what the catalogues hold and must not fall below a floor — so the one place a figure persists is the one place a suite derives it. The second refuses a coverage fraction in the carriers that describe the catalogues in the present tense (`README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `meta.py`, `docs/SEO_VERIFICATION.md`) and names four retired sentences by their exact spelling; dated run records (`PLAN.md`, `ROADMAP.md`, the M3/M4 verification logs) are exempt by identity, because a figure measured at a named run is evidence about that run. **10/10 arms matched a prediction written before the run**: A1 denominator 2891, A2 numerator overclaiming, A3 under-floor, A4 row deleted, A5 the old `287/288` back in `ARCHITECTURE.md`, A6 the README sentence, A7 the SEO heading, A8 a catalogue that gains one translated key (the real drift source, red), and A9 the same key with the table updated (green) as the reverse control. Prose cured here beyond the lane's `a5fd7db`: the root `README.md` claim, the `capabilities` docstring — which is *published* in `docs/api/openapi.json`, so the false sentence was API documentation — `docs/SEO_VERIFICATION.md` §6's `1036 today` now states its formula (the 10 `PUBLIC` entries plus one `<loc>` per world/knowledge row; 10 on an unseeded box, where every world list answers nothing), and `app/sitemap.ts`'s comment, which claimed `/` and every My Football area answer **302** (`/` answers 200; the gated routes answer 307). Contract regenerated from the tree: 430210 → **430382 bytes**, the only diff being that one description. **Left red, attributed, not mine:** `test_spec_audit_currency` §36's census still says 7 paths / 11 operations under `/api/v1/creator` where the committed contract answers 10/16 — M10's census row is stale, and it is the next unit. |
| **— the creator census counted a tier that had grown twice past it** | ✅ 2026-10-21 | `docs/SPEC_COVERAGE_AUDIT.md` §36 published **7 paths / 11 operations** under `/api/v1/creator` and said `/creator` had no browser walk. The committed contract answers **10 paths / 16 operations** — the training program's three paths / five operations landed `5a79598` behind migration `0030`, and that commit updated the two figures C1/C2 recompute while leaving the census (C7) to a suite it did not run — and `scripts/qa-creator.mjs` has been committed since `ab2d4c8`, where it answered **56 of 56** checks. The row now names `creator_programs` / `creator_program_steps` and `services/creator/{publishing,programs}.py`, states the recomputed census, and records the walk. `ROADMAP.md`'s M10 row carried the same snapshot in words — **eleven doors**, *one public, ten private*, **15 refusal codes** — where the tree holds **16 doors** (one public, fifteen private) from **24** registered refusal codes, none mapping to 403; its present-tense sentence now delegates the census to §36's row, the one carrier C7 recomputes, and leaves the dated 2026-09-28 measurements as the historical record. **Witness:** `test_spec_audit_currency` at `fc1cb5f` was red on exactly this row (`(10, 16) == (7, 11)` at `tests/test_spec_audit_currency.py:429`) and is green at the landing commit; before committing, the gate's own regexes read all **11** dual censuses equal to the contract, no C8-shaped count, and **33** cited path tokens / **53** expanded candidates resolving against the committed tree. Dated records are left alone: `docs/M10_CREATOR_VERIFICATION.md`'s 7/11 and `docs/SPEC_AUDIT_CENSUS_VERIFICATION.md`'s "7/11 ✓" are evidence about the runs they name. |

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
| M9 Community | 🟡 §35 (posts, reactions, follows, feed) landed 2026-09-28; §35's pointer promise landed 2026-10-09 (Item 3). The §36/§37 claim that stood here until now was false and Item 3 says so: those are the creator system and gamification, landed at M10 and M1, and this spec asks for no moderation, reporting or blocking at all | `docs/M9_COMMUNITY_VERIFICATION.md` |
| M10 Creator Economy | 🟡 §38 portfolio landed, share links + CV PDF landed 2026-10-06, and **§36's first kind of content landed 2026-10-21** (Item 10): a training program is a row of its own - a schedule, a dose and a progression, each step naming a catalogue drill, and starting one plans the learner's own training sessions | `docs/M10_PORTFOLIO_VERIFICATION.md`, `docs/M10_CREATOR_VERIFICATION.md` |
| M11 Multi-Agent | ✅ verified 2026-10-20 — all six agents + `FootballOrchestrator` landed, the orchestrator replaced the keyword router, §30's graph has its own joint-retrieval evidence, and **§33's stored trace landed 2026-10-20** (Item 5): every composite run is stored on §34's own tier and read back at two new doors, with `trace_integrity` measured at 1.0 against a gate of 1.0 | `docs/M11_AGENT_TRACE_VERIFICATION.md` |
| M12 Hardening | 🟡 §61 erasure landed 2026-10-06; structured logging, cache, latency percentiles, cost advisor, governance + backup docs landed 2026-10-09; **the spend cap gates the coach door at the call** 2026-10-11 (/coach/ask skips only the LLM phrasing when today is spent, so the arithmetic still ships; /knowledge/ask still refuses 429); **OpenTelemetry tracing landed 2026-10-11** (packages pinned, span path measured through an in-memory exporter, no collector on this host) and **the restore drill was executed 2026-10-11** — `pg_dump` → `pg_restore` inside the project's own container, 58/69 tables byte-identical, and it found the one defect no gate could see: the long-lived container still carried `2e197f085070`'s duplicate indexes, closed by migration `0027`. What has *not* landed is listed in the verification doc's "does not claim" (no authenticated Redis tier (the layer is now the response cache's shared second tier; 6379 here needs a password, so every load figure above was taken with it degraded), no trace backend, no off-host backup; **the load ceiling is now published for one worker** (90.80 req/s at c10 on this shared host, and 52.54 at c50 — saturation, not scaling), and four workers were measured against one: +29% at concurrency 10, +6% at 50, and the 15s max outlier fell to 656ms once a second process existed — the figures are a floor — `scripts/bench_api.py` and the run found a defect in the harness first: it reported 0.00 ms latency for every non-2xx response, so a door that always answers 401 measured as instantaneous), and **two more that the response cache turned up when it was verified live rather than read**: a HIT replayed the MISS's X-Request-ID and X-Request-Duration-Ms because the cache middleware wrapped the request-context one, and the cache key ignored Origin, so the second allowlisted origin was served the first one's Access-Control-Allow-Origin as soon as a path was warm - both fixed, both with a case that was run once in the broken configuration to prove it fails there), and **the rate limiter guarded login with no test at all** - eight cases now, which found its stated 5000-bucket bound was never enforced, the prune having dropped only idle buckets while distinct live ones grew the map without limit), and **the crash answer arrived with no headers at all** - Starlette renders an unhandled exception outside every user middleware, so a 500 reached the client without the X-Request-ID its own log line already carried; one function now dresses both, and a test drives a raising route through the real stack to prove it, and **the shared cache tier landed 2026-10-20** (Item 6) — the project publishes its own authenticated Redis, two server processes were measured sharing one store (`MISS` then `HIT`), and the cross-account replay the tier would have spread is closed: the near tier's key names the caller, the shared tier never stores a credentialed response, and the metrics door no longer publishes the cache's password. The load figures above are still the degraded ones, and **the paired ones are in (Items 8-9, 2026-10-21)**: the shared tier counts its own hits, two server processes over one store were measured serving each other's answers (worker B: 12 HIT / 0 MISS), and the load runs were repeated against a live tier and a degraded one on the same host - four workers at c50 gave **84.34 req/s live against 39.86 degraded (2.12x)**, with one worker the tier a small tax (-15% at c10) and the tail worse (p95 1955 ms against 1205 ms). **The trace backend landed too (Item 7)**: `app/core/span_store.py` is an OpenTelemetry exporter that writes each finished span into `request_spans` (migration `0029`) and `GET /api/v1/traces/{trace_id}` reads a request's spans back, so a span reaches somewhere without a collector | `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md` |
| §81 i18n | 🟡 catalogues full, switcher works, shell switches; **58 files bind a translator (83 bindings), counted on HEAD blobs at `844216d`** — nav/auth/scout/career/settings/world/progress plus `common`'s verbs, nouns and its attribute labels; `agents` (36 keys) exists only in a writer's uncommitted catalogue. Still English literals: the content-page namespaces whose keys do not exist yet (club, community, video, simulate, market). | the grep that counts `useTranslations`/`getTranslations` callers on HEAD blobs; the label census re-run **with a TSX parser over all eleven HEAD dictionaries** (`census-ast.mjs`, 105 files, 0 parse diagnostics). At `8feda9a` it read **A 24 sites, B 168, C 54 — 245 distinct sites**; re-run at `844216d` after the `nav` group it reads **A 24, B 168, C 40 — 231 distinct sites**, plus **E 3** (a label in a component's default parameter, which no earlier shape could see). `world`'s C group closed at `8feda9a` (17 found, 16 wired, 1 named sense skip), `common`'s at the two shape-C landings (11 wired + 1 skip) and `nav`'s at `844216d` (21 rows: 15 wired, 4 reachable only case-insensitively so wiring them would rewrite `en`, 2 left as key-ownership questions with the reason named). The union fell by 14 for 15 wired attributes, and the one is not a missing label: `tactics/[slug]/page.tsx` `title="Tactical system"` survived its own file's edit but moved from `:79` to `:81`, so a census keyed on `file:line` re-counts a site when a line *above* it is written. That is why every figure in this arc names the ref it was measured at. The parser also **withdrew the older "shape A 0"**: `common`/`world` words do stand as bare JSX text — 7 A sites and 76 B sites carry one of their values, every one of them still a sense question rather than a wiring. | A **fourth shape** is now measured and partly closed: a label inside an object literal, e.g. `back={{ label: "Back to Football World" }}` or `metadata = { title: "Community" }`, which no JSX-shaped census can see. `census-d.mjs` parses every HEAD `.tsx` (108 files, 1331 object literals) and read **14 D sites**, of which **10 were byte-exact against `en`** — all ten are `export const metadata` titles, so wiring them needs `generateMetadata`, not a prop — and **4 are case-only** (`label: "Career mode"` vs `nav.career` = "career"), which stay open because wiring them would rewrite English's bytes. Re-run at `2348ed1` it read **15 rows / 11 byte-exact**: the knowledge landing surfaced an eleventh site, `/knowledge`'s own metadata title. **The metadata half is now wired for nine of those eleven (`dd8618c`)**, and the census re-run at `dd8618c` reads **6 rows / 2 byte-exact**. The rule the slice states, because it is what makes a literal title safe to delete: *a page's document title takes the key its own heading already reads* — no new catalogue keys (all three message files were dirty from concurrent work, and a key written there would ride along in someone else's commit). The two that stayed, stayed for named reasons: `/community`'s h1 says "Community wall" while `nav.community` says "Community", so wiring its tab would couple two copies that do not agree; `/knowledge` was the file another writer is standing on. **That one is now wired** (`ef0ff8b`, reading the orphan `knowledge.metaTitle` its own writer had authored), so the census re-run at `ef0ff8b` reads **5 rows / 1 byte-exact** — the survivor being `/community`'s metadata title — and the pair the gate's ledger carries is `/community` ("Community" over "Community wall") and `/club` ("My clubs" over "Club tenancies"), two copies that differ in English where choosing between them is a sense decision, not a wiring. One case-only row moved line but not shape (`app/scout/page.tsx` :41 → :46) — the census is `file:line`-keyed, which is why every figure above names its ref. **The description half is now closed too (2026-10-14, eleven pages measured at the re-run)**: career and scout gained `metaDescription` in namespaces that already existed, knowledge's own orphan `metaDescription` finally got its reader (byte-identical), the six world list pages took six flat keys, and `/my-football` + `/portfolio` gained minimal namespaces of their own because their descriptions belong to neither the nav nor any existing catalogue — a second binder name per file, so the gate's one-name-one-namespace clause stays green. English byte-identical; the rescan reads zero literal descriptions; both metadata gates and the locale claims pass unchanged; live read repaints per locale. Still disclosed: three pages (`/portfolio`, `/scout`, `/my-football`) carry a bare metadata object with no `openGraph` block, so their link-preview title is the layout's `title.default`. The permanent form **is** written and shipped now (`ef0ff8b` + `5ef05eb`): `apps/web/scripts/qa-metadata-title.mjs` states the rule over the whole page population instead of one change's diff — every `app/**/page.tsx` must declare its tab in exactly one form, **may not** hold a load-time literal on a page whose heading reads a key (check 4, DRIFT), **may not** read a key on a page whose headings are all literals (check 11, MIRROR — the same mismatch in the other direction, empty today so it refuses rather than ratchets), and where both are literals they must be the same copy unless a ledger row whose predicate is re-read from that file's bytes on every run says otherwise (checks 5/6). Plus the population floor, a per-file parse-diagnostic floor, a heading-carrier floor, one-namespace-per-binder, per-key resolvability in all three catalogues, a differs-from-English test on every tab key, an orphan clause on `<ns>.metaTitle`, and a descending ceiling on literal-titled pages — every count derived from the same walk that finds the pages, so a narrowing scan goes red instead of quietly shrinking what is protected. At `ef0ff8b` on a clean plane it reads **population 59, tabs keyed 25 / literal 24 / dynamic 10, heading carriers 45 (keyed 25, literal 13, dynamic-only 21), CHECKS 94/94**; the same script over the dirty worktree reads 101/101 with keyed 27 / literal 22, because a concurrent writer has since wired two more pages — the ceiling is a ratchet, so the fall is what the gate wants. Witness **12/12 planes matched** (`arms-meta.mjs`): reverse control to the pre-wiring blob, stale exemption, an added disagreeing page, a tab pointed at the h1's own key, a deleted zh value, a zh value copied from English, an added agreeing page, `app/` deleted, a heading carrier retyped as a `Panel`, a page declaring both metadata forms, and a keyed tab over a literal heading; each red judged by its clause id **and the file it names**, never by a count. Two lessons the writing taught, both recorded here because they are not obvious from the file: (i) the "2 remaining sites" this row carried for a whole slice was a **D-census** number being read as a **page-population** number — the population holds 24 literal-titled pages, of which exactly 2 disagree with their own heading and 1 more (`/knowledge`) was drifting from a keyed heading; and (ii) the rule is **not** "the tab reads the key its heading reads". `/knowledge`'s tab names the surface ("Football Knowledge") while its h1 names the corpus ("The football knowledge base"), exactly as `agents`, `coach` and `settings` already do — so the gate forbids the two directions of *mismatch*, not a difference of copy. A census written earlier in this arc (`meta-census.mjs`) printed a bucket labelled `title-keyed-heading-literal` reading 7 and looked like a population the gate ignored; all 7 are keyed headings under a different key or dynamic ones (`board.name` twice) — the label described the census's equality test, not the heading's kind. Cross-checking two scans is what found both, and `/knowledge` closed without new copy: its own writer had already authored `knowledge.metaTitle` and left it with **no reader** (7 `metaTitle` keys, 6 read), so the drift page and the orphan key were one fact seen from two sides. Live read **34/0** over `/knowledge` × 3 locales with `/world/search` as the still-literal control: the wired tab repaints ("Football Knowledge" / "足球知识库" / "足球知識庫", `og:title` with it) while the control does not move, and every description stayed the page's own bytes. `dmeta-check.mjs` and `knowledge-meta-check.mjs` remain as change-time instruments for the next wiring slice; the shipped rule no longer depends on them. The **back-link half of shape D is closed** (`c7e9f4c`, seven pages: `/club`, `/community`, `/graph`, `/portfolio`, the portfolio share page, `/simulate`, `/video` now read `nav.home` / `nav.myFootball`), which is what found the middleware defect in the row above: the live read could not reach two of those pages at all. Six `/world/*` pages still carry `back={{ label: "Back to Football World" }}`, a label with **no key** — the value is `"Back to " + en[nav.world]`, so it needs either a new key or an interpolated one, and the sense rule for it is not written yet. A **fifth** shape is measured (shape E, 3 sites) and open for a different reason: one of its strings is used as data by a page that compares against it. **The crawl half of the same decision is now measured, fixed and gated.** Three files split one decision — `middleware.ts`'s `PROTECTED_PREFIXES`, `app/robots.ts`'s `DISALLOWED`/`ALLOWED`, `app/sitemap.ts`'s `PUBLIC` — and each only *described* the others in a comment, so nobody had ever reconciled them. The reconciliation (files only) reads **population 59 `page.tsx`, gated 34, advertised 10, 30 pages declaring `robots:{index:false}`**, and **8 gated pages stood in no disallowed prefix at all**: `/agents`, the four `/graph` pages, the three `/simulation/aggregates` pages. Seven of the eight lean on their own `noindex`, which is **inert** — a signed-out fetch answers 307, a redirect has no `<head>`, so the one crawler that would honour the declaration never reads it. Confirmed live on `:8837` (a fresh `next build` with `NEXT_DIST_DIR=.next-m107`): all eight answer 307. The fix adds the three missing prefixes (`DISALLOWED` 21 → 24; `/career` was already carried) with each prefix's own rationale, and `ALLOWED` is unchanged. The permanent form is `apps/web/scripts/qa-crawl-policy.mjs` — **9 checks**, transpiling and *calling* all three shipped decisions, then: floors + callability (1), gated ⇒ disallowed (2), advertised ⇒ not gated (3), an advertised path under a disallowed prefix needs a strictly longer `Allow` (4a) **and** that mechanism needs at least one live carrier (4b), advertised ⇒ not self-declared `noindex` (5), a stale `Allow` (6), an orphan `DISALLOWED` prefix, with `/api/` held in a two-directional ledger (7), and a readable `robots:` declaration (8). Green on the fixed tree at **9/9** — `population=59 | gated=34 | advertised=10 | noindex=30 | disallowed=24 (23 matching a page, 1 not)` — and the reverse control, the same script over the parent's `robots.ts`, reads **8/9 with check 2 red naming exactly those 8 routes** (`disallowed=21 (20 matching a page, 1 not)`). Witness **13/13 planes matched** (`arms-crawl.log`), judged by clause id and never by a count; two of the arms found a hole in the gate *before* they ran. First, `robots: SOME_IDENTIFIER` made **no** clause red anywhere, so a declaration whose value is not an object literal is now reported opaque and refused — check 8 exists because arm A8 predicted it. Second, my denominator was wrong: I predicted "8 checks", and clause 4 is really 4a/4b, so the runner prints 9. Two prediction misses are recorded because the gate was right and the prediction was the hole: A3's needle matched 0× because `git archive HEAD apps/web` emits **CRLF** on this host (213 CRs measured in the plane's `middleware.ts`) — single-line needles had hidden that in the previous battery, so `buildBase()` now LF-normalises every `.ts/.tsx/.mjs/.json/.css` in the base plane — and arms A9/A10 under-predicted check 7, because deleting a page strands the `DISALLOWED` prefix that named it. Registered in `scripts/check.sh` and `.github/workflows/ci.yml` (the web job now runs 7 named gates). The live read (`robots-live.mjs`, **24 green / 0 red**) attributes the fix to the build rather than to a restart: the new server's served `Disallow:` set is exactly the worktree's 24, the older pre-fix server's exactly HEAD's 21, the served difference exactly the file difference (3 prefixes), `Allow` unchanged on both planes, and `Host`/`Sitemap` carry `:8837`, which is the plane's own attestation. All ten paths that `sitemap.ts`'s own `PUBLIC` list advertises still answer 200 for a signed-out reader, each with its own `og:title`. This retired the premise of the row above about preview titles: of the six reachable pages with no `pageMetadata` call, `/club/rules` writes its own `openGraph`, `/tactics/compare` and `/world/search` are `noindex` and absent from the map, and what is left is `/`, `/login`, `/register` — not content pages. The trap that keeps that item open is a *conversion* one: `pageMetadata` sets no `robots` field, so routing one of those pages through it would silently drop a declaration. **The copy itself is now gated (2026-10-20).** `apps/web/scripts/qa-i18n-literals.mjs` walks every `app/**/*.tsx` through the repo's own TypeScript and counts the copy written in English in the source - JSX text, label-ish attributes and label-ish object properties, three shapes, because a JSX-text scan reaches neither of the other two - and the count is a ceiling that may only fall: wiring a page to its catalogue lowers it, and a page that adds copy in English raises it. Measured at the ref it landed: **617 sites over 41 files** (75 `.tsx` parsed, 0 diagnostics). The landing page was the first group, and ten have landed since: the ceiling is now **161** against the **617** the gate was landed with, and the gate read **0 English literal sites** over every `app/**/*.tsx`, with the floor committed at 0 - a new page that writes copy in English fails the build. The metadata gate agrees: **tabs keyed 51 / literal 0, headings keyed 43 / literal 0** - every page's tab and every page's heading is now locale-driven, and the two literal tabs that survived until the end (`/community` and `/club`, whose tabs and headings say two different things in English) are gone with them. The gate counts three shapes - JSX text, label-ish attributes and label-ish object properties - and the arc wired more than it counts: the `KeyValueGrid` row labels are array literals, which no JSX-shaped scan reaches, and they went too. The gate also stopped counting field names - `data_origin: synthetic`, `max_depth`, `identity_retained=`, the example address, the export file name and the product's own name - because a field name is not copy, and each exclusion is named in the file with the reason. Fourteen groups in all, with the namespace each one added: `home` (55), `careerDetail` (96) and `career` (+23), `worldPlayer` (75), `simulationAggregates` (64), `onboarding` (52 - the form's options were module constants in the client bundle, so a Chinese reader chose from English options and read English errors), `worldTeam` (53) and `worldMatch` (58), `graph` (80), `myFootball` (+34) and `worldTraining` (31), `world` (+35), `worldCompetition` (36), `worldNews` (30), `notFound` (4), `simulationAggregates` (+19) and `portfolio` (44), `creator` (23) and `scout` (+30), and the last small ones on the club, knowledge, login, tactics, career, news and 404 pages.

**The components arc is closed too (2026-10-21): the ceiling is zero.** The gate's population is every `.tsx` under `app/` **and** every `.tsx` under `components/` (111 files), and the ceiling that wider scan read was **392**; thirteen groups later it is **0**, with the floor committed at 0. The groups: `CreatorWorkbench` (42 sites, the `creator` namespace), the shared primitives `components/ui.tsx` (the labels every page inherits, the `common` namespace), `ClubTools` (62, the `club` namespace), `AcademyTools` (45, a new `academy` namespace), the scout's `ScoutShortlistPanel` (39), `MatchTools` (30), `NoticeBoardTools` (26), `ScoutTransferPanel` (24), `SessionReportTools` (24), `ScoutReportPanel` (21), the five small ones (`BoardsNew`, `CareerForm`, `CareerTools`, `PhasePlayer`, `PortfolioSection`, 23), and the last four (`ScoutComparePanel` 16, `PortfolioSharePanel` 12, `BoardEditor` 11, `ScoutWorkbench` 11).

**The gate grew a third check while they landed, and it earned its place.** Every key the source asks for is in the catalogue — a key the catalogue does not hold is a **runtime error** in next-intl, not a build error, so the page renders an exception instead of a sentence and nothing says so. It found fourteen keys this arc had introduced (`thGoals`, `thClub`, `thCompetition`, `thPos`, the club tier's eight `*DoorMissing` keys, `notTiedToOneTeam`, `noneNamed`), and hand-checking found two more, one of which (`common.remove`) the creator workbench had been asking for since before the arc. **3361 key calls are checked on every run** — and that number moved twice: the arc's own conversions first, then the **rich-text form**, which the check had been blind to. `t.rich("key")` is the same catalogue read as `t("key")`, and next-intl throws `MISSING_MESSAGE` for a rich key it does not hold exactly as it does for a plain one, so a check that only saw the identifier form stopped counting the moment a sentence needed a tag inside it. The ten rich reads in the tree were invisible to it, and a typo in one of them would have rendered an exception instead of a sentence with nothing to say so.

**The five walks that had not been re-run since the arc were re-run on 2026-10-21, and the arc had broken three things the copy gate cannot see.** A gate that counts English literals cannot see a catalogue key used for the *wrong field*, and the scout's screen had two of them: the wiring gave the shortlist's career field and the transfer panel's career field one `aria-label` between them, so a page-wide selector filled the list's field and the projection's own career stayed empty — the button stayed server-rendered `disabled` and seventeen checks went red. The report's percentile sentence printed its number **twice** (a `.num` span beside a catalogue sentence that already carried the value), and the community walk was still pointing at an address the tier had stopped accepting since §35's pointer promise landed on 2026-10-09. All three are recorded in their own milestone's document, and the fix for the first of them is a **gate that does see it**: **`apps/web/scripts/qa-field-labels.mjs`** reads every page's own component graph and refuses two different components on one page declaring the same constant `aria-label` key — **2/2** today over **111 files, 61 pages, 104 keys, 0 collisions**, and red (exit 1, the collision named) with the defect planted back into a scratch copy of the tree. It is in `scripts/check.sh` and in CI, and the script-inventory census now holds **15** files at **68/68**.

Two kinds of value were technical rather than copy, and the gate names both with the reason: a field's own name printed as itself (`data_origin: synthetic`, `role_fit: null`) and a value that is a product name, an enum or a parameter. The rest was copy, and all of it is in a catalogue now — in three languages, with the count of keys the suite recomputes in `apps/web/messages/README.md`.

**A fifth shape, found on 2026-10-21, and the claim it narrows.** The ceiling of zero was a statement about **three shapes** — JSX text, a label-ish attribute, a label-ish object property — and the tree holds copy in a fourth place the three never looked at: a string literal that reaches the reader from somewhere else. The scout's compare panel prints `A AHEAD` from a helper, so no JSX text, no label attribute and no label property ever saw it; the gate reported zero and the page was English. The census over the whole population read **61** such sites — a helper's sentence, a ternary's wording, a note a component builds — and the gate now counts them with a floor of their own, because the first floor is a statement about those three shapes and this one is a statement about the rest of the source. The exclusions are structural rather than a list of words (an import specifier, a naming attribute, a class name held in a variable, a comparison operand, a schema.org type or field, a snake_case property, a language tag, the framework's own directive, a CSS custom property), so a new class name or a new API field does not have to be added to an allowlist to keep the gate quiet. **The floor may only fall, and the work is now a list rather than a hunt.** It fell to **0** the same day: twenty-six files were wired, twenty-eight keys were added in three languages, and — the finding inside the finding — **the catalogue already held most of the labels the pages were writing out by hand** (the scout's twelve promise rows had keys sitting unused), so the work was mostly a page reading a key that was already there. The gate is **4 checks** now, and the copy check counts **3435 key calls** over **3594 keys** per catalogue. **A template is one site, and a key's values are part of the contract (2026-10-21).** The fifth shape grew two more clauses. A **template** — a sentence assembled from a template's pieces — is now read as the one sentence it is (it was invisible before, because the pieces are not string literals): the class held **26** sentences across eighteen files, and all of them are in the catalogue now. And a **new check** holds every key read to the values its message needs, because a key read without them prints the placeholders: it found four pages broken in a way nobody could see — the scout's rules panel printing `{default} by default, {max} at most` where a label should read "Search limits", its candidate table printing `headroom {value}` as a column header, and the club tier printing a literal `{rule}` where the API's own sentence should have been. The check reads ICU the way next-intl reads it, so a catalogue full of plurals does not read as a catalogue full of missing values, and it holds **3459 key calls**. The gate is **5 checks** now, and every floor is at 0. **What is still open, named rather than assumed away:** the heuristic still reads a lone English word in JSX text as a value rather than a sentence, so "at" and "overall" in a comparison panel are still English in a Chinese page. That class is measured before it is wired, and it is not closed by this commit.

Three cross-cutting defects have now been found and fixed **three separate times** (M4's `tactics/sync.py`, M7's
scouting modules, M8's academy tier): *the committed tree does not pass the gate its own documents quote.* The
cause is always the same — `ruff` is run against a narrower target than CI uses. Item 0 exists so this stops
recurring instead of being rediscovered.

---

## Item 0 — make the local gate the same gate as CI

**Why first (as written 2026-09-30).** `scripts/check.sh` ran `ruff check app tests seed.py migrations`. CI ran
`ruff check app tests evals seed.py migrations`. The documents quoted `ruff check app tests`. Three targets, one of
them enforced. A green local run was therefore not evidence that the commit was green, and the difference had
already cost three repair passes.

**Closed 2026-10-20, and the 2026-09-30 closure was incomplete.** That day's fix removed the path arguments, which
made the local and CI commands identical — and both commands were then run from inside `apps/api`, so the walk
covered `apps/api` and nothing else. `git ls-files '*.py'` counts **252** committed files, **248** of them under
`apps/api`; the **4** outside it (`scripts/bench_api.py`, `scripts/export_openapi.py`, `scripts/qa_db.py`,
`scripts/schema_drift.py`) were read by neither caller while this file's own comment claimed the whole project was
in scope. The target is now written down once, in `scripts/lint.sh`, and both callers run that file:
`bash scripts/lint.sh` from the repository root locally and in CI. It lints all of `apps/api` plus the directories
holding every committed `.py` outside it, derived from `git ls-files` on every run, and prints the population it
read so a narrowing is visible rather than silent.

**Evidence.** Six arms on a worktree at `33bdd8c` whose index is its own (`.scratch/r117_arms.txt`, all 6/6 MATCH):
at that ref the old command answers `All checks passed!` while the shared target names 2 real defects in files it
never read (`bench_api.py` UP041, `schema_drift.py` I001); a planted unused import in `scripts/qa_db.py` is caught
by the shared target and stays invisible to the old command; a **newly** `git add`ed `tools/probe.py` joins the
population the same run (4 → 5 files, 1 → 2 derived directories) and is linted; a plant inside `apps/api` still
goes red, so the widened target contains everything the narrow one read; and a derivation that finds no committed
`.py` refuses with exit 2 instead of passing.

**One number this item owes a correction.** The first measurement in this session reported 3 defects in the
unlinted population, because it ran `ruff check --config apps/api/pyproject.toml` **from the repository root**.
That invocation is not the same gate: with the project root one level up, `app.*` stops being first-party, ruff
sorts it into the third-party block, and the run reports **71 I001 errors in files the real target calls clean**
(arm D). One of the three was that artifact — `scripts/qa_db.py` was `--fix`ed into the wrong order and reverted;
it is byte-identical to `33bdd8c` and was never defective. The honest figure for the population is **2**.

**Files.** `scripts/lint.sh` (new), `scripts/check.sh`, `.github/workflows/ci.yml`, `scripts/bench_api.py`,
`scripts/schema_drift.py`, `CONTRIBUTING.md`, and this item's text. The verification documents that quote
`ruff check app tests` and its variants keep their quotations: they record what was run at the milestone, and a
record of a narrower command is not a claim about today's gate.

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
The rest are **content-page** namespaces that do not exist yet — `club`,
`community`, `video`, `simulate` each need new keys in all three catalogues before a page can
be wired, because their copy is page-specific rather than a shared word (`tactics`, `training`, `progress`, `coach`, `history`, `knowledge`, `challenges` and `market` are done). The `validation` namespace (8 keys) waits for a form that
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

**Done 2026-10-20.** The orchestrator and the six specialists were already here; the *stored trace* was not, and the
item was not finished without it: `/agents/composite` returned its steps and kept nothing, so a run that answered
could not be audited, and the benchmark could measure the answer while saying nothing about the run behind it.

`services/agents/traces.py` stores every composite run on the tier §34 already built for per-account agent state
(`agent_memories`, agent type `orchestrator`, `trace:` key prefix, 30-day TTL) — user-scoped by construction, no
migration, and `prune_expired` already knows how to sweep it. `POST /agents/composite` now answers with `trace_id`
and `status`; `GET /agents/traces` lists the caller's runs and `GET /agents/traces/{trace_id}` returns the whole one —
the plan, every step's query, status, confidence, stamps, duration, citation count, error and the tool calls it
made. A foreign id and a never-issued id answer the same 404 (`no_such_trace`), and a run where **every step failed**
is still traced, because that is the run worth reading.

The tool call is recorded where it is made, not inferred: `research` records its corpus call, `scout` its index
query, `tactical` its catalogue read, `coach` its three reads — and `simulation` and `video`, which answer from a
static explanation, record **none**, so a step's empty list reads as what it is: nothing was looked up.

§64's benchmark gained the metric this item is about. `trace_integrity` is the share of composite runs whose stored
trace replays the steps the answer named, and it measures **1.0** against a gate of **1.0** (the full run:
`overall_answer_rate` 1.0, `avg_confidence` 0.7684, `citation_integrity` 1.0, `refusal_accuracy` 1.0,
`multi_step_completion` 1.0). The harness reads each run's trace back over HTTP and compares it with the answer.

The gate file was measuring eight times: `tests/test_agents_benchmark.py`'s eight cases each called `evaluate()`, so
one file ran the whole 27-case benchmark eight times and let every case disagree with the report the next one read.
The report is now computed once per module and read by all nine cases.

Evidence: `docs/M11_AGENT_TRACE_VERIFICATION.md` — the benchmark run and its score, the full trace of the run that
produced it, the five gating cases in `tests/test_agent_trace.py`, and the two browser checks that the console names
the trace its answer came from.

---

## Item 6 — M12's shared cache tier, live, and the cross-account leak that was behind it

**Done 2026-10-20.** The M12 row's "does not claim" list opened with *"No authenticated Redis tier"*, and the reason it
had not landed was not the plumbing. The shared tier was the response cache's second tier, the cache key was path +
query + origin and **named no caller**, and every private `GET` in this API was therefore stored under a key any other
account's request matched. Measured against a live server with the cache engaged: account A asked for
`GET /api/v1/players` and account B, with its own token, was **served A's player row** — a 200 carrying somebody else's
football identity, with nothing in the response to say so. Landing a tier that is shared across workers would have spread
that answer to every worker on the box.

**Do.** Close the leak, then land the tier.

1. **The key names the caller.** A credentialed request is keyed by a hash of its credential
   (`caller_identity`), so a private answer is stored under its own caller's name and no other
   caller's request can match it. `Authorization` is the only credential this API honours, so it
   is the only one the cache has to consider.
2. **The shared tier never sees a private answer** — RFC 9111 §3.5: a shared cache must not store
   a response to a request that carries an `Authorization` header. So a credentialed request is
   neither read from nor written to the shared tier, and the shared store holds public answers
   only. A public `GET` is still cached, still shared across workers, and still labelled
   `HIT`/`MISS`.
3. **The project's own authenticated cache.** `infra/docker-compose.yml` publishes a `redis:7-alpine` with
   `--requirepass` on host port 63790 — not 6379, which on this host belongs to another application's cache — and CI
   starts the same image with the same password and the same URL.
4. **The password stops leaving the process.** `get_stats()` published the whole `redis_url`, and a Redis URL is where
   the credential lives; the connection log line printed it too. `redact_url()` parses the userinfo off, keeping the
   host, the port and the database number.

**Evidence.** The leak, measured before and after on the same live server: account B's `GET /api/v1/players` answered
`[{"name": "Alice Only Player", ...}]` and now answers `[]`, and the shared store holds no key for that path at all.
The tier, measured with **two server processes** (each with its own empty process-local tier): the first answers
`X-Cache: MISS`, the second `X-Cache: HIT`, and the key is in Redis with its payload.
`redis-cli ping` without the password answers `NOAUTH Authentication required.`
Gates: `tests/test_response_cache_privacy.py` (10) and `tests/test_redis_shared_tier.py` (10). The record, including
what is still not claimed, is in `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md`.

---

## Item 7 — M12's trace backend: a span that reaches somewhere without a collector

**Done 2026-10-21.** The M12 row's "does not claim" list carried one observability sentence that this repository could fix
in itself: *"no span has reached a real backend"*. OpenTelemetry was wired with an OTLP exporter, and a host that runs no
collector has nowhere to send a span — which is every host this project measures on.

**Do.** Build the backend the project already had a database for, and read it back.

1. **`app/core/span_store.py`** is an ordinary OpenTelemetry *exporter* that writes each finished span into `request_spans`
   (migration `0029`), installed behind the SDK's `BatchSpanProcessor` so the request path never pays for the write. The
   rows carry the span's own identifiers — `trace_id`, `span_id`, `parent_span_id` — so the tree is stored rather than
   rebuilt by the reader.
2. **Two rules the exporter holds to**: a store failure is never a request failure (the exporter catches everything and
   returns a failure result), and the store is bounded (every export prunes the spans older than seven days).
3. **`GET /api/v1/traces/{trace_id}`** returns a request's spans, oldest first, each with the parent it hung from.
   Auth-gated; an unknown trace id answers `404 no_such_trace`.
4. **Off by default** (`TRACE_STORE_ENABLED=1` turns it on), because it writes a row per span; the OTLP collector path is
   untouched and the two are independent.

**Evidence.** `tests/test_trace_store.py` (6 cases): a finished span is stored with its own timings and identifiers; a
child span names its parent, read back through the door; a broken store reports failure and raises nothing into the
caller; the door reads a stored trace, answers 404 for an unknown one, and needs a session. mypy is clean over 148 files;
the contract is regenerated at 188 paths / 237 operations. The record is in
`docs/M12_PRODUCTION_HARDENING_VERIFICATION.md`.

---

## Item 8 — M12: what sharing buys, measured with the tier live

**Done 2026-10-21.** Item 6 landed the shared cache tier, and the M12 document still carried the sentence that
no figure measured what it buys: *"the load numbers were all measured with the tier degraded"*. Two things were missing
for that sentence to be answerable, and only one of them was the tier itself.

**Do.** Count the shared tier's own hits, and measure the difference between two workers.

1. **`RedisCache` counts its own reads.** A read the shared tier answered is a hit; a read it did not is a miss. Redis's
   own `INFO stats` counters are deliberately *not* used: they are server-wide, so they could not be attributed to
   this application, and a figure that cannot be attributed is not a figure about this project. The counters reach the
   metrics door, so an operator reads them without a debugger.
2. **Measure two workers against one store.** The claim is not "the cache is fast" but "the cache is *shared*":
   a worker whose own tier is empty must serve the answers another worker paid for.

**Evidence.** Measured on this host, 2026-10-21, two server processes and one store: worker A alone answered 12
requests 9 HIT / 3 MISS from its own tier (its shared hits: **0** — its near tier answered first); worker B, whose own
tier was empty, answered **12 HIT / 0 MISS**, every one of them an answer A had already paid for, with B's shared tier
counting 4 hits and 0 misses (hit rate 1.0). Gates: `tests/test_redis_shared_hits.py` (4 cases), including the
attribution case — two cache objects over one store, where the writer counts no hit and the reader counts one. The
figures are in `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md`; the load numbers are still the degraded ones and the
document says so.

---

## Item 9 — M12: the load figures, paired, with the tier live and degraded

**Done 2026-10-21.** Item 8 answered *what sharing buys* at the cache's own level. This item answers it at the level
the milestone's numbers are written at: throughput.

**Do.** One host, the same minutes, the same endpoint, the same code — one server with the shared store and one without.

**Evidence.** `/api/v1/healthz`, 15 seconds per run, 2026-10-21:

| workers | concurrency | tier live | tier degraded | difference |
| --- | --- | --- | --- | --- |
| 1 | 10 | 201.71 req/s | 236.38 req/s | **-15%** |
| 1 | 50 | 175.22 req/s | 168.05 req/s | +4% |
| 4 | 10 | 187.84 req/s | 175.52 req/s | +7% |
| 4 | 50 | **84.34 req/s** | 39.86 req/s | **2.12×** |

Three findings, and the third is the one worth having. With **one** worker the shared tier is a small tax: the
process-local tier already answers every repeat, so the shared store is a round trip paid for nothing. With **four**
workers at saturation it more than doubles throughput - four workers each holding their own cache is four caches, and
the requests are spread across them, so the working set is four times what one worker needs; one store is one cache.
And the **tail gets worse**: p95 1955 ms live against 1205 ms degraded, because the requests that miss pay for the
shared store before they pay for the database. The record is in `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md`, which
still says plainly that the figures published earlier in it are the degraded ones and a floor on this shared host.

---

## Item 10 — M10: the training program, §36's first kind of content

**Done 2026-10-21.** The creator tier published guides, and its own verification record said what a guide is not: *"Nothing here
is a runnable program: no row carries a schedule, a dose or a progression."* §36 lists six kinds of content a user can
create, and the first is a **Training Program** — so the tier owed an object of its own.

**Do.** Build the program, and make it walkable.

1. **`creator_programs` and `creator_program_steps`** (migration `0030`): a title, a visibility, and an ordered list of steps,
   each naming a catalogue drill, the minutes it asks for and the author's own words. The schedule is the step order, the dose
   is the minutes, and the progression is the position column — unique per program, so a program cannot hold two steps in
   the same place in its own schedule.
2. **A step names a drill, or the program is not a plan.** A step naming a drill the training catalogue does not hold is
   refused **at publication** (404 `no_such_drill`), not at the learner's first session.
3. **Starting a program plans the learner's own training sessions** — the training tier's rows, so completing one is the
   same act as completing any other session, and the schedule is dated from today: the first step today, each later step the
   next day. An account with no player row is refused with the platform's `no_player`.
4. **Five doors** under the tier's existing prefix and rules: publish, the shelf, one program, erase (which takes the sessions
   it planned with it), and start. The codes join the tier's own sets — one tier owns its codes — and the rulebook publishes
   the program's ceilings, formulas and rule beside the guide's.

**Evidence.** `tests/test_creator_programs.py` (10 cases) green together with `tests/test_creator.py` (42): a program carries its
schedule, its dose and its progression; a step naming a drill that is not there is refused at publication; a program with
no steps and a step asking for impossible minutes are refused; starting one plans the learner's own sessions in the
program's order; an account with no player is refused; another account's program answers as absence; erasing a program erases
the sessions it planned. mypy is clean over 149 files; the contract is regenerated at 191 paths / 242 operations. The record is
in `docs/M10_CREATOR_VERIFICATION.md`, whose claim list now says the first kind has an object of its own — and that the other
five do not.

---

## Item 11 — M10: the tactical guide, §36's second kind of content

**Done 2026-10-21.** Item 10 gave §36's first kind an object. The second kind — a **Tactical Guide** — was still only a
section: a guide with a title, a frame and citations, whose subject did not exist in the tier at all.

**Do.** Anchor a guide to a stored tactical system without copying it.

1. **`creator_tactical_guides`** (migration `0031`): the author, a title and summary, a visibility, and the **address**
   of a system. `system_slug` is a plain pointer, not a foreign key, because `sync_tactics` retires catalogue rows;
   `system_hash` is the content address the system carried at publication.
2. **No measurement is stored.** Both phases' eight metrics come from `metrics_for_rows` on the read, the same function
   the `/tactics` door answers with. The column list is asserted as a set so a board, a coordinate or a metric cannot be
   added without a failing case; editing a scratch system's dots moves the guide and flips `moved`.
3. **Publication resolves the anchor** (404 `no_such_system`), the read of a retired system is absence, and the shelf
   keeps the address with null name/formation/path — so nothing of the author's is deleted by a retirement.
4. **Four doors** under the tier's prefix: publish, shelf, one guide, erase. Reach is §35's follow predicate; another
   account's guide is absence; no door answers 403.

**Evidence.** `tests/test_creator_tactical.py` (15 cases) green together with `tests/test_creator.py` (46) and
`tests/test_creator_programs.py` (10) — **71 tests / 0 failures / 0 errors / 0 skipped**. mypy is clean over 150 files;
ruff is clean; the contract is regenerated at 193 paths / 246 operations. A whole-suite SQLite leg over the pre-unit
plane `f4d6146` is recorded in `docs/M10_CREATOR_VERIFICATION.md`: **1,740 / 1 / 0 / 4**, the one red being the plane's
CRLF copy of the contract rather than the tree. The record's claim list now says two kinds have objects of their own —
and that the other four do not.

---

## Item 12 — M10: the player analysis, §36's third kind of content

**Done 2026-10-21.** Item 11 gave the second kind an object. The third kind — a **Player Analysis** — was still only a
section, and the tier could point at a shape but not at a footballer.

**Do.** Anchor an analysis to a stored player without copying him.

1. **`creator_player_analyses`** (migration `0032`): the author, a title and summary, a visibility, and the **address**
   of a footballer. `player_slug` is a plain pointer, not a foreign key, because `services/world/sync.py` retires
   generated rows; `player_hash` is the content address the player carried at publication.
2. **No total is stored.** Five rates come from the anchored row's own columns on the read, each beside its unit and
   formula. The column list is asserted as a set; editing a scratch player's totals moves the analysis, matches the
   world door's own `season_stats` through the published formulas, and flips `moved`.
3. **Publication resolves the anchor** (404 `no_such_analysed_player`), the read of a retired player is absence, and
   the shelf keeps the address with null name/position/overall/team/path — nothing of the author's is deleted by a
   refresh. The first draft's code was `no_such_player`; the tier's own invariant case caught that §39–§41 own it.
4. **Four doors** under the tier's prefix: publish, shelf, one analysis, erase. Reach is §35's follow predicate;
   another account's analysis is absence; no door answers 403.

**Evidence.** `tests/test_creator_analyses.py` (15 cases); the four creator files together answer **90 tests / 0
failures / 0 errors / 0 skipped in 48.356s** (junit `.scratch/leg_analyses_creator.xml`). mypy is clean over 151 files;
ruff is clean on the six touched Python files; the contract is regenerated at 195 paths / 250 operations; migration
`0032` upgrades to head, passes `alembic check` silently and round-trips on a scratch SQLite database. The record's
claim list now says three kinds have objects of their own — and that the other three do not.

---

## Item 13 — M10: the match analysis, §36's fourth kind of content

**Done 2026-10-21.** Item 12 gave the third kind an object. The fourth kind — a **Match Analysis** — was still only a
section, and the tier could point at a footballer's rates but not at the fixture they were earned in.

**Do.** Anchor an analysis to a stored fixture without copying its result.

1. **`creator_match_analyses`** (migration `0033`): the author, a title and summary, a visibility, and the **address**
   of a fixture. `match_slug` is a plain pointer, not a foreign key, because `services/world/sync.py` retires and
   re-creates generated fixtures; `match_hash` is the content address the fixture carried at publication.
2. **No score or stat line is stored.** Five measurements (`total_goals`, `goal_margin`, `shot_accuracy`,
   `chance_conversion`, `possession_edge`) come from the anchored row's own score columns and `stats` object on the
   read, each beside its unit and formula. The column list is asserted as a set; replaying a scratch fixture with a
   different score and stats moves the analysis, matches the world door's own figures through the published formulas,
   and flips `moved`.
3. **An unplayed fixture is refused, not read as a blank result.** Publication answers 409 `match_not_played` for a
   scheduled fixture, and the read answers the same if the anchor has lost its result; the anchor resolves by slug or
   id and an unknown one is 404 `no_such_match`. A retired fixture is absence at the address, while the shelf keeps
   the address with null home/away/kickoff/status/path — nothing of the author's is deleted by a refresh.
4. **Four doors** under the tier's prefix: publish, shelf, one analysis, erase. Reach is §35's follow predicate;
   another account's analysis is absence; no door answers 403.

**Evidence.** `tests/test_creator_matches.py` (16 cases); the five creator files together answer **110 tests / 0
failures / 0 errors / 0 skipped in 52.428s** (junit `.scratch/leg_matches_creator.xml`). mypy is clean over 152 files;
ruff is clean on the seven touched Python files; the contract is regenerated at 197 paths / 254 operations; migration
`0033` upgrades to head, passes `alembic check` silently and round-trips on a scratch SQLite database. The record's
claim list now says four kinds have objects of their own — and that the other two do not. The tactical retired-system
shelf case also needed the same `creator=` scoping the analyses and matches shelves use: the ceiling cases fill the
public shelf past its default page, so an unscoped lookup was reading page one only.

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
