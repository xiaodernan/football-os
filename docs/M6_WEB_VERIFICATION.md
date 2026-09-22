# M6 verification — the simulator and the world's training log in a browser

M6's engine half is documented in [`M6_VERIFICATION.md`](M6_VERIFICATION.md): the possession-block model, the
ten factor rows and nine named rates it measures per side, the block digest, and the `sim_matches` row that stores
both the report and the four inputs that produced it. This document is the browser half — the evidence that a
person can actually play a fixture with those inputs, read a result that says what it is, and get the same digest
back when the server re-plays the stored rows.

Date: 2026-09-23. Build: `NEXT_DIST_DIR=.next-ci SITE_URL=http://127.0.0.1:3211 npx next build`, served by
`next start` on the throwaway port, driven by `scripts/visual-qa.mjs` (system Chrome, puppeteer-core) against the
API on 8731, whose world is at `WORLD_VERSION = 3.2`. Nothing below is asserted by reading source: each line is a
value the browser reported.

The walk is one program for every milestone, so its total is the platform's: **190/190 checks**, 64 screenshots,
**1,037 sitemap `<loc>` entries each answering 200**, exit 0.

## 1. What is now browsable

| Route | What it is | Visibility |
| --- | --- | --- |
| `/simulate` | the account's played fixtures, plus the form that picks two clubs, two shapes and a seed | `PROTECTED_PREFIXES` — a signed-out visitor is bounced to `/login?next=%2Fsimulate` |
| `/simulate/{slug}` | one stored match: the block timeline, the measured inputs, the digest and the replay panel | same wall, and another account gets a real 404 page |
| `/world/training` | the generated world's training log — spec §65's 100 Training Sessions | public, like the rest of the synthetic world, with `Provenance` and the world disclaimer on the page |

The index's own head prints the model it will use (`possession-block-v1@1.0.0`), the club and system lists come from
the API rather than a fixture file (20 clubs, 50 systems), and the list states its own capacity: the walk read
`2 cards · 2 kept · 2 seed chips` after two matches had been played.

## 2. Three claims a played fixture makes about itself

Each was read out of the rendered page, not out of the engine's own test:

```text
PASS  a played fixture lands on its own stored report with digest, seed and model version printed
      — /simulate/braa-v-cort-e55b88b85cdc5e55 · e55b88b85cdc5e55 · SEED 20260922
PASS  re-running the stored inputs server-side reproduces the digest on the row
      — stored e55b88b85cdc5e55 · replayed e55b88b85cdc5e55 · page e55b88b85cdc5e55 · row e55b88b85cdc5e55
        · possession-block-v1@1.0.0 · Identical.
PASS  the same fixture, shape and seed play to the same digest as a second, separately stored row
      — /simulate/braa-v-cort-e55b88b85cdc5e55-a034 vs /simulate/braa-v-cort-e55b88b85cdc5e55 · e55b88b85cdc5e55
```

The second line is the one worth the sentence: the panel does not ask the reader to trust a stored number, it calls
`POST /api/v1/simulate/{ident}/replay`, which re-plays from `seed + minutes + the two stored systems` and prints both
digests side by side, so a report that had been edited after the fact would show as `Differs`.

Privacy was probed the same way, from a second account in its own browser context: `page 307 → /login?next=…` for a
signed-out visitor, `options 200 · list 401` for the public parts, a 404 for the other account's report on all four
doors, and after `Delete this match` both rows answer 404 to their own owner while the list returns to empty.

## 3. The last item on the §65 list

`Training Sessions` was the one entry in the spec's demo-world table the world could not produce: the catalogue had
24 authored drills and the generated players had no history. World 3.2 gives them one — `real_training_sessions`,
100 rows, drawn across the squad in proportion to the minutes each generated player actually played, each citing a
drill from the project-authored catalogue and copying its duration and difficulty, with
`load_units = duration_min × rpe` spelled out in the row's own sentence.

Six checks in the walk belong to it:

