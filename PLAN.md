# PLAN — the work that is left, in the order it should be done

`ROADMAP.md` says which milestone is open and what has been proven. This file says what to build **next**, in
order, with the evidence each item has to produce before it counts as done. It is written to be picked up cold:
every item names the files it touches, the gate it must pass, and the thing that would make it a lie.

Rule inherited from spec §96 and this project's own practice: **an item is done when its claim is measured, not
when its code exists.** A number in a document that no command reproduces is not evidence.

Last updated 2026-10-08.

---

## Done, and what it cost

| Item | Landed | Evidence |
| --- | --- | --- |
| **0. one gate, not three** | ✅ 2026-09-30 | `scripts/check.sh` and CI both run `python -m ruff check` with no path arguments. Proven by planting an unused import in `evals/`: invisible to the old target, caught by the new one, and the script exits 1. |
| **1. §13's 3D pitch** | ✅ 2026-09-30 | `components/pitch.tsx` projects the board's own metres isometrically; `237/237` walk checks on a production build, with a check that recomputes every dot from its metres and another that holds the projected lawn inside its `viewBox`. `docs/M4_WEB_VERIFICATION.md` §8. |
| **2a. §81's `locales` claim** | ✅ 2026-10-01 | `tests/test_locale_claims.py` binds `locales` to the catalogues in both directions. Found that `zh.json`/`zh-TW.json` are 278/278 copies of English, so the field stays `["en"]` — and now cannot be moved without a translation or left unmoved with one. |
| **2b. §81's translations + the switcher** | ✅ 2026-10-06 | `LocaleSwitcher` writes the `fo_locale` cookie middleware has always read; `locales` moved to `["en","zh","zh-TW"]`; both Chinese catalogues are now **complete** — `zh` 392/394 translated (fallbacks: `scout.placeholder` already Chinese in the English file, `settings.apiBadge` = 'API {status}'), `zh-TW` 393/394 (`settings.apiBadge` only), `zh-TW` written as Traditional rather than converted. `test_locale_claims.py` 4/4; the locale walk drives the real switcher and reads the repainted shell. |
| **2c. the catalogue is reachable from 14 files** | 🟡 2026-10-09 | **Coach is wired** — a 78-key `coach` namespace **written from the page's own 78 strings** across three files (`page.tsx`, `CoachAsk`, `PlanBuilder`), not wired from keys that already existed like scout/career/world were. Earlier: `scout` (99 keys), `career` (17 of 23), `world` (54). **14 files now read a catalogue.** Walk 196/199 with three coach checks (the Chinese read, the English-gone read, and the switch-back). Still literals: tactics, training, progress, history, knowledge, club, community, video, simulate, market, challenges. `validation` (8 keys) waits for a form that shows custom messages. |
| **— `common` is 97 keys and 3 are read** | ⚠️ not the next step | Measured 2026-10-09. `common` is generic UI vocabulary (`save`, `cancel`, `loading`, `yes`, `no`, `or`, `of`) and **three keys are read** — `language`, `demoMode`, `demoModeTitle`, all from `Nav`/`LocaleSwitcher`. Of its 97 English values, 16 appear as a literal anywhere in `app/`+`components/` and 80 appear nowhere: there is no `Loading…` string in the project at all. The app's real vocabulary is domain words (Player, Age, Position, Club, Expected goals, Fixture) which belong to pages, not a shared namespace. So the plan's "wire `common` next" had nothing to wire; the next work is a page, and `coach` was the next page a reader meets. |
| **4. §61 account erasure end to end** | ✅ 2026-10-06 | `GET/DELETE /auth/account`: preview inventories every row and byte, one confirmed transaction, media containment refused before any write, last-owner blocking (409), §60's third 403 code (`invalid_password`) registered. 4 tests including the escaping-storage-key case a planted-defect probe demanded. |
| **§38/§60 portfolio share + PDF** | ✅ 2026-10-06 | `POST/GET/DELETE /portfolio/share[/{token}]`, `/portfolio/cv.pdf` (reportlab), robots keeps both off crawlers. Committed with the two above because all three share one contract file. |
| **— migration `0026`** | ✅ 2026-10-07 | Not on the plan. `alembic upgrade head` did not run at all: `0026` and `2e197f085070` both revised `0025`, so the graph had **two heads** and every fresh database, gate run and deploy failed at the first step — invisible because `python -m seed` builds its schema from the models. Behind that: `sa.Index` inside `create_table` (invalid SQL), `now()` (not a SQLite function), and a table declaring `id INTEGER` where the model says `String(40)`, with no `updated_at`. Verified: `0025 → 2e197f085070 → 0026`, `rc=0`, `alembic check` clean. |
| **— every commit is refused on this host** | ⚠️ environment | Found 2026-10-09. The global `pre-commit` hook (`~/.codex/git-hooks/pre-commit`) ends with `trap 'rm -f "$FILES_TMP"' EXIT`, and `FILES_TMP="${TMPDIR:-/tmp}/codex-global-pre-commit-files.$$"`. This host exports `TMPDIR=C:\Users\18414\AppData\Local\Temp`, so the path becomes `C:\Users\...\Temp/codex-global-pre-commit-files.958` — mixed separators — and the safe-delete shim refuses it: `[safe-delete][SAFE_DELETE_INVALID_PATH] embedded drive prefix is not allowed`. The trap's failure becomes the hook's exit status, so the hook prints *passed* and then fails the commit. **The checks are not the problem and the hook is not wrong to run**: `TMPDIR=/tmp git commit …` commits normally. Worth fixing in the hook (use `mktemp`, or strip the drive) rather than in every caller. |
| **— this host cannot run `next build` twice** | ⚠️ environment | Not on the plan. The Recycle Bin rejects the operation (`Unknown { description: "Some operations were aborted" }`), so the safe-delete shim times out on the delete Next performs against a **pre-existing** dist directory. The build compiles, then dies before writing `prerender-manifest.json`, leaving output that cannot be served. Building with the directory absent works. `scripts/check.sh` runs `npm run build` once, but any second run in a row fails here, and `rm -rf`-style cleanup of a build directory hangs. |
| **— migration `2e197f085070`** | ✅ 2026-09-30 | Not on the plan; found by trying to run the SQLite leg it broke. Unadjusted autogenerate, PostgreSQL-only DDL, a `downgrade()` that could not run anywhere, and each new column indexed twice. |
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
| M11 Multi-Agent | ⬜ not started — and §30 Knowledge Graph waits on it by decision | `docs/SPEC_COVERAGE_AUDIT.md` |
| M12 Hardening | 🟡 §61 account erasure landed 2026-10-06; the rest of M12 (load, ops) untouched | `docs/SECURITY_AUTHORIZATION_VERIFICATION.md` |
| §81 i18n | 🟡 catalogues full, switcher works, shell switches; **45 files bind a translator (63 bindings)** — nav/auth/scout/career/settings/world plus `common`'s verbs, nouns and both scanned label shapes. Still English literals: the ten content-page namespaces, which have no keys yet. | the grep that counts `useTranslations`/`getTranslations` callers, and the value-derived label census (shape A 0, shape B 4 — the four are sense skips) |

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
- `common` is now closed on both scanned shapes. It is **not** closed on a third: a label in an **attribute**
  (`aria-label="Search"`) is neither shape A nor shape B, and no scanner here reads it.

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
