# PLAN — the work that is left, in the order it should be done

`ROADMAP.md` says which milestone is open and what has been proven. This file says what to build **next**, in
order, with the evidence each item has to produce before it counts as done. It is written to be picked up cold:
every item names the files it touches, the gate it must pass, and the thing that would make it a lie.

Rule inherited from spec §96 and this project's own practice: **an item is done when its claim is measured, not
when its code exists.** A number in a document that no command reproduces is not evidence.

Last updated 2026-11-08 — the pointer itself had been left at 2026-11-03 while a row dated 2026-11-08 landed
below it, which is the same drift this table exists to cure.

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
| **— the OpenAPI contract gate read the checkout's newline policy** | ✅ 2026-10-23 | A clean `git worktree` at `394cd10` on this Windows host (`core.autocrlf=true`) checked the committed LF contract out as **484939 bytes / 17305 CRLF pairs**, while `scripts/export_openapi.py` writes **467634 bytes / LF** — so `test_openapi_contract_currency`'s byte case failed on *equal content* — the recurrence the 2026-10-06 row below recorded and predicted. Regenerating cures the working copy only; the next clone checks the same file out CRLF again. The case now normalises the checkout side to LF before comparing (the separate assertion that the exporter wrote no CRLF is unchanged), and a one-byte content change (`"openapi": "3.1.0"` → `"3.1.1"`, same length) on the same CRLF plane still reds it. Witness: old case red on the plane (484939 vs 467634), fixed case **4/4** on the still-CRLF plane, the five documentation gates **38/38 rc=0** there and in the working tree, `ruff` clean. Recorded in `docs/OPENAPI_CONTRACT_VERIFICATION.md`. |
| **— the OpenAPI contract and autocrlf** | ✅ 2026-10-06 | Not on the plan. The working copy of `docs/api/openapi.json` had been checked out CRLF while `scripts/export_openapi.py` writes LF, so the byte gate failed with *equal byte counts* — a host newline policy, not an artifact defect. Regenerated from the tree (162 paths / 208 operations, LF). Windows checkouts of this repo will do this again; the remedy is the exporter, never hand-editing. |
| **— boards could be private or shared by token, never stand in a public place (M9's consent story, §13 follow-up)** | ✅ 2026-10-17 | `POST/DELETE /boards/{ident}/list-publicly` is a dedicated consent door whose payload carries the sentence it grants; `tactic_boards.listed_publicly` (migration `0028`, `server_default false`) is the predicate the gallery reads, so revocation is an **absence, not a delete** — the row survives, the read stops seeing it. Two server pages (`/tactics/gallery`, `/tactics/gallery/{slug}`, both `noindex` and `Disallow`ed) read a new `gallery` namespace (all three catalogues) plus ten `tactics` consent keys, with a `GalleryConsent` control on the owner's edit page. **Measured**: `test_boards.py` 23/23 (`TestPublicGallery` 6/6 — consent door, revocation-as-absence, owner-name-only leak check, arithmetic recomputed not replayed) on throwaway SQLite; `test_locale_claims` 4/4; `tsc` + `lint` + `next build` green; a live walk of a listed board reads the card, the owner's display name and the consent sentence at 200, the board page 200, an unlisted slug 404, and zh renders Chinese while every English literal drops then returns. Committed `862079a`. |
| **— the community wall and both simulation routes read their catalogues** | ✅ 2026-10-20 | §81 2c, three more content-page namespaces. `community` (86 keys, page + `CommunityTools`) landed `ef2595c`; `simulate` was extended across the index + `SimulatorForm` (`31c43ce`, 56 keys) and the `[slug]` report + the seven `simulation.tsx` server components + `SimTools` (`38e254c`, +96 keys → 150). Each: English byte-identical to HEAD (static substring; JSX-split/tagged sentences normalised, nullable figures `String()`-coerced so an absent one still prints as the template literal did), all three catalogues key-identical, and a signed-in walk of the route in en and zh (the English labels gone in zh). The report page's seven components were made `async` and read `getTranslations` themselves; two sentences with inline markup use `t.rich`; the COMPARED/EVENT label tables mapped to keys. Measured: tsc + scoped eslint clean, `test_locale_claims` 4/4, all 150 × 3 ICU messages parse. The shared production build/lint are transiently red **only** on a concurrent session's uncommitted club edit (`focus_items_max` on `PlanView`), which these commits do not touch and which is absent at HEAD — so each commit's tree is buildable — and the report route was walked on a `next dev` server that compiles routes on demand and never touches the club page. |
| **— the two owed suite legs read the same five reds on both engines** | ✅ 2026-10-20 | Recorded in [docs/ASSERT_MESSAGE_VERIFICATION.md](docs/ASSERT_MESSAGE_VERIFICATION.md) §7. Both legs ran on the same frozen plane, `D:/r119-legs` at `fb5453b` (verified with `git rev-parse`; the runner's binding probe printed `app/__init__.py` and `app/main.py` inside the plane): **1660 collected / 5 failed / 2 skipped on each**, SQLite `3965.73s`, PostgreSQL `3978.52s` on server 16.15 with a per-run database the conftest created and dropped. The reds are identical by name: three `test_openapi_contract_currency` cases refuse the three gallery routes (`/api/v1/boards/gallery/public`, `/api/v1/boards/gallery/public/{slug}`, `/api/v1/boards/{ident}/list-publicly`) and the committed contract's 411051 bytes against 416045 serialised; two `test_spec_audit_currency` cases refuse the stale 59-page and 6-`/tactics/*` figures, cured after the plane by #116 (`33bdd8c`). No other case failed. The two skips are the Redis integration case (no Redis) and the `[need_fit]` sorting case. This closes the two legs #114's record left owed. |
| **— a share link previewed the site, not the page, and every indexed page promised a picture that did not exist** | ✅ 2026-10-21 | Recorded in [docs/SHARE_PREVIEW_VERIFICATION.md](docs/SHARE_PREVIEW_VERIFICATION.md). `sharedMetadata()` now owns the two decisions a caller must not forget (`noindex`/`nofollow`, the parent canonical) and the three `/…/shared/<token>` pages build through it; `scripts/make_og_image.mjs` renders `public/og.png` (1200×630) from `app/icon.svg`, `lib/site.ts` and the stylesheet's tokens, so §89's ban on copied imagery still holds and the SEO doc's §3 exclusion is retired in place. `apps/web/scripts/qa-share-preview.mjs` grades it in **25 checks** by *transpiling and calling* the helpers rather than searching for strings, and `.scratch/share109-arms.mjs` proves each clause decisive: **17/17 arms matched a prediction written before the run**, R0 being the reverse control that re-grades HEAD's own two pages and answers `2, 2, 9, 9, 9b, 9b`. The live leg (`next build` + `next start` on port 3213, signed-out reads) reports `summary_large_image declared: 10, of those carrying an image: 10` — the promise is paid everywhere it is made, and `/club/rules`'s smaller `summary` card is the one page that owes no picture. **§109b, found while verifying:** a clean `git archive HEAD` plane does not type-check — `app/portfolio/shared/[token]/page.tsx(10,10): error TS2305: Module '"@/lib/site"' has no exported member 'sharedMetadata'`, one error, because `cc0ad34` wired that page and committed the page only. `check.sh:110` arms exactly this control and did not fail the commit because the gate was run against a dirty tree that held the helper. `lib/site.ts` lands here, retiring it; the same read also corrected `docs/SEO_VERIFICATION.md` §3, which had the root route's story backwards (`/` answers **200** to a signed-out reader — the two `redirect()`s sit inside `if (user)`). |

| **— the locale figures were named three times, and none of them could fail** | ✅ 2026-10-21 | On the day this closed, the same catalogue was published as **288** keys (`ARCHITECTURE.md`, `meta.py`), **393** (`apps/web/messages/README.md`) and **2890** (`en.json` itself), and the repository's front door still said *the translation layer is not built*. A figure in prose has no reader, so the cure is a reader: two cases in `apps/api/tests/test_locale_claims.py`. The first recomputes the README table — its population must equal `en.json`'s leaf count exactly, its numerator must not exceed what the catalogues hold and must not fall below a floor — so the one place a figure persists is the one place a suite derives it. The second refuses a coverage fraction in the carriers that describe the catalogues in the present tense (`README.md`, `ARCHITECTURE.md`, `CONTRIBUTING.md`, `meta.py`, `docs/SEO_VERIFICATION.md`) and names four retired sentences by their exact spelling; dated run records (`PLAN.md`, `ROADMAP.md`, the M3/M4 verification logs) are exempt by identity, because a figure measured at a named run is evidence about that run. **10/10 arms matched a prediction written before the run**: A1 denominator 2891, A2 numerator overclaiming, A3 under-floor, A4 row deleted, A5 the old `287/288` back in `ARCHITECTURE.md`, A6 the README sentence, A7 the SEO heading, A8 a catalogue that gains one translated key (the real drift source, red), and A9 the same key with the table updated (green) as the reverse control. Prose cured here beyond the lane's `a5fd7db`: the root `README.md` claim, the `capabilities` docstring — which is *published* in `docs/api/openapi.json`, so the false sentence was API documentation — `docs/SEO_VERIFICATION.md` §6's `1036 today` now states its formula (the 10 `PUBLIC` entries plus one `<loc>` per world/knowledge row; 10 on an unseeded box, where every world list answers nothing), and `app/sitemap.ts`'s comment, which claimed `/` and every My Football area answer **302** (`/` answers 200; the gated routes answer 307). Contract regenerated from the tree: 430210 → **430382 bytes**, the only diff being that one description. **Left red, attributed, not mine:** `test_spec_audit_currency` §36's census still says 7 paths / 11 operations under `/api/v1/creator` where the committed contract answers 10/16 — M10's census row is stale, and it is the next unit. |
| **— the creator census counted a tier that had grown twice past it** | ✅ 2026-10-21 | `docs/SPEC_COVERAGE_AUDIT.md` §36 published **7 paths / 11 operations** under `/api/v1/creator` and said `/creator` had no browser walk. The committed contract answers **10 paths / 16 operations** — the training program's three paths / five operations landed `5a79598` behind migration `0030`, and that commit updated the two figures C1/C2 recompute while leaving the census (C7) to a suite it did not run — and `scripts/qa-creator.mjs` has been committed since `ab2d4c8`, where it answered **56 of 56** checks. The row now names `creator_programs` / `creator_program_steps` and `services/creator/{publishing,programs}.py`, states the recomputed census, and records the walk. `ROADMAP.md`'s M10 row carried the same snapshot in words — **eleven doors**, *one public, ten private*, **15 refusal codes** — where the tree holds **16 doors** (one public, fifteen private) from **24** registered refusal codes, none mapping to 403; its present-tense sentence now delegates the census to §36's row, the one carrier C7 recomputes, and leaves the dated 2026-09-28 measurements as the historical record. **Witness:** `test_spec_audit_currency` at `fc1cb5f` was red on exactly this row (`(10, 16) == (7, 11)` at `tests/test_spec_audit_currency.py:429`) and is green at the landing commit; before committing, the gate's own regexes read all **11** dual censuses equal to the contract, no C8-shaped count, and **33** cited path tokens / **53** expanded candidates resolving against the committed tree. Dated records are left alone: `docs/M10_CREATOR_VERIFICATION.md`'s 7/11 and `docs/SPEC_AUDIT_CENSUS_VERIFICATION.md`'s "7/11 ✓" are evidence about the runs they name. |
| **— §81's copy gate could not see a key, a template or a word — and no walk had been re-run since the arc** | ✅ 2026-10-21 | The arc closed with a ceiling of zero, and the zero was true of **three shapes** — JSX text, a label-ish attribute, a label-ish object property — and false of the tree. The gate's own census read the difference on 2026-10-21: **61** string literals that reach the reader from somewhere else (a helper's sentence, a ternary's wording, a note a component builds), **26** of them inside templates (a template is *one* sentence, not five fragments), **32** lone English words standing between two tags (eighteen units and field names, **fourteen** real words), and **five** sentences that mixed a translated fragment with a word of their own (`${t("save")} board` read "保存 board" in Chinese). All four classes are wired and the floors are back at 0. Four contracts were added to the same gate: every key against **the namespace it was asked of** (a page asking `club` for `yes`, which lives in `common`, passed a check that asked whether *any* bound namespace held it — and the page threw `MISSING_MESSAGE` at runtime), every placeholder against the values supplied with it (a key read without its values printed `{default} by default, {max} at most` in a column that should read "Search limits"), every key the page **names in its own data** (`t(link.key)` — 63 of them), and no sentence half-translated. Two more gates came out of the same arc: `qa-field-labels.mjs` (no two panels on one page may give a field the same accessible name — the collision that made the scout's walk fill the *list's* field, leave the projection's career empty and take seventeen checks with it) and `qa-proxy-gate.mjs` (a browser may only reach the API through the cookie proxy, because the access token is httpOnly). **All ten walks were re-run** on the builds that carry the arc — scout **124/124**, community **39/39**, timeline **29/29**, carry **45/45**, ledger **39/39**, club **252/252**, creator **72/72**, portfolio **53/53**, market **106/106**, visual-qa **291/291** — and four of them were red before their own repairs: the doubled percentile, a needle that still spelled the pre-ICU plural, a walk still pointing at an address the tier had stopped accepting since §35's pointer promise landed, and a drag that stopped reaching the lawn because the page grew above it. The harness that runs them is in the repository now (`scripts/run-walks.mjs`), and it reads the tiers' own log for `MISSING_MESSAGE` — an error raised on the server, where no browser console can see it. |
| **— M12's account-erasure gate had a door, four tests, and a policy that said it did not exist** | ✅ 2026-10-21 | M12's gate names **account-level erasure** as a condition, and `DATA_POLICY.md` §3 said, in as many words, that it was *not implemented, so not claimed as a feature* — "full account erasure (`DELETE /me` with cascade and aggregate anonymisation) … a UI that offered them would be a lie, so it does not." **The door, the service, the preview and the panel had all been there since the account tier landed**: `DELETE /api/v1/auth/account` erases the account, the rows it owns go through the schema's own cascade, the rows with no foreign key to it are deleted explicitly, the **aggregates are retained with the account id removed** rather than deleted — the platform's cost and action counts survive, the person does not — the account's private media is unlinked from storage with the byte count reported, a phrase and the password are both required, the tenant-orphan case is refused **before any write**, and `GET /api/v1/auth/account` prints the whole inventory without changing a row. What was missing was the *evidence* and the *record*: four API cases and **no walk had ever pressed the most destructive button the interface offers**. `visual-qa.mjs` §10a now does, on a throwaway account — the panel names what it destroys (the inventory's own counts), the control stays inert until the phrase **and** the password are there, the wrong password is refused while the account still answers, and the erasure takes the account and its session stops working (**401**). Two harness defects were found and closed on the way: the settings page holds **two** danger panels, and the walk had been reading the wrong panel's button; and the success branch *replaces* the form, so a wait that looked for the receipt through the confirm field could never see it. The policy now says what is true, and the two things that are still not implemented — per-entity visibility toggles, and a single clip's own delete — are still named as unimplemented. `ROADMAP.md`'s M12 row still carries the old parenthetical ("today only player data is deletable"); that file is another lane's, so the correction is recorded here rather than made there. |
| **— the policy said two things were missing; both were there, and one of them left a row behind** | ✅ 2026-10-21 | `DATA_POLICY.md` §3 listed **full account erasure** and **per-video deletion with storage purge** as *not implemented, so not claimed as a feature*. The account erasure had been there since the account tier landed (`DELETE /api/v1/auth/account`, the cascade, the aggregate anonymisation, the storage purge, the inventory preview) and the per-video delete since M5 (`DELETE /api/v1/video/{ident}`) — and the walk had pressed the second one in a browser for weeks. The policy now says what is true, and the account erasure is **walked** for the first time (§10a of `visual-qa.mjs`: the panel names what it destroys, the control stays inert until the phrase **and** the password are there, the wrong password is refused with the account still there, and the erasure leaves the session answering **401**). Two harness defects were closed on the way — the settings page holds two danger panels and the walk had been reading the wrong one, and the success branch replaces the form, so a wait that looked for the receipt through the confirm field could never see it. And the clip's delete **did** leave something behind: the `jobs` table has no foreign key to `video_assets`, so a clip's analysis job outlived the clip it described — a row that outlives its subject. The delete now takes the clip's own jobs with it, and the case that says so was turned red on purpose first. |
| **— the copy gate's "0 English literal sites" was an artefact of a rule, and a browser found it** | ✅ 2026-10-21 | The i18n arc (§81) closed with a ceiling of **0 English literal sites** over every `.tsx` in the web tier, held by two floors at 0, and the claim was checked by a gate that had been read and re-read. It was also **wrong**. The gate asked, of every string, *is this already translated?* — and answered "yes" whenever the string held **any character outside ASCII**. A middle dot, an em dash, a curly apostrophe, a `×` and a `§` are all outside ASCII, so **every English sentence carrying one of those marks was read as Chinese and never counted** — and this project's copy is full of them. The rule now asks whether the string holds a **letter** from another script, and the gate immediately reported **47 English strings over 15 files** the arc had left behind: the settings page's ten milestone labels, the pitch's two axis labels and two captions, five scout-workbench eyebrows, the erase row's sentence, the club page's four eyebrows and a tooltip, the career form's three strings, the layout's title template, the creator workbench's eyebrow, the portfolio panel's clause, the world components' two sentences, the tactics pages' two titles, the knowledge page's tooltip and the search page's empty answer. **All of them are in the catalogue in three languages now, and both floors are 0 again — with a gate that can see them.** A **formula** (an arithmetic expression whose words are variable names) is exempt structurally, because translating it would make the page wrong and copying it into the catalogue would give one rule two sources to drift apart; a sentence that merely *holds* a formula is still copy and was wired. What found it was a **locale sweep**: a new check in `visual-qa.mjs` that re-opens every page the walk visited with the Chinese cookie and asks whether the page carries any of the English catalogue's own sentences — it answered with three pages, and one of them was `<span className="unavailable">Not played · Data unavailable</span>`, a hard-written English sentence on the world's fixture rows. The lesson is the one the arc exists to teach, and it is now written down in `docs/I18N_ARC_VERIFICATION.md` §7: **a floor is a statement about the gate before it is a statement about the tree.** A gate that cannot see a class of defect holds its floor for a reason that has nothing to do with the code it is watching. The second time in this project that a source-shaped scan missed what a page actually shows — the first was the fifth shape, the string a helper returns. |
| **— a catalogue message is a program, and nothing parsed the programs** | ✅ 2026-10-21 | The i18n arc wired **3736 keys** into three catalogues and every key the source asks for is checked for existence — but **no gate ever parsed a message**. A catalogue message is not a string: `next-intl` parses it when the page renders it, and a message that does not parse **throws instead of printing**. Nothing in the build reads a catalogue — `next-intl` resolves a key in the browser — so a malformed message compiles, typechecks, lints, and then 500s the page that reads it. The one time this project checked ICU syntax, it was a scratch script written for one namespace's own landing (`.scratch/i18nprobe/market-icu.mjs`, 459 messages): never shipped, never run again, and never applied to the other two-thirds of the catalogue. **`apps/web/scripts/qa-icu-messages.mjs` is that check, shipped and permanent** — it parses **every message in all three catalogues** (11208 of them) with the app's own parser (`@formatjs/icu-messageformat-parser`, the one `next-intl` depends on) and refuses three things: a message that does not parse, a plural or a select with no `other` branch, and a key whose placeholders differ between the catalogues (a key that takes `{count}` in English and `{n}` in Chinese prints the literal `{count}` on the Chinese page, and no build step can see that). **It found five messages on its first run**, in all three locales: `scout.transferSubtitle` and `validation.{minLength,maxLength,minValue,maxValue}` were written with **mustache** placeholders — `{{count}}`, `{{min}}`, `{{max}}`, `{{writes}}` — which ICU reads as the end of an argument that never began. They are fixed, and the gate keeps that class out. The English bytes of those five move, and that is safe for one reason: **nothing reads them** — the `validation` namespace is the one the arc left waiting for a form that shows custom messages, and `scout.transferSubtitle` has no reader either, which is exactly why the defect could sit in the tree without a page ever throwing. The third check is what makes the gate worth more than its first run: it compares the placeholders of all **3736 keys** across the three files, so a translation that renames an argument is refused at the door rather than printed as a literal brace on a page. Registered in `scripts/check.sh` and `.github/workflows/ci.yml`; the script-inventory gate reads it at **78/78**. |

| **— the copy gate could not see a translator it had not been told the name of** | ✅ 2026-10-22 | §7 of the arc's own record found a rule about *what counts as Chinese*; this row is about a rule about **who is a translator**. The copy gate decided that a call reads the catalogue by looking at the **name** of the function being called — `/^t[a-z]{0,2}$/` — which is a naming convention, not a fact. Three translators in this tree are named outside it: `tAuth` (the nav's sign-in link and sign-out button), `tCommon` (the nav's demo badge) and `settingsT` (the register form's display-name field). **Seven literal key reads go through them, and the gate saw none of them** — not checked for existence in the catalogue, not checked for the placeholders their messages need, not checked for a word said twice. All seven keys are in the catalogue, so **nothing was broken**: the same *green for the wrong reason* as §7, one layer down. It was found by asking the tree a **different question** — *which catalogue keys does nothing read?* — which needed a resolver that could tell a translator from a local function, and reading the tree's bindings gave sixteen names, three of them invisible to the gate. **The rule now asks about the binding**, resolved in the scope that holds it, and four shapes had to be learned: a **named** binding (`const t = useTranslations("nav")`); a **scope** (`components/ClubTools.tsx` binds `t` to `club` in one function and to `common` in the next — the old file-wide map resolved that function's fifteen reads against the wrong catalogue); a **destructured** binding (`const [t, td, tc] = await Promise.all([…, getTranslations("home"), …])` binds each name **positionally**, and `app/layout.tsx` and `app/page.tsx` both read five namespaces that way); and a **parameter** (`shelfEyebrow(shelf, tp)` hands the `creator` translator to a parameter called `t`, so the **call site** is the fact). The gate now checks **3600** key calls against the namespace each is asked of, up from **3593**, and **nothing the old rule saw was lost**: every one of its eighteen unqualified keys is now held under a namespace, and fourteen qualified keys are new. The red path was watched: a file reading two keys the catalogue does not hold through `tAuth` and `tCommon` made the **old** gate report **8/8 PASS** and the new one report both keys with their namespaces. |
| **— the catalogue held 226 keys no page asks for, and nothing had ever asked** | ✅ 2026-10-22 | The copy gate asks whether every key the source asks for **is** in the catalogue. The other half of that question — whether every key the catalogue holds is **asked for** — had never been asked, so the catalogue could hold **3736** keys while the tree read **3510**, and every gate in the suite would still have said the catalogue was complete. `apps/web/scripts/qa-unused-keys.mjs` is that check, and it read **226** dead keys: **77** in `common` (seventy prepositions and verbs — `common.or`, `common.and`, `common.of` — written so a sentence could be assembled from parts and never assembled, plus a real stale duplicate in `common.pitchCaption3d`), **53** in `scout`, **42** in `club`, **15** in `auth`, **9** in `nav`, **8** in `validation`, **7** in `settings`, **6** each in `career` and `creator`, **1** each in `disclaimer`, `home` and `worldNews`. Three classes, and they are not the same kind of thing: **two answers to one question** (`nav.video` = “Video Analysis” and `nav.videoShort` = “Video” both name the nav's video entry, and the nav prints the second; `nav.login` and `auth.signIn` both say “Sign in”; `nav.register` and `auth.createAccount`; `nav.simulate` and `nav.simulator` — and each page's own title lives in its own namespace, `video.metaTitle` and `simulate.metaTitle`); **a vocabulary for a page the spec names and the tree has not built** (`auth.forgotPassword`, `auth.resetPassword`, `auth.confirmPassword`, `auth.passwordTooShort`, and `validation.*`, which the plan itself records as “waiting for a form that shows custom messages”); and **the preposition table**. The gate's only hard job is to be *right about what it calls dead*, because a gate that reports a key as dead when a read of it is merely unresolved would send someone to delete a key the page needs — and the tree has six shapes of read a naive resolver cannot see: a **named** read (`t("key")`), a **destructured** one (`const [t, td, tc] = await Promise.all([…, getTranslations("home"), …])`, where the namespace is the **position**), a **dynamic** one (`t(band.key)`, the value in the page's own data), a **named-key** one (`t(link.key)`, `labelKey="rowSession"`), a **callback parameter** (`SUGGESTIONS.map((suggestion) => t(suggestion))`) and a **parameter handed a translator by another file** (`EraseRow` reads `t(whatKey)`, and the three call sites that hand it `"rowSession"`, `"rowQuestion"` and `"rowReview"` are in two other files). So the rule is: **a read that cannot be resolved exempts its whole namespace** — a key that cannot be shown to be dead is not dead. On 2026-10-22 **every** read in the tree resolved and **no namespace was left unjudged**, which is what the number rests on. The floor is **226** and it may only fall: wiring a key to a page lowers it, adding a key nothing reads raises it. Registered in `scripts/check.sh` and `ci.yml`; the script-inventory gate reads **83/83**. |
| **— 63 catalogue keys were a second answer to a question another key already answered** | ✅ 2026-10-22 | The dead-key gate names, for each key no page asks for, the **live key that holds the same English sentence** — and 63 of the 226 were in that class. `nav.video` (“Video Analysis”) and `nav.videoShort` (“Video”) both name the nav's video entry and the nav prints the second; `nav.login` and `auth.signIn` both say “Sign in”; `nav.simulate` and `nav.simulator`; `nav.career` and `career.title`; `nav.settings` and `settings.title`; `common.next`/`common.previous` and `common.nextPage`/`common.previousPage`; `common.pitchCaption3d` and `tactics.pitchCaption3d`; six `scout.kv*` rows and their shorter twins (`scout.asksFee` = `scout.kvAskingFee`, `scout.releaseClause` = `scout.kvReleaseClause`, `scout.weeklyWage`, `scout.seasonWage`, `scout.contractYears`, `scout.budgetLeft`); the whole `scout.shortlist*` family and the `scout.lists*` family that replaced it; and `creator.thMinutes` / `creator.thSessions`. **All 63 are gone from all three catalogues** and the gate's floor fell from **226** to **163**. The most interesting deletion is the `club.tableHeaderDate2` / `club.tableHeaderCoach2` / `club.tableHeaderErase3` family: those suffixes are the **field-name gate** at work — `qa-field-labels.mjs` refuses two panels on one page giving a field the same accessible name, so a second “Date” column was disambiguated with a suffixed key — and the suffixed key was then **never read**, because the panel it was disambiguated from is not on the same page as the panel that needed it. So it was a second answer to a question no page was asking, and the field-name gate still reads **2/2** after the deletion, which is the proof that the disambiguation was never needed. The catalogue holds **3673** keys now (was 3736), the two Chinese files fall back on the same **82** / **81** technical tokens they did before, and `messages/README.md`'s coverage table is recomputed from the files rather than written by hand. Gates: qa-unused-keys 3/3, qa-i18n-literals 8/8, qa-icu-messages 2/2, qa-field-labels 2/2, test_locale_claims 6/6, tsc --noEmit clean, next lint clean. |
| **— 67 catalogue keys were a shared vocabulary for copy the interface never wrote** | ✅ 2026-10-22 | The dead-key gate's remaining list was dominated by one thing: a **shared vocabulary for copy the interface has not written**. `common.or`, `common.and`, `common.of`, `common.in`, `common.for`, `common.with`, `common.by`, `common.on`, `common.at`, `common.to`, `common.from`, `common.as`, `common.is`, `common.not` — and the same list of verbs around them (`loading`, `error`, `retry`, `cancel`, `edit`, `back`, `submit`, `confirm`, `ok`, `done`, `hide`, `show`, `more`, `less`, `none`, `select`, `choose`, `required`, `description`, `details`, `actions`, `active`, `inactive`, `enabled`, `disabled`, `public`, `private`, `draft`, `archived`, `deleted`, `restored`, `created`, `updated`, `removed`, `added`, `changed`, `duplicated`, `imported`, `exported`, `downloaded`, `uploaded`, `sent`, `read`, `unread`, `seen`, `unseen`, `completed`, `pending`, `failed`, `success`, `warning`, `info`, `alert`, `critical`). They were written so a sentence could be **assembled from parts** — and no message in this catalogue is assembled from parts: every one is a whole sentence with its own placeholders, which is exactly what the ICU gate holds them to. So the table was never used, and it cost **67 × 3 = 201** translated strings that had to be right and had to be re-read whenever a message beside them changed. They are gone from all three catalogues; the gate's floor fell from **163** to **96** and the catalogue holds **3606** keys (was 3736). The two Chinese files still fall back on the same **82** / **81** technical tokens, because the removed keys were translated in every locale — so nothing about the *coverage* moved, only the size of the thing being covered. The coverage table in `messages/README.md` is now **recomputed from the files** rather than written by hand, so it cannot drift again. Gates: qa-unused-keys 3/3, qa-i18n-literals 8/8, qa-icu-messages 2/2, qa-field-labels 2/2, qa-metadata-title 165/165, qa-crawl-policy 9/9, test_locale_claims 6/6, tsc --noEmit clean. |
| **— the catalogue's floor is zero: every key it holds is asked for by a page** | ✅ 2026-10-22 | The dead-key gate's floor went **226 → 163 → 96 → 0** across three slices, and the last **96** were gone from all three catalogues. Three of the classes are worth naming, because they are mistakes of a different kind rather than dead weight. **36 of them are `club.*` keys whose value is nothing but a placeholder name** — `club.matrixRule` is `“{rule}”`, `club.addressing` is `“{addressing}”`, `club.figuresFrom` is `“{figures}”`, `club.noPayment` is `“{no_payment}”` — and a message that is only its own placeholder is **not a translation**: it is the same string in all three catalogues, so a Chinese page reading one would print the API's English sentence with an empty frame around it. The club page does not read them; it prints the rule the API sends (`rules.data.matrix.rule`), which is the tier's own published prose — the same kind of English the knowledge corpus publishes on purpose. **15 `auth.*` and 8 `validation.*`** are vocabulary for forms that do not exist yet, and the plan itself says so: “`validation` (8 keys) waits for a form that shows custom messages”. **6 `nav.*`** are labels for entries the nav does not offer (`nav.challenges`, `nav.market`, `nav.onboarding`) plus the stale twins of the entries it does. The rule the catalogue now holds is the one the nav's own comment states: **a catalogue nothing reads is a translation that ships to nobody** — a key is created when a page needs a sentence and removed when no page needs it, and when a future page needs one the arc's method writes it from that page's own strings. The catalogue holds **3510** keys (was 3736), and the two Chinese files still fall back on the same **82** / **81** technical tokens, because every removed key was translated in every locale: **nothing about the coverage moved, only the size of the thing being covered**. Gates: qa-unused-keys 3/3 with a floor of 0, qa-i18n-literals 8/8, qa-icu-messages 2/2, qa-field-labels 2/2, qa-metadata-title 165/165, qa-crawl-policy 9/9, test_locale_claims 6/6, tsc --noEmit clean, next lint clean. |
| **— the visual walk read 201/205, and the locale sweep's blocker is now named** | ✅ 2026-10-22 | The visual walk was run again on the build that carries the catalogue work (build `HRuYA1koLs7jIG6XG1qIS`, API `:8773`, web `:3250`, its own fresh SQLite, by `scripts/run-walks.mjs`). It read **201 of 205** checks and exited **1**. **The sitemap probe is whole: 1039 URLs probed, 1039 answered 200** — the retry the harness carries (`ef584d4`) has now cleared the class of failure that killed four earlier runs, and the ten slow renders that read as ten broken routes are gone. **Every page the walk visited renders the Chinese catalogue**: each of the nine per-page checks read the page again with the Chinese cookie, compared it with `messages/zh.json`, checked that the English copy is *gone* and that switching back leaves the screen in English, and all passed. And the tier log carries **no `MISSING_MESSAGE`**, which is what says the catalogue work broke nothing. **The locale sweep did not run**: it is the last check before the walk's own completion check (`visual-qa.mjs:3337`), and the **career section throws before it** — after clicking “Retire from this club” the page still offers “Play the next round” enabled and carries no retired copy, so the walk's next step, clicking “Take charge again”, finds no such button and the walk ends there. So **201/205 was not the sweep’s number**: the sweep was still unobserved, and its blocker was now **named** — which is the thing four dead runs did not have. **And the blocker was the walk’s own timing.** The record on the career page is **server-rendered** — the “Round 1 played” block is the client’s own state and appears at once, but the record beside it comes back from the server on the next refresh — and the walk waited a fixed two seconds for a round-trip it had never measured. It read a zero record under a season that had just played a round and called it a defect; the same race, the other way round, retired the season and produced three more reported defects that were one timing, and then the walk **threw** looking for a button the fresh page would have had, which ended it before the sweep. **The waits are now waits for the condition each check measures** — the record’s own `Rounds` cell, a button labelled “Take charge again”, the play button enabled — and with the first two fixed the walk read **298 of 298**, exit 0, and **the locale sweep ran for the first time**: *“every page this walk visited reads the Chinese catalogue, and none of them carries an English sentence” — **49 pages read in Chinese, 1964 English phrases compared, 4 corpus pages skipped***. It reported three pages, and the finding was that `tactics.phaseOutLower`’s Chinese value is “无球時” while the English on those pages came from the **API’s authored metric prose** (“Mean 12.3 m to the nearest team-mate while out of possession, …”), which is quoted rather than translated — the same kind of English the knowledge corpus publishes on purpose. The sweep had been matching a catalogue value **anywhere** in a page’s text, so a label’s own words inside a longer English sentence read as an untranslated label; the comparison is now **per element**, so an element whose text **is** the value is a forgotten label (the defect the sweep was born to find) and an element whose text merely *contains* it is a longer sentence. This is the **third** time a walk’s own measurement has been mistaken for the product’s — after the probe timeout that recorded 408 for a slow render, and a census keyed on `file:line`. |
| **— the locale's two claims were conventions, and eleven English phrases were in the Chinese catalogue** | ✅ 2026-10-22 | Two claims about the catalogues had never been checked. **“The identical values are the ones that are supposed to be identical”** — a key whose Chinese value is byte-identical to its English is a technical token — was true of every key anybody had looked at and false of **eleven**: the club tier’s **cap names** (`visibility defaults`, `addressing`, `invitations`, `axes`, `weekly minutes`, `focus items / goals`, `goal keys`, `feedback / assessment text`, `plan statuses`) and the academy’s **example placeholders** (`technique, tactics`, `pressing, transitions`). A cap was named in English while the five caps beside it were named by the API’s own field name (`name_max`, `country`, `kinds`), so the row was half field names and half English sentences. All eleven are translated now. **“The English catalogue is English”** was false too: `en.json` held `scout.placeholder` as a **Chinese** sentence, so an English reader saw Chinese — and because the Chinese catalogue held the same Chinese sentence, the *identical values* counted it as translated and the coverage figure was wrong about it. Neither the copy gate (which reads the source, not the catalogue) nor the locale sweep (which looks for *English* on a Chinese page) could see it. `apps/web/scripts/qa-locale-tokens.mjs` holds both claims: the English file may hold no Chinese, and the set of identical values is **named** — **44** keys, each with the reason it is the same in every language (an acronym, an API field name printed as itself, a template of names, a proper name used as an example) — so an identical value without a name is a finding and a name that is no longer a token is a finding. Its **red path was watched**: an English phrase planted in the Chinese catalogue and a Chinese sentence planted in the English one, and the gate named both. The catalogue holds **3510** keys. **The arc's open edge is named in `docs/I18N_ARC_VERIFICATION.md` §6**: the API publishes **66 refusal codes**, each with an English sentence, and the web tier's `errorMessage()` returns that sentence — so a Chinese reader is told “The current password is incorrect” in English. The design is worked out there: the catalogue holds one key per code with the English value being the API's message verbatim (so the English rendering is byte-identical), the code stays the locale-neutral handle it already is, and the switch is **one place, not 31 files** — every browser request passes through the cookie proxy and every server read through `serverFetch`, and `lib/api.ts`'s `errorMessage` is shared by both. The 42 call sites pass a generic fallback today, so the specificity of the API's message is what a per-code catalogue would restore, and a gate would then hold the two in step in both directions. The coverage figures live in `apps/web/messages/README.md`, which the locale test recomputes. Gates: qa-locale-tokens 3/3, qa-unused-keys 3/3, qa-i18n-literals 8/8, qa-icu-messages 2/2, test_locale_claims 6/6. |
| **— all ten walks re-run together, green, on the build that carries the committed catalogue** | ✅ 2026-10-22 | The catalogue work changed what three pages render — the club page’s **cap row** (nine cap names that were English sentences now translated), the academy’s **example placeholders**, and the scout page’s **search placeholder** (the English catalogue’s Chinese sentence, replaced with English) — and the walks are the only thing that can say the change did not break them. So all ten were re-run together on build `eSZ6okbO84ws9gJKLQbxQ`, each against its own API on its own port over its own fresh SQLite database, by `scripts/run-walks.mjs`: **10/10 walks green**, every one exit 0 — scout 124, community 39, timeline 29, carry 45, ledger 39, club 252, creator 72, portfolio 53, market 106, and the visual walk **298/298** with the locale sweep reading *49 pages read in Chinese, 1964 English phrases compared*. The build is the one that carries the catalogue **as committed**, so the evidence and the tree are the same tree. |
| **— a refusal is the reader's copy, so the catalogue holds the API's refusals** | ✅ 2026-10-22 | The API answers a refusal with a **code** and a **sentence**: the code is the stable handle and the sentence is the API's own English — and the web tier shows the sentence (`errorMessage()` returns `error.message`), so a Chinese reader was told **“The current password is incorrect” in English**, on a page whose every other sentence came from the Chinese catalogue. It is the same shape as the arc’s two earlier findings: a convention the implementation did not match (`SessionReportTools.tsx` says a refusal is printed as “the code and the figure the API answered with”). Neither gate could see it — the copy gate reads the **web tier’s source** and the English was in the **API’s answer**; the locale sweep looks for **catalogue values** on a page and the refusal never reaches it as one. The fix is the arc’s method applied to the other side of the wire: **the catalogue holds one key per refusal code, with the English value being the API’s message verbatim**, so the English rendering is byte-identical and this is a *translation* rather than a copy change — and the code needs no translation at all. The switch is **one place, not 31 files**: `lib/refusals.ts` holds the shape and the lookup, `serverFetch` uses it for the server’s reads and the cookie proxy for the browser’s (the middleware skips `/api`, so the proxy had to learn the locale from the `fo_locale` cookie — `i18n/request.ts` now falls back to it). `errorMessage()` and the 42 call sites are **untouched**. The catalogue holds **26** codes; the API publishes **65**, and the other **39** have a message that names a value the request supplied or that a helper chooses, so the catalogue cannot reproduce them — they keep the API’s own words and are **named** in the test. `test_locale_claims.py` holds the two in step in **both directions**: every fixed code has a key whose English value is the API’s message, every `errors.*` key is such a code, and every code whose message is not fixed is named in `NOT_FIXED_CODES`, so a new refusal has to be classified before it can be published. **The census that names it now follows the API’s *helpers*** — it finds the function that raises a refusal, finds its call sites, and sees what they pass — which took two bugs of its own to get right: it read the API’s own **documentation** as if it were code (a comment that quotes the refusal it explains was counted as a second raise site), and it classified a helper’s message as an f-string because the check for a letter-less literal ran first. With both fixed, `invalid_password` resolves through `password_refusal()` to the one message its callers pass, leaves the named list, and joins the covered ones where the drift rule holds its catalogue sentence to the API’s message. The named list is **38**. Its red path was watched. The claim was **read through the proxy** in three languages: `EN 401 \"Email or password is incorrect\"` / `zh 401 \"邮箱或密码不正确\"` / `zh-TW 401 \"信箱或密碼不正確\"` — the English is the API's own message byte for byte, the other two are the catalogue's. The nine tier walks are green (**scout 124, community 39, timeline 29, carry 45, ledger 39, club 252, creator 97, portfolio 53, market 106**) and the visual walk **298/298, exit 0**. The second slice added `invalid_password` and the rule that the **English reader keeps the API's wording** while every other language is shown the catalogue's sentence — because the catalogue cannot carry a value it does not have, and the API's wording is the more specific of the two. The read after it reads the same way (the English byte-identical, the Chinese the catalogue's), and the walk on that build is **298/298, exit 0**. Gates: test_locale_claims 7/7, qa-unused-keys 3/3 (the `errors` namespace is the one the gate reports as left unjudged — the read is dynamic, by the code — and the contract test is what covers it), qa-i18n-literals 8/8, qa-icu-messages 2/2, qa-locale-tokens 3/3, qa-field-labels 2/2, tsc --noEmit clean, next lint clean. |
| **— the aggregate rules door published ten figures it could not derive, including its readiness** | ✅ 2026-10-25 | `/simulation/aggregates/rules` returned sixteen keys, ten without a source: three knowledge-graph walk ceilings for a tier with no traversal, six clause-census fields filled with invented zeros (the census belongs to `/graph/rules`, measured from live metadata), and `world_ready: True` written by hand — under a docstring claiming "Nothing here is typed by hand". Nothing in `apps/web` read any of the ten. The door now publishes `world_ready(db)` measured on the request's database, its own vocabulary and two doors, and the aggregate service's constants; `tests/test_simulation_aggregates_rules.py` (6 cases; 3 red before the fix) pins the key set, both readiness directions, the route list against `app.routes`, the constants and the contract description. 10/10 arms MATCHED at `d7bc120` with the plane clean, including a punctuation control (green) and a service-constant move (green — the door follows). The export sweep also paid M13's contract debt (+30/−2 lines, four input fields), the audit's 37→40 migration figure, and moved three contract-SHA declarations to `4b283580…`; 38/38 in the five currency files, ruff clean, `mypy app` 155 files, `tsc --noEmit` and `next lint` clean. Recorded in [M6_SIM_LEDGER_VERIFICATION.md](docs/M6_SIM_LEDGER_VERIFICATION.md) §9. |
| **— the community and creator rulebooks promised zeros before the migration, and a 500 answered** | ✅ 2026-10-25 | `GET /community/rules` and `GET /creator/rules` answered **500** on a database without the migration (`no such table: creator_profiles`), while both count services held a `ready=False` branch returning true zeros that no door could reach: `rules` defaulted `ready=True` and both doors passed it by hand, unlike every sibling rulebook (`world_ready`, `club_ready`, `academy_ready`, `scout_ready`). The doors now derive readiness from the presence of every table they count (five and twelve, from the models' own `__tablename__`), publish it beside `ready_rule`, and `rules` takes no default. `tests/test_rules_readiness.py` (10 cases; **10 red** before the fix on a plane at `90f3453`) pins both directions, the one-table and dropped-table states, the literal table universe, the two signatures and the contract sentence. 13/13 arms MATCHED at `114edec`, plane clean before and after. The contract's two rulebook descriptions were regenerated (+2/−2) and four SHA declarations moved to `71a5f9bc…`; 25 currency cases green, `ruff check` clean on the touched files, `mypy app` 155 files, and the full SQLite suite **1928 passed, 4 skipped, 0 failed in 1134.89s**. Also measured: the shared lint target is red at HEAD in `tests/test_locale_claims.py:402` (`B007`, an unmodified committed file), left for its own unit. Recorded in [M9_COMMUNITY_VERIFICATION.md](docs/M9_COMMUNITY_VERIFICATION.md) §"The rulebook promised zeros before the migration". |
| **— CI watched a branch that does not exist, so the workflow never ran once** | ✅ 2026-10-25 | `.github/workflows/ci.yml` was written at `c9e48cb` with `on.push.branches: [main]`; the repository's only branch is `master`, so GitHub recorded **zero runs** — `gh api repos/xiaodernan/football-os/actions/runs --jq .total_count` answered `0`, including after the `f297951` push. Fixed at `cc4939f` (`branches: [master]`) together with the shared lint target's own red (`test_locale_claims.py:402`, `B007` from `525fe4d`). `tests/test_ci_trigger.py` (7 cases) asks each workflow's own trigger for the branch the run is about (`GITHUB_REF_NAME` on push, `GITHUB_BASE_REF` on pull request, `git` locally), pins exactly one `Lint` step running `bash scripts/lint.sh` from the root, and runs that target both for real (green) and against an interpreter stub that must receive exactly the population it announces. Pre-fix control at `f297951`: **2 failed / 5 passed** (coverage, lint-green). 11/11 arms MATCHED at `cc4939f`, plane clean; the full SQLite suite was **1935 passed, 4 skipped, 0 failed in 832.90s** (+7 = the new cases). The first run the fix armed (`40131268450`) fired and failed in **two places no local leg could see**, landed as the next two rows. Recorded in [M0_M1_VERIFICATION.md](docs/M0_M1_VERIFICATION.md) §3. |
| **— the first `npm ci` refused the lock npm 10 had to resolve** | ✅ 2026-10-25 | CI run `40131268450` reached `npm ci` for the first time and got `EUSAGE`, `Missing: @swc/helpers@0.5.23 from lock file`: `next-intl`'s optional peer on `@swc/core` asks `>=0.5.17`, the tree resolves 0.5.23, and the lock recorded only the 0.5.15 Next requires. npm 11 (this host) tolerated the gap; npm 10 (Node 22, the workflow's) calls it out of sync. Fixed at `e8fa575` by adding the one nested entry and nothing else — the npm-10 rewrite would also have stripped 126 `libc` metadata lines, so the entry was inserted into the existing lock by hand. Red reproduced before the fix with `npx npm@10.9.4 ci --dry-run`, green after under both npm 10 and the local npm 11, and green again on the plane at `ce0bb4e`. |
| **— the migrations built naive timestamps, and `alembic check` refused the first fresh database** | ✅ 2026-10-25 | CI run `40131268450` applied every migration to a database that had never existed and the check step exited 255 with 27 `modify_type` operations: `0021`–`0025` created `created_at`/`updated_at`/`revoked_at` as `sa.DateTime()`, while `TimestampMixin` and `cv_shares.revoked_at` declare `DateTime(timezone=True)`. PostgreSQL keeps `timestamp` and `timestamptz` apart; SQLite stores both as `DATETIME`, so no local leg saw it, and the check had never run against a fresh PostgreSQL. Fixed at `ce0bb4e`: the five migrations declare the type the models do, and `0040` moves the 27 columns on databases that already applied the older bytes (PostgreSQL only, reversible). `tests/test_migration_timestamps.py` (4 cases) reads the upgrade bodies by AST — prose cannot be charged — and refuses a naive or bare `sa.DateTime`, with a self-test for each spelling it must refuse. Measured: a pre-fix database read 27 naive columns and upgraded to `No new upgrade operations detected`; its downgrade restored 27 and the re-upgrade was green; a fresh PostgreSQL and a fresh SQLite (0001→0040, 41 revisions) both replay clean. The audit's migration census moved 40 → 41. |
| **— 0021's docstring called a tracked, replayed migration a parked draft** | ✅ 2026-10-25 | Found while correcting the file for the row above: `apps/api/migrations/versions/0021_club_fixtures.py` opened with “PARKED DRAFT — not in the tree on purpose … Move to `apps/api/migrations/versions/0021_club_fixtures.py` once the leg is green”, while `git ls-files` tracks it at that path, `alembic upgrade head` replays it on fresh databases, `0022` names it as its `down_revision`, and the models it places “beside it in this directory” live in `app/models/__init__.py`. The note was written before the move and nothing read it afterwards. Fixed at `a0af642`: the paragraph points at the models and the club fixtures door that reads them. `tests/test_migration_docstrings.py` (2 cases) reads every migration's module docstring and refuses the drafting residue — “not in the tree”, “not committed”, “untracked”, “parked”, the word “draft”, and any `migrations/versions/*.py` path — with a self-test for each spelling it must refuse; the scan of the 41 pre-fix docstrings named `0021` as the only carrier, and the reverse control over HEAD's bytes charges `not in the tree`/`PARKED`/`DRAFT`/the path while the fixed file charges nothing. 7/7 arms MATCHED at `a0af642`, each restoring its file by bytes and asserting the restore: the HEAD bytes, a “not committed” sentence, a move instruction, a “draft” sentence and an emptied docstring red the population case, while an untouched plane and a punctuation-only edit stayed green. Recorded in [M0_M1_VERIFICATION.md](docs/M0_M1_VERIFICATION.md) §3.2. |
| **— both catalogue gates reported zero checks on a clean checkout, CI included** | ✅ 2026-10-26 | `qa-translation-freshness` and `qa-population-floor` compared the catalogues with a baseline read from an **untracked file** (`.gate-baseline` / `.population-baseline`), so a clean checkout — every clean checkout, CI's included — printed `CHECKS passed=0 total=0 failed=0` and exited 0. The floor gate's three-locale parity check needs no baseline at all and sat inside the same `else` branch, so a tree whose English catalogue had a key the Chinese ones lacked passed it without that claim being evaluated. And a baseline commit the clone could not read (CI checks out shallow) made the freshness gate print "Resetting baseline.", **rewrite the file to HEAD** and pass — a shallow clone certified its own stale keys. Measured on a scratch repository at a parity-broken commit (en 3 keys, zh/zh-TW 2) with no baseline: both gates `passed=0 total=0 failed=0`, rc 0; with `.gate-baseline` naming a commit the repository did not contain, the freshness gate rewrote the file and exited 0; with a `.population-baseline` file the floor gate did charge a deleted key — the file path worked, the absence path was the defect. Both gates now resolve the baseline from `--base`, then `QA_BASELINE_COMMIT`, then the file; a run with nothing to compare **refuses** with one failing check naming the three ways to supply one; an unreadable or unrelated commit refuses by name and is never rewritten; a shallow clone refuses before comparing; the freshness gate compares against `merge-base HEAD <base>` and runs its two checks when the base equals HEAD; the floor gate's parity check moved out of the baseline branch and its baseline can be read out of a commit (the `getPopulationAtCommit` helper had existed since the gate was written and had never been called). The CI web job checks out with `fetch-depth: 0` and passes `github.event.before || github.event.pull_request.base.sha`. `apps/web/scripts/qa-baseline-gates.mjs` (16 checks, wired into `scripts/check.sh` and CI) builds a seven-commit fixture in `mkdtemp` and holds each verdict: **16/16 green**, with the reverse control over HEAD's two scripts at **3 passed / 13 failed** — the three greens are the paths that already worked (the fixture build, the baseline-file comparison, `--init-baseline` then read). Landed at `4564708`; on a clean plane at that commit the four gates read 2/2, 3/3, 16/16 and a green script inventory. Recorded in [M0_M1_VERIFICATION.md](docs/M0_M1_VERIFICATION.md) §3.3. |
| **— the age profile's sort key stopped type-checking, and CI stopped at it** | ✅ 2026-10-26 | The first CI run after §3's branch fix (`40338019930`) got past the steps that had never run and exited 1 in the api job's `Types` step: `app/services/simulation/market.py:735: error: Unsupported operand type for unary - ("object")`. M13's `retirement_risk` (`cdba698`) built its rows with a dict comprehension, from which mypy infers `dict[str, object]`; the sort key's `-item["age"]` therefore negates an `object`. Every local leg was green — `scripts/lint.sh` is ruff-only, the web type-check does not read Python, and the SQLite suite exercises the door without a type checker — so the gate CI adds is the one that saw it. The block now sorts typed `(name, age)` pairs and builds the dictionaries from the sorted pairs afterwards: the key is still `(-age, name)`, the list order and each dictionary's field order are unchanged. Pre-fix control with HEAD's bytes swapped into the worktree: `1 error in 1 file (checked 155 source files)`, rc 1, the same line and message CI reported; the saved file was restored and verified by `sha256 ac41d847…`. After: `Success: no issues found in 155 source files`, and `tests/test_transfers.py` **46 passed**. Landed at `8aa8b93`. Recorded in [M0_M1_VERIFICATION.md](docs/M0_M1_VERIFICATION.md) §3.4. |
| **— the key-drift gate was red on a correct tree, so CI never reached the gates after it** | ✅ 2026-10-26 | CI run `40338019930` got past Lint and the api job's `Types` fix and stopped the web job at `Key-drift gate`: `CHECKS passed=0 total=2 failed=2`, 119 sentence drifts and 107 key drifts, reproduced locally. The gate demanded one Chinese translation for every English sentence shared **across namespaces**, and for every key name shared across namespaces. A review of all 226 differences on 2026-10-25 found **none** was a defect: `nav.home` is 首页 and `simulate.home` is 主队; `settings.plan` is 套餐 and `coach.tabPlan` is 计划; `thP` is "played" in one table and "passes" in the other. A gate whose population is mostly correct differences can never be green — it had never been green — so **the six gates after it, plus `tsc` and `next build`, had never run in CI at all**. The gate now judges the population where the question means something: **two keys in one namespace** that share an English sentence are the same sentence in the same context, so they must share its Chinese. That population is 115 groups, and the 12 that diverge are named in a ledger keyed on **identity** (`namespace|key1,key2`) with the reason each differs, so fixing one cannot pay for a new one. The cross-namespace figures stay **measured**, as ceilings that may only fall. A population guard refuses a scan that read three catalogues with unequal keys, or found no shared sentence, shared key or same-context group — so empty or misparsed catalogues cannot read as clean. `apps/web/scripts/qa-key-drift-witness.mjs` (10 checks, wired into `scripts/check.sh` and CI) runs the shipped gate over scratch catalogues: the real ones 4/4; a new same-context drift reds check 2 alone and names the site; a key deleted from `zh` reds the population guard alone; a synthetic catalogue with 60 shared sentences and keys translated differently reds both ceilings (120 sentence issues, 240 key issues) while the guard passes; three empty catalogues red the guard; a reviewed site made to agree keeps 4/4 green and prints the one prunable ledger entry; and the real tree still reads 4/4 afterwards. The witness's first run was **0/8**: the gate itself crashed on a leftover identifier after the rename — which the witness caught — and the same-context arm counted sentence occurrences instead of distinct namespaces. Both were fixed before the green. Reverse control with the pre-fix bytes over the real catalogues: `CHECKS passed=0 total=2 failed=2`, rc 1. The script inventory reads 162/164, its two reds naming the foreign staged `qa-translation-quality.mjs`. Landed at `dce0734`. Recorded in [M0_M1_VERIFICATION.md](docs/M0_M1_VERIFICATION.md) §3.5. |
| **— the shared-key gate counted key names, so 24 real translation divergences were invisible** | ✅ 2026-10-26 | `qa-shared-keys.mjs` asked every key **name** held in two namespaces to be named with a reason — 234 rows, 133 named, 101 admitted under a tolerance of 120 — and never compared a value. **136 of the 234** are independent keys whose sentences differ (`backLabel` holds fifteen different sentences); of the **98** whose English really is one sentence in every namespace that holds it, **24** carried different Chinese — and all 24 sentences are at most 12 characters, exactly the length `qa-locale-tokens` skips, so no other gate could see them. **15 rows were aligned** (28 cross-namespace values plus 2 companion edits to `challenges.metMissed` after the suite caught the same-namespace pair the alignment broke), **9 survive as named context differences** (`home` is the nav page and a fixture's home side; `thP` is played and passes; `vs` is a token and 对阵), and the tolerance became two verdicts: a divergence is green only for a named row, and the population is a ceiling of **234 namespace bindings** that may only fall. Witnessed **8/8** on scratch catalogues; the reverse control runs HEAD's gate over six fixtures and it is green on all six — including three empty files. |
| **— the career page published a finance block that nothing rendered** | ✅ 2026-10-27 | `career_view["affordability"]` has carried the wage runway, the balance and the round-by-round budget timeline since `a11d965`/`6b864d6`/`3c47b56`, and `apps/web/app/career/[slug]/page.tsx` never read it. `components/CareerFinance.tsx` now renders the block: the standing figures, the runway with the API's own formula, and the timeline row by row with each stored `budget_after` beside the recomputed balance and an agrees/disagrees badge, plus the empty state for a career with no ledger rows. The page does no arithmetic; the zero-deal `signing` block is deliberately omitted. Twenty-four keys were authored in each of `en`/`zh`/`zh-TW` (population **3,624**, **3,579** translated; `messages/README.md` counts updated to match), with English values chosen to keep `qa-shared-keys` at **234 bindings / 98 rows**. Verified on a production build served on 3211 against a private API on 8732: **31/31** checks in `en` and `zh` on a career that signed Xaniel Kastan (fee 668,250, wage 1,335) and played two rounds — rows 9,331,750 / 9,330,415 / 9,329,080 with 0 disagreements and a 6,988-round runway — and **9/9** on a zero-wage, empty-timeline career. One absence check had to be re-aimed: "Running balance" is embedded in the page's message catalogue, so the empty-page check now asserts the table's structural carrier instead. `tsc --noEmit` and `next build` clean; `qa-locale-tokens` 5/5, `qa-shared-keys` 4/4, its witness 8/8, `qa-key-drift` 4/4, its witness 10/10. Recorded in [M13_CAREER_FINANCE_VERIFICATION.md](docs/M13_CAREER_FINANCE_VERIFICATION.md). |
| **— each transfer listing published what signing it would cost, and the board never showed it** | ✅ 2026-10-27 | `listing_row` has carried a `signing` block (`fee_affordable`, `remaining_after_fee`, the new weekly bill, the new runway) since `3c47b56`; `lib/market.ts`'s `Listing` did not type it and `MarketTools` did not read it. The type is imported from `lib/types.ts`, and the buying board gains an **After signing** column between *Offers* and *Deal*: a `covered` / `over budget` verdict, the balance the fee would leave or how short it is, the new bill and its runway. The Sign button was already driven by `affordable`, the same comparison as `fee_affordable`; the walk asserts they agree. Eight keys per locale (catalogue **3,632 / 3,587**, README updated; shared-key ceiling stays **234 bindings / 98 rows**). Verified on a production build over two branches: the career with wages on the books (12 listings, all affordable — first row leaves 7,754,080 career credits, bill 3,435, runway 2,257) and a fresh 100,000-budget career (12 listings, all over budget, Sign disabled — first row short 1,475,000, bill 2,100, runway 0). **156/156** checks read every cell back out of the served HTML, compare all four figures plus verdict and button per listing, and cover one translated cell per branch. `tsc --noEmit`/`next build` clean; catalogue gates green including `qa-locale-tokens` 5/5, `qa-shared-keys` 4/4 + witness 8/8, `qa-key-drift` 4/4 + witness 10/10. The `no wage limit` branch is rendered but unexercised. Recorded in [M13_CAREER_FINANCE_VERIFICATION.md](docs/M13_CAREER_FINANCE_VERIFICATION.md) §7. |
| **— the career page published a season projection that nothing rendered** | ✅ 2026-10-27 | `career_view["board"]` has carried the pace projection since 2026-10-25 (`board_view`, pinned by `TestBoard`), and the career page never read it. `lib/types.ts` now types the block (`CareerBoard`, `CareerBoardObjective`) and `components/CareerBoard.tsx` renders it: the horizon and its source, both per-round paces, the three projected figures or an explicit empty sentence, the on-track verdict, and one row per objective with target / so far / at this pace and an on-pace, off-pace or as-it-stands badge, plus the API's note, formula and the projections limitation. Twenty-five keys per locale (population **3,657**, **3,612** translated; README updated; shared-key ceiling stays **234 bindings / 98 rows**). Verified on a production build served on 3211 against a private API on 8732: **93/93** checks in `en` and `zh` across three careers — 3 rounds projecting 3 wins · 8 points · −5 GD with one target off pace and the unbeaten run reading as it stands; a never-played career with an empty projection and the unprojectable verdict; and a two-round career whose target is on pace. A negative control mutated the projected wins and confirmed the row disappears from the same output. `tsc --noEmit`/`next build` clean; all seventeen catalogue gates green (`qa-shared-keys` 4/4 at 234/98, witness 8/8; `qa-key-drift` 4/4, witness 10/10; `qa-baseline-gates` 16/16) and `test_locale_claims.py` 7/7. The zero-objective empty state is unreachable through the API and left unexercised, disclosed in the record. Recorded in [M13_BOARD_PROJECTION_VERIFICATION.md](docs/M13_BOARD_PROJECTION_VERIFICATION.md). |
| **— the career page published the next opponent's two measurements, and nothing rendered them** | ✅ 2026-10-27 | `career_view["head_to_head"]` (this career's own record against the next opponent, from its fixtures and nothing else) and `career_view["next_fixture_brief"]` (the engine's band measurements of the next fixture's two sides, side by side with the delta) have been published and pinned in the API since 2026-10-25, and `/career/{slug}` never read either. `lib/types.ts` now types both blocks and `components/CareerNextOpponent.tsx` renders them in one panel: the never-met empty state or the meetings grid and table, the venue/formation/system/overall/form grid, the five-band table with signed deltas, and the stronger / weaker / level sentence the API's own lists select; the page formats numbers and does no arithmetic. Thirty-six keys per locale (population **3,712**, **3,667** translated; README updated; shared-key ceiling stays **234 bindings / 98 rows**). Verified on a production build served on 3212 against a private API on 8732: **23/23** checks in `en` across four careers — never-met all-weaker, all-stronger, mixed with a `0.000` level band, and a two-meeting head-to-head — plus the mixed career in `zh`, every expected string composed from the saved payload, with a reverse control on the pre-change build showing none of the five panel strings. `tsc --noEmit`/`next build` clean; `qa-locale-tokens` 5/5, `qa-shared-keys` 4/4, `qa-key-drift` 4/4. Disclosed: the level-in-every-band sentence has no reachable pairing in the generated world (0 of 190 measured), and the API's 60-second response cache still lets a page serve up to a minute of pre-play data — queued as its own unit. Recorded in [M13_NEXT_OPPONENT_VERIFICATION.md](docs/M13_NEXT_OPPONENT_VERIFICATION.md). |
| **— a successful write left the writer reading their own pre-write answers for up to 60 seconds** | ✅ 2026-10-27 | Measured live before the fix: after `POST /careers/{slug}/play`, **five consecutive plain GETs returned the pre-play career view** — `cached_response_for` caches every 2xx JSON GET for a 60 s TTL and a write neither stored nor dropped anything, and the web tier's `no-store` is a Next-side directive that never reaches the API as an upstream header. The fix is read-your-writes, scoped by the identity the cache key already carries: after a 2xx non-GET the middleware calls `CacheTier.drop_identity(identity)` — `TTLCache` deletes every key whose final colon component is that caller (the percent-encoded components make the suffix exact), `RedisCache` delegates to its process-local fallback and never sweeps the shared store, which holds no private answer by RFC 9111 §3.5 — an anonymous write drops nothing, and a non-2xx write drops nothing. Five new tests (writer misses, failed write stays warm, another caller's answers survive, anonymous write drops nothing, the drop mechanism itself); a five-arm mutation battery with zero extra reds (control clean; the two first-draft predictions corrected on the record — arms B/E keep the anonymous guard, so anonymity is arm D's witness); and a live leg on the private API: A's post-write GET is a **MISS** showing played 2→3, A's next read is a **HIT** of the *new* answer, and B's warm entry survives A's write. CI attribution: the `api` Types red since `f4aa59a` was my own shadowed `row` binding in `ledger.py`, fixed in `28473e4`; the `web` namespace-ownership red is foreign (`7f17b30`'s `notifications` namespace, declaration already sitting in the lane's worktree — untouched). Disclosed: the anonymous branch has no live leg (play requires auth; unit + arm D witness it), the Redis delegation has no live-Redis leg, and B may still read a pre-write answer for up to the TTL by design. Recorded in [M13_READ_YOUR_WRITES_VERIFICATION.md](docs/M13_READ_YOUR_WRITES_VERIFICATION.md). |
| **— the contract book was published on every career read and no page could read it** | ✅ 2026-10-28 | `career_view["contracts"]` has carried the deal book since `90739d7` — each held deal's projected expiry (`signed_round + contract_years × season_rounds − 1`, or the loan's agreed last round), a flag inside `EXPIRY_WARNING_ROUNDS = 3`, and the squad's stored age profile with its retirement flag — and `apps/web/lib/types.ts` had no type for any of it. The page now types the block (`CareerContracts`, `CareerContractRow`, `CareerAgeProfile`) and renders it in `components/CareerContracts.tsx`: the standing figures, the two-branch deal table (permanent row / loan row, the "expiring" badge inside the warning window, the API's own basis string per row), and the age profile with its five bands and named retirement risks. 36 new keys across `en`/`zh`/`zh-TW`; two header wordings were chosen to *not* duplicate existing cross-namespace values ("Age range", "Players counted"), keeping the shared-keys ceiling at 98 sentences / 234 bindings. The live walk signed one buy through a rival's release clause (the plain-price refusal `rival_will_not_sell` is part of the record) and one 2-round loan on `opponent-walk-cycle-braa-05Qm`: expiry 17 from `1 year(s) × 8 rounds`, the loan expiring at round 11 flagged inside the window, and the age profile reading 17 players, mean 27.2, with the loaned 36-year-old named as a retirement risk — asserted against the API's own response on a shipped build, 46/46 checks over the three locales plus the zero-deal career's empty branch. Recorded in [M13_CONTRACTS_PANEL_VERIFICATION.md](docs/M13_CONTRACTS_PANEL_VERIFICATION.md). |
| **— the season's story was published on every career read and no page could read it** | ✅ 2026-10-28 | `career_view["highlights"]` — biggest win, worst loss, the two runs, clean sheets kept, rounds without a goal, and the same played rounds split by venue, all recomputed from the fixture rows the view already holds — was published but unrendered and untyped. The page now types the block (`CareerHighlights`, `CareerHighlightMeeting`, `CareerHighlightSplit`) and renders it in `components/CareerHighlights.tsx`: meeting lines like "Round 2 · Home · 1–0 against Durgard Metropolitan" (the API's own raw `round_index`, the same convention the next-opponent panel prints, so the two panels cannot disagree), the runs grid, the venue-split table (an absent split prints a dash; an all-zero away split prints its zeroes), the API's own formula and note, and an explicit "Nothing to retell yet" branch with the API's reason for the career that has not kicked off. 17 new keys per locale; four sentences reuse existing namespace keys (`thPlayed`, `rowPoints`, `rowUnbeaten`, the venue names) so the shared-keys ceiling holds at exactly 234 bindings / 98 rows. The walk played three rounds at Braeford Athletic and left Dunmoor Town untouched: 78/78 checks against the API's own response on a shipped build (`next start -p 3214`), over `en`/`zh`/`zh-TW` and both branches — the check's three first-run reds were its own apostrophe-escaping needle, not the panel. **Disclosed:** the concurrent momentum batch (`b05804e`..`08199bb`) had staled `qa-key-drift` and `qa-locale-tokens` on master (a new label/aria pair sharing "Substitutions" with deliberately divergent Chinese; a fourteen-key census drift) — both cured in `b59544b`, the ledger entry reviewing the pair and the README recounting the keys the batch added, before this unit landed. Recorded in [M13_HIGHLIGHTS_PANEL_VERIFICATION.md](docs/M13_HIGHLIGHTS_PANEL_VERIFICATION.md). |
| **— the career page published a minutes-based development curve that nothing rendered** | ✅ 2026-10-28 | `career_view["development"]` (`development_view`, M13 Phase 2) has carried the projection since the depth batch — each appearance-holding player's match minutes plus 0.5·training-load units fed through the engine's saturating curve (τ = 3000 minutes, rate 0.18) toward his stored potential, with before/after/delta dicts over all 27 attributes — but the page never read it and `lib/types.ts` had no type for it. The page now types the block (`CareerDevelopment`, `CareerDevelopmentPlayer`) and renders it in `components/CareerDevelopment.tsx` directly under the season's story: the curve's own constants in the key/value grid, and a seven-column table whose movement cell rebuilds the wire's own nonzero deltas as spaced machine keys (`ball control 43→44 · first touch 41→43`) — no new attribute catalogue keys, no arithmetic on the page. 10 new keys per locale ("Potential ceiling" avoids the taken "Potential" value; four column headers reuse existing keys), so the `qa-shared-keys` ceiling holds at exactly 234 bindings / 98 rows. The walk played the highlights walk's career on to its season's end (7,920 minutes) because at three rounds the τ=3000 curve had moved nothing — an em-dash cell is a correct render, but it witnesses nothing; the final state gives every top row 1–24 moved attributes. 111/111 checks against the API's own response on a shipped build (`next start -p 3215`), both branches × en/zh/zh-TW, with two structural pins on the empty branch (no table, no formula paragraph). **Disclosed:** master's api CI job is red from the foreign market batch (`bb712f0`, 13 mypy errors in `market.py`, whose file carries that lane's uncommitted edits) — not cured here. Recorded in [M13_DEVELOPMENT_PANEL_VERIFICATION.md](docs/M13_DEVELOPMENT_PANEL_VERIFICATION.md). |
| **— the youth academy's outcomes had no implementation in the career domain, and the roadmap's own wording was unbuildable as written** | ✅ 2026-10-28 | Roadmap item 7 asked for trainees "graduating into the squad with attributes derived from their `Sessions`/`Reports` … a deterministic roll" — but M8's academy tier hangs off user-created `organizations` (the demo world seeds none, no door writes an org↔career link, so a bridge would be invented data), and a "deterministic roll" is a contradiction: a roll would make a stored match's replay report a squad the one that played never used, breaking the replay identity the M13 Phase 2 determinism guard owns. Both re-scopes are published on the wire (`academy_formula`/`note`), not silently taken. `career_view["academy"]` (`simulation/academy.py`, new) reads the career's under-21 squad players (stored roster with the transfer overlay applied, `YOUTH_AGE_MAX = 21`) and judges each against the eleven the engine's own `select_starting_xi` picks from the same squad with the career's formation — `selected`, `next_in_line` (band rank = seats + 1), `off_the_pace` — projecting the stored overall toward the stored potential over effective minutes (match + 0.5·training units) through `developed_overall`, the scalar twin added to `development.py` so the overall and attribute projections share `_develop_one` and cannot disagree (a pure test pins the equality in behavior). The block is recomputed from the rows on every read, writes nothing back, and carries three explicit empty branches with the API's own reasons. `tests/test_academy_outcomes.py`: 8 pure cases + 3 database-backed (`TestAcademyBlock`, two rounds played through the real `play_round`) — green 11/11 on SQLite with the career view's per-table query pins intact (`test_career.py`+`test_development.py` 38/38) and 49/49 on the PostgreSQL leg. One live read verified the wire (three-round career, class of 3 under-21s all `selected` in the 4-4-2, stored 48–49 → projected 48.2–49.2 at 270 minutes). **The prediction error is part of the record**: the first draft of the off-the-pace case expected a band-rank-5 CB (4 seats) to be off the pace; the block correctly said `next_in_line` — the rule's own boundary — so the case gained an adult CB to make rank 6 genuine. **The live read's first run hit the dev database** (`FOOTBALL_OS_TEST_DATABASE_URL` is conftest-only; `apps/api/.env`'s `DATABASE_URL` wins in any other process) and its rows were cleaned by counted deletes with zero leftovers verified — the trap is written into the verification doc so the next unit does not rediscover it. mypy clean outside the foreign lane's `market.py` (14 errors there, up from 13, still that lane's file). Recorded in [M13_ACADEMY_OUTCOMES_VERIFICATION.md](docs/M13_ACADEMY_OUTCOMES_VERIFICATION.md). |
| **— the key-drift gate's ceilings no longer sat where the tree's drift does** | ✅ 2026-10-28 | `qa-key-drift.mjs`held its cross-namespace ceilings at the 2026-10-25 review's figures (119 sentence issues / 107 key issues) while the tree now measures **99 / 42**: the same-sense alignment cures of 2026-10-27..28 (16 changed values per CJK file inside `dce0734..b59544b`; the other eight catalogue commits in that window only added keys) dissolved most of the reviewed population and no new drift arrived. Both constants were ratcheted onto the measured counts — a ceiling that may only fall was left 20/65 loose, tolerating regressions the review would have red. The ratchet is armed, not just typed: a three-plane arm battery (`.scratch/kd-arm-battery.mjs`, `QA_I18N_WEB` copies of the committed catalogues) shows the control green at 99/241 and 42/260, one mutated shared sentence reding check 3 at 100>99, and one mutated shared key name reding check 4 at 44>42 (once per namespace holding the key — the review's own accounting, preserved). The gate's docstring re-reads the census it quotes (117 same-context groups / 13 reviewed sites; it had said 115/12 since `b59544b` added the substitutions pair). Recorded in [M13_KEY_DRIFT_CEILING_RATCHET.md](docs/M13_KEY_DRIFT_CEILING_RATCHET.md). |
| **— the API had no measured load story: the bench suite drove one endpoint in a loop and nothing asserted what a concurrent career walk must survive** | ✅ 2026-10-28 | `scripts/bench_api.py` gained the `sims` scenario — a task-count walk that registers accounts, opens careers, plays a fixed number of rounds per career with concurrency only *across* careers (the same-career play race is serialized by the database layer: probed 10/10 trials, exactly one 200 + one 409 `conflict` from the `IntegrityError` handler, zero duplicate round rows, `rounds_played` always equal to the row count; the refusal is coarse, but the invariant holds), then re-reads every career and checks its count — with refusal-coded error accounting, a `measured_over` denominator discipline, and a JSON summary whose `ok` folds setup, play and verify into one verdict. `docs/LOAD_ENVELOPE.md` publishes the envelope as the single JSON author of the ceilings (measured p95 1745 ms at 4 workers × 36 plays; the gate shape 2×2×2 measured p95 1656 ms; published ceiling 15000 ms ≈ 9× headroom because a threshold a correct tree cannot meet is not a gate; throughput reported, never gated). `apps/api/tests/test_load_envelope.py` boots a real `uvicorn.Server` in a thread against the test run's own seeded database — proven green on **both** legs (SQLite 3 passed, PostgreSQL 3 passed) — runs the script as a subprocess, and requires both directions: the gate shape must exit 0 with 0 non-2xx, exact rounds per career and p95 under the ceiling, and two refusal arms must exit 1 with the refusal named (wrong prefix → setup 404; `--careers 6` → 409 `career_limit` after exactly 5 careers). Exit codes were read from the subprocess's return code, never through a pipe. **Disclosed:** master's api CI job stays red from the foreign market batch (`bb712f0`, 13 mypy errors in `market.py`, whose file carries that lane's uncommitted edits) — not cured here. |
| **— the copy gate could not see a translator it had not been told the name of** | ✅ 2026-10-28 | Item 22, closed at the gate rather than at the panel. `qa-i18n-literals.mjs` resolved a namespace inside the file that asks for the key, so a `components/` panel handed its translator as a prop resolved to nothing: **7 panels, 167 bare `t("…")` calls** contributed nothing to the check whose whole job is to stop a page throwing MISSING_MESSAGE. The reachability was proved both ways before the fix — the academy panel's real `KeyError: 'thAge'` planted in the *panel* answered 8/8 at an unmoved 3661 calls, in the *page* answered 7/8 at 3662. The seam resolves the hand-off where it happens: import → exported component → the prop's local name → the namespace of the expression the caller passes, iterated to a fixed point (≤6 rounds) so a panel handing `t` to its own sub-panel is followed too. **Two passes, not one, and that was the bug on the first run:** the population walks `app/` before `components/`, so reading the hand-offs while exports were still being collected resolved nothing and named the whole 167 as unfollowable — the figure that matched the independent census was the diagnosis. The merge is deliberately asymmetric: every namespace a panel was ever handed goes into the permissive set (a panel used by two pages is checked against both, never dropped), while the scope stack gets a binding only when exactly one namespace arrived and the file declares none, which is what lets the adjacency and translator-call checks reach panels without guessing an ambiguous case. The ninth check refuses the silence: a key-shaped read through a parameter that resolves to no namespace is named at file, line, key and parameter. **Five arms, all MATCHED, every mutation on a plane copy of the tier outside the repository and restored byte-identically with sha256 compared:** baseline 9/9 at 3824 calls / 7 props / 138 files; a planted key in `CareerAcademy` → 8/9 red at 3825; a key borrowed from another namespace → red at the *same* 3824, which is the crash shape the old gate passed; one `t={t}` deleted from the career page (panel untouched) → 3801, **−23 exactly the panel's census figure**, with the seam check naming `components/CareerAcademy.tsx`; a second hop → 3825 with props 7→8 and files 138→139; control restored → 9/9 at 3824, rc 0. **Disclosed:** the "props bound" figure prints only on the green path, so the two arms that redden that check were graded on the count and the named file instead. Re-read on today's tree, which has moved since: **9/9 — 143 `.tsx` files, 4012 key calls, 97 named keys, 7 props bound** — and that is why the shipped prose no longer copies the count: `ARCHITECTURE.md` states the claim and names the gate as its reader, the arc doc's §18 carries the dated landing figures, and this row carries the reaction. The mirror finding is measured and opened as item 23: `qa-unused-keys.mjs` exempts a **whole namespace** for one unresolvable read, and three dynamic reads spend two namespaces — `careerDetail` (288 keys) and `errors` (66) = **354 of 3971** never asked whether anything reads them; a two-arm plane probe shows a dead key in `careerDetail` leaves the gate green at 0 orphans while the same key in `common` reds it at 1. **Landing note:** the gate's bytes reached HEAD inside the concurrent i18n lane's commit `df1675e`, which swept this session's working copy along with its own; the doc cure and this ledger row are the commits after it. Recorded in [I18N_ARC_VERIFICATION.md](docs/I18N_ARC_VERIFICATION.md) §18. |
| **— the youth class was published on every career read and no page could judge it** | ✅ 2026-10-28 | The web half of item 7: `career_view["academy"]` has answered every career read since `1cd4d93` with the under-21s measured against the engine's own eleven, but `lib/types.ts` had no type for it and the page printed nothing. The page now types the block (`CareerAcademy`, `CareerAcademyTrainee`) and renders it in `components/CareerAcademy.tsx` between the development and board panels: a six-figure key/value grid (class size, selected, next in line, squad size, formation, the age ceiling), an eight-column trainee table — player, position, age, minutes, stored→projected, **potential headroom**, standing against the band's seats with the gap to the last seat, and the verdict as a badge whose class is the verdict's own (`badge--live` for `selected`, `badge--demo` for `off_the_pace`) — then the API's `note`, its `academy_formula` and all six `formulas` sentences, and an explicit empty branch that prints the API's own reason. `potential_headroom` got a column rather than staying a printed-derivation-with-no-reader: its formula sentence was already on the panel, so the figure it names is now visible beside it. 20 new `careerDetail` keys per locale, every one of them an `academy*` name that no other namespace holds, so the `qa-shared-keys` ceiling holds at exactly 234 bindings / 98 rows. **Walked by surgery, not by luck:** the block is recomputed per read, so `.scratch/phase-driver.sh` sets the walked player's stored `overall`, **restarts the private API** (the response cache would replay the previous phase's answer), and the walk composes every expected string from that view plus the committed catalogues — 49 → `selected`, 48 → `next_in_line` (gap 1), 44 → `off_the_pace` (gap 5), 49 restored, so all three verdicts, all three badge classes and the gap interpolation are each reached on the shipped build: **686 checks over four runs (171/172/172/171), 0 red**, both branches × `en`/`zh`/`zh-TW`, with an anti-vacuity check per surgery phase that a trainee row really carries that verdict on the wire. Three iterations were red and all three were mine, not the wire's: the stale-build server (bash `kill` kills the `npx` wrapper, not the Node listener — found by `netstat -ano`, stopped by `taskkill //PID … //F`), three cells built from **adjacent JSX expressions** that React splits with `<!---->` comment nodes (now one template literal per cell), and 20 apostrophe reds from an escaper called with `quote=False` (React writes `&#x27;` in text). **The walk found a shipped-page defect before anything landed:** the component asked `careerDetail` for `thAge` and `thVerdict`, which live in `scout`/`world`/`club`/`academy` — the page prints only what its bound namespace holds — and **no gate could have caught it**: with the draft spelling restored, `qa-i18n-literals.mjs` answered 8/8 at an unmoved 3661 key calls, while the identical planted key in `app/career/[slug]/page.tsx`, which binds `careerDetail` itself, answered 7/8 at 3662. Measured blind-side population: **7 files under `apps/web/components/` make 167 bare `t("…")` calls outside the gate's recorded set**; opened as item 22 with the reaction (not the pass) named as its witness. **Disclosed:** the walk database's copy of Cordale Town has its under-21s aged past 21, so the empty branch is walked on a real career rather than a fixture; and HEAD's `apps/web/messages/README.md` blob ends every line `\r\r\n` (a `5d55d41` bulk-rewrite artifact), so the recount was re-encoded to the file's own spelling and lands as a 2/2 diff instead of churn over all 95 rows. Recorded in [M13_ACADEMY_PANEL_VERIFICATION.md](docs/M13_ACADEMY_PANEL_VERIFICATION.md). |
| **— the signing window was published, typed by nothing, and the walk counted a board it had been told the shape of** | ✅ 2026-11-02 | ROADMAP §22 item 5's first half. `career_view["window"]` / `GET /transfers/{career}` have answered with the block since 2026-10-28 and `/career/[slug]/market` printed none of it: a manager met `transfer_window_closed` only *after* pressing a refused button. The page now binds `const signing = view.window` and renders a `market-window` panel — a notice that follows `state`, eight grid rows (state, the season being judged, which table the length came from, every range with its label, the range holding this round, how many of that range's rounds are played, how many signing rounds are left, where the next opens) and the tier's own formula beside the two constants it is built from; `MarketSigningWindow`/`MarketWindow` and `MarketView.window` are typed, and 20 `market` keys were authored in all three catalogues, three of them plurals on `{count}`. **The panel is not the evidence — the gate is.** `apps/web/scripts/qa-wire-readers.mjs` (12 checks as it landed, 18 today with the `totals` and `moves` populations; file-only, wired into `check.sh` + CI) derives three populations from bytes on every run — the service's own `return {…}` literals through a brace-depth body scan and a string-aware key scanner, the properties `lib/market.ts` declares (followed through `["windows"]`/`["constants"]`), and the fields `page.tsx` really asks for, including inside the `windows.map()` row callback — with four floors so a scan that finds nothing cannot read as agreement, and one exemption (`demo_data`) that only holds while both spellings and the page's own name are in the bytes. `CHECKS passed=12 total=12 failed=0` on the basis it lands on; **arms 10/10 MATCHED** at `wire basis: HEAD ed9b631e…` (control `[]`, A1 `[7,8,9]`, A2 `[7,8,9,10]` — panel *and* binding, so a census that merely looks for the name cannot pass on the binding alone — A3 `[5]`, A4 `[6]`, A5 `[3,5]`, A6 `[3]`, A7 `[10,11]`, A8 `[4,10]`, W `[9]`). **It caught a live drift the same day, from a lane not in this commit:** the working tree then published 13 constants while the type declared 10, so check 9 reads `published, typed by nothing: season_grant_per_round, season_grant_per_point, promotion_grant`. Not fixed from under them — typing those keys here would red the same check in the other direction on CI's basis, and their service file is not mine to edit, and they had taken the handoff one commit earlier than this row knew: `c5d0979` types the three constants, so at the landing commit `05f2a10` the two populations check 9 compares already agree; the handoff is named in §6. **Three copied figures cured the same way:** the board read columns by index and its `cells.length === 13` pin was already stale at HEAD (`142/143`, the lone red `… — 14 columns`) — `board()` now maps every figure through `BOARD_COLUMNS`, header text taken from the catalogue the component renders, plus a header-presence check and a cells-against-headers check (`14 cells against 14 headers, across 12 row(s)`); the rule *count* became a three-way reconciliation of `GET /transfers/rules`, the career door's `view.rules` and the rows the panel printed (`public 14, career 14`, followed the other lane's growth without being edited); and the walk re-draws the window from `early=4 half=1` and compares the eight printed rows through the catalogue's own interpolations. Live: `node scripts/run-walks.mjs market` → **144/144 checks passed**, `--- market: exit 0`, **1/1 walks green** on build `VNv19az9qYbeALp8GaIdh` · API :8772 · web :3249, fresh SQLite. The `count` rename was forced by a real gate, not taste: `{opensIn}`/`{inRounds}` are plural variables `qa-translation-quality` reads as untranslated English in `zh`/`zh-TW` (4 issues on my keys → 4/4), and the pass also corrected `zh-TW`'s doubled particle `賽季的的第`. File-only family green on that tree — re-run 2026-11-08 in M6 §6, where 12 checks read 18, 4026 keys read 4269 and `qa-icu-coverage`'s 2 became 1: `qa-gate-inventory` 188/188 (new script inventoried into both callers), `qa-icu-messages` 2/2 over 12078 messages / 4026 keys, `qa-population-floor` 3/3, `qa-icu-coverage` 2/2 over 3141 calls, `qa-unused-keys` 3/3 (3960 judged + 66 delegated, 0 dead at a floor of 0), `qa-translation-quality` 4/4, `qa-shared-keys`/`qa-key-drift` green. **Found and filed, not cured here — and cured by the row two lines below:** `qa-plural-select.mjs` prints `Plural/selectordinal: 0` on a catalogue the same parser reads as **86 plural nodes across 4026 English messages** — it compares `node.type` to the *string* `"plural"` while `@formatjs/icu-messageformat-parser` returns its numeric `TYPE`, and calls its `walk()` on the array `parse()` returns, so every check grades an empty population; a first recount of locale shape drift (106 messages whose node count differs from English) is *not* a defect count, because `other`-only Chinese collapses are legitimate and the re-armed gate needs a rule that says so. That rule landed 2026-11-08 at `ee5464b`: seven checks, a vacuity floor of 80, and a 16/16 witness; the 86 became 89 on HEAD's catalogues and 87 on the shared working tree, and the 64 `zh`/`zh-TW` flattenings are now the gate's named column rather than an unexplained count. Disclosed residuals: the walk still quotes `asking / 500` by hand (±2.5 = the half-step of the `round_5` it reproduces) and needles `2 left` and `round_5`; the panel prints `2 × half_width + 1`, an arithmetic step the tier does not publish as data; and the clipping/merge rule now lives in Python *and* JavaScript, which is what makes the walk the thing that notices. Recorded in [M6_MARKET_WEB_VERIFICATION.md](docs/M6_MARKET_WEB_VERIFICATION.md) §6. |
| **— the dead-key gate exempted a whole namespace on one dynamic read, so nine keys in a hundred were never asked whether anything reads them** | ✅ 2026-10-31 | Item 23, and the fix keeps the soundness rule while shrinking what it costs. `qa-unused-keys.mjs` will not call a key dead when a read of it is merely **unresolved** — right in principle, **namespace-wide** in practice: `t(column.hintKey)` and `t(column.labelKey)` in the career page and `t(refusal.code)` in `lib/refusals.ts` were spending `careerDetail` (**288** keys) and `errors` (**66**) while the gate printed 3/3 and 0 orphans, so the figure was true of the namespaces it judged and vacuous for the rest. Three mechanisms. (a) The reader now follows an identifier to the **file that declares** the value — `LEDGER_COLUMNS` lives in `lib/ledger.ts` and is imported — and resolves the collection a **chained iteration** started from, because `MILESTONES.filter(…).map(…)` iterates `MILESTONES`, not the filter's result. (b) The seam applies the translator a caller **handed** a function, so a read two links deep (page → `CareerAcademy` → `standingCell`) is visible, and the pass runs to a **fixed point** — 2 rounds on today's tree, the discipline the copy gate learned in item 22. (c) The third check is graded in **keys left unjudged** against a floor that may only fall, and an exemption counts only while the carrier file it names is found, at run time, holding the clause that judges: `errors` is that one delegation, because `KNOWN` in `lib/refusals.ts` is `Object.keys(enMessages.errors)` — self-derived, so it witnesses nothing — and `qa-api-strings.mjs` declines a second census of the API's source, so those keys are judged by `test_locale_claims.py`'s `unheld` assertion, which recomputes them from the codes the API publishes. Reading today, dated because the population moves: **3/3 — 149 files, 149 parsed, 0 parse diagnostics, 2 seam rounds · 0 keys asked for by nothing · 3905 judged here and 66 delegated, which is the whole catalogue at 3971 and 0 unjudged.** **Eight runs on a detached worktree — two baselines, five arms and one control — each prediction written before its run and every mutation restored byte-identically**, with the plane's gate `cmp`-verified against the shipped blob so the arms grade HEAD and not a draft: the differential **inverted** — the same key planted in `careerDetail` answers 1 orphan at rc 1 exactly as one in `common` does, while the pre-fix gate over that same plant stayed 3/3 green, which is the blind spot measured rather than argued; a key planted in the **delegated** `errors` leaves the JS gate green and reds the carrier (`1 catalogue sentence(s) name a code the API does not publish at all: ['qa_probe_dead_code']`), and neutralising the carrier's clause hands the gate back **66 unjudged** with the footer `NOT JUDGED BY ANY READER`; neutering pass 1's handed bindings returns exactly the six seam keys (`academyGap`, `academyStanding`, the three `academyVerdict*`, `highlightsMeeting`), which names the mechanism that does the work rather than the tally. **Disclosed:** the first resolution pass was *more* precise than the scan it replaced and briefly exempted `settings` — an over-narrow read widening the blind spot, caught by re-reading the exemption list and not the pass count — and S1 first ran as a deletion of the declaration it was ablating, so the gate crashed with no verdict, and a re-run lost `NODE_PATH` and exited 1 for the same reason: **a crash is not a red**, and both were re-cast before the figures above were read. The whole file-only family — **32** gates, population derived from `scripts/check.sh` — ran over this tree at `REDS 0`. Recorded in [I18N_ARC_VERIFICATION.md](docs/I18N_ARC_VERIFICATION.md) §19; the gate and roadmap item 23's own closure landed at `5a7d987`, and this row plus the two `ARCHITECTURE.md` claims that gate's old shape cured are the record after the bytes. |
| **— the plural gate read nothing, reported agreement, and its caller said so in a comment** | ✅ 2026-11-08 | Item 5's i18n sibling, and the finding row left at the end of the signing-window row is what this closed. `qa-plural-select.mjs` had **2** checks over a tree holding **89** English plural nodes: both extractors ended in `catch { return [] }`, so a message the app's own parser refused was an absence rather than a finding; `ordinal: node.pluralType === "ordinal"` was computed and never read, so every `selectordinal` was judged against the *cardinal* table and an ordinal missing CLDR's `few`/`many` was complete; the check looped `continue` whenever the other locale had no plural for the argument — measured at **64 of 89** on `zh` and `zh-TW`, both legitimate flattenings and neither a comparison, while the detail line printed "89 plural(s) checked"; `LOCALES` filtered itself *down* to the files present, so adding a fourth catalogue added an unread locale; and `scripts/check.sh` asserted **"Currently 0 plurals/selects in catalogue."** **Seven** checks now: discovery (`readdirSync`, so an unjudged `fr.json` is charged by filename), the anti-blindness invariant (every message counted twice — by the `, plural,`/`, selectordinal,`/`, select,` spellings and by the parsed AST, per locale *and* per key, an exact equality on both bases: en 87/87 · zh 23/23 · zh-TW 23/23 in the working tree, 89/89 · 25/25 · 25/25 at `55f7ea7`), a parse ledger that names the refusal (`EXPECT_ARGUMENT_CLOSING_BRACE`, `MISSING_OTHER_CLAUSE`) and the message it came from, a vacuity floor of **80** placed *under* both the committed 89 and the in-flight 87 so this unit cannot red another milestone's catalogue edit yet cannot be satisfied by a walker that reads nothing, cardinal completeness, **ordinal** completeness against a declared table with an explicit refusal where a locale's ordinal set is undeclared (`he` — the sentence says so instead of being quietly green), and select completeness against the cases English itself declares. Two ICU facts wrote themselves into the header the hard way: a plural without `other` does not **parse**, so no completeness rule can ever name a missing `other`, and an empty branch `one {}` parses fine — which is why the arm intended for the first became two arms. `apps/web/scripts/qa-plural-select-witness.mjs` (337 lines, **16** checks, arms 0/A–O) runs the **shipped** gate over scratch catalogues through `QA_I18N_WEB`, so the verdicts the real tree cannot exercise — every ordinal and select node, an unjudged locale, a parse refusal, an empty population — are each held red *alone*, with the population's own shape disclosed (`89 en, 25 zh (64 flattened)`) and arm O proving the fixtures never leaked into it. First run **5/16**; every red was attributed before a single expectation was re-pinned and none was the gate lying — two witness bugs (a `detailOf` regex that could not find a check whose name contains ` — `, three expectations keyed on the fixture's key where the gate prints the ICU argument name), one bad fixture (an English ordinal omitting CLDR `many`, charged for a real defect), one impossible arm; two more defects were found only by arms reading the printed sentences (`fr .json`, `is a ordinal … declares no ordinal category table`). Second run **16/16**. **The reverse control is the finding:** the parent's bytes, copied out of `55f7ea7` and run over the *same* fixtures, read `passed=2 total=2 failed=0` on all four of ordinal-missing-`few`, an emptied plural population, an unparseable message and a fourth catalogue — and `2/2` on the unmutated control too, so the fixtures were the only difference. A gate that has never been wrong is not a gate that cannot be. Green on both bases (`55f7ea7` via `QA_I18N_WEB`, 7/7 · 1.06 s; working tree, 7/7), witness 16/16 in 17.5 s, `qa-gate-inventory` **204/204** as read that morning (§40's witness takes it to **209/209** the same day) with both files carrying `gates=[scripts/check.sh,.github/workflows/ci.yml]`, `bash -n scripts/check.sh` clean, and the reverse control's temporary carrier directory removed by the script that made it. `ar` and `he` stay dormant-by-absence (no `ar.json`, no `he.json` on either base) and the ordinal rule has **0** live nodes, so the gate's own detail line says the rule is run by the witness, not by these bytes. Recorded in [I18N_ARC_VERIFICATION.md](docs/I18N_ARC_VERIFICATION.md) §37. |
| **— the RTL script rules printed one clean sentence for a real Arabic catalogue, a byte copy of English, and no file at all** | ✅ 2026-11-08 | #199, found by the M6 §6 re-read and cured the same day. `qa-translation-quality`'s two script checks were `for (const locale of LOCALES.filter((l) => l === "ar"))` over a `LOCALES` that had already filtered itself down to the files present: zero iterations, then a `check()` whose detail was a string constant. Measured on the shipped pre-fix bytes at `0a7a9da` — **6/6 green** on the real tree, where neither `ar.json` nor `he.json` exists; **6/6 green** over an `ar.json` written as a literal byte copy of `en.json` (4224 identical messages, 4218 of them Latin text — a file an Arabic reader cannot read, passing as a translation); and **6/6 green** with a planted `fr.json` that every other gate counted and this one never named. Two more holes fell out of the same walk: the exemption set was a hand-copied list (the same 45 paths written out in three files), and the literal-structure loop carried one `/g` regex through every message, so four planted defects scored **2** issues where four exist. The gate is nine checks now — discovery by `readdirSync`, the table read from `qa-locale-tokens.mjs` with an unreadable table itself a finding, a new *byte-identical-to-English must be named* check, both script rules table-driven over five detail branches with floors on messages **showing** the script (the first draft floored on messages carrying Latin letters, which makes a correct Arabic catalogue red), and `lastIndex` reset. Dormancy is a PASS that says `dormant` in its own line and again in a `DORMANT` trailer, because a permanently red lane for an unshipped locale teaches everyone to ignore the gate. `apps/web/scripts/qa-translation-quality-witness.mjs` (315 lines, **11** arms) runs the shipped gate over scratch catalogues through `QA_I18N_WEB`; first run **8/11** — two arms had asked the whole-file branch for the per-message branch's evidence, and one caught a gate wording defect (`fr` printed where the reader needs `fr.json`) — second run **11/11**. Green on both bases (working tree **9/9** in 429 ms over 8538 messages, with both script lines reading `dormant`), and `qa-gate-inventory` **209/209**: read **204** on a plane holding HEAD's 45 scripts, **209** once that same plane is given the witness plus its two carrier lines, so the five-check delta is this unit's and not the lane's. `ar` and `he` stay unshipped; what this buys is that the day one lands, an English catalogue in an Arabic envelope is a finding rather than a green line. Recorded in [I18N_ARC_VERIFICATION.md](docs/I18N_ARC_VERIFICATION.md) §40. |
| **— the two token gates judged a population they had written out in their own source, and one of them carried the exemption table as a second copy** | ✅ 2026-11-08 | #200, the unit §40 deliberately left open ("the same drift surface, in a gate whose verdict does not depend on it being right — worth a unit"). At `1ac0901` both gates began from `const LOCALES = ["zh", "zh-TW"]` and walked the catalogues **two levels deep**, and `qa-token-drift.mjs` re-stated all 45 named tokens — paths *and* reasons — as literals beside the file that defines them. Measured with HEAD's own bytes over the same eight fixtures the new witness ships (definer 5 checks, drift 2): a byte-copied `ar.json` **5/5 + 2/2 green**; a Chinese sentence at `probe.deep.inner` — the founding defect of the file written to catch it — **5/5 + 2/2 green**; a plane with no `qa-locale-tokens.mjs` left the drift gate **2/2 green** on its own copy; a `messages/` holding only `en.json` **crashed both** (`ENOENT …zh.json`, no tally). Nothing was removed and five checks were added. The definer discovers the directory, flattens every leaf at every depth, reddens *and* labels a plane with nothing to compare (`NOT JUDGED` trailer), keys its drift floors per locale so a shipped catalogue without one is a finding rather than a crash, reads README figures for every discovered locale, and censuses any script holding 5+ of the entries as its own literals. The drift gate reads `TOKENS` out of the definer at run time — three named ways the table can be unreadable — and says `not judged —` where it used to print agreement over a zero population; the `TOKENS` literal itself is byte-unchanged because `qa-translation-quality.mjs` scrapes it (§40). `apps/web/scripts/qa-token-gates-witness.mjs` (**386 lines by the inventory's own count, 10 arms**, both gates per plane, exact red set demanded in **both** files): first run **4/10**, six arms red, four causes — a witness that read each refusal twice (the trailers echo them), three `FAIL` lines quoting the success sentence (§40's defect, in my own files), one arm that predicted the strict rule's 4051 where this gate's lenient floor charges 3943, and one arm that asked for a value the check never prints. Then **10/10**. Green on both bases: **7/7 + 4/4** on a `git archive HEAD` plane; on the shared working tree the definer's single red is `the table counts a population of 4096; the catalogue holds 4269` — the M13 lane's **uncommitted** keys, counted in all three catalogues (4096 leaves at HEAD, 4269 on disk; translated 4051 → 4224) — and it is not cured by editing a README that would then publish figures for keys nobody committed. `qa-gate-inventory` **214/214** (209 on HEAD's plane, 214 once it is given the witness and its two carrier lines: the five-check delta is this unit's). The line-ending rule was decided by measurement, not convention: JSON reads need no fold (0 `\r` on disk and 0 in HEAD's object, and a raw CR is illegal inside a JSON string), text reads do (`messages/README.md` is 96 CRLF on this checkout, 0 in the commit; the same for the definer's source the drift gate scrapes), so `readText()` wraps exactly those two kinds of read — one site per file, and the lane's in-flight un-strip of the other 11 files was left alone. Still open, counted in §41: 11 gates still build their locale list as a candidate list filtered by existence, 7 sites still name `["zh", "zh-TW"]` inside a loop, and `qa-rtl-readiness.mjs:149` still names the shipped LTR set — item 201 turns that census into a gate. Recorded in [I18N_ARC_VERIFICATION.md](docs/I18N_ARC_VERIFICATION.md) §41. |

**The pattern worth naming.** Four of the five items above were *claims that had drifted from their evidence*,
not missing features: a gate three targets wide, a `locales` field nobody checked, a migration that had never
been run on the engine the docs tell you to use, and a pair of token gates that named the population they
judged in their own source instead of reading the directory. The features in this project are in good shape.
The documents and the fields are where the work is.

---

## What is actually open

| Area | State | Where the truth is |
| --- | --- | --- |
| M0–M7 | ✅ verified | `ROADMAP.md` gate table |
| M8 Club OS | ✅ verified 2026-09-28 — only §42's **payments** open, and spec §42 says not to rush them | `docs/M8_CLUB_OS_VERIFICATION.md` |
| M9 Community | 🟡 §35 (posts, reactions, follows, feed) landed 2026-09-28; §35's pointer promise landed 2026-10-09 (Item 3). The §36/§37 claim that stood here until now was false and Item 3 says so: those are the creator system and gamification, landed at M10 and M1, and this spec asks for no moderation, reporting or blocking at all | `docs/M9_COMMUNITY_VERIFICATION.md` |
| M10 Creator Economy | 🟡 §38 portfolio landed, share links + CV PDF landed 2026-10-06, and **§36's six kinds of content all have objects of their own (Items 10–16, 2026-10-21/22)**: training program, tactical guide, player analysis, match analysis, career challenge and scouting list each store an address or a rule and compute their figures on the read. The last (Item 15) is a rule another account enters with a career of its own, judged from that career's own fixtures; Item 16 wires it into `/creator` — five writing panels now — and the tier's production walk reads **97/97 checks, exit 0** over a fresh SQLite database | `docs/M10_PORTFOLIO_VERIFICATION.md`, `docs/M10_CREATOR_VERIFICATION.md` |
| M11 Multi-Agent | ✅ verified 2026-10-20 — all six agents + `FootballOrchestrator` landed, the orchestrator replaced the keyword router, §30's graph has its own joint-retrieval evidence, and **§33's stored trace landed 2026-10-20** (Item 5): every composite run is stored on §34's own tier and read back at two new doors, with `trace_integrity` measured at 1.0 against a gate of 1.0 | `docs/M11_AGENT_TRACE_VERIFICATION.md` |
| M12 Hardening | 🟡 §61 erasure landed 2026-10-06; structured logging, cache, latency percentiles, cost advisor, governance + backup docs landed 2026-10-09; **the spend cap gates the coach door at the call** 2026-10-11 (/coach/ask skips only the LLM phrasing when today is spent, so the arithmetic still ships; /knowledge/ask still refuses 429); **OpenTelemetry tracing landed 2026-10-11** (packages pinned, span path measured through an in-memory exporter; **a local OTLP collector now witnesses a live span — 2026-10-22**, and the live walk found the documented base URL had been POSTing to the collector root, fixed to `/v1/traces` with its own test) and **the restore drill was executed 2026-10-11** — `pg_dump` → `pg_restore` inside the project's own container, 58/69 tables byte-identical, and it found the one defect no gate could see: the long-lived container still carried `2e197f085070`'s duplicate indexes, closed by migration `0027`. What has *not* landed is listed in the verification doc's "does not claim" (no authenticated Redis tier (the layer is now the response cache's shared second tier; 6379 here needs a password, so every load figure above was taken with it degraded), no durable or queryable trace backend (a local collector with the debug exporter now witnesses a live span), no off-host backup; **the load ceiling is now published for one worker** (90.80 req/s at c10 on this shared host, and 52.54 at c50 — saturation, not scaling), and four workers were measured against one: +29% at concurrency 10, +6% at 50, and the 15s max outlier fell to 656ms once a second process existed — the figures are a floor — `scripts/bench_api.py` and the run found a defect in the harness first: it reported 0.00 ms latency for every non-2xx response, so a door that always answers 401 measured as instantaneous), and **two more that the response cache turned up when it was verified live rather than read**: a HIT replayed the MISS's X-Request-ID and X-Request-Duration-Ms because the cache middleware wrapped the request-context one, and the cache key ignored Origin, so the second allowlisted origin was served the first one's Access-Control-Allow-Origin as soon as a path was warm - both fixed, both with a case that was run once in the broken configuration to prove it fails there), and **the rate limiter guarded login with no test at all** - eight cases now, which found its stated 5000-bucket bound was never enforced, the prune having dropped only idle buckets while distinct live ones grew the map without limit), and **the crash answer arrived with no headers at all** - Starlette renders an unhandled exception outside every user middleware, so a 500 reached the client without the X-Request-ID its own log line already carried; one function now dresses both, and a test drives a raising route through the real stack to prove it, and **the shared cache tier landed 2026-10-20** (Item 6) — the project publishes its own authenticated Redis, two server processes were measured sharing one store (`MISS` then `HIT`), and the cross-account replay the tier would have spread is closed: the near tier's key names the caller, the shared tier never stores a credentialed response, and the metrics door no longer publishes the cache's password. The load figures above are still the degraded ones, and **the paired ones are in (Items 8-9, 2026-10-21)**: the shared tier counts its own hits, two server processes over one store were measured serving each other's answers (worker B: 12 HIT / 0 MISS), and the load runs were repeated against a live tier and a degraded one on the same host - four workers at c50 gave **84.34 req/s live against 39.86 degraded (2.12x)**, with one worker the tier a small tax (-15% at c10) and the tail worse (p95 1955 ms against 1205 ms). **The trace backend landed too (Item 7)**: `app/core/span_store.py` is an OpenTelemetry exporter that writes each finished span into `request_spans` (migration `0029`) and `GET /api/v1/traces/{trace_id}` reads a request's spans back, so a span reaches somewhere without a collector, and **the cookie proxy carries a caller's trace context since 2026-10-23**: a valid W3C `traceparent`/`tracestate` crosses the proxy and the API's stored span names the caller's span as its parent, while an invalid context is dropped and the tier mints nothing — `qa-proxy-gate` 6/6 over 131 files, 8/8 arm planes, and a live proxy→API walk leaving the caller's trace id in `request_spans`; **the caller's sampling decision is honoured since 2026-10-23**: a `traceparent` with `sampled=0` produces no server span while `sampled=1` does (seven tracing cases; forced always-on reds only that case on `got 2`, forced always-off on `got 0`); **the trace door asks for the operator standing its docstring documents since 2026-10-23**: only an `admin` may read a stored trace, a player is refused `403 insufficient_role` before the lookup for both a stored id and an unknown one, because a stored `SERVER` span carries the request's concrete `http.target` (measured on a share route, token included) and the store has no ownership column — seven store cases, removing the guard reds the refusal case alone at `assert 200 == 403`, and a `("fan",)` standing reds it at `required == ['fan']` and both admin door cases (`403 == 200`, `403 == 404`); the contract was regenerated; **the seven-day retention window is gated since 2026-10-23**: an export deletes an eight-day-old span, keeps a six-day-old one and the span it just wrote (eight store cases; removing the prune call or widening `RETENTION` to 365 days reds that case alone, and a delete-all prune reds it at the six-day row plus the two store-shape cases); **the metrics doors ask for the operator standing their own description names since 2026-10-23**: all six `/api/v1/metrics/*` doors were guarded by `current_user` alone — a session, not a standing — so any registered player read platform-wide account totals, AI spend, the provider mix, per-feature latency and the cache tiers; the standing is now one `require_operator` dependency on the router (`standing_check(("admin",))` → `role_refusal`'s 403 `insufficient_role`), so every current and future door inherits it along with the bearer check (51 cases / 0 failures / 2 skipped; the pre-fix file, `if False`, and a widened `("admin","player")` standing each red the six refusal params, removing the dependency reds ten — the six plus four anonymous-auth cases — and a message-only control stays 51/0; contract regenerated 202 paths / 264 operations / 91 schemas, `HTTPBearer` retained); **the provider tier asks for the same operator standing since 2026-10-24**: `/model-router/costs` published today's platform AI spend to any session while `/metrics/providers` required admin, and `/status`'s `budget_spent_today` was a hardcoded `0.0` beside a docstring promising today's spending — the standing is now one router-level dependency (403 `insufficient_role` before any row) and the status row reads `spend_today_usd(db)` rounded like `/costs` (12 cases / 0 failures; the pre-fix file reds three refusals + parity, `if False` and a widened `("admin","player")` red the three, removing the dependency reds six with the three anonymous cases, restoring `0.0` reds parity alone, message-only control 12/0; contract descriptions updated, 202 / 264 / 91 **The jobs tier asks whose work it is since 2026-10-24**: `POST /jobs` stored no owner, `GET /jobs` listed every account's rows and the read/cancel/delete doors acted on any id, so a player read, cancelled and deleted another account's work; the video pipeline also wrote `DONE`, a seventh state ADR-006 never named, which left a finished job cancellable and `completed_at` a constant `None` — creation now names its owner, the list is the caller's own even for an admin, the three id doors answer a foreign id with `404 not_found` through `ownership_or_admin`, one `TERMINAL_JOB_STATUSES` tuple governs delete (409 `job_not_deletable`), cancel (409 `job_not_cancellable`) and `completed_at`, the pipeline writes `COMPLETED`, and migration `0036` rewrites legacy `DONE` rows (16 job cases, the 52-case file set 0 failures; the pre-fix file, a dropped `user_id`, an unfiltered list, a removed guard, a two-state tuple, the old delete predicate, `completed_at=None`, the pipeline's `DONE` and a no-op migration each red their predicted cases, message-only control 52/0; contract descriptions updated, 202 / 264 / 91 unchanged, audit migrations 36 → 37). unchanged) | **The security probe's report gets readers since 2026-10-24**: its declared contract SHA-256 had frozen at the first runs while four tiers' description edits moved the contract's bytes, and no case opened the report; run D reread the committed contract on a fresh PostgreSQL database at head `0036` (10/10, 0 failed, 0 server errors, 6.88 s; 212 / 52 / 91 unchanged) and the report, the M12 record and the ROADMAP name it, with a 12-case gate recomputing the census through the probe's own methods over the committed tree (stale SHA/row/floor/S1/run mutants each red their predicted case, message-only control 12/0; focused 25 / 0 / 0 / 0) **The video run ledger counts the attempt that ran since 2026-10-24**: the synchronous pipeline created its `video.analyse` job with the column default `attempts=0` while `/video/{id}/jobs` renders `attempts`, so a completed or failed run was traced to a row saying it had run zero times; the row now records its one attempt at creation (the video file's 36 cases green, 0 failures / 0 errors / 0 skipped; removing the line, changing the count to 2, and blanking the door each red the two new cases alone — reporting 0, 2 and 0 — and a message-only control stays 36/0, so the cases pin the rendered count) | `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md` |
| §81 i18n | ✅ catalogues full, switcher works, shell switches, and the copy gate now reads the whole tier; **108 files bind a translator (277 bindings), counted on the tree at `c3fadcd`** — every namespace, including the ones this row once called "not yet existing". **No English literal is left**: the copy gate (`apps/web/scripts/qa-i18n-literals.mjs`) reads **0** over every `app/**` and `components/**` file **and every `.ts` module the tier owns** — it was taught to read the tier's own modules on 2026-10-22, and the copy it found there was the career page's ledger headers, English in every language — on five floors, and that 0 is only true because the rule that decided a string was "already translated" by asking whether it held *any* character outside ASCII was corrected on 2026-10-21 — a middle dot is punctuation, not another script — which alone found **47** more, and because the gate's own rule for **who is a translator** was corrected on 2026-10-22 (it read the *name* of the variable, so `tAuth`, `tCommon` and `settingsT` were invisible to it). The catalogue holds **3596** keys and **every one of them is asked for by a page** — a new gate (`qa-unused-keys.mjs`) holds that, with a floor of **0**. The **65 refusal codes the API publishes** each carry a sentence in all three languages, and the English reader is shown the API's own message byte for byte (`apps/web/lib/refusals.ts`, held by `apps/api/tests/test_locale_claims.py`); the tier's own error sentences live in the catalogue too, and a new gate (`qa-api-strings.mjs`) holds that the web tier holds no copy of an API sentence anywhere in its own code. A third new gate (`qa-error-boundary.mjs`) holds that the tree keeps
a **failure boundary** in the reader's language: it had a localised not-found page and no boundary at
all, so a page that threw was the framework's own English default. | the grep that counts `useTranslations`/`getTranslations` callers on HEAD blobs; the label census re-run **with a TSX parser over all eleven HEAD dictionaries** (`census-ast.mjs`, 105 files, 0 parse diagnostics). At `8feda9a` it read **A 24 sites, B 168, C 54 — 245 distinct sites**; re-run at `844216d` after the `nav` group it reads **A 24, B 168, C 40 — 231 distinct sites**, plus **E 3** (a label in a component's default parameter, which no earlier shape could see). `world`'s C group closed at `8feda9a` (17 found, 16 wired, 1 named sense skip), `common`'s at the two shape-C landings (11 wired + 1 skip) and `nav`'s at `844216d` (21 rows: 15 wired, 4 reachable only case-insensitively so wiring them would rewrite `en`, 2 left as key-ownership questions with the reason named). The union fell by 14 for 15 wired attributes, and the one is not a missing label: `tactics/[slug]/page.tsx` `title="Tactical system"` survived its own file's edit but moved from `:79` to `:81`, so a census keyed on `file:line` re-counts a site when a line *above* it is written. That is why every figure in this arc names the ref it was measured at. The parser also **withdrew the older "shape A 0"**: `common`/`world` words do stand as bare JSX text — 7 A sites and 76 B sites carry one of their values, every one of them still a sense question rather than a wiring. | A **fourth shape** is now measured and partly closed: a label inside an object literal, e.g. `back={{ label: "Back to Football World" }}` or `metadata = { title: "Community" }`, which no JSX-shaped census can see. `census-d.mjs` parses every HEAD `.tsx` (108 files, 1331 object literals) and read **14 D sites**, of which **10 were byte-exact against `en`** — all ten are `export const metadata` titles, so wiring them needs `generateMetadata`, not a prop — and **4 are case-only** (`label: "Career mode"` vs `nav.career` = "career"), which stay open because wiring them would rewrite English's bytes. Re-run at `2348ed1` it read **15 rows / 11 byte-exact**: the knowledge landing surfaced an eleventh site, `/knowledge`'s own metadata title. **The metadata half is now wired for nine of those eleven (`dd8618c`)**, and the census re-run at `dd8618c` reads **6 rows / 2 byte-exact**. The rule the slice states, because it is what makes a literal title safe to delete: *a page's document title takes the key its own heading already reads* — no new catalogue keys (all three message files were dirty from concurrent work, and a key written there would ride along in someone else's commit). The two that stayed, stayed for named reasons: `/community`'s h1 says "Community wall" while `nav.community` says "Community", so wiring its tab would couple two copies that do not agree; `/knowledge` was the file another writer is standing on. **That one is now wired** (`ef0ff8b`, reading the orphan `knowledge.metaTitle` its own writer had authored), so the census re-run at `ef0ff8b` reads **5 rows / 1 byte-exact** — the survivor being `/community`'s metadata title — and the pair the gate's ledger carries is `/community` ("Community" over "Community wall") and `/club` ("My clubs" over "Club tenancies"), two copies that differ in English where choosing between them is a sense decision, not a wiring. One case-only row moved line but not shape (`app/scout/page.tsx` :41 → :46) — the census is `file:line`-keyed, which is why every figure above names its ref. **The description half is now closed too (2026-10-14, eleven pages measured at the re-run)**: career and scout gained `metaDescription` in namespaces that already existed, knowledge's own orphan `metaDescription` finally got its reader (byte-identical), the six world list pages took six flat keys, and `/my-football` + `/portfolio` gained minimal namespaces of their own because their descriptions belong to neither the nav nor any existing catalogue — a second binder name per file, so the gate's one-name-one-namespace clause stays green. English byte-identical; the rescan reads zero literal descriptions; both metadata gates and the locale claims pass unchanged; live read repaints per locale. Still disclosed: three pages (`/portfolio`, `/scout`, `/my-football`) carry a bare metadata object with no `openGraph` block, so their link-preview title is the layout's `title.default`. The permanent form **is** written and shipped now (`ef0ff8b` + `5ef05eb`): `apps/web/scripts/qa-metadata-title.mjs` states the rule over the whole page population instead of one change's diff — every `app/**/page.tsx` must declare its tab in exactly one form, **may not** hold a load-time literal on a page whose heading reads a key (check 4, DRIFT), **may not** read a key on a page whose headings are all literals (check 11, MIRROR — the same mismatch in the other direction, empty today so it refuses rather than ratchets), and where both are literals they must be the same copy unless a ledger row whose predicate is re-read from that file's bytes on every run says otherwise (checks 5/6). Plus the population floor, a per-file parse-diagnostic floor, a heading-carrier floor, one-namespace-per-binder, per-key resolvability in all three catalogues, a differs-from-English test on every tab key, an orphan clause on `<ns>.metaTitle`, and a descending ceiling on literal-titled pages — every count derived from the same walk that finds the pages, so a narrowing scan goes red instead of quietly shrinking what is protected. At `ef0ff8b` on a clean plane it reads **population 59, tabs keyed 25 / literal 24 / dynamic 10, heading carriers 45 (keyed 25, literal 13, dynamic-only 21), CHECKS 94/94**; the same script over the dirty worktree reads 101/101 with keyed 27 / literal 22, because a concurrent writer has since wired two more pages — the ceiling is a ratchet, so the fall is what the gate wants. Witness **12/12 planes matched** (`arms-meta.mjs`): reverse control to the pre-wiring blob, stale exemption, an added disagreeing page, a tab pointed at the h1's own key, a deleted zh value, a zh value copied from English, an added agreeing page, `app/` deleted, a heading carrier retyped as a `Panel`, a page declaring both metadata forms, and a keyed tab over a literal heading; each red judged by its clause id **and the file it names**, never by a count. Two lessons the writing taught, both recorded here because they are not obvious from the file: (i) the "2 remaining sites" this row carried for a whole slice was a **D-census** number being read as a **page-population** number — the population holds 24 literal-titled pages, of which exactly 2 disagree with their own heading and 1 more (`/knowledge`) was drifting from a keyed heading; and (ii) the rule is **not** "the tab reads the key its heading reads". `/knowledge`'s tab names the surface ("Football Knowledge") while its h1 names the corpus ("The football knowledge base"), exactly as `agents`, `coach` and `settings` already do — so the gate forbids the two directions of *mismatch*, not a difference of copy. A census written earlier in this arc (`meta-census.mjs`) printed a bucket labelled `title-keyed-heading-literal` reading 7 and looked like a population the gate ignored; all 7 are keyed headings under a different key or dynamic ones (`board.name` twice) — the label described the census's equality test, not the heading's kind. Cross-checking two scans is what found both, and `/knowledge` closed without new copy: its own writer had already authored `knowledge.metaTitle` and left it with **no reader** (7 `metaTitle` keys, 6 read), so the drift page and the orphan key were one fact seen from two sides. Live read **34/0** over `/knowledge` × 3 locales with `/world/search` as the still-literal control: the wired tab repaints ("Football Knowledge" / "足球知识库" / "足球知識庫", `og:title` with it) while the control does not move, and every description stayed the page's own bytes. `dmeta-check.mjs` and `knowledge-meta-check.mjs` remain as change-time instruments for the next wiring slice; the shipped rule no longer depends on them. The **back-link half of shape D is closed** (`c7e9f4c`, seven pages: `/club`, `/community`, `/graph`, `/portfolio`, the portfolio share page, `/simulate`, `/video` now read `nav.home` / `nav.myFootball`), which is what found the middleware defect in the row above: the live read could not reach two of those pages at all. Six `/world/*` pages still carry `back={{ label: "Back to Football World" }}`, a label with **no key** — the value is `"Back to " + en[nav.world]`, so it needs either a new key or an interpolated one, and the sense rule for it is not written yet. A **fifth** shape is measured (shape E, 3 sites) and open for a different reason: one of its strings is used as data by a page that compares against it. **The crawl half of the same decision is now measured, fixed and gated.** Three files split one decision — `middleware.ts`'s `PROTECTED_PREFIXES`, `app/robots.ts`'s `DISALLOWED`/`ALLOWED`, `app/sitemap.ts`'s `PUBLIC` — and each only *described* the others in a comment, so nobody had ever reconciled them. The reconciliation (files only) reads **population 59 `page.tsx`, gated 34, advertised 10, 30 pages declaring `robots:{index:false}`**, and **8 gated pages stood in no disallowed prefix at all**: `/agents`, the four `/graph` pages, the three `/simulation/aggregates` pages. Seven of the eight lean on their own `noindex`, which is **inert** — a signed-out fetch answers 307, a redirect has no `<head>`, so the one crawler that would honour the declaration never reads it. Confirmed live on `:8837` (a fresh `next build` with `NEXT_DIST_DIR=.next-m107`): all eight answer 307. The fix adds the three missing prefixes (`DISALLOWED` 21 → 24; `/career` was already carried) with each prefix's own rationale, and `ALLOWED` is unchanged. The permanent form is `apps/web/scripts/qa-crawl-policy.mjs` — **9 checks**, transpiling and *calling* all three shipped decisions, then: floors + callability (1), gated ⇒ disallowed (2), advertised ⇒ not gated (3), an advertised path under a disallowed prefix needs a strictly longer `Allow` (4a) **and** that mechanism needs at least one live carrier (4b), advertised ⇒ not self-declared `noindex` (5), a stale `Allow` (6), an orphan `DISALLOWED` prefix, with `/api/` held in a two-directional ledger (7), and a readable `robots:` declaration (8). Green on the fixed tree at **9/9** — `population=59 | gated=34 | advertised=10 | noindex=30 | disallowed=24 (23 matching a page, 1 not)` — and the reverse control, the same script over the parent's `robots.ts`, reads **8/9 with check 2 red naming exactly those 8 routes** (`disallowed=21 (20 matching a page, 1 not)`). Witness **13/13 planes matched** (`arms-crawl.log`), judged by clause id and never by a count; two of the arms found a hole in the gate *before* they ran. First, `robots: SOME_IDENTIFIER` made **no** clause red anywhere, so a declaration whose value is not an object literal is now reported opaque and refused — check 8 exists because arm A8 predicted it. Second, my denominator was wrong: I predicted "8 checks", and clause 4 is really 4a/4b, so the runner prints 9. Two prediction misses are recorded because the gate was right and the prediction was the hole: A3's needle matched 0× because `git archive HEAD apps/web` emits **CRLF** on this host (213 CRs measured in the plane's `middleware.ts`) — single-line needles had hidden that in the previous battery, so `buildBase()` now LF-normalises every `.ts/.tsx/.mjs/.json/.css` in the base plane — and arms A9/A10 under-predicted check 7, because deleting a page strands the `DISALLOWED` prefix that named it. Registered in `scripts/check.sh` and `.github/workflows/ci.yml` (the web job now runs 7 named gates). The live read (`robots-live.mjs`, **24 green / 0 red**) attributes the fix to the build rather than to a restart: the new server's served `Disallow:` set is exactly the worktree's 24, the older pre-fix server's exactly HEAD's 21, the served difference exactly the file difference (3 prefixes), `Allow` unchanged on both planes, and `Host`/`Sitemap` carry `:8837`, which is the plane's own attestation. All ten paths that `sitemap.ts`'s own `PUBLIC` list advertises still answer 200 for a signed-out reader, each with its own `og:title`. This retired the premise of the row above about preview titles: of the six reachable pages with no `pageMetadata` call, `/club/rules` writes its own `openGraph`, `/tactics/compare` and `/world/search` are `noindex` and absent from the map, and what is left is `/`, `/login`, `/register` — not content pages. The trap that keeps that item open is a *conversion* one: `pageMetadata` sets no `robots` field, so routing one of those pages through it would silently drop a declaration. **The copy itself is now gated (2026-10-20).** `apps/web/scripts/qa-i18n-literals.mjs` walks every `app/**/*.tsx` through the repo's own TypeScript and counts the copy written in English in the source - JSX text, label-ish attributes and label-ish object properties, three shapes, because a JSX-text scan reaches neither of the other two - and the count is a ceiling that may only fall: wiring a page to its catalogue lowers it, and a page that adds copy in English raises it. Measured at the ref it landed: **617 sites over 41 files** (75 `.tsx` parsed, 0 diagnostics). The landing page was the first group, and ten have landed since: the ceiling is now **161** against the **617** the gate was landed with, and the gate read **0 English literal sites** over every `app/**/*.tsx`, with the floor committed at 0 - a new page that writes copy in English fails the build. The metadata gate agrees: **tabs keyed 51 / literal 0, headings keyed 43 / literal 0** - every page's tab and every page's heading is now locale-driven, and the two literal tabs that survived until the end (`/community` and `/club`, whose tabs and headings say two different things in English) are gone with them. The gate counts three shapes - JSX text, label-ish attributes and label-ish object properties - and the arc wired more than it counts: the `KeyValueGrid` row labels are array literals, which no JSX-shaped scan reaches, and they went too. The gate also stopped counting field names - `data_origin: synthetic`, `max_depth`, `identity_retained=`, the example address, the export file name and the product's own name - because a field name is not copy, and each exclusion is named in the file with the reason. Fourteen groups in all, with the namespace each one added: `home` (55), `careerDetail` (96) and `career` (+23), `worldPlayer` (75), `simulationAggregates` (64), `onboarding` (52 - the form's options were module constants in the client bundle, so a Chinese reader chose from English options and read English errors), `worldTeam` (53) and `worldMatch` (58), `graph` (80), `myFootball` (+34) and `worldTraining` (31), `world` (+35), `worldCompetition` (36), `worldNews` (30), `notFound` (4), `simulationAggregates` (+19) and `portfolio` (44), `creator` (23) and `scout` (+30), and the last small ones on the club, knowledge, login, tactics, career, news and 404 pages. **The ceiling of 0 above was wrong when it was measured, and is right now only because the gate changed**: the rule that decided a string was "already translated" asked whether it held *any* character outside ASCII, so every English sentence carrying a middle dot, an em dash or a curly apostrophe was read as Chinese and never counted. A browser found it (the locale sweep), the gate reported **47 English strings over 15 files**, and they are all in the catalogue now — see the row *the copy gate's "0 English literal sites" was an artefact of a rule* below and `docs/I18N_ARC_VERIFICATION.md` §7.

**The components arc is closed too (2026-10-21): the ceiling is zero.** The gate's population is every `.tsx` under `app/` **and** every `.tsx` under `components/` (111 files), and the ceiling that wider scan read was **392**; thirteen groups later it is **0**, with the floor committed at 0. The groups: `CreatorWorkbench` (42 sites, the `creator` namespace), the shared primitives `components/ui.tsx` (the labels every page inherits, the `common` namespace), `ClubTools` (62, the `club` namespace), `AcademyTools` (45, a new `academy` namespace), the scout's `ScoutShortlistPanel` (39), `MatchTools` (30), `NoticeBoardTools` (26), `ScoutTransferPanel` (24), `SessionReportTools` (24), `ScoutReportPanel` (21), the five small ones (`BoardsNew`, `CareerForm`, `CareerTools`, `PhasePlayer`, `PortfolioSection`, 23), and the last four (`ScoutComparePanel` 16, `PortfolioSharePanel` 12, `BoardEditor` 11, `ScoutWorkbench` 11).

**The gate grew a third check while they landed, and it earned its place.** Every key the source asks for is in the catalogue — a key the catalogue does not hold is a **runtime error** in next-intl, not a build error, so the page renders an exception instead of a sentence and nothing says so. It found fourteen keys this arc had introduced (`thGoals`, `thClub`, `thCompetition`, `thPos`, the club tier's eight `*DoorMissing` keys, `notTiedToOneTeam`, `noneNamed`), and hand-checking found two more, one of which (`common.remove`) the creator workbench had been asking for since before the arc. **3361 key calls are checked on every run** — and that number moved twice: the arc's own conversions first, then the **rich-text form**, which the check had been blind to. `t.rich("key")` is the same catalogue read as `t("key")`, and next-intl throws `MISSING_MESSAGE` for a rich key it does not hold exactly as it does for a plain one, so a check that only saw the identifier form stopped counting the moment a sentence needed a tag inside it. The ten rich reads in the tree were invisible to it, and a typo in one of them would have rendered an exception instead of a sentence with nothing to say so.

**The five walks that had not been re-run since the arc were re-run on 2026-10-21, and the arc had broken three things the copy gate cannot see.** A gate that counts English literals cannot see a catalogue key used for the *wrong field*, and the scout's screen had two of them: the wiring gave the shortlist's career field and the transfer panel's career field one `aria-label` between them, so a page-wide selector filled the list's field and the projection's own career stayed empty — the button stayed server-rendered `disabled` and seventeen checks went red. The report's percentile sentence printed its number **twice** (a `.num` span beside a catalogue sentence that already carried the value), and the community walk was still pointing at an address the tier had stopped accepting since §35's pointer promise landed on 2026-10-09. All three are recorded in their own milestone's document, and the fix for the first of them is a **gate that does see it**: **`apps/web/scripts/qa-field-labels.mjs`** reads every page's own component graph and refuses two different components on one page declaring the same constant `aria-label` key — **2/2** today over **111 files, 61 pages, 104 keys, 0 collisions**, and red (exit 1, the collision named) with the defect planted back into a scratch copy of the tree. It is in `scripts/check.sh` and in CI, and the script-inventory census now holds **15** files at **68/68**.

Two kinds of value were technical rather than copy, and the gate names both with the reason: a field's own name printed as itself (`data_origin: synthetic`, `role_fit: null`) and a value that is a product name, an enum or a parameter. The rest was copy, and all of it is in a catalogue now — in three languages, with the count of keys the suite recomputes in `apps/web/messages/README.md`.

**The copy gate grew two shapes and two checks on 2026-10-21, and the claim it makes is now the whole tree.** The ceiling of zero was a statement about **three shapes** — JSX text, a label-ish attribute, a label-ish object property — and the tree held copy in three places those three never looked at.

* **A string literal that reaches the reader from somewhere else.** The scout's compare panel prints `A AHEAD` from a helper, so no JSX text, no label attribute and no label property ever saw it: the gate reported zero while the page was English. The census read **61** such sites — a helper's sentence, a ternary's wording, a note a component builds, a row label in a grid — across twenty-six files, and the gate now counts them with a floor of their own, because the first floor is a statement about those three shapes and this one is a statement about the rest of the source. It fell to **0** the same day: twenty-six files were wired and twenty-eight keys were added in three languages, and — the finding inside the finding — **the catalogue already held most of the labels the pages were writing out by hand** (the scout's twelve promise rows had keys sitting unused), so the work was mostly a page reading a key that was already there.
* **A template is one sentence, not five fragments.** `` `${method} ${path} was refused with ${status}` `` was invisible, because a template's pieces are not string literals. The class held **26** sentences across eighteen files — a JSON-LD description, a meta description, a row's value, a note, an accessible name — and it is **0** now.
* **A key read without the values its message needs prints the placeholders.** This is a *new check*, and it found four pages broken in a way nobody could see: the scout's rules panel printed `{default} by default, {max} at most` in the column that should read "Search limits" and `{count} phrases (articles, fillers and conjunctions in six languages)` in the column that should read "Connectors ignored" (the arc had wired two *labels* to keys that hold a *pattern*); the scout's candidate table printed `headroom {value}` as a column header; and the club tier printed a literal `{rule}` where the API's own sentence should have been. The check reads ICU the way next-intl reads it — `{name}` is a placeholder, and `{name, plural, one {…} other {…}}` is a placeholder whose branches are the words the reader sees — so a catalogue full of plurals does not read as a catalogue full of missing values.
* **A lone English word between two tags is copy.** The heuristic read a single lowercase word as a value, which is how "at", "overall", "every {n} weeks" and "score {n}" stayed English in a Chinese page. The *shape* can tell what the word cannot: in JSX text, a lone lowercase word is copy unless the gate's own unit list names it ("min", "ms", "yrs", "x", "v", "sha", "xp") or a colon after it says it is a field name printed as itself. The class was **32** words — eighteen units and field names, **fourteen** real words and labels — and all fourteen are in the catalogues now.

The exclusions are **structural** rather than a list of words — an import specifier, a naming attribute, a `data-` hook, a class name (in an expression, in a template, or held in a variable), a style value, a comparison operand, a schema.org type, field or vocabulary value, a snake_case property, a language tag, a colour, a measurement, a byte unit, a path, a query parameter, a cookie, a date or time format, a field name, an SVG reference, a locale's own name, the framework's own directive, a CSS custom property, and a marker that matches the tier's own wording — so a new class name or a new API field does not have to be added to an allowlist to keep the gate quiet.

The gate is **5 checks** now, every floor is at 0, the key check holds **3479 key calls** for existence *and* for their values, and the catalogues hold **3636 keys** each (3554 translated in Simplified Chinese, 3555 in Traditional; 82 are identical in every catalogue because they are technical tokens).

**Two more gates came out of the same arc, because it found what it could not see.** `apps/web/scripts/qa-field-labels.mjs` reads every page's own component graph and refuses two different components on one page declaring the same constant `aria-label` key — the collision the scout's walk found, held shut for good (**2/2** over 111 files, 61 pages, 104 keys, 0 collisions; the defect planted back into a scratch copy turns it red and names it). And `apps/web/scripts/qa-proxy-gate.mjs` holds the one sentence the web tier's session design rests on — the access token is httpOnly, so a browser may not hold it, and every call it makes has to reach the API through the cookie proxy (**6/6** over 131 files; a planted direct call is named and refused), and since 2026-10-23 the same gate compiles and calls the proxy's trace-context helper — a valid `traceparent`/`tracestate` crosses unchanged, nine invalid shapes are dropped and no id is minted — and reads the route's AST to hold all three seams that carry it to the API, with 8/8 arm planes matched and a live proxy→API walk whose span carries the caller's trace id and parent.

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

**Done 2026-09-23, in `1494219` ("M4 §13: the 3D pitch, as a projection of the board's own metres") — and
this item had not been marked, which is why it is written down here now.** The third view is on
`/tactics/{slug}` beside the 2D board: the same eleven, projected from the same `x_metres`/`y_metres` through
a **stated isometric transform** — `screen_x = ((x + 34) − (105 − y)) × cos30 + 105 × cos30`,
`screen_y = ((x + 34) + (105 − y)) × sin30` — and drawn as SVG, with the formula printed beside the view and
the constants riding on the `<svg>` as `data-iso-constants`, so a reader (and the walk) can recompute any
point from its own metres rather than trusting the drawing.

**The claim that holds, and how it is checked.** A point at a known metre coordinate lands at the projected
pixel the printed formula gives for it. `apps/web/scripts/visual-qa.mjs` reads every marker's
`data-iso-x`/`data-iso-y` out of the DOM, recomputes the projection **in the browser** from the constants
the `<svg>` publishes and each marker's own `data-metres-x`/`data-metres-y`, and refuses a drift over
0.02 — so a drawing that drifted as a whole cannot pass by agreeing with itself. Two more checks hold it: the
3D board shows the same eleven, in the same order, as the API's own `phase_in`; and the four projected
corners fit the viewBox, which is invisible when it is wrong (a clipped far touchline still renders, still
looks like a pitch, and silently loses the bottom of it — the first draft of this view had exactly that bug).

**One difference from this item's wording, named.** It asked for a *toggle*; the view is a `<details>`
element, because the 3D view is a second way of reading numbers that are already on the page and so needs no
client state to open, and it stays in the document for a reader who has no JavaScript. The claim the toggle
was to protect — that the 3D view cannot become a second source of truth — holds by construction: it projects
the same metres and stores none.

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

## Item 14 — M10: the scouting list, §36's sixth kind of content

**Done 2026-10-21.** Item 13 gave the fourth kind an object. The sixth kind — a **Scouting List** — was still only a
section, and the tier could anchor one row but not a selection of many.

**Do.** Store a selection of world footballers as addresses, with the author's note on each.

1. **`creator_scouting_lists` + `creator_scouting_entries`** (migration `0034`): the list holds author, slug, title,
   summary, visibility, date and provenance; each entry holds the list, its position, the **address** of a player, the
   hash witness and the author's own note. Both column lists are asserted as sets: no name, position, overall or club.
   `player_slug` is a plain pointer for the same reason the analyses' anchors are (`services/world/sync.py` retires
   generated rows); publication resolves every address (slug or id) and refuses an unknown one (404
   `no_such_scouted_player`). Two selections naming one footballer are refused (422 `scouting_duplicate_player`), as
   are the size bounds 1–50 (`scouting_players`).
