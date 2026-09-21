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

## 3. Known gaps (not hidden)

- **The QA PNGs are on disk, not in git.** `docs/screenshots/*.png` is ignored because each run re-stamps 9 MB
  of images and because the global pre-commit hook scans staged bytes for conflict markers and false-positives
  on the deflate streams inside two of them. The checks those images prove are reproduced as text in §2.2 and
  indexed in `docs/screenshots/README.md`. The hook was not bypassed.
- **CI has never run.** The repository has no git remote yet, so `.github/workflows/ci.yml` — including the
  Postgres test step added in this pass — is unexecuted automation. Everything it claims to run was instead
  executed by hand on this host and is reproduced in §1.
- **The mobile pass covers 6 surfaces.** `/history` and a drill detail page are not yet checked at 375px.
- **`progress.export` and account deletion are tested via the API only**, not through the settings UI.
- Achievement awards now work on both databases, but the achievement *pages* (spec §37 surfaces) are M4+ scope.
- Each QA run leaves one real account (`visual-qa-<stamp>@footballos.test`) plus its session in whichever
  database the dev servers use. That is deliberate — it is what proves persistence — but the dev database
  accumulates test users and should be reset before any public demo.
