# M0 + M1 verification report

Date: 2026-09-21 · Host: Windows 10 (x64) · Python 3.11 · Node v24.18.0 · Docker image `pgvector/pgvector:pg16`

Every claim below is a command that was run on this machine, with the output it produced. Where a gate is
only partly met, that is written down instead of glossed over (spec PRINCIPLE 3, §88).

Ports owned by this project: API `8731`, web `3210`, Postgres `54321`.

---

## 1. M0 — foundation

### 1.1 Static gates (apps/api)

```
$ python -m ruff check .
All checks passed!

$ python -m mypy app
Success: no issues found in 28 source files
```

### 1.2 Test suite on both supported databases (ADR-002)

`tests/conftest.py` defaults to a throwaway SQLite file and honours
`FOOTBALL_OS_TEST_DATABASE_URL` for the Postgres leg; the fixture refuses any URL whose name does not
contain `test`, because it drops and recreates the schema so that per-run isolation matches SQLite.

```
$ python -m pytest -q                                       # SQLite
.......................                                     [100]  23 passed

$ FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest -q                                       # PostgreSQL + pgvector
.......................                                     [100]  23 passed
```

Running the same suite on PostgreSQL earned its keep immediately — see §1.5.

### 1.3 Migrations on real PostgreSQL + pgvector

```
$ DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os" python -m alembic upgrade head
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.

$ ... python -m alembic check
No new upgrade operations detected.

$ ... python -m alembic current
0001 (head)

$ docker exec football_os_db psql -U football -d football_os -tAc \
    "select extname from pg_extension; select count(*) from information_schema.tables where table_schema='public'"
plpgsql
vector
21
```

The `docker compose` stack in `infra/` is healthy (`football_os_db`, `Up (healthy)`), the extension is created
by `infra/postgres/init-extensions.sql`, and the ORM models and the migration agree (no drift from `alembic check`).
This closes the last open M0 box in `ROADMAP.md`.

### 1.4 The API really runs on PostgreSQL, not only on SQLite

A second instance was booted against the compose database on port `8732` and driven over HTTP:

```
$ DATABASE_URL=postgresql+psycopg2://… APP_SECRET=… python -m uvicorn app.main:app --port 8732
$ curl :8732/healthz                            -> {"status":"ok","demo_mode":true}
  POST /api/v1/auth/register                    -> 201, access token
  POST /api/v1/players                          -> 201, ply_YQr0neWl8gLyjyio
  GET  /api/v1/coach/today                      -> demo_mode=true, recommendation rondo-press-resistance
  POST /api/v1/trainings/sessions               -> ses_hhgFdnF2is7e31LJ
  POST /api/v1/trainings/sessions/…/complete    -> xp_awarded=60, new_achievements=["first-session"],
                                                   skill_progress rows=4
$ psql "select self_notes, status from training_sessions where id='ses_hhgFdnF2is7e31LJ'"
pg leg round trip|completed
```

The verification server on `8732` was stopped again afterwards; `8731` remains the project's dev instance.

The documented setup path also works on PostgreSQL:

```
$ DATABASE_URL=postgresql+psycopg2://… python -m seed --with-demo-user
training catalogue: 0 rows synchronised
DEMO account ready: demo@footballos.local / demo-password-123 (player Demo Midfielder, OVR 51)
```

(0 rows because that database was already migrated and seeded by the earlier run; the DEMO account label is
what matters for spec §62.)

### 1.5 Defect found and fixed by the PostgreSQL leg

`app/services/achievements.py` built award ids as `f"ua_{slug}_{user.id}"` = 42 characters into a
`VARCHAR(40)` primary key. SQLite accepts that silently; PostgreSQL does not:

```
sqlalchemy.exc.DataError: (psycopg2.errors.StringDataRightTruncation)
value too long for type character varying(40)
[SQL: INSERT INTO user_achievements (id, user_id, achievement_id, awarded_at) VALUES (...)]
```

Any user earning an achievement in production would have hit a 500 on session completion. Fixed by using the
project's normal opaque id (`new_public_id("ua")`); the `(user_id, achievement_id)` uniqueness the composite
id was trying to encode is already declared as `uq_user_achievement` in the model, so no migration was needed.
`test_skill_points_bank_until_an_attribute_moves` now covers the award path on both databases, and CI runs the
whole suite against pgvector so the next instance of this class of bug is caught before merge.