2. **The witness is per entry.** Each entry compares its stored `player_hash` with its own player's `content_hash` on
   every read, so one refreshed footballer says `moved` on their line while the rest stand still. A retired player
   leaves a **bare address** (`retired: true`, brief fields null) and the list stays readable — deliberately not the
   single-anchor absence an analysis uses, because a list is a selection of many.
3. **The proof is behavioural.** Two scratch players are published, then one is edited between two reads: that entry
   follows its own row, flips `moved`, and the figures read `players=2, moved=1, retired=0`; a separate case retires a
   player and reads `retired=1` with the list intact. Erasing a list takes its entries (FK cascade) and touches no
   player row.
4. **Four doors** under the tier's prefix: publish, shelf, one list, erase. Reach is §35's follow predicate; an
   unlisted list is readable at its address and in no listing; another account's list is absence; no door answers 403.
   Ceiling: 40 lists per creator (409 `scouting_list_limit`).

**Evidence.** `tests/test_creator_scouting.py` (17 cases); the six creator files together answer **131 tests / 0
failures / 0 errors / 0 skipped in 58.799s** (junit `.scratch/leg_creator6.xml`). mypy is clean over 153 files; ruff is
clean on the six touched Python files; the contract is regenerated at 199 paths / 258 operations; migration `0034`
upgrades to head, passes `alembic check` silently and round-trips on a scratch SQLite database. Two defects the first
run found: the entries were inserted before their parent list (a plain FK and no ORM relationship, so an explicit
`session.flush()` now fixes the order), and `ROUTE_GUIDE` said `{list}` where the router names `{list_id}`, caught by
the project-wide guide census. The record now says five kinds have objects of their own; Career Challenge is the
remaining one.