```text
PASS  the world index counts the training log against its §65 gate instead of asserting it
      — training_sessions · 100 · 100 · MEETS
PASS  the training log is labelled demo data and prints the formula it uses
      — load_units = duration_min x rpe
PASS  every rendered load figure is the minutes and RPE on the same row, multiplied — 25/25 rows read · first: 14′ × 7 = 98
PASS  each session links the player to their page and the drill to the academy
      — /player/ranek-gener · /training/cone-weave-close-control
PASS  the focus filter chip really narrows the table to "1v1" — 4 rows · 1v1
PASS  the training log is a sitemap entry while the academy it links into is not — listed · drill pages absent
```

The `/world` contents table needed no change to gain its row: it iterates the API's own `counts` and compares them
against the API's own `gate`, so the §65 column is measured on the request rather than written into the page. The
drill links cross into the sign-in wall on purpose, and the page says so in one line; the academy's own pages stay
out of the sitemap, which is the check above.

## 4. The defect this walk found, and what it cost to fix

An earlier run of this same walk — before the training log existed — failed the `/login` round trip with
`129/135`: the browser had been signed out by its own requests. That was not a harness problem. The refresh cookie
rotates on every proxied call, and the web tier fires several calls per navigation; two of them racing carried the
same old cookie, and the second was treated as a *replay*, which revoked the whole family. A user could be logged
out by loading one page.

The fix is in the auth layer and the proxy together, and it is documented where it belongs — `docs/adr/ADR-003-auth.md`
carries an amendment: rotation needs a reuse grace window (`REFRESH_REUSE_GRACE_SECONDS`, default 60, in
`apps/api/.env.example`). Inside the window a repeated credential is the same browser racing itself and is served;
past it, a revoked token arriving back destroys every session of that account and answers `refresh_reused`, which is
the replay response a real theft should get. Logout now deletes the row instead of flagging it, so a dead credential
cannot be re-admitted by its own grace window, and the proxy makes a refresh per cookie value single-flight. Four
tests in `tests/test_api_flow.py` cover the window, the stale replay, the missing cookie and the logout; they
manipulate `revoked_at` directly rather than sleeping through a minute.

## 5. What the console gate is now able to say

The walk ends by failing if Chrome logged any error it did not plan to provoke. Two of the walk's own privacy
checks *ask* for a 404 — the second account reading someone else's match, and a deleted match being re-read — and
Chrome reports a failed request as `Failed to load resource: … 404 (Not Found)` without naming the request. The line
was being attributed to `page.url()`, i.e. to wherever the reader was standing, so a provoked 404 on `/simulate`
read as a page defect and the real URL never appeared.

The handler now attributes resource errors by `message.location().url`, so the provoked list matches the request
path (`/api/v1/video/{id}/file`, `/api/v1/simulate/{slug}`) and anything else says which URL failed. That change
paid for itself immediately: the run after it failed with `HTTP 404 /world/training/world/training`, which is the
walk's own new check prefixing an already-absolute chip href. A page-level attribution would have printed
`@ /world/training` and left the doubled path invisible. Run 5 aborted at 78/80 on that bug; run 6 is the 190/190
above.

## 6. Gates measured for this increment

`ruff check` and `ruff format --check` clean, `mypy` clean on 67 modules, **317 API tests green on both engines**
(throwaway SQLite and `football_os_pytest` on the pgvector container), `python -m evals.run_rag_eval` reporting
`all gates passed`, `alembic upgrade head` + `alembic check` with no drift for migration `0008`, `npx tsc --noEmit`
and `npm run lint -- --max-warnings 0` clean, `docs/api/openapi.json` regenerated from the restarted server so
`GET /api/v1/world/training` is in the committed contract, and the walk at 190/190 against a production build.

## 7. Still open in M6

1. [ ] Career Mode (§20): a manager identity with club, budget, philosophy, tactics and objectives, and seasons
   played through the engine rather than one fixture at a time.
2. [ ] Manager live challenges (§21) and the transfer market (§22) — both need the career container to exist first.
3. [ ] Squad, training and finance carry-over between matches: the engine reads the world's stored rows, but nothing
   yet writes back to them.
4. [ ] A match events table (`sim_events`) so the block timeline can be quoted by minute instead of regenerated.
5. [ ] `player_detail` already returns `training_log` and it is covered by API tests; the player page does not render
   it yet, so spec §4's `has_training` edge is visible from the log page, not from the player.