### 1.6 API contract snapshot

`scripts/export_openapi.py` regenerates `docs/api/openapi.json` from the running service:

```
$ python ../../scripts/export_openapi.py
wrote docs\api\openapi.json — 22 paths, 26 operations, schemas=13
```

---

## 2. M1 — the player + AI coach vertical slice

### 2.1 Web tier

```
$ npx tsc --noEmit
(no output; exit 0)

$ NEXT_DIST_DIR=.next-ci npx next build
Route (app)                                 Size  First Load JS
┌ ƒ /                                      168 B         106 kB
├ ƒ /_not-found                            131 B         103 kB
├ ƒ /api/v1/[...path]                      131 B         103 kB
├ ƒ /coach                               3.75 kB         110 kB
├ ƒ /healthz                               131 B         103 kB
├ ƒ /history                               168 B         106 kB
├ ○ /icon.svg                                0 B            0 B
├ ƒ /login                               1.53 kB         108 kB
├ ƒ /my-football                           179 B         106 kB
├ ƒ /onboarding                          2.72 kB         105 kB
├ ƒ /progress                              173 B         103 kB
├ ƒ /register                             2.3 kB         108 kB
├ ƒ /settings                            2.17 kB         105 kB
├ ƒ /training                            2.93 kB         109 kB
└ ƒ /training/[slug]                     1.64 kB         108 kB
+ First Load JS shared by all             103 kB
ƒ Middleware                             34.8 kB
```

### 2.2 Browser walk

`apps/web/scripts/visual-qa.mjs` (puppeteer-core driving the installed Chrome) registers a brand-new account
through the cookie proxy and walks the whole loop against the running dev servers, then re-runs the main
surfaces at 375×812 and asserts no horizontal overflow. It exits non-zero on any failed check.

Run `202609211947` — 34 checks, 19 screenshots written to `docs/screenshots/`, no browser console errors:

```
$ node scripts/visual-qa.mjs
PASS  middleware guards /my-football — http://127.0.0.1:3210/login?next=%2Fmy-football
PASS  register mints session and lands on onboarding — visual-qa-202609211947@footballos.test
PASS  player created and My Football renders — QA Mid 1947
PASS  My Football shows archetype + level
PASS  My Football labels demo mode
PASS  coach /today renders a recommendation with reasons
PASS  coach /today self-labels as rule engine demo
PASS  coach /ask returns intent + reasons
PASS  coach /plan returns a 7-day plan with sessions
PASS  training index links to a drill — /training/1v1-isolation-channel
PASS  drill scheduled from detail page
PASS  training index shows a planned session card
PASS  completion returns XP + formula — +60 XP · 50 base x quality 1.03 (execution 4/5, focus 4/5, difficulty 3/5) x difficulty 1.15 x streak 1.02 = 60 XP
PASS  completion explains skill point banking
PASS  completion returns coach feedback
PASS  notes typed in the browser persist to the session row — ok · dom="Visual QA session: felt balanced, kept the head up." · request={"execution":4,"focus":4,"difficulty_experience":3,"self_notes":"Visual QA session: felt balanced, kept the head up."}
PASS  server ledger records the completed session — sessions=1 xp=60 level=1
PASS  progress page renders level, streak and attribute history
PASS  history lists the completed session with its evidence — note shown
PASS  settings shows account email + platform status
PASS  mobile 375px: my-football renders "QA Mid 1947" with no horizontal overflow — overflow 0px
PASS  mobile 375px: my-football keeps every nav link visible — visible 7/7
PASS  mobile 375px: coach renders "Recommended session" with no horizontal overflow — overflow 0px
PASS  mobile 375px: coach keeps every nav link visible — visible 7/7
PASS  mobile 375px: training renders "min" with no horizontal overflow — overflow 0px
PASS  mobile 375px: training keeps every nav link visible — visible 7/7
PASS  mobile 375px: progress renders "QA Mid 1947" with no horizontal overflow — overflow 0px
PASS  mobile 375px: progress keeps every nav link visible — visible 7/7
PASS  mobile 375px: settings renders "Data" with no horizontal overflow — overflow 0px
PASS  mobile 375px: settings keeps every nav link visible — visible 7/7
PASS  signed-in visitor is redirected away from /login — /my-football
PASS  logout clears the session (protected route bounces to login) — status 204
PASS  mobile 375px: login-signed-out renders "Sign in" with no horizontal overflow — overflow 0px
PASS  mobile 375px: login-signed-out keeps every nav link visible — visible 7/7

34/34 checks passed. Screenshots: 19 -> docs/screenshots/
```