---

## Item 15 — M10: the career challenge, §36's fifth kind of content

**Done 2026-10-22.** Item 14 gave the sixth kind an object, and its record said five kinds had objects of their own —
Career Challenge was the remaining one. §36's fifth kind is a **rule** an author publishes and another account enters
with a career of its own.

**Do.** Store the author's rule and the entrant's address, and judge the run on the read.

1. **`creator_career_challenges` + `creator_career_attempts`** (migration `0035`): the challenge holds the author's
   title and summary, a visibility and the rule — `objective_kind` over the career tier's own `OBJECTIVE_KINDS`,
   a target and a `window_rounds`. An attempt holds the entrant, the challenge, the entrant's own `career_slug` and
   the `start_round` the window opens at. Both column lists are asserted as sets: no win, point, goal or verdict.
   `career_slug` is a plain pointer, not a foreign key, so an entrant may erase their career without an attempt
   blocking it.
2. **The verdict is summed on the read.** `_attempt_view` slices the career's `career_fixtures` to
   `start_round < round_index <= start_round + window_rounds`, hands them to the career tier's own `record_of`, and
   reads `wins` / `points` / `goal_difference` / `unbeaten` off that record. The target earns only when the window
   closes, exactly as M6's scenarios judge a run; a career retired mid-run reads `career_retired`, and a career erased
   since entry leaves a bare address (`career_missing`, brief fields null, nothing summed into a zero).
3. **The proof is behavioural.** A career enters with two wins behind it and they do not count; one in-window fixture
   is flipped from W to L between two reads and `actual` moves 6 → 3 while the career's stored totals do not move.
   Entering an inactive or exhausted career is refused (409 `career_challenge_inactive`), a second entry is refused
   with the first run's figures (409 `career_challenge_entered`), and erasing a challenge takes its attempts and
   touches no career row.
4. **Six doors** under the tier's prefix: publish, shelf (joined to the viewer's own `entered` flag), one challenge,
   erase, enter and withdraw. Reach is §35's follow predicate; a stranger reading a public challenge sees the attempt
   count but `attempt: null` and no career slug; an unlisted challenge is readable at its address and in no listing;
   another account's challenge is absence; no door answers 403. Ceiling: 30 challenges per creator
   (409 `career_challenge_limit`), target 1–99, window 1–38 rounds.

**Evidence.** `tests/test_creator_challenges.py` (20 cases); the seven creator files together answer **157 tests / 0
failures / 0 errors / 0 skipped in 121.069s** (junit `.scratch/leg_challenges_creator.xml`). mypy is clean over 154
files; ruff is clean on the six touched Python files; the contract is regenerated at 202 paths / 264 operations;
migration `0035` upgrades to head, passes `alembic check` silently and round-trips on a scratch SQLite database. The
record now says all six kinds have objects of their own.