The small circle with an "N" that appears at the left edge of some captures is Next.js's dev-mode indicator,
which production builds do not ship.

### 2.3 M1 exit criteria, one line each

| # | Criterion | Evidence |
| --- | --- | --- |
| 1 | register | QA check 2 — new account reaches `/onboarding` through `/api/v1/*` proxy |
| 2 | create UserPlayer | QA check 3 — `QA Mid …` profile created from the onboarding form |
| 3 | derive archetype + attributes | QA check 4 — archetype + level rendered, values come from `attributes.py` weights |
| 4 | player card renders | QA checks 3-5 (desktop 1440px and mobile 375px) |
| 5 | ask the coach "what should I train today" | QA checks 6-8 — `/coach/today`, `/coach/ask` intent, `/coach/plan` 7 days |
| 6 | session from catalogue with full drill content | QA checks 10-12 — detail page shows setup/coaching points/mistakes/progression/test |
| 7 | complete session with self-rated execution | QA check 13 — `+60 XP · 50 base x quality 1.03 … x difficulty 1.15 x streak 1.02 = 60 XP` |
| 8 | XP with reason + attribute delta with reason | QA check 14 + `skill_progress` ledger (`earned/banked/needed/ceiling`), regression test in `test_api_flow.py` |
| 9 | progress shows level/streak/skill curves | QA check on `/progress` (level, streak, attribute history) |
| 10 | history lists sessions with evidence | QA check on `/history` (status, XP ledger, the note typed in the browser) |
| 11 | coach follow-up reflects new state | QA check 15 — post-session coach message with reasons |
| 12 | API + engine tests green | 23 passed on SQLite and on PostgreSQL; ruff + mypy clean |
| 13 | desktop + mobile screenshots | 13 desktop + 6 mobile PNGs captured on this host at run `202609211947`; every assertion they prove is quoted in §2.2, and the files themselves are regenerated rather than committed (see `docs/screenshots/README.md`) |

### 2.4 Explainability gap that was closed in this pass

A single session banks ~90 of the 100 skill points needed to raise an attribute, so the first completion can
legitimately show *no* attribute change. The UI was silent about that, which read as a lost reward. The
progression service now returns `skill_progress` (`earned`, `banked`, `needed`, `ceiling`) with every
completion, the session logger renders it, and `test_skill_points_bank_until_an_attribute_moves` pins the
behaviour.

### 2.5 What the browser walk exposed that unit tests could not

1. **Primary navigation was unreachable at 375px.** `.nav__links` shared one flex row with the brand and the
   account actions, so on a phone it collapsed into a clipped, scrollbar-hidden strip. The "no horizontal
   overflow" assertion passed while the screen was actually unusable — overflow alone is not mobile
   correctness. Fixed by wrapping the header into two rows under 640px, and the harness now asserts that every
   `.nav__link` has a visible box (7/7) on each mobile surface.
2. **`/favicon.ico` 404** on every page. Replaced with an original `app/icon.svg` (a pitch marking; no
   third-party imagery, per `DATA_POLICY.md`), which Next links from the document head, so the console is clean.
3. **A suspected data-loss bug was disproved layer by layer.** An earlier run reported that the note typed in
   the session logger reached the database as `null`. The check now prints the DOM value, the outbound request
   body and the stored row: the app was correct and the harness had misused the deprecated element-scoped
   `type()` signature. The same check would now catch a genuine drop at any of those three layers.

---

## 3. CI had never run: the workflow watched a branch that does not exist

**The defect.** `.github/workflows/ci.yml` was written in the initial commit (`c9e48cb`) with
`on: push: branches: [main]`. The repository's only branch — the one every commit lands on — is
`master`. GitHub therefore recorded **zero** runs for the life of the project:

```
$ gh api repos/xiaodernan/football-os/actions/runs --jq .total_count
0
```

That number was still `0` after the `f297951` push, so it was not a queue delay. The same commit
range also made the shared lint target red (`tests/test_locale_claims.py:402`, `B007`, introduced
by `525fe4d`), which CI would have reported first.

**The fix (`cc4939f`).** The trigger names `master`, and the lint target is green again.
`tests/test_ci_trigger.py` (7 cases) keeps both honest:

- it reads each workflow's own `on:` block and asks it about the branch the run is about —
  `GITHUB_REF_NAME` on a push, `GITHUB_BASE_REF` on a pull request, `git rev-parse` locally — so a
  renamed default branch fails the gate instead of silently disarming the workflow;
- it pins exactly one `Lint` step, running `bash scripts/lint.sh` from the repository root, and
  that no second lint target exists;
- it runs the shared target for real (green, on the population it announces) and again with an
  interpreter stub first on `PATH`, whose recorded argv must equal `-m ruff check` plus every
  directory the target announces — the printed population and the enforced population are one list.

At `f297951` (the parent) the file is **2 failed / 5 passed** on a plane — the coverage case and the
lint-green case. At `cc4939f` 11/11 arms matched their predictions, plane clean; `mypy app` read
155 files clean and the full SQLite suite read **1935 passed, 4 skipped, 0 failed in 832.90s**.

**What the first run found.** Run
[`40131268450`](https://github.com/xiaodernan/football-os/actions/runs/40131268450) is the first
this project has ever had. Its `api` job passed lint, types and the SQLite tests, then failed at
the migrations step; its `web` job failed at `npm ci`. Both are fresh-checkout defects no local leg
could see — a long-lived database in one case, npm 11 instead of npm 10 in the other — and both
are fixed:

- `e8fa575` — the lock records the optional peer npm 10 resolves (`@swc/helpers` 0.5.23 under
  `next-intl`), one nested entry and nothing else. `npx npm@10.9.4 ci --dry-run` is red before the
  fix and green after, as is the local npm 11; the plane at `ce0bb4e` is green under npm 10.
- `ce0bb4e` — see §3.1.

### 3.1 The migrations built naive timestamps

`alembic check` refused the first database CI ever built from scratch with 27 `modify_type`
operations. `0021`–`0025` declared `created_at`/`updated_at` (`cv_shares.revoked_at` as well) as
`sa.DateTime()`, while `TimestampMixin` declares `DateTime(timezone=True)`. PostgreSQL keeps
`timestamp` and `timestamptz` apart; SQLite stores both as `DATETIME`, so every local leg was blind
to it, and the check had only ever run against a database migrated long ago.

The five migrations now declare the type the models do — what a fresh database replays — and
`0040` moves the 27 columns on databases that already applied the older bytes. The repair skips
SQLite in both directions (one timestamp type there, and no drift to repair), and its downgrade
restores the naive shape.

Measured on this host, with `football_os_db` at 16.15:

```
# a database migrated at 0039 from the pre-fix bytes: 27 naive timestamp columns
$ ... alembic upgrade head        # 0039 -> 0040
$ ... alembic check
No new upgrade operations detected.
$ ... alembic downgrade 0039      # 27 naive columns again
$ ... alembic upgrade head        # and back
$ ... alembic check
No new upgrade operations detected.

# fresh PostgreSQL, 0001 -> 0040
$ ... alembic check
No new upgrade operations detected.   # 0 naive timestamp columns

# fresh SQLite, 0001 -> 0040 (41 revisions)
$ ... alembic check
No new upgrade operations detected.
```

`tests/test_migration_timestamps.py` (4 cases) reads the upgrade body of every migration by AST —
prose cannot be charged — and refuses a naive `sa.DateTime()`, a `timezone=False` type and a bare
`sa.DateTime` reference, with a self-test for each spelling it must refuse. It also walks `0040`'s
map against the models, so a column the models call timezone-aware cannot fall out of the repair.
The audit's migration census moved 40 → 41 in the same commit.

### 3.2 The chain's own note called `0021` a parked draft

Found while correcting the same file in §3.1: `0021_club_fixtures.py` opened with "PARKED DRAFT — not in
the tree on purpose … Move to `apps/api/migrations/versions/0021_club_fixtures.py` once the leg is green,
together with the model block sitting beside it in this directory". Every clause was false by then: the
file is tracked at that path, `alembic upgrade head` replays it on fresh databases, `0022` names it as its
`down_revision`, and the models live in `app/models/__init__.py`. It was a note from before the file moved,
and nothing read it afterwards.

Fixed at `a0af642`: the paragraph says what is true — the rows are complemented by `ClubFixture` and
`club_match_appearances` in the models, and by the club fixtures door that reads them. The design notes
below it are unchanged.

`tests/test_migration_docstrings.py` (2 cases) reads each migration's module docstring and refuses the
drafting residue: a claim that the file is outside the tree ("not in the tree", "not committed",
"untracked", "parked"), the word "draft", and any `migrations/versions/*.py` path — in a docstring that is
an instruction to move the file, not a description of what it creates. A self-test feeds the scanner each
spelling it must refuse and a plain description it must accept, so "no residue" cannot pass by matching
nothing. A census over the 41 docstrings found `0021` as the only carrier.

Reverse control: the scanner over `git show HEAD:apps/api/migrations/versions/0021_club_fixtures.py` charges
`['not in the tree', 'PARKED', 'DRAFT', 'migrations/versions/0021_club_fixtures.py']`; over the fixed file it
charges nothing. Seven arms at `a0af642`, each restoring the file by bytes and asserting the restore: the HEAD
bytes, a "not committed" sentence, a move instruction, a "draft" sentence and an emptied docstring each red the
population case (1 failed / 1 passed), while an untouched plane and a punctuation-only edit stayed green.

Whole-suite leg, owed above and now measured: the SQLite suite on a plane at `a0af642` — which carries this
change and §3.1's migration — read **1963 passed, 4 skipped, 0 failed, 328 warnings in 1259.47s (20:59)**, run
with `GITHUB_EVENT_NAME=push` and `GITHUB_REF_NAME=master` so the CI-trigger cases judge the ref a push runs on.

### 3.3 The two catalogue gates asserted nothing on a clean checkout

The freshness and population-floor gates each compared the catalogues with a baseline they read from an
**untracked file** — `.gate-baseline` and `.population-baseline`, neither of which is in `git ls-files`. On a
checkout without them, which is every clean checkout and therefore CI's:

* `qa-translation-freshness.mjs` printed `No baseline commit found`, then `CHECKS passed=0 total=0 failed=0`,
  and exited 0.
* `qa-population-floor.mjs` printed the same zero-check tally and exit 0 — and its **three-locale parity**
  check, the one claim that needs no baseline at all, lived inside the same `else` branch, so it vanished with
  the other two.
* If a baseline commit *was* named but this clone could not read it (CI's checkout is depth 1), the freshness
  gate printed "Could not retrieve baseline catalogues. Resetting baseline.", **rewrote the file to HEAD** and
  exited 0: a shallow clone certified its own stale keys and moved the baseline past them.

Measured on a scratch repository of five commits (a translated baseline, a translated follow-up, an
English-only change, a key deleted from all three locales, a key added to English only): at the parity-broken
commit — English 3 keys, both Chinese catalogues 2 — with no baseline file, both gates reported
`CHECKS passed=0 total=0 failed=0`, exit 0. With `.gate-baseline` naming a commit this repository did not
contain, the freshness gate rewrote the file to HEAD and exited 0. With a `.population-baseline` file, the
floor gate did charge a deleted key (one pass, two failures) — the file path worked; the absence path was the
defect.

The repair, in both gates:

* The baseline comes from `--base <commit>`, then `QA_BASELINE_COMMIT`, then the local file. CI sets the
  variable from the event that started the run — `github.event.before` on a push, `pull_request.base.sha` on a
  pull request — and the web job's checkout now asks for `fetch-depth: 0`, because the base commit has to be
  in the clone for any comparison to read it.
* A run with no baseline **refuses**: one failing check naming the three ways to supply one, exit 1. A named
  baseline this clone cannot read, or one that shares no ancestor with HEAD, refuses *by name* and is **never
  rewritten**.
* A shallow clone refuses before comparing — `git rev-parse --is-shallow-repository` — because `merge-base`
  would otherwise answer from the commits it happens to hold and present a truncated history as a baseline.
* The freshness gate compares against `merge-base HEAD <baseline>`, and a baseline equal to HEAD now runs the
  two checks instead of "Gate passes trivially" with a zero tally.
* The floor gate's parity check left the baseline branch and is charged whether or not a baseline exists, so
  its tally is never fewer than two checks. Its baseline can now be read out of a commit
  (`git show <base>:apps/web/messages/en.json`) — the `getPopulationAtCommit` helper had existed since the
  gate was written and had never been called.

**Witness.** `apps/web/scripts/qa-baseline-gates.mjs` builds a seven-commit scratch repository in `mkdtemp`
whose commits differ from the baseline by exactly one edit each — a stale Simplified translation, a stale
Traditional one, both stale, a key deleted from all three catalogues, and a key added to English only — and
runs the two **shipped** scripts against it through `QA_I18N_WEB`. It is wired into `scripts/check.sh` and the
CI web job. 16 checks, **16/16 green** at `4564708`, where the two catalogue gates read 2/2 and 3/3 against the
commit CI would name for that push and the script inventory is green. Two of the
sixteen written predictions were wrong on the first run and were corrected before the green was accepted: the
unreadable-baseline floor case expected `total=1`, and the floor's unconditional parity check makes its minimum
two; and the harness's first check was a placeholder that could not fail, replaced with a real assertion that
all seven fixture commits exist.

**Reverse control.** The same harness over `git show HEAD:apps/web/scripts/qa-translation-freshness.mjs` and
`…/qa-population-floor.mjs` (the pre-fix bytes, in a scratch directory) reports
`CHECKS passed=3 total=16 failed=13`. The three greens are the ones the old gates did perform: the fixture
build, the freshness comparison driven by a **baseline file**, and `--init-baseline` followed by a read. The
thirteen reds are exactly the absence, refusal and reset cases.

Local runs on the real catalogue tree at the fixed bytes: freshness **2/2**, floor **3/3** (3600 → 3600,
+0), the behaviour gate **16/16**. The script-inventory gate reports **157/159**, its two failures naming
`qa-translation-quality.mjs` — a file another unit has staged in the shared worktree; it is not in HEAD and
not part of this change.

### 3.4 The age profile's sort key stopped type-checking

The first CI run after §3's branch fix (`40338019930`) got past the steps that had never run — Lint, the web
lock — and exited 1 in the api job's `Types` step:

```
app/services/simulation/market.py:735: error: Unsupported operand type for unary - ("object")  [operator]
```

M13's retirement-risk list (`cdba698`) built its rows with a dict comprehension, and mypy infers
`dict[str, object]` from one; the sort key's `-item["age"]` therefore negates an `object`. Nothing on this host
runs `mypy app` per commit — `scripts/lint.sh` is ruff-only, the web type-check does not read Python, and the
SQLite suite exercises the door without a type checker — so every local leg was green while CI's type gate was
red. That is the gate CI adds, working as intended.

The block now sorts typed `(name, age)` pairs and builds the dictionaries from the sorted pairs afterwards. The
key is still `(-age, name)` and each dictionary's field order is unchanged, so the door answers the same rows in
the same order.

**Pre-fix control.** `git show HEAD:apps/api/app/services/simulation/market.py` (the committed bytes) was
swapped into the worktree and `python -m mypy app` read `1 error in 1 file (checked 155 source files)`, rc 1,
naming the same line and message CI named. The worktree file was then restored from a saved copy and verified by
`sha256 ac41d847…`. With the fix: `Success: no issues found in 155 source files`, and `tests/test_transfers.py`
**46 passed**. Landed at `8aa8b93`.

## 4. Known gaps (not hidden)

- **The QA PNGs are on disk, not in git.** `docs/screenshots/*.png` is ignored because each run re-stamps 9 MB
  of images and because the global pre-commit hook scans staged bytes for conflict markers and false-positives
  on the deflate streams inside two of them. The checks those images prove are reproduced as text in §2.2 and
  indexed in `docs/screenshots/README.md`. The hook was not bypassed.
- **CI had never run until 2026-10-25.** The workflow's push trigger named `main` while the only branch is
  `master`; GitHub held zero runs for the project's whole history (§3). Fixed at `cc4939f`, and the first run
  (`40131268450`) then found two fresh-checkout defects, fixed at `e8fa575` and `ce0bb4e`. Every claim in §1–§2
  was executed by hand on this host before that; the workflow now runs the same commands on GitHub's runners.
- **The mobile pass covers 6 surfaces.** `/history` and a drill detail page are not yet checked at 375px.
- **`progress.export` and account deletion are tested via the API only**, not through the settings UI.
- Achievement awards now work on both databases, but the achievement *pages* (spec §37 surfaces) are M4+ scope.
- Each QA run leaves one real account (`visual-qa-<stamp>@footballos.test`) plus its session in whichever
  database the dev servers use. That is deliberate — it is what proves persistence — but the dev database
  accumulates test users and should be reset before any public demo.