---

## Item 16 — M10: the career challenge on `/creator`, and the walk that presses it

**Done 2026-10-22.** Item 15 gave §36's fifth kind its objects and six doors; the page did not know the noun existed.
This item wires the fifth writing panel and extends the tier's production walk to press it.

**Do.** Read the challenge vocabulary the rules door already publishes, and make every press verifiable through the
door.

1. **The vocabulary panel reads what the door publishes.** `lib/creator.ts` types
   `career_challenge_caps` (eight caps), `career_challenge_objective_kinds` (kind → formula),
   `career_challenge_counts` and `career_challenge_rule`; `/creator` prints them as four rows beside the other
   published vocabulary, so no ceiling, kind, count or sentence is typed into the page.
2. **A publish form, a shelf and a run panel.** The challenge panel publishes title, summary, objective, target,
   window and visibility through `POST /creator/challenges`; the shelf is the account's own listing with the
   viewer's `entered` flag and Open/Erase; opening a row re-reads `GET /creator/challenges/{id}`, and the detail
   panel paints the rule's formula, this account's careers (`GET /careers`), and — once entered — the status,
   actual vs target, the career address, the window line, the door's reason and the per-fixture table the sum
   used, or the no-run marker. Enter and withdraw each hold their own runner, so an answer lands beside its press;
   erase asks first, as the program and guide rows do.
3. **The panel is translated.** 48 `creator` keys per catalogue for the challenge surface (the namespace goes
   **99 → 148** together with the open guide's eyebrow, which this commit moves out of an inline literal): form
   labels and placeholders, table headers, the five statuses, the detail sentences, the erase confirmation and the
   vocabulary rows. English uses ICU plurals; both Chinese catalogues keep plain forms.
4. **The walk presses it.** The two vocabulary readers and 23 challenge checks take `qa-creator.mjs` from 72 to
   **97 checks**.

**Evidence.** `node scripts/qa-creator.mjs` against a production build (`NEXT_DIST_DIR=.next-ci npm run build`,
BUILD_ID `G3GPpkpU_Mv57zF3c0X6e` on `127.0.0.1:3218`) and the API on `127.0.0.1:8741` over
`.scratch/m10-challenge-walk.db` migrated to `0035`: **97/97 checks, exit 0**. The walk read back, through the door,
the published `unbeaten 3` / window 2 rule, the 0-target refusal (`422 career_challenge_target`, "a target is
between 1 and 99"), the entry (`in_progress`, 0 played, 2 remaining, actual 0, start round 0), the stranger's
`attempt: null` beside one attempt, the second entry (`409 career_challenge_entered`), the withdrawal and re-entry,
and the erase (`404 no_such_career_challenge`) with the career that played it still answering 200; 46 knocks were
made, none answered 400 or 403, and no console line left behind is a 5xx or a page exception.
`qa-i18n-literals.mjs` **8/8** over 3593 key calls; `qa-field-labels.mjs` **2/2**. The measured figures and the
screenshots are recorded in `docs/M10_CREATOR_VERIFICATION.md` ("The career challenge on the page").

## Item 17 — spec module 27: the notification tier, its producers, and the tray on the page

**The gap.** The spec's 28 modules list carried "27 Notifications" with nothing in the tree — no model, no door,
no page, no mention. The community's three verbs (follow, comment, reaction) were events that happened silently:
the follow landed, the comment landed, and the only way to learn of them was to re-read the wall.

**The shape.** `notifications` (migration `0041`): one row per event, written when the event happens — recipient,
kind (`follower`/`comment`/`reaction`), a payload of addresses (post id, actor display name, an 80-char excerpt),
and `read_at`, whose null/not-null is the entire read-state machinery. Producers are wired inside the three
community verbs themselves: a first follow notifies the followed, a first reaction and a comment notify the post's
author — and `actor == recipient` writes nothing, because an account's own act is not news to it. Four doors under
`/api/v1/notifications` (list with page arithmetic and `unread_total` beside it, `unread-total` for the nav badge,
`read-all`, `/{id}/read`), every one private, another account's row answering 404 — the same absence every private
tier gives a caller probing for ids. The tray caps at 200 rows, and the overflow policy is written in the service:
the oldest **read** row makes room; a tray with no read rows drops the new event, because a tray that grows without
bound is a leak wearing a feature's clothes.

**The page.** `/notifications` — session-gated, in the middleware's protected prefixes and robots' disallowed list
(a tray is the account's own correspondence), the crawl-policy gate reconciling it at 9/9. Each row names its kind
in the reader's language and carries the sentence the payload supports ("{name} now follows you", "{name} commented:
…"), a Mark read button per unread row and Mark all read above, and the tier's own formula printed under the panel.
The nav gains a Notifications link with the unread count as a badge, fetched once per mount, quiet at zero.

**Final record (2026-11-07): the walk reads 312/316** — the Live section's four checks green in a full walk
(index lists the played match; the replay names itself and prints its source sentence; the clock ticked to minute
14 with the feed holding exactly that match's events-so-far, 0 goals, score 0–0 — correct for a match whose goals
arrive later; the score-sum check holds against the feed's own GOAL rows), the notification section green, the
erasure green on the re-keyed bucket, and the 1,779-URL probe survived end to end. The four reds are unchanged
across two runs and all belong to another lane: three career/season checks (the season-boundary commit is the
suspect) and the sweep's coverage gate (the ordering finding recorded below).

**Walk runs against the fixed tree, each finding named**: run with the client-fetch buttons and the favicon
exemption landed **296/301** — the notification section fully green for the first time in a full walk (tray, badge,
mark-all, stranger verbs through the API), the erasure green on the re-keyed bucket, and the five reds: four in the
career/season checks (the fixture table, the record arithmetic, the fresh-season zero — the same season-boundary
commit their lane landed this week is the suspect; the fixture table and the record disagree on which rounds count)
and one harness bug this lane fixed: the sign-out sweep had been written to call the walk's own navigator from
inside page.evaluate ("page is not defined"), and the opens are hoisted to Node now.

**The targeted verification that settled the section** (after four full-walk attempts died on host contention —
the sitemap probe's 1715 SSR renders, up from 1039 before M13, saturate the web tier on this shared host): a
puppeteer run against the production build registers an author through the proxy and a stranger against the API
(the two shapes this tier actually has), follows the author's member id read from `/auth/me` — the walk's meId fix
proven live — reacts and comments, and reads the tray in the browser: `tray total: 3, unread: 3`, kinds
`comment,follower,reaction`, every payload naming the stranger, **the nav badge rendering 3**, and Mark all read
clearing the badge. The full walk's 15b section now carries these same assertions for every future run.

**Run 3 exposed a real limiter defect the suite could not see.** The erasure check answered 429 for an account
that had never erased anything: `account_delete`'s bucket was keyed by client address alone, and the Nth
verification walk of the day had spent the address's three-an-hour budget. The door already requires a valid
session, so the per-address bound added nothing the register and login limiters don't already provide — the bucket
now keys on the account, keeping one hijacked session bounded at three an hour, and `tests/test_rate_limiter.py`
drives the two-accounts-behind-one-address case directly. **Also named for another lane**: the career-challenge
verdict check read `Pts 8 / Points 0 / record 0-0-0` against a career whose fixtures played — landed the same day
as "a career's season boundary decides its league", so the boundary change is the first suspect; the fixture table
and the record disagree on which rounds count.

**The walk's first two runs failed on the host, not the tier, and the failures are the record.** Run 1: the API
process died mid-walk (connection refused during the erasure probe), so every check after it starved. Run 2: the
port had changed hands — a second uvicorn bound 8731 while the first still held it, the stranger's register met the
restart window, and its token was `undefined`, so all three stranger verbs answered 401 and the tray stayed empty.
Both runs' other 285 checks passed. **Evidence.** `tests/test_notifications.py` (8 cases): an empty tray answers zeroes; another account's
notification and read-marking are 404; the badge arithmetic moves 3 → 2 → 0 through one- and all-marking, marking
twice staying the same state; the tray pages newest-first with page arithmetic; and the three producers fire — the
followed account hears (`follower_name` in the payload), the author hears with the actor's display name and the
comment excerpt, the actor hears nothing, and an author's own reaction writes no row. ruff and mypy (157 files)
clean; the metadata gate at 168/168 and the crawl gate at 9/9 with the new prefix; tsc green. The walk section
(15b) publishes its own post, acts as a stranger through the API, and reads in the browser.

## The challenge record after its window closes (fixed 2026-10-31)

The defect filed above is fixed. `season_bounds` advanced a challenge career into a second season the moment
`close_season` wrote the window's boundary row — `play_round` refuses past the window, so no round could ever fill
that span, and every season read (record, table, objectives, board) summed zero rows while the fixture list still
showed the played rounds. A challenge career now has exactly one season, its window: `season_bounds` returns rounds
1…window whatever boundary rows exist, `close_season` returns the one row rather than deciding again, and the view
reads `Points 11 = Pts column 11, record 3-2-1` after a six-round `win-with-academy-players` run on a fresh
alembic-built SQLite (`.scratch/walk-challenge-record.py` → `.scratch/challenge-walk.json`). The same read also
refuses to offer a next fixture once the window is closed (`available: false`, "this run's window closed at round
6; no further round exists"), so the run page cannot print a "next up" round the disabled button could never play.
Pinned by
`tests/test_career.py::TestSeasons::test_a_closed_challenge_window_still_sums_its_own_rounds`, which reads
`(2, 3, 2, 4)` for the span on the old code and `(1, 1, 2, 2)` on the fixed one.

## The board pays a season (M13 Phase 7 item 24, done 2026-11-02)

A career's budget had one door in and two doors out. `career.budget` was written when the career opened, and
after that only a sale brought money back: fees left on `buy`/`loan`, a wage charge left every round played.
Items 8 and 9 made a career cross its season boundary and start another, so the shrink stopped being
theoretical — season two began with less than season one and a long career walked toward a market it could no
longer enter. `career_budget_awards` (migration `0047`) is the third ledger table and the first whose money
arrives: `season_grant` is 8,000 per round played, 2,500 per point earned and 150,000 when that season's verdict
is `promoted`, with the challenge exemption stated once inside that function so the boundary that pays and the
page that projects cannot disagree about it. `close_season` pays in its own transaction, so a verdict and its
money appear together or not at all, and `uq_career_award_season` is what makes "one grant per season" a schema
fact rather than a hope. It is published wherever the balance is read — position, timeline (rank 2 in its round,
after the move and the wage), the market ledger as a row of its own, affordability, and `seasons_view` with both
the closed season's grant and a `grant_if_closed_now` projection that writes nothing — and rendered in
`CareerSeasons` beside the verdict, in the finance timeline and in the market ledger. The live walk says what it
did rather than what the rule says: two generated worlds, both exit 0, 14 rounds and 14 points paying 147,000 and
14 rounds and 16 points paying 152,000, and in both the same 90,110 loan refused from 0 before the boundary is
signed from the grant alone afterwards, ending with `['season_grant', 'loan', 'wage']` and 0 disagreements. The
honest economic figure, measured on the same board: the cheapest listing costs 668,250 outright and 100,238 on
loan, so a season's grant keeps a career in the market and does not buy it a first-class player. Evidence:
[M13_SEASON_GRANT_VERIFICATION.md](docs/M13_SEASON_GRANT_VERIFICATION.md).
Landing: those bytes reached master inside the concurrent batch's commit `c5d0979`, which committed the shared index while this item's sixteen paths were staged in it, so the subject names that lane's catalogue table; the record's section 9 carries the pre-move grading of the staged tree and the suite verdict on the commit after it.

## The deal book starts to expire (M13 Phase 7 item 25, done 2026-11-02)

Item 6 left the expiry a projection on purpose and said so: `contract_years` was stored, `contract_book`
derived a date, and no round enforced it. A signed player stayed in the eleven forever and the wage bill
never shrank, so the season grant item 24 had just added could only be spent on a squad that could never
lose anyone.

`0049_career_contract_expiry` adds `career_squad_moves.expiry_round`, fixed when the deal is signed as
`signed_round + contract_years × the season length then in force − 1`. Storing it is the point: a later
promotion changes future season lengths, and a contract already agreed must not stretch with it. A row
written before the migration holds 0 and keeps the old projection until it is re-signed; the contract book
names that basis rather than inventing a date.

`expire_contracts()` runs at the top of `play_round`, after the next fixture is planned and before
`squad_as_of` composes the eleven. A permanent deal past its stored last round gets an `expire` row at that
round: the overlay drops the player and `held_deals` stops charging the wage. The row carries fee 0 and the
standing `budget_after`, so a contract ending moves no money and the ledger still adds up. The one authored
exception is fieldability: if the departure would leave fewer than eleven players or no keeper, a `renew`
row extends the deal by one season at the same wage and the result publishes the counts that decided it.

The reader sees it in `career_view["contracts"]["recent"]` and in `components/CareerContracts.tsx` on
`/career/{slug}`: player, outcome, effective round, expiry and wage. The held-deal column now says "Expiry
round" rather than "Projected expiry round". The market ledger prints both new kinds as ordinary zero-fee
rows, with no new panel.

**Measured.** 62 transfer-service tests and 88 career+wire tests passed on SQLite; `alembic check` clean
after `0048 → 0049`; ruff, mypy over 161 files, tsc and the four i18n/wire gates green. The live walk
`.scratch/walk-contract-expiry.py`, against a fresh alembic-built SQLite database, signed a player with a
5-year deal, read stored expiry 70, played round 71, and measured the `expire` row at 71 with fee 0, the
player gone, the balance unchanged at 7,675,000, `deals_after 0`, `recent_kind expire` and `wage_after 0`.

**Open.** No production-build browser pass yet; no manager-chosen renewal at expiry; no fee or compensation
when a player leaves; pre-`0049` rows keep the projection until re-signed. Evidence:
[M13_CONTRACT_EXPIRY_VERIFICATION.md](docs/M13_CONTRACT_EXPIRY_VERIFICATION.md).

## Manager-chosen renewals (M13 Phase 7 item 26, done 2026-11-02)

Item 25 made a contract date real; this item gives the manager a way to move it. A renewal is not a
transfer, so it does not wait for a signing window, and it is refused only by arithmetic: the fee
against the balance, or the bill after replacing the old wage against the board's ceiling. The quoted
fee is 5% of the player's current asking fee (rounded to 5); the new wage is the player's current
valuation; the new stored expiry is `signing round + years × season_rounds − 1`.

**What a reader sees.** `contracts.rows[].renewal` is the contract book's own quote — years, new
wage, fee, the balance after the fee, the bill after the renewal, the ceiling, both affordability
flags, `can_renew` and the formula. `components/ContractRenewal.tsx` prints that quote in the deal
book's new Renewal column, states why a blocked quote is blocked, and posts
`/transfers/{slug}/renew` with `{ player, years }`. The page is refreshed afterwards, so the expiry
column, the recent-endings table and the ledger all show the stored result. `move_row` now carries
`expiry_round`, so a renewal row and the deal book cannot disagree.

**Refusals name their numbers.** `loan_cannot_be_renewed` (a loan's last round belongs to the other
club), `no_contract_to_renew` (a squad player with no stored deal), `insufficient_budget` (`fee`,
`remaining`) and `wage_ceiling_exceeded` (`wage_bill_before`, `proposed_weekly_wage`,
`wage_bill_after`, `wage_ceiling`, `headroom`).

**Measured.** 66 transfer-service tests and 89 transfer tests over both files passed; ruff, mypy
(161 files), tsc, ESLint and the four i18n/wire gates green. The live walk
`.scratch/walk-contract-renewal.py`, against a fresh alembic-built SQLite database, signed a player
whose stored expiry was 14, renewed him for two seasons against the book's 30,040 quote, and read the
stored expiry back as 28 — balance 9,098,875 → 9,068,835, `recent_kind renew`, and the round's wage
charge at the renewed 1,200.

**Open.** No production-build browser pass yet; the fee does not scale with term; the player cannot
refuse; no signing bonus; pre-`0049` rows project until renewed. Evidence:
[M13_CONTRACT_RENEWAL_VERIFICATION.md](docs/M13_CONTRACT_RENEWAL_VERIFICATION.md).

## A home round pays its gate (M13 Phase 7 item 27, done 2026-11-02)

The ledger had one recurring income, the board's season grant, while a career paid wages out of savings
and a home fixture earned nothing. This item makes the ground pay: one `career_gate_receipts` row per
home round, unique on `(career_id, round_index)`, carrying the attendance, the authored ticket price,
the amount, the basis in words and the running `budget_after`.

**The arithmetic.** `gate = attendance × ticket_price`; price is 3 for a tier-1 league and 2 for tier 2
or a cup. Attendance is the world fixture's stored figure; a round on the career's own rotation sells
`capacity × (62 + seed mod 38)%` — the same band the world builder uses. An away round writes no row,
and a ground with no capacity writes no zero row. A challenge window pays no gate: its budget is an
authored constraint, and a gate would silently raise the figure the scenario stated.

**The order.** The receipt is written after the fixture is stored and before the wage charge, so the
wage row's stored balance includes the gate. The timeline reads moves → gate → wage → boundary grant,
and `budget_timeline` ranks the gate there. `BUDGET_FORMULA` names the fourth table; `received` is now
every cent in, split into `received_sales` and `received_gate`.

**What a reader sees.** The market ledger prints a `gate` row with its attendance, price, amount and
basis; `totals.gate_rows` counts it; `CareerFinance.tsx` prints "Gate receipts so far" when it is
non-zero; the contract column prints an em-dash for a gate, not "0 years". The four constants are
published in the market view.

**Measured.** 5 new service cases and 1 new wire case; 164 career+transfer tests and 9 affordability
tests passed; `alembic check` clean after `0049 → 0050`; the OpenAPI contract regenerated for the new
routes; ruff, mypy (161), tsc, ESLint, the four i18n/wire gates green. The live walk played a home round
at a 48,184-seat ground — 38,725 seats × 2 = 77,450 — and the following away round wrote nothing; the
balance moved 1,000,000 → 1,077,450 with one `gate` timeline entry and 0 disagreements.

**Open.** No production-build browser pass yet; away clubs earn nothing; no cup prize or broadcast
money; capacity never grows and attendance does not react to form. Evidence:
[M13_GATE_RECEIPTS_VERIFICATION.md](docs/M13_GATE_RECEIPTS_VERIFICATION.md).

## A career clock that ages and retires (M13 Phase 8 item 28, done 2026-11-03)

The contract book's age profile said in words that nothing aged a player or retired one, so a long
career carried the same squad forever. This item gives the career its own clock without touching the
world's shared `real_players.age`: a player's effective age is the stored age plus the seasons this
career has closed, and `close_season` retires a player at 40.

**The boundary.** `close_season` writes its `CareerSeason` row, then calls
`retire_at_boundary(..., round_index=last_round + 1, closed=season_index)`. The `retire` move binds
from the next season's first round: the player played the season that just closed, and the squad
overlay drops him when the next eleven is picked. The row stores `fee = 0` and the wage it was paying,
so the ledger neither charges a fee nor a wage after it. Candidates are walked oldest first; one is
retained when retiring him would leave fewer than eleven players or no keeper, and the boundary result
names the retained player and the count that refused. A challenge career has no boundary after its
window, so it retires nobody.

**One age, everywhere.** `valuation`, `open_market`'s listing rows, `buy`, `loan`, `sell`, `release`,
`renew`, `_record_move`'s stored terms and `contract_book`'s profile all read the same offset. The
age profile now prints 40 as the retirement age (the age that ends a career) while keeping the 35+
list as the warning flag.

**Measured.** 4 new cases in `test_ageing.py`; 165 career+transfer tests passed; `alembic check` clean
(no column — `retire` is a `career_squad_moves.kind` value); ruff, mypy (162), tsc, ESLint and the four
i18n/wire gates green. The live walk closed a 14-round season: the forced 39-year-old became 40, the
`retire` row landed at round **15**, the squad fell to **15**, the wage bill moved **3,100 → 0**, and
`recent` read `retire / Corand Ruceek`. Evidence:
[M13_AGEING_VERIFICATION.md](docs/M13_AGEING_VERIFICATION.md).

**Open.** No production-build browser pass yet; 40 is the only rule (contract, role and wage are not
weighed).

## A boundary youth intake (M13 Phase 8 item 29, done 2026-11-03)

The retirement half left the squad shrinking. This item promotes young world players at the same
boundary, from the world's existing rows and by the academy's own judgment.

**The rule.** Candidates are world players at or under 21 on the career clock, outside the current
squad. `academy.judge_candidates` appends them to the squad and runs the same `academy_class` the
academy page uses, against the same eleven and seats; only `selected` or `next_in_line` candidates are
signed, preferring the band a retiree vacated. At most one per retiree, capped at four. The row is
`kind = "youth"`, fee 0, with the valuation's wage and years and a stored expiry; `IN_KINDS`,
`expire_contracts`, the contract book's renewal quote and `renew()` all treat it as a permanent deal.
A wage that would cross the board's ceiling is skipped and named. A challenge career and a boundary
with no retirement sign nobody.

**Measured.** 2 new cases in `test_ageing.py` (6 total); **176** career+transfer+academy tests passed;
`alembic check` unaffected; ruff, mypy (163), tsc, ESLint and the four i18n/wire gates green. The live
walk retired a **3,100**-a-week player and promoted **Noa Veitmann**, age **20**, on a **5-year**,
**1,730** deal with expiry **84**; the squad went 15 → 16 and the bill ended at exactly **1,730**.
Evidence: [M13_YOUTH_INTAKE_VERIFICATION.md](docs/M13_YOUTH_INTAKE_VERIFICATION.md).

**Open.** No production-build browser pass yet; the intake is sized by retirements, not a squad target;
the pool is the world's young players, so two careers can promote the same player.

## A window measured against stored fixtures (M13 Phase 8 item 30, done 2026-11-03)

The signing window trusted `career.rounds_played`. A fixture stored ahead of that counter — an imported
or repaired career — let a move book into a round that was already decided. The stored rows are now the
fact the window reads.

**The rule.** `transferable` refuses a move whose round (`rounds_played + 1`) already has a
`career_fixtures` row: `round_already_played`, `constraint = "stored_fixture"`, with the round and the
latest stored round. Every move and `open_market` answer through the same verdict.
`transfer_window` counts stored rows in the current window's lifetime range; `played_in_window` is the
larger of that and the counter's own count, and `signing_rounds_left` subtracts stored rounds at or after
the next one. The career view passes the fixture list it already fetched, so the page still reads
`career_fixtures` once.

**Measured.** 2 new cases in `TestTransferWindow` (**11** in the class); **173** career+transfer tests
passed; the read-efficiency and query-count tests unchanged; ruff, mypy (163), tsc, ESLint and the four
i18n/wire gates green. The live walk played round 1, rewound the counter to 0, and read
`round_already_played` with window **1/3**; restoring the counter made the career transferable again.
Evidence: [M13_WINDOW_STORED_FIXTURE_VERIFICATION.md](docs/M13_WINDOW_STORED_FIXTURE_VERIFICATION.md).

**Open.** `play_round` still does not refuse a fixture that already exists at its planned round; the
check covers the next round only; no production-build browser pass.

## Renewals that negotiate (M13 Phase 8 item 31, done 2026-11-03)

Item 26's renewal was a price list: a flat 5% fee and the valuation wage, accepted every time. This
item makes the term cost what it is worth and lets the player refuse a low offer.

**The rule.** `fee_per_year = round_5(asking × 5%)` and `fee = fee_per_year × years`. The demand is
`round_5(valuation wage × tier_factor × minutes_factor)`, with tier factors **1.15 / 1.00 / 0.90** for
tier 1 / tier 2 / cup and `minutes_factor = 0.90 + 0.20 × (appearance minutes ÷ (rounds_played × 90),
clamped 0–1)`. `POST /renew` takes an optional `wage`: at or above the demand it is accepted at the
offer, below it answers `409 renewal_refused` with `demanded_wage` and `offered_wage`. Omitting `wage`
pays the demand, so the one-click path survives. The quote publishes the demand, per-year fee, share
and both factors; the UI adds a weekly wage input.

**Measured.** 2 new service cases and 1 new wire case (10 renewal cases across both files); **176**
career+transfer tests passed; OpenAPI regenerated for `wage` and 4/4 currency tests passed; ruff, mypy
(163), tsc, ESLint and the four i18n/wire gates green. The live walk read **64,575** for one year and
**193,725** for three, refused **2,320** against a **2,325** demand, then accepted two years for
**129,150** with expiry **28**. Evidence:
[M13_RENEWAL_NEGOTIATION_VERIFICATION.md](docs/M13_RENEWAL_NEGOTIATION_VERIFICATION.md).

**Open.** The demand reads career appearances only; tier factors are authored bands; a refusal is not
remembered and there is no multi-round bargaining; no production-build browser pass yet.

## A ground that responds to tier and form (M13 Phase 8 item 33, done 2026-11-03)

Item 27 made a home round pay, but it read two constants a career could never change. A promoted club
sold the same seats, and a five-match winning run sold exactly what five losses sold. This item makes the
gate a consequence of the career — without letting one manager's promotion rewrite a stadium two careers
share.

**The rule.** `gate_capacity(club, tier)` returns an *effective* capacity and the factor it applied:
the stored row x **1.25** in tier 1, **x1.10** in tier 2, x1.00 otherwise. `teams.capacity` is never
written. `gate_form` reads the career's own last five results before the round (W = 1, D = 0.5, L = 0,
newest first; no history reads 0.5 rather than an empty ground), and the gate sells
`min(effective_capacity, base x (0.90 + 0.20 x form))`, where `base` is the world fixture's stored
attendance or, on the career's own rotation, the effective capacity x a seeded 62–99% share. The
receipt's `basis` names both factors and the window, and `GATE_FORMULA` publishes every constant.

**Measured.** 2 new cases in `TestGateReceipts` (**7** in the class); **187** career+transfer tests
passed; ruff, mypy (163), tsc, ESLint and the four i18n/wire gates green; no migration. The live walk
played the same fixture and the same seed twice: five wins sold **46,641** seats for **93,282** credits,
five losses **38,161** for **76,322**, and each basis printed `form 1.00 / 0.00` and
`tier 2 capacity x1.10`. Evidence: [M13_GROUND_RESPONSE_VERIFICATION.md](docs/M13_GROUND_RESPONSE_VERIFICATION.md).

**Open.** Capacity grows with the tier factor, not with a stadium a manager buys; no ticket price the
manager sets; no away support; cup ties do not count toward form yet; no production-build browser pass.

## Cup runs and prize money (M13 Phase 8 item 32, done 2026-11-03)

The world has always held a knockout cup per season and a career never touched it: its calendar was the
league's double round-robin. This item makes the cup a run the career plays and a second income beside
the gate and the grant — without a fifth ledger.

**The rule.** A career is *entered* when the world's own `real_matches` for a `kind = "cup"` competition
name its club in that season. It plays the quarter-final it was drawn into; a win puts it in the
semi-final the world drew for that half, with the other club in that row as the opponent and the side the
club it beat occupied; a win there puts it in the world's final, at a neutral venue. The career's own
result *replaces* the slot the world's simulation filled, so a club the world knocked out still has a
route. Each tie runs through `run_simulation` with the career's overlay and a seed from career + season +
cup + stage; a draw is separated on penalties by the match digest. A tie is not a round: `rounds_played`
does not move, and `career_cup_ties.round_index` is the league round it was played after. A round won
pays **40,000 / 90,000 / 220,000** (quarter / semi / final) into `career_budget_awards` as
`kind = "cup_prize"` with `stage = "<cup>:<round>"`, so the one balance arithmetic already sums it;
`uq_career_award_stage` keeps one prize per round and one grant per season. A challenge career enters no
cup, like its grant and its gate.

**Measured.** `tests/test_cup.py` (13 cases) plus `TestCupWire` in `tests/test_career_api.py` (3);
**196** career+transfer+cup tests passed; `alembic check` clean after `0051`; OpenAPI regenerated (4/4);
ruff, mypy (164), tsc, ESLint and the four i18n/wire gates green. The live walk won its quarter-final on
penalties and its semi-final 1-0, lost the final 0-1, and read **130,000** credits in prizes against
**1,000,000 → 1,130,000** with `rounds_played` still **0** and a timeline that added up. Evidence:
[M13_CUP_PRIZE_VERIFICATION.md](docs/M13_CUP_PRIZE_VERIFICATION.md).

**Open.** The world draws no cup for a second season; several cups per club are separate runs; no
production-build browser pass yet.

## Cup tie gate and minutes (M13 Phase 9 item 34, done 2026-11-03)

Item 32 stopped at the score: a tie's ground was a string, its gate was never paid, and the eleven that
played it left no trace, so a cup minute neither tired nor developed a player. Both ledger and trace were
keyed by the league round, and a tie played after round 7 shares round 7.

**The rule.** `career_gate_receipts.tie_id` and `career_appearances.tie_id` are nullable and name the tie;
the league uniques become partial indexes over `tie_id IS NULL`, and each tie has its own unique key. A
home tie pays a gate with the arithmetic item 33 shipped - effective capacity, a seeded 62-99% crowd, the
stored form factor capped at the capacity, times the ticket price - except that the crowd is always built
from capacity (the bracket row a later tie replaces belonged to other clubs) and the form window includes
the round the tie follows. A final, at a neutral venue, pays no gate: it is the competition's. The eleven
is rebuilt and checked against the report exactly as a league round is, then written under the tie, so
`carry_over` (condition) and `development_view` (the curve) sum cup minutes. Cup ledger rows sort at
timeline tier 4, after the round's grant, because they are written after that round; the gate precedes the
prize so the prize's `budget_after` includes it.

**What changed.** `models` (two nullable `tie_id`s, partial uniques), migration `0052`,
`carry_over` (`record_appearances(tie_id=...)`, `appearances_of_tie`, `appearances_of_round` league-only,
`cup_appearances`), `market` (`_gate_terms`, `pay_cup_gate`, `received_gate_cup`, `gate_cup_rows`,
`_ledger_tier`, cup `gate` rows in the ledger and timeline), `cup` (`_trace_tie`, `gate` on each tie,
`gates` per run and in `totals`), the cup panel's gate column and total, and four keys in three locales.

**Evidence.** `docs/M13_CUP_TIE_GATE_VERIFICATION.md`: 16 cup cases plus 163 across cup/career/transfers;
walk on Postgres at `0052` - quarter-final at home lost 0-1, 64,624 seats x 2 = **129,248** (form 1.00 over
1 round x 1.10, capped at the effective capacity), 11 league + 11 cup traces at 90 minutes,
`rounds_traced` 1 with `cup_appearances` 11, balance 1,115,030 -> 1,244,278 by exactly the tie's money,
timeline `["gate", "cup_gate"]` with 0 disagreements.

## The world draws next season's cup (M13 Phase 9 item 35, done 2026-11-05)

A career's second season had no cup: the world drew only next season's opening league round, so
`cup_view` answered `no cup bracket`. The fix is not "draw a full bracket" - a knockout cannot be drawn
past the round whose participants exist - but "draw what is knowable, resolve the rest when a route needs
it".

**The rule.** `world/builder.py` stores every cup's four next-season quarter-finals (eight entrants,
dated, `scheduled`, no score). `cup.py::_slot` resolves a stage the world has not drawn: the semi-final's
opponent is the engine's winner of the adjacent quarter-final, and the final's opponent the winner of the
other half's route; each is played by `simulate_match` over the two clubs' stored profiles with a seed
derived from the row or the cup and stage, so it is reproducible and writes no `sim_matches` row. The
first quarter-final of a half hosts the semi-final and the higher half is nominal home in the final, at a
neutral venue. `career_cup_ties.basis` widens to 512 (migration `0053`); `scheduled_matches` becomes
`leagues x 2 + cups x 4`.

**Evidence.** `docs/M13_NEXT_SEASON_CUP_VERIFICATION.md`: 19 cup cases, 59 world cases (one new, one
scoped to league fixtures); walk on Postgres at `0053` - 2027 quarter-final from the drawn row won on
penalties, semi-final opponent `Ostdera Naval` from `engine 2-1 (seed 1174159400)`, gates 135,057 over
two home ties, one 40,000 prize.

## Next up (Phase 9)

1. **The world draws next season's cup (done 2026-11-05).** The section below "Next up" states the rule
   and the resolution rule for undrawn rounds; `docs/M13_NEXT_SEASON_CUP_VERIFICATION.md` carries the
   evidence (19 cup cases, 59 world cases, a 2027 walk).
2. **Objectives that pay (done 2026-11-04; landed as `0cf34c1`).** The section before "How to work an
   item" states the rule and the rates, and `docs/M13_OBJECTIVE_BONUS_VERIFICATION.md` carries the
   evidence; the shared migration chain must renumber around `0049` before it lands (section 9 there).
3. **A stadium a manager buys (done 2026-11-05).** `career_stadium_works` prices a 500–20,000 seat stand at
   120 credits a seat, and `gate_capacity` reads the tier-factor capacity plus every bought seat. The
   section "Buying seats" below states the wiring; `docs/M13_STADIUM_VERIFICATION.md` carries the evidence.
4. **The locale claims grade the commit (done 2026-11-04; landed as `e8fa569`).** The section before
   "How to work an item" states the sourcing and the arms, and `docs/I18N_ARC_VERIFICATION.md` §21
   carries the evidence.
5. **The contract-currency gate reads the commit, not the checkout (filed 2026-11-04, landed as `f10e232f`).** Its docstring
   claims the committed contract, and now the bytes are read from `git show HEAD:docs/api/openapi.json` (LF-normalised for a
   historyless checkout), the exporter case compares its output to HEAD's, and `answers()` stays live from the imported app
   — the disk pair is only a fallback for a checkout with no `.git`. Filed against the days when both read the checkout;
   the cure is on HEAD and the tests are green.

## Objectives that pay (M13 Phase 9 item 36, done 2026-11-04)

Item 24 gave a career a second door in, but it was the board's door: a season was paid for its rounds and its
points. The objectives a manager picked at the opening were still only prose — `objectives_of` compared the
season's sums against the targets and the board printed `met`, and the money never saw them. This item makes a
met objective an award row of its own, so the targets a manager chooses are a reason the balance moves. The whole
rule is one pure function, `objective_bonus_report`, and one authored table beside the grant's:
**30,000 for wins, 40,000 for points, 25,000 for goal_difference, 50,000 for unbeaten** — 145,000 if all four
are met, a little under one full season's grant (174,500), so meeting the board's targets is a good season's
extra income rather than a reset button. It pays only what was met: `actual >= target` read from the same report
the board prints; a target of zero or less pays nothing, because nothing had to be met; a miss writes no row; and
a `challenge` window pays nothing because that run is judged by its own reward. `close_season` calls
`pay_objective_bonuses` after the grant in the same transaction, one row per met objective with the objective's
kind as the award's `stage`, flushed before each balance read because `SessionLocal` runs with `autoflush=False`;
the grant and the bonuses share the ledger's boundary tier, the stage orders them, and the timeline's running
balance replays that order and counts its own disagreements. At HEAD the award table had no `stage` and its
unique key was one grant per season, so `0049_objective_bonuses` adds the column and swaps the key to
`uq_career_award_stage (career_id, season_index, kind, stage)` — a fresh SQLite reports head 0049 and
`DRIFT none`, and the audit's machine-checked migration figure moves 49 → 50 in both carriers
`test_spec_audit_currency.py` reads. It is published wherever the balance is read: `budget_position.received_objectives`/`objective_rows`
/`objective_detail` and the printed sum, the timeline, the market ledger (a row in the moves table's shape, with
`OBJECTIVE_BONUS_EFFECT`), `market_view.totals.bonus_rows` and `constants.objective_bonus_by_kind`, the
affordability block, and `seasons_view` — each closed season's `bonuses` block, and `bonus_if_closed_now` for the
season being played, a projection that writes nothing. The web tier prints the projection and the paid bonuses
in `CareerSeasons`, the received total in `CareerFinance`, and the ledger rows plus the two income terms the
balance sentence had been missing (`+ in board grants + in objective bonuses`) on the market page; five new
catalogue keys per locale. Evidence: [M13_OBJECTIVE_BONUS_VERIFICATION.md](docs/M13_OBJECTIVE_BONUS_VERIFICATION.md).

## The locale claims grade the commit (item 38, done 2026-11-04)

`test_locale_claims.py` sourced both of its inputs from the working tree — `_prose()` read `REPO / rel`,
`_catalogues()` globbed `apps/web/messages/*.json` — so a figure pinned to equality was graded in a place no
commit owns. `25c6873` proves the split: on its own checkout the README row says `3988 of 4033` while that
commit's `en.json` holds 4,053 keys (45 language-neutral), so the true pair is `4008 of 4053` and the test
fails; in the shared tree the same row reads `4074 of 4119` against a catalogue that had grown again, and the
run is green. The whole module now reads the commit through `git show HEAD:…` and `git ls-tree HEAD`, the two
helpers `test_spec_audit_currency.py` already uses: `_raw()`/`_names()` for the catalogues, `_prose()` for the
five carriers, and `_refusals()` for the API-source census that compares published codes against `errors.*`
keys — a disk census against a committed catalogue is the same mixed-tree comparison one layer out. A
checkout with no `.git` falls back to disk, as the sibling does. `_capabilities()` is the one live input: the
app boots from the checkout by necessity, and its `locales` answer is compared to the committed catalogues.
Three arms on a clean worktree, each making the checkout disagree with HEAD in a different input — a dirty
`en.json` (4,059 keys vs 4,058), a README row rewritten to `1 of 1` plus a planted `287/288` sentence in
`ARCHITECTURE.md`, and a working-tree-only `zz_item38_probe` refusal — left this file green in all three;
HEAD's old reader failed each arm, the census arm naming `["zz_item38_probe -> 'Probe refusal'"]`. Evidence:
[I18N_ARC_VERIFICATION.md](docs/I18N_ARC_VERIFICATION.md) §21. **Landing:** `e8fa569`, one path through a
private index.

## The contract is read from the commit too (item 39, done 2026-11-04)

`test_openapi_contract_currency.py` graded a mixed tree: `committed()` parsed `docs/api/openapi.json` from disk
while `answers()` booted the app from disk, so the artifact side — the very thing the commit publishes and every
`docs/*_VERIFICATION.md` line quotes — was whatever the checkout held. The 2026-10-23 follow-up had settled which
*newline* arrived and never asked which *tree*. The instance is live rather than invented: the shared working tree
answers `/api/v1/careers/{ident}/cup` and `/api/v1/transfers/{ident}/renew` with its contract regenerated to 220
paths / 282 operations, while the commit holds 218 / 280 — and HEAD's gate answers **4 passed** on that tree,
because disk agrees with disk about a surface no commit has published. Sourcing the artifact through
`git show HEAD:docs/api/openapi.json`, with the `_git` + `@cache` shape `test_spec_audit_currency.py` and
`test_locale_claims.py` already use, turns the same four cases into **4 failed**, each on its own clause: 2 routes,
2 `(path, verb)` pairs, `CupIn` and `RenewIn` missing from the committed schemas, and 497,932 bytes against the
blob's 492,817. The app side stays live by necessity, which is what makes the gate a pre-commit alarm: it reds
while the cure is one more `python scripts/export_openapi.py` in the same commit as the route. Three arms on a
clean plane — a contract dirty on disk alone (old 3 failed / 1 passed, new 4 passed), a planted route with its
contract regenerated beside it (old 4 passed, new 3 failed / 1 passed), and the baseline green on both sources.
Evidence: [OPENAPI_CONTRACT_VERIFICATION.md](docs/OPENAPI_CONTRACT_VERIFICATION.md). **Landing:** `f10e232`, one
path through a private index; the record, this section and the roadmap bullet land after it.

## A landing can revert a landed unit (item 40, done 2026-11-04)

`c0d376c` carried 22 paths. Two were its own unit — `qa-wire-readers.mjs` and section 20 of the i18n record — and
the other twenty were the checkout's stale answer to item 36: `CareerBudgetAward.stage` and
`uq_career_award_stage`, `objective_bonus_report`, `pay_objective_bonuses`, `TestObjectiveBonuses`, the market
page's bonus ledger and its second income term, five catalogue keys per locale, the README rows back to
`3988 of 4033`, `migrations=50` back to `49` in both audit carriers, and the item's record, plan section and
roadmap bullet. `0049_objective_bonuses.py` was not in the set and stayed, so the commit held a revision that
builds a column no model declares. Two gates red on that tree — `test_spec_audit_currency` (49 claimed, 50
revision files) and `test_locale_claims` (README 4,033 against an `en.json` of 4,053) — and both are figure
against file; the schema was invisible. `21bbf86` restores the twenty blobs exactly as `e8fa569` held them and
keeps the lane's two paths, measured at **208 passed** across the six API files with ruff, mypy and `tsc` clean and
the file-only web gates at **194/194**. The repair is also why item 38's record landed rebased rather than as
written: a section appended to an older copy of that file would have deleted the RTL record the same way.
The whole suite on the repair answers **1 failed / 2148 passed / 4 skipped** in 36:54 — the same population item 38
measured, so the restore neither lost nor gained a test — and the single red is `test_ci_trigger` refusing a
detached plane's `HEAD`, which is item 43, not the repair.
Evidence: [MIGRATION_MODEL_DRIFT_VERIFICATION.md](docs/MIGRATION_MODEL_DRIFT_VERIFICATION.md) §1–3. **Landing:**
`21bbf86`, 20 paths through a private index.

## The chain and the models describe one schema (item 41, done 2026-11-04)

The half of the revert that no test could see. `apps/api/tests/test_migration_model_drift.py` runs the committed
chain to head on a temporary SQLite file in a subprocess with its own `DATABASE_URL` — so the checkout's `.env`,
the suite's test database and the dev database are all out of the picture — and asks alembic's own
`compare_metadata` what would move the migrated schema to `Base.metadata`, with the revisions and the models both
read from the committed tree. Four clauses, each failing alone: a column the chain builds and no model declares —
and its message names the revision that shipped it, found by reading the committed migration sources for the ones
naming both table and column; a column a model declares and no revision builds; the tables in both directions; and
everything else `compare_metadata` can name, constraints included. Types and widths are deliberately out
(`compare_type` on SQLite is reflection noise, and widths are `scripts/schema_drift.py`'s claim against a live
database). **4 passed** in 10.9 s at master; **2 failed / 2 passed** on the real `c0d376c`, clause 1 answering
`career_budget_awards.stage … ['0049_objective_bonuses.py']`; a planted model column and a planted model table each
red on exactly one clause. Evidence: [MIGRATION_MODEL_DRIFT_VERIFICATION.md](docs/MIGRATION_MODEL_DRIFT_VERIFICATION.md)
§4–7. **Landing:** `f5d6abf`, one path through a private index; this record, section and bullet are the commit
beside it. It filed two findings — `qa-wire-readers`'s prose census (item 42) and a CI gate that is green only
under a fabricated environment (item 43).

## Buying seats (M13 Phase 9 item 37, done 2026-11-05)

The gate responded to a career but the ground did not: `teams.capacity` is shared by every career at a
club, so no manager could build. `career_stadium_works` is the career's own purchase history — one row
per stand, with the seats, the 120-credit unit price, the ground either side and the `budget_after` it
produced. The current ground is the world's stored capacity plus the sum of bought seats, and the gate
reads `round(stored x tier factor) + bought seats`: a career that bought nothing still reads item 33's
figure, while every bought seat is exactly one more seat the next home gate can sell. A stand is
private to the career and does not grow when the club is promoted; the club's own stored share still
does.

`market.buy_seats` is the only spender, refuses `career_retired`, `challenge_budget`, `bad_seats`,
`no_club` and `insufficient_budget` through the registered table, and writes nothing on a refusal. The
purchase is a ledger row of kind `stadium`, so `budget_position` subtracts it, `budget_timeline` replays
it in the round's first slot beside squad moves, and `market_view` merges it into the ledger.
`POST /careers/{ident}/stadium` takes `{"seats": n}` and returns the work row plus the re-derived career
view; `career_view["stadium"]` and `CareerStadium.tsx` print the ground, the price, a live cost preview
and the history. Migration `0054` adds the table; the duplicate `0049_objective_bonuses.py` was removed
so the chain has one head.

**Evidence.** `docs/M13_STADIUM_VERIFICATION.md`: 4 service cases, 2 wire cases, 9 targeted finance
cases and the answer/locale gates green; `alembic check` clean at `0054`, ruff clean, mypy 164 files
clean, tsc/ESLint and the four i18n gates green; contract regenerated to 221 paths / 283 operations. The
Postgres walk bought 1,500 seats (53,002 -> 54,502 gate capacity), spent 180,000, played a home round
for 77,450 and read a timeline with 0 disagreements and a closing balance of 897,450.

## The gate is priced (M13 Phase 10 item 44, done 2026-11-06)

The price of a seat was the last authored figure in the gate. `careers.ticket_price_pct` is the
manager's setting — 50–200% of the competition's price in steps of five — and migration `0055` copies
the setting and the demand it drew onto every receipt, so changing the price tomorrow cannot rewrite
the crowd that paid today. One curve, `market.demand_pct_for`, is read by the preview and the gate:
`d = (pct − 100)/100`, `demand = max(20%, 1 − 0.50d − 0.50d²)`, and the gate is
`round(attendance × base × pct / 100)`. The revenue peak sits at 120% (index 106); 120% sells 88% of
the neutral crowd, so the panel states a trade rather than a dominant choice.

`market.ticket_price_view` publishes both the manager's setting and the best one, its formula and the
bounds; `market.set_ticket_price` refuses `career_retired`, `challenge_budget`, `no_club` and
`bad_ticket_price` (422, with the step) through the registered table. `GET` and `PUT
/careers/{ident}/tickets` expose the read and the decision; `career_view["tickets"]` and
`market_view["tickets"]` carry it; `RULES["ticket_price"]` states the arithmetic; `CareerTickets.tsx`
puts the stepped input on the career page; the market page prints the same figures and every gate
ledger row now carries its own `price_pct` / `demand_pct`.

**Evidence.** `docs/M13_TICKET_PRICING_VERIFICATION.md`: 7 service cases and 2 wire cases green in the
directed regression over seven files; `alembic upgrade head` 0054 → 0055 and `alembic check` clean;
ruff clean, mypy 164 files clean, tsc/ESLint clean; `qa-wire-readers` 18/18, `qa-i18n-literals` 9/9,
`qa-unused-keys` 3/3, `qa-token-drift` 2/2, `qa-locale-tokens` 5/5 at 4,181 keys / 4,136 translated;
contract at 222 paths / 285 operations. The Postgres walk played a neutral round at 38,725 seats /
77,450, then a 120% round at 33,806 / 81,134: fewer seats, more money. The first receipt still read
100% / 77,450 after the setting moved to 150%, and the timeline closed at 1,158,584 with 0
disagreements.

## The ground costs money to run (M13 Phase 10 item 45, done 2026-11-06)

Buying seats had no running cost, so building was always right. Every home league round and every home
cup tie now pays `round(capacity × 25%)` credits for the seats it opens; the capacity is the physical
ground, not the tier-adjusted figure the gate sells. A 48,184-seat ground pays 12,046 a match, a
tier-2 full house earns 96,368 at the neutral price, and 500 more seats add 125 a round. An away
round, a neutral-venue final and a challenge career pay none.

`career_upkeep_charges` (migration `0056`) stores one row per home round with the round and fixture or
tie, capacity, `seat_rate_pct`, amount, basis and `budget_after`; partial uniques keep one league row
per round and one row per tie. `BUDGET_FORMULA` subtracts the sum; `budget_position` publishes
`upkeep_spent`, `upkeep_rows`, `upkeep_detail`; `budget_timeline` places the row immediately after its
gate and before the wage charge; `market_view` merges it as kind `upkeep` / `cup_upkeep` with
`capacity` and `seat_rate_pct`. `stadium_view` prints the rate at the current ground,
`RULES["upkeep"]` states the formula, and `CareerFinance`, `CareerStadium` and the market page print
the running total.

**Evidence.** `docs/M13_UPKEEP_VERIFICATION.md`: 5 new service cases and the cup tie's own row green
in the directed regression over nine files; `alembic upgrade head` 0055 → 0056 and `alembic check`
clean; ruff clean, mypy 164 files clean, tsc/ESLint clean; `qa-wire-readers` 18/18 with moves 34 and
14 named, `qa-i18n-literals` 9/9 over 4,234 calls, `qa-unused-keys` 3/3, `qa-token-drift` 2/2,
`qa-locale-tokens` 5/5 at 4,185 keys / 4,140 translated. The Postgres walk read gate 77,450, upkeep
12,046 and net 65,404; after 500 more seats the next home round cost 12,171, the first row did not
move, the two rows summed to 24,217, and the timeline closed at 1,070,065 with 0 disagreements.

## Season tickets (M13 Phase 10 item 46, done 2026-11-06)

The gate sells one crowd; a season ticket sells the same seat for every home league round before the
season starts. The offer is `round(home_rounds × base × 85%)` per seat — 7 home rounds at a walk-up
price of 14 make a season seat 12 — capped at half the ground and sold in blocks of 100. The sale is
written once per season before round one, and the seats it sells are in the ground every home round
without being charged again: the gate charges `attendance − season_ticket_seats` while the receipt
stores the whole crowd, so the two figures can be read apart.

`career_season_tickets` (migration `0057`) and `career_gate_receipts.season_ticket_seats` carry the
state; `BUDGET_FORMULA` adds the income, `budget_timeline` places the sale before round one, and the
ledger carries kind `season_tickets`. `GET`/`POST /careers/{ident}/season-tickets`,
`career_view["season_tickets"]`, `RULES["season_tickets"]` and `CareerSeasonTickets.tsx` make it a
page decision. A second sale, a started season, an off-step block, a challenge career and a retired
career each have their own refusal code.

**Evidence.** `docs/M13_SEASON_TICKETS_VERIFICATION.md`: 7 service cases and 2 wire cases green in
the directed regression over ten files; `alembic upgrade head` 0056 → 0057 and `alembic check` clean;
ruff clean, mypy 164 files clean, tsc/ESLint clean; `qa-wire-readers` 18/18 (constants 30, moves 35),
`qa-i18n-literals` 9/9, `qa-unused-keys` 3/3, `qa-key-drift` 4/4, `qa-token-drift` 2/2,
`qa-locale-tokens` 5/5 at 4,209 keys / 4,164 translated, `qa-locale-completeness` 2/2. The Postgres
walk sold 1,000 seats for 12,000, played a home round with 38,725 in the ground and 37,725 paid, a
gate of 75,450, and a timeline closing at 1,075,404 with 0 disagreements.

## Item 18 — spec module 02: Live, as the replay a deterministic engine makes honest

**The gap.** The spec's 28 modules carried "02 Live" with no form in this build — and the honest form is not
obvious: world matches hold aggregate stat lines with no minutes, so a ticker over them would invent the very
minutes a broadcast is made of. The data that can be replayed honestly already existed: a career's sim matches
carry minute-level `sim_events` rows the engine wrote when the match was played.

**The shape.** Live is a replay layer, and the page wears that word: `/live` lists the account's replayable
matches from the simulate list door; `/live/{slug}` reads the detail door's timeline (`row(full=True)` already
carried it, re-read from `sim_events`) and hands it to `MatchTicker` — a client clock at one wall-second per
match minute, events arriving as their minutes pass, the score tracking goal events only, with play/pause/
restart and the whole-timeline type index. **Zero new API doors and zero new tables**: the replay reads the
same rows the report serves, both pages print the source note that says where the minutes came from, and the
badge says REPLAY rather than implying a broadcast.

**Gates and privacy.** Session-gated (middleware prefix, robots disallowed, crawl gate reconciled), a 37-key
`live` namespace in all three catalogues plus the nav link, tsc green, metadata gate 184/184, crawl gate 9/9.

**Evidence.** The browser verification against the production build: a match played through the API (36 events,
source `sim_events rows`), then the replay ticked live — at wall-second 14 the feed held 7 events and the score
had tracked 0–0 to 0–1 as the minute-13 goal arrived; the index listed the match with its score card and the
replay chip. Walk section to follow with the next full walk (the tier's own section sits in the simulate area,
after a match has been played).

---

## Finding (another lane's gate, recorded 2026-11-07): the sweep runs signed out, so its coverage gate can never see a gated page

The walk's English sweep (the section that re-reads every visited path hunting catalogue phrases that leaked back
into literals) runs **after sign-out**, and its coverage gate compares the app tree's routes against the paths the
sweep actually landed on. A gated page swept while signed out lands on `/login`, so its route reads as uncovered —
which is why the gate reports exactly the gated population ("40 route(s) no page was read under", led by `/agents`,
`/career`, `/coach`, routes the walk demonstrably reads earlier while signed in). The gate is another lane's fresh
work; the fix it needs is an ordering one (sweep while signed in, or sign-out after the gate), and it is recorded
here rather than fixed under a writer who is standing on the file. The Live replay section this lane added sits
outside the sweep for the same reason.

---

## Verification record (2026-11-07): the committed tree at `ee19799` verified on a clean plane

A `git worktree` at HEAD ran the API gates against the **committed** tree, with the worktree left to another
lane's in-flight landing: ruff clean, mypy clean over 161 files, and the full suite **green except two currency
figures — both transient, neither a defect to fix here**. `test_locale_claims` grades the *committed* catalogue
(4,096 keys at this HEAD) against the worktree's README table (which the landing has already recomputed to 4,269),
and `test_spec_audit_currency` compares the audit's page-route figure against a tree that has gained two pages the
landing will carry. Both figures agree the moment the landing's commit lands; editing either file now would guess
at another writer's final numbers. Everything else — 1,600+ tests — green on the committed tree.

---

## Cross-verification (2026-11-11): the M14 service plane booted from clean jars and read back live

The service plane another lane built (M14, items 47–62) was verified end to end from this lane's side, from the
Maven reactor's own jars — `mvn -o -B package` green over the three modules, then registry (8761), config (8888),
the core registered at 8100 and the edge at 18080 booted in one shell and probed live:

* `GET /actuator/health` on the edge: **200**;
* `GET /api/v1/healthz` **through the Gateway**: the product's own answer, with `demo_mode`, `pgvector: true` and
  the provider table intact — the edge routes and forwards without judging or reshaping;
* **trace propagation**: a request sent with `X-Trace-Id: verify-trace-001` came back with the same id in the
  response headers — item 58's "one trace across both planes" read back live rather than quoted.

One boot failure on the way was the operator's, not the plane's: the edge defaulted to port 8080 when `EDGE_PORT`
was not exported, and the runbook's "EDGE_PORT and `--apc.core-uri` are the two knobs" is the sentence that was
missed. Recorded because a runbook sentence that saved one verification is worth its place.

---

## Harness finding (2026-11-11): the 1,782-URL probe saturates the shared host's web tier — the walk's full green needs a quiet window

Two mitigations landed (the probe at two workers with a two-minute budget; the five-failure early bail), and the
probe **still** wedges the single-process web tier when the host is carrying another lane's full landing: the
client-side early bail stops the walk from hanging, but the server's own render backlog keeps its event loop busy
for the rest of the run. Three runs measured it — each died in or right after the probe, each with 81+ checks green
before it. The 312/316 record above was taken in a quiet window and stands as the tier's verified state; the full
walk's next green needs the host quiet (the other lane idle), not a product fix. Two further options are named for
whoever takes it: probe with a HEAD-shaped request if the framework ever grows one, or split the probe across two
walks (world rows on one, the rest on the other) so no single run carries 1,782 renders.

---

## Item 19 — spec 27's second slice: per-kind mutes, and the tray the account wants

**The gap.** The tray wrote every event the three producers fired; the account could not say "stop telling me
about reactions". The tier's own products — a tray that fills, a badge that counts — become noise the moment the
account cannot shape them.

**The shape.** `users.notification_mutes` (migration `0061`, one JSON column) holds the kinds the account wants:
`notify` checks before inserting, so a muted kind is never written — a muted tray is empty by choice rather than
by a filter the reader applies after the fact. Two doors (`GET`/`PUT /notifications/preferences`), the GET's map
carrying every known kind so an untouched key reads as wanted, the PUT raising a 422 from the service's own
sentence for an unknown kind. The settings page gains the panel: three toggles bound to the door's map, saving
through the client fetch and refreshing from the answer.

**The six-locale finding.** The catalogue carried four locales when this slice started and six when it landed
(fr, ar, he joined): the panel's copy went into all six, and the gates taught the difference between the three
kinds of "same" — fr's page titles were differentiated at the **English source** (the same-sentence gate holds
each locale to English's own key duplication, so a locale cannot escape a duplicated English sentence by
translating it differently), fr's `prefsEyebrow` was differentiated because French spells the loanword the same
way (the tokens gate refuses an unnamed identical value), and the Arabic copy had to end with the Arabic full
stop (the punctuation gate names the script of every sentence-ending). The README table was recomputed for all
six locales at population 4,300.

**Evidence.** `tests/test_notifications.py` now 14 cases (mutes 5: untouched reads as wanted, muting stops the
write while the others still write, muting twice is the same state, unmuting reopens, an unknown kind is a 422;
producers 3; erasure 1). ruff and mypy (167 files) clean; the i18n gates all green (locale-completeness,
key-drift, tokens 7/7, translation-quality 9/9 after the Arabic full stop and the English source fix, metadata
188/188, literals 9/9); the doors verified live through the API (read → mute → re-read → unknown-kind 422).

## Item 20 — M15: one limiter, one clock, one identity

**The gap.** The project had two rate limiters. The middleware priced every `/api/v1` door against a
process-local token bucket; the per-door `limit()` helper charged a *fixed window* held in a dict in
`app.core.security`, keyed on the socket's peer. That second tier's own docstring had said "swap for Redis
when horizontally scaled" since M1, and four defects sat behind that sentence: behind the project's own
edge every caller arrives from the proxy's address, so one bucket counted the whole internet; a
credentialed caller was counted by address anyway, so one account could spend another's budget by sharing
its NAT; the dict's LRU eviction dropped buckets *still inside their window*, handing that caller a fresh
budget; and a fixed window admits `2 × limit` across its boundary while its `Retry-After` promised the
seconds to window rollover. Two places wrote the headers, so a cache HIT replayed the miss's numbers and a
500 — which never comes back through the middleware — carried no budget at all.

**The shape.** `app/core/ratelimit.py` holds the algorithm (`Policy`, `Decision`, `MemoryLimiter`,
`RedisLimiter`, `TwoTierLimiter`) and `app/core/rate_policy.py` holds the policy: the ordered prefix table,
`policy_for`, `caller_key` and `rate_decision_var`. The read-modify-write is one Lua `EVALSHA` that reads
`redis.call('TIME')` — N workers share the server's clock, and `elapsed` is clamped at zero so a replica
whose clock is behind cannot mint tokens by travelling backwards. A bucket expires at the instant it would
have refilled to capacity (`PEXPIRE ceil(capacity/refill_per_ms) + 1000`, floored at `MIN_TTL_MS`), because
from that instant its state is the state a missing key produces. The local tier is an **admission
pre-filter** sized to the cluster's capacity, so it can never refuse what the cluster would admit; a caller
outside its burst is answered locally, so a flood reaches the store at the refill rate rather than the
flood's rate, and `short_circuited` counts those answers. With no store the tier degrades to per-process and
**stamps `X-RateLimit-Scope: process` on every answer**. `dress_response` is the one dresser: the 200, the
HIT, the 429 and the 500 publish the same seven headers from the same `Decision`, and all eight budget names
joined `PER_REQUEST_HEADERS` so the cache cannot replay another request's `Remaining`. `GET
/api/v1/metrics/rate-limit` publishes the tier, the counters and the price list behind the administrator
standing the metrics router already carries.

**The census that decided the key's shape.** A read-only walk of the tree's `limit(...)` call sites measured
**222 scoped doors, 8 scopes reused at more than one ceiling, and 4 `(scope, path)` pairs priced differently
by verb** — `career_tickets` is a GET at 60/60 and a PUT at 20/60 on one path. So the door key carries the
path *and* the verb: `door:{scope}:{method}:{identity}:{path}`. Without the verb, twenty writes leave the
read door serving nothing against a ceiling it publishes as sixty.

**Three harness findings, each paid for in red.** (1) A test that hard-codes the degraded tier's name lets
the operator's environment decide the verdict: `test_the_crash_answer_carries_the_budget_too` asserted
`process` and went red `cluster != process` on a working limiter because `REDIS_URL` was exported. The
fixture now pins `rate_limit_redis_url=""` and the cluster direction has its own case. (2) A case that counts
tokens across two HTTP calls is counting the host's speed: `DEFAULT` refills 40/s, so a 25 ms gap puts back
the token the first request spent. The fixture pins *only the tier's arithmetic*, not `time.monotonic`
process-wide — the event loop under `TestClient` reads that clock for its own deadlines. (3) The arm script's
blanket `\n` → `\r\n` re-encode would have written `\r\r\n` into CRLF `security.py`, making A1's red the
corruption's rather than the verb's; it now matches in LF and re-encodes to the file's own EOL.

**A behaviour change, disclosed.** The limiter answers before routing and before body validation, so a
throttled door returns 429 where FastAPI previously returned 422. That changed the project's own probe: S1
now waits out a throttle it caused itself and publishes the count (run K: 3 waits, `retry_after: 10`, policy
`"upload";q=8;w=1`), and S6's malformed post moved to `POST /api/v1/boards` as the account. The first run of
the changed probe read **8 passed, 2 failed** — those two — before the run recorded as current.

**Evidence.** `tests/test_rate_limit.py` 26 cases + `tests/test_rate_limiter.py` 12 = **38**, green on both
legs: **57 passed** with `REDIS_URL` (146.68 s) and **55 passed / 2 skipped** without (121.99 s), the two
skips named and both live-store cases. **3/3 reverse controls MATCHED** with the tree proved green at rest
and every file restored byte-exactly. `mypy app` clean over 169 files; ruff clean. Probe run K:
**10/10, 0 failed, 0 server errors, 44.51 s**, census 239 / 55 / 102 at contract SHA-256 `03fb360b…`,
**239 knocked, 239 × 401, 0 deviations**; S5's retry is now **22 s to one token** where the fixed window
published 297 s to rollover. The record is `docs/M15_RATE_LIMIT_VERIFICATION.md`.

## Item 21 — M15 at the edge: the shared bucket behind the last door

**The gap.** M15's limiter landed in the Python core, and the service plane's gateway kept its own
bucket in a `LinkedHashMap`. Two doors, two ceilings, two identities: a caller refused by the core was
admitted by the edge in the same second, and a caller that spread its requests across gateway replicas
got N times the published limit — which is exactly what a caller being refused tries next.

**The shape.** `DistributedRateLimitFilter` (order +5) asks Redis with the same Lua script the core runs
and stamps the exchange; `RateLimitFilter` (+10) sees the stamp and steps aside, so one request is
judged once and the published ceiling is the real one. Identity is `CallerKey`, the same three branches
as `app/core/rate_policy.py` — credential digest, then a forwarded address only from a configured
trusted proxy, then the socket's peer — implemented twice on purpose: a shared library would have to be
a third language in the build, and the rule is twelve lines. The store's call is bounded at 250 ms; an
error, a timeout, a malformed reply or no store at all resolves to the local bucket and the answer says
`X-RateLimit-Scope: process`. `RedisBucketStore` is `@ConditionalOnProperty` and off by default, because
a gateway that tries to reach a store nobody gave it spends a timeout per request proving it.

**One defect found while wiring it.** An empty `spring.data.redis.host` does not mean "no store" to
Spring Boot — it fails `RedisConnectionDetails` at startup and takes the whole context down (35 test
classes red). The fix is to leave the block out entirely and let a deployment name the host through
relaxed binding (`SPRING_DATA_REDIS_HOST`), documenting that an absent store is a supported state.

**Evidence.** `mvn -B -pl edge -am test` green over **55 tests**, including 8 new filter cases (allowed,
refused, error, timeout, no store, disabled, malformed reply, body shape) and 6 identity cases. Live,
against the project's own Redis and the running core: `edge.rate-limit.burst=5`,
`requests-per-second=1`, eight requests through `:18085/api/v1/healthz` answered `200` ×7 (remaining
4,3,3,2,1,0,0 — one token refilled mid-burst) then `429` with `Retry-After: 1`, every answer carrying
`X-RateLimit-Scope: cluster`; `/edge/limits` reported `distributed=true, distributedChecks=8,
distributedDegradations=0`; and the bucket was readable at `football_os:edge:rate:ip:127.0.0.1`.

---

## Item 22 — the coach's voice: the question reaches the model

**The gap.** `POST /coach/ask` computed its answer arithmetically and then asked a model to phrase it
with `{"intent": …, "facts": "<one sentence>"}`. Against a live provider on 2026-11-12, a player asking
"how do I scan before receiving the ball?" got a paragraph about the recommended rondo: the question had
never crossed the wire, no measurement had either, and the model's reply was appended *after* the
template, so the page said the same thing twice in two voices.

**The shape.** `app/services/coach_voice.py` builds the prompt from the question, the intent, the
player, the seven attributes the recommendation was scored on, the drill's session block, the engine's
reasons and the recent history; the system message states three rules (answer first, only `FACTS`,
"Data unavailable" rather than a guess, no headings). The model's reply *replaces* the template; a
capped turn, a demo provider, a failed call and an empty completion all still answer with the
arithmetic.

**Evidence.** `test_coach_voice.py` 7 cases (question crosses the wire, measurements cross it, an absent
fact is absent rather than invented, the rules are in the system message, a reply replaces rather than
follows, the prompt is one compact JSON object); `test_api_flow` + `test_coach_budget` + this file 27
green. Live: three prompts through the running API answered by `gpt-6-sol`, each citing stored numbers
("your gap to target in these areas is 66 points", "ball control and composure are both 44") and the
third saying "unavailable" where no session evidence exists.

**A gate that depended on the machine.** Two cases in `test_api_flow` assumed demo mode and failed the
moment a real key landed in `.env`, because `_load_dotenv` re-read it after `conftest.py` cleared the
keys. `FOOTBALL_OS_SKIP_DOTENV=1`, set by conftest before any app import, makes the suite independent
of a developer's `.env`.

---

## Item 23 — the skeleton that was only a word, and four routes that now have one

`.skeleton` has been in `styles/globals.css`'s published vocabulary since the base surface, and the
only rule that ever painted it was scoped to `/progress`'s own stylesheet. Every other route that
reached for the token got an invisible inline `<span>` — a zero-height element, which is worse than no
placeholder: the page is blank, and the markup says it is not.

The token is now a shared object: a quiet raised bar that breathes through the accent's hue rather than
a grey shimmer, so a loading page still looks like this product. `/world`, `/tactics`, `/scout` and
`/career` — the four routes whose first paint waits on a database read — gained a `loading.tsx` built
from the same shapes their pages use. No copy, so nothing there needs a catalogue key and nothing shifts
language.

**Evidence.** `qa-a11y` 33/33, `qa-i18n-literals` 9/9, `qa-unused-keys` 3/3, `qa-metadata-title` 188/188,
`tsc --noEmit` exit 0, and a production `next build` exit 0 (68 routes). The harness's bulk-delete guard
refused a mid-build unlink of `.next/static` — a tool-environment limit, not a code failure; the build was
re-run against a cleared `.next` and finished green.

---

## Item 24 — M16: the queue gets a transport, and the row stays the truth

**The gap.** ADR-006 built the job state machine and closed with a promise: *"the same repository
interface can be driven by Redis/Celery later without touching call sites."* Nothing had driven it. The
only read path was `drain_one`, which claims the oldest `QUEUED` row — so a job waited for a timer, and
in practice the timer ran inside the web process, where a video analysis holds a request thread for
minutes.

**The shape.** The row stays authoritative; Redis Streams is only the wake-up. `JobStream`
(`app/core/job_stream.py`) publishes one message per committed `QUEUED` row (`MAXLEN ~ 20000`), consumes
through one group created at `$`, recovers a killed consumer with `XAUTOCLAIM` after 60 s, reads delivery
counts from the pending list, dead-letters a message past `MAX_DELIVERIES` **before** acknowledging it,
and deregisters a consumer on a clean exit so `consumers` counts processes rather than history. The claim
is still the conditional `UPDATE … WHERE status='QUEUED'`, now reachable by id (`claim_by_id`) — so
at-least-once delivery sits on exactly-once execution, and the guarantee is the database's.

`requeue_expired` is the sweep ADR-006 deferred to "the operator": a `RUNNING` row with a past lease
returns to `QUEUED` without spending an attempt, unless it already spent `max_attempts`, in which case it
is failed with the reason. `app/worker.py` is the consumer process (`--once`, `--max-jobs`,
`--sweep-every`, SIGINT/SIGTERM finish the current job); `scripts/drain_jobs.py` is now a thin front end
over it, so the script, the container and a laptop cannot drift into three loops. `POST /jobs` publishes
after the commit; `GET /metrics/jobs-stream` reports the transport to an admin.

**Evidence.** `tests/test_job_broker.py` 26 cases, 8 of them live-Redis integration cases — a lost hint,
a duplicated hint, a hint naming a missing row, a raising handler, a poison message, a claim race, the
sweep's two verdicts, clean-exit deregistration, reclaim, and end-to-end drain. Live through the API with
a real worker: `POST /jobs` → `QUEUED` → worker → `COMPLETED` with the echo result, `pending` 0; a worker
with Redis unreachable logged `job stream unavailable, the poll loop carries the queue` and completed the
job anyway; a healthy worker then consumed the stale hint, executed 0 jobs and left `pending` 0.

**Two defects found while wiring it.** `JobStream.read` was both the consumer method and the counter of
messages taken, so `self.read = 0` made every later call `'int' object is not callable` — the counter is
`taken` now. And redis-py 8 removed the range form of `XPENDING`: the old call raised `TypeError` into the
`except`, so every delivery count read 0 and the poison rule could never fire. `deliveries()` now asks
`xpending_range` with a one-millisecond window and reads `times_delivered`.

---

## Item 25 — the home hero: a board that scans, and no copy to translate

**The gap.** The first screen of the product was a heading on `pitch-backdrop` — the same panel every
other page uses. A reader deciding whether this is serious saw a wall of text and four "not built"
columns.

**The shape.** `components/HeroPitch.tsx`: one server-rendered `<svg>` — a field in perspective, a pass
network, opponents, and a wedge sweeping around the player holding the ball, i.e. the thing the product
actually teaches. Four CSS animations, no client JavaScript, `aria-hidden`, and **no text at all**, so the
drawing is not a twentieth string to translate and the heading is still the first thing a screen reader
meets. `prefers-reduced-motion` stops every animation rather than pausing one mid-frame.

**Evidence.** `qa-a11y` 33/33, `qa-i18n-literals` 9/9, `qa-unused-keys` 3/3, `qa-metadata-title` 188/188,
`tsc --noEmit` exit 0.

---

## Item 26 — the queue's claim was half-indexed, and now it is not

**The gap.** `ix_jobs_status_created` was `(status, created_at)` while every claim reads
`WHERE status='QUEUED' ORDER BY created_at, id`. `id` is a `String(40)` primary key, not SQLite's rowid, so
the planner served the filter and the first sort term from the index and then built a temporary B-tree for
the second:

```
SEARCH jobs USING INDEX ix_jobs_status_created (status=?)
USE TEMP B-TREE FOR LAST TERM OF ORDER BY
```

**The shape.** Migration `0062` recreates the index as `(status, created_at, id)` and the model says why in
the place the next reader will look. The plan is now one line — `SEARCH jobs USING INDEX
ix_jobs_status_created (status=?)` — with no sort step, which matters because the claim is the queue's only
hot path and runs on every worker tick, busy or idle.

**The audit that found it, and did not find more.** `EXPLAIN QUERY PLAN` over the five hot reads (a team's
sheet, a player's season, articles by entity, articles by category, the claim) against the real fixture —
16 481 news links, 7 280 stat lines, 856 articles — showed the other four already index-served, with a
temporary B-tree only where the result set is a dozen rows. No index was added "for performance" at that
size: it would cost every write and buy nothing a reader could feel. `tests/test_query_plans.py` is the part
worth keeping — five parametrised plans plus the claim's own, asserting **no SCAN in any relation** and no
temporary sort on the claim, so the day a filter loses its index the suite says so instead of a page getting
slow.

---

## Item 27 — the door says why it refused, in one header

**The gap.** A caller could see *that* it got a 503 but not *why*. A core refusing connections, a breaker already
open, and a slow call past its budget all produced the same status and the same body — and those are three
different operational facts: one is a service to restart, one is a door deliberately held shut, one is a budget to
raise. The breaker's state was readable at `/edge/breaker`, which is a door an operator has to know about; the
response the caller already holds is the cheaper place to say it.

**The shape.** `CircuitTraceFilter` (a global filter, order `HIGHEST_PRECEDENCE + 1`, i.e. just inside the trace
filter) writes `X-Circuit: coreBreaker=<state>;outcome=<pass|fallback>` before commit. Two details are the whole
design. The state is read **at commit time**, not when the filter starts, so the value describes the breaker after
this request was counted rather than before the failure that matters. And `FallbackHandler` writes the header
itself instead of letting the filter do it, because the fallback knows the outcome even when the breaker is still
CLOSED — the first connection refusal is counted but does not open anything, so a filter-only version would label a
fallback response `pass`.

**Evidence.** `EdgeCircuitHeaderTest` 2/2 (a live stub core: `coreBreaker=CLOSED;outcome=pass`, and the value is
two parseable fields with no whitespace), `EdgeFallbackTest` 1/1 — now asserting `outcome=fallback` on the refusal
body it already checked — and the edge suite 57/57.

---

## Item 28 — one sheet, one frame, and a gate that can see the difference

**The gap.** Three tools panels — `CommunityTools`, `MatchTools`, `NoticeBoardTools` — wrapped their tables in
`.table-wrap` and forgot `className="table"`. So 112 of the app's 115 sheets carried the design system's rules and
three fell back to the browser's defaults: no uppercase head, no row rule, no hover, a different size. Nothing in
the suite could see it. `tsc` does not read a class name, ESLint does not compare two files, and the browser walk
checks that a row is there, not that it is dressed like its neighbours.

**The shape.** Three classes in `globals.css`: `.table-wrap` (the scroll frame — without it a wide sheet makes the
*page* scroll sideways and takes the nav with it), `.table--sticky` (the head rides the top of the frame; the
background is opaque because a translucent sticky head over dark rows is a smudge, and the rule under it is a
`box-shadow` because `border-collapse: collapse` drops a travelling border), and `.table-wrap--tall` (a long sheet
scrolls inside its panel instead of stretching the page to thousands of pixels, which is what puts the head and the
column meanings out of sight at the same time). Phones get one density step rather than disappearing columns.
`history`'s inline `style={{overflowX:"auto"}}` became the class it was imitating; `leaderboard` gained the frame it
never had.

**The gate.** `scripts/qa-table-shape.mjs` resolves every `<table>` through the repo's own TypeScript and asks two
questions of each: does it name `.table`, and does it sit inside a frame (walking the real JSX tree, because a
`table-wrap` three panels away in the same file does not wrap this table and a regex cannot tell). It found exactly
the three panels above, and reads 115/115 after the fix. Registered in `scripts/check.sh`, so the next bare table
goes red instead of shipping.

**Evidence.** `qa-table-shape` 115/115, `qa-gate-inventory` 241/241, `qa-token-drift` 4/4, `tsc --noEmit` exit 0.

---

## Item 29 — two random instances, one comparison, and a deliberate five-percent mistake

**The gap.** `lb://football-core` sat behind Spring Cloud's round-robin balancer, which spreads requests
evenly by construction — including over an instance that has begun to answer slowly. With two cores and one
degraded, half of every caller's requests pay the degraded latency, and the edge cannot tell: the only
per-instance fact it kept was "registered". The circuit breaker does not cover this, because a breaker is a
binary at five failures; an instance that is merely three times slower never trips it, and by the time it
does, every caller has paid five times.

**The shape.** Three pieces. `InstanceStats` keeps one exponential moving average of answered latency per
instance (`edge.lb.ewma-alpha`, 0.3) plus a consecutive-failure streak, and turns them into a score: the
average, plus `penalty × target` while failing (a 5 ms connection refusal must not outrank a healthy 60 ms
answer), decayed back toward the target once the sample is older than 30 s. `P2cLoadBalancer` draws two
*distinct* instances at random and keeps the lower score — power of two choices, whose whole point is that
randomness prevents a herd and the comparison still finds the better of any pair. `InstanceStatsFilter`
(order 10151, one step inside `ReactiveLoadBalancerClientFilter`) closes the loop from the response side,
because nothing in the choice API ever hears how the request ended.

**The first trap: the terminal signal is not a verdict.** The filter's first version skipped every
cancellation as "the caller left" — which is what a cancellation means in ordinary Reactor. In the gateway
the body is written by Netty and the routing chain terminates by cancelling its upstream, so *every
successful proxied exchange* arrives as `SignalType.CANCEL`. Forty of forty samples were dropped, the
balancer chose between two unknown instances, and the integration test measured **21 of 40** — round robin
wearing a new name. The status code, not the signal, separates a finished answer from an abandoned one.

**The second trap: an instance exiled by its own first impression.** With the samples flowing, the same test
measured **1 of 40**. A stub core's first exchange cost 298 ms — cold connection pool, uncompiled path — so
its score opened at 124 against the other core's 62. Power of two then never chose it again, so its average
never corrected, so it was never chosen: a closed loop, and the statistics plainly showed it (the "fast"
instance had answered 35 times and was still scored worst). The fix is two-sided: 5% of draws ignore the
scores entirely (`edge.lb.explore-rate`), which is the only way a stale memory can be corrected, and the
memory decays with age so an instance that has gone quiet is re-measured rather than remembered forever.

**Evidence.** `P2cChoiceTest` 7/7 (greedy draws never pick the slower of three over 2 000 draws; a failing
instance loses to a healthy one even though it answers faster; one recovery restores it; decay returns an
old sample to neutral), `EdgeP2cRoutingTest` 1/1 through a real gateway against two stub cores (≥ 28 of 40 to
the fast one, and `/edge/lb` reports both scores), edge suite **65/65**. The policy is inspectable at
`GET /edge/lb` — strategy plus per-instance score, EWMA, failure streak, observations and sample age, worst
first — and `edge.lb.strategy=round-robin` restores the stock balancer. Design record:
[ADR-009](docs/adr/ADR-009-load-balancer-p2c.md).

---

## Item 30 — the background re-analyse door: the queue reaches the product's own UI

**The gap.** M16 built the queue and the worker; `video.analyse` has drained through it since §130. But
the product's own UI never asked for the queued path — the analyse button ran the pipeline inside the
HTTP request and the report rendered from the same response. The queue was real and unreachable from the
one page every clip owner lands on.

**The shape.** `POST /api/v1/video/{ident}/analyse?background=true` creates a `QUEUED` `video.analyse`
job (payload `asset_id` / `target_frames`), commits, publishes the stream hint **after** the commit, and
answers `202` with `{job_id, status, poll}`. A pending run for the same clip is named, not duplicated
(`deduplicated: true` on the second click), deduped in the same conditional-UPDATE spirit as the rest of
the queue. The clip report page's tools panel gained a **Queue a background run** button beside
**Analyse this clip**: it enqueues, then polls `GET /api/v1/jobs/{job_id}` every two seconds for up to
two minutes, shows QUEUED → RUNNING → COMPLETED, and refreshes the server-rendered report when the row
settles. A two-minute poll cannot outwait a slow ffmpeg run, so on timeout the UI says what it knows
("the worker process drains the queue") rather than spinning forever — and the job row keeps the outcome
either way. The synchronous door is unchanged and remains the interactive default; nothing on the page
claims visibility the worker does not have.

**The i18n half.** Eight new `video`-namespace keys (`queueAnalyse`, `queueing`, `queueQueued`,
`queueRunning`, `queueDone`, `queueFailed`, `queuePending`, and the rewritten `toolsNote` that now names
the worker instead of denying it) landed in all six catalogues — `en`, `zh`, `zh-TW`, `fr`, `ar`, `he` —
in the same commit, so the completeness and key-drift gates never see a half-translated door.

**The honesty half.** The clip's `jobs` listing no longer says "there is no queue and no worker behind
these rows" — it names both paths. The `SPEC_COVERAGE_AUDIT.md` async-job row moved from "in-process, no
queue" to the M16 state. M5's dated verification record and `PROJECT_AUDIT.md` are left as the
point-in-time snapshots they are.

**Evidence.** `tests/test_video_background.py` (5 cases, real clip): the 202 + queued row + payload +
no-duplicate rule, the row drained to `COMPLETED` by the same handler the worker registers, the `GET
/jobs/{job_id}` poll path, the clip-delete erasing its own queued jobs, the 404 shape, and the inline
default untouched. `tsc --noEmit` clean; the production build (`NEXT_DIST_DIR=.next-verify2`)
completed with BUILD_ID `h4ILtLe_xKXyltqn7xUiF`. The contract re-exported once more (`background` on
the analyse door; 228 paths / 295 operations unchanged), and the security probe was rerun live
(run L, port 8798, scratch SQLite, `ENV=development`): **10 passed / 0 failed / 0 server errors**,
census **240 / 55 / 103**, contract SHA-256
`d4b4ae0a8b5e65cf703dca541381534600b8a80d64742bb0eb6a42a2cd258e99`. The three ledgers that name the SHA
(`SECURITY_PROBE_REPORT.md` §1, the M12 record, the ROADMAP row) moved in the same commit.

---

## Item 31 — the service plane console: the edge's three doors get a page

**The gap.** M15 put a circuit breaker, a rate limiter and a load balancer in the Spring Cloud edge;
`/edge/breaker`, `/edge/limits` and `/edge/lb` answered JSON, but only to whoever already knew they
existed. A screen whose job is "what does the edge think right now" was curl-only.

**The shape.** `apps/web/app/plane/page.tsx` (server-rendered, one fetch per door with a 1500 ms
timeout, `no-store`) renders the operator read of the service plane on one page: the breaker's state
and failure-rate window, the rate limiter's tier (cluster vs process), its request budget and its
distributed-check accounting, and the load balancer's score board per core instance with an EWMA, a
failure streak and a sample age — worst first is the LB's own ordering, restated as a table. Each door
that does not answer renders as its own unavailable panel; the page never collapses three doors into one
verdict. The page gates on `currentUser()` and redirects to `/login?next=%2Fplane`; the middleware
refreshes the session for it (`/plane` in `PROTECTED_PREFIXES`), robots keeps crawlers out of it, and
`EDGE_URL` names the address the *web server* uses, not a public URL. The head is deliberately quieter
than the home hero — this is an instrument panel; its numbers are the subject. `.h4`, `.badge--ok`,
`.badge--warn`, `.btn--warn`, `.notice--info`, `.grid-cards` and `.tac-card__meta` landed with it: those
names were already used with no rule behind them, and a verdict that differs from its neighbour by a word
and not a colour is not a verdict.

**The other hand's work, finished by this window.** The page, its CSS, the `plane` i18n namespace in all
six catalogues (committed ahead of the page itself by 67c8674's sweep — recorded here because it is a
fact of that commit), the robots and middleware wiring and the tsconfig dist-dir entries were written by
another hand and arrived uncommitted. This window verified and pushed them: `tsc --noEmit` clean,
production build (`NEXT_DIST_DIR=.next-plane`) completed (BUILD_ID quoted in the commit message with the
`plane` catalogue key parity machine-checked across `en`, `zh`, `zh-TW`, `fr`, `ar`, `he`). The two
leaderboard/my-football one-liners ride the same commit: the empty-state class name the design system
already ships under `.empty`, and the `.mp-hero` tint that had an element with no rule.

**Evidence.** `tsc --noEmit` exits 0; key parity across the six catalogues holds byte-for-byte in flat
form (machine-checked); the production build prints its `BUILD_ID` (see the commit message); the edge
suite is unaffected (no Java changes). CI prints its verdict on this push.

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
