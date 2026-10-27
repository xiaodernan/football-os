# M13: read-your-writes in the response cache

Date: 2026-10-27. Scope: `apps/api` only — no web files, no catalogue keys.

## 1. The defect, measured live before the fix

`cached_response_for` (`apps/api/app/main.py`) caches every 2xx JSON GET for 60 seconds,
keyed `http:{path}:{query}:{origin}:{identity}`. A successful POST stored nothing and
dropped nothing, so the write's own caller kept being served the answer the write had
just made false, for the rest of the TTL.

Measured 2026-10-27 on the private API (127.0.0.1:8732, `.scratch/walk-board.db`):
after `POST /careers/{slug}/play` returned 200, **five consecutive plain GETs of
`/careers/{slug}` returned the pre-play career view**. The web tier cannot help:
`apps/web/lib/server.ts` sends `cache: "no-store"` to Next.js's own fetch — that
directive never leaves the machine as an upstream `Cache-Control`, so the API's
middleware never sees a reason to skip its cache.

This is the defect disclosed as "queued as its own unit" in
[M13_NEXT_OPPONENT_VERIFICATION.md](M13_NEXT_OPPONENT_VERIFICATION.md).

## 2. The fix

After a 2xx non-GET, the middleware drops every cache entry that names the writing
caller, then returns the write's response:

- `TTLCache.drop_identity(identity)` (`apps/api/app/core/cache.py`) deletes every key
  whose final colon component equals the identity. The key shape makes this exact:
  `response_cache_key` percent-encodes every component with `safe=""`, so no component
  can contain a colon, and `identity=""` names the anonymous keys, whose keys end in a
  colon.
- `RedisCache.drop_identity(identity)` (`apps/api/app/core/redis_cache.py`) delegates to
  its process-local `_fallback` and deliberately does not sweep the shared store: a
  credentialed response is never written to the shared tier (RFC 9111 §3.5), so the
  shared store holds no private answer of this caller's, and sweeping it would delete
  other callers' public answers for no correctness gain.
- `CacheTier` (`app/main.py`) declares `drop_identity` so the middleware names the shape
  it depends on, not the classes it happens to use.
- An anonymous write (no `Authorization` header) drops nothing: an anonymous caller
  holds no identity their future reads could be keyed under — the next read after they
  register or sign in runs under a fresh identity with no entries at all.
- A non-2xx write drops nothing: a write that changed nothing may not invalidate answers
  that are still true.

## 3. Unit witnesses

Five tests in `apps/api/tests/test_response_cache.py` (cache trio: 42 passed, 0 failed
after the fix; `test_response_cache.py`, `test_response_cache_privacy.py`,
`test_response_cache_tiers.py`):

1. `test_a_successful_write_drops_the_callers_cached_answers` — warm GET, 2xx POST, next
   GET is a MISS that reaches the origin again.
2. `test_a_failed_write_leaves_the_callers_cache_warm` — POST 500, next GET still a HIT.
3. `test_another_callers_answers_survive_one_callers_write` — after A's write, A is a
   MISS and B is still a HIT.
4. `test_an_anonymous_write_drops_nothing` — anonymous warm GET survives an anonymous
   POST.
5. `test_drop_identity_deletes_only_the_entries_that_name_the_caller` — the mechanism
   itself: one entry per matching identity, other callers' and anonymous entries
   survive, `drop_identity("")` deletes exactly the anonymous entry.

## 4. Mutation-arms battery

`.scratch/run-cache-arms.py`: each arm is a plausible wrong implementation of the
non-GET branch; the battery predicts the red set, runs the five tests, and grades the
prediction. The file is restored from a byte backup after every arm and its sha256 is
verified at the end (`a1424f45965cfdb1…`); `PYTHONDONTWRITEBYTECODE=1` throughout.

| Arm (mutation) | Predicted reds | Observed | Verdict |
| --- | --- | --- | --- |
| control (no mutation) | 0 | 0 | clean |
| **A** — the drop call removed entirely | successful-write, another-callers | 2, same names | MATCH |
| **B** — drop only this request's own path key (`response_cache_key(path, query)`) | successful-write, another-callers | 2, same names | MATCH |
| **C** — drop regardless of response status | failed-write | 1, same name | MATCH |
| **D** — drop even when the caller is anonymous (guard removed) | anonymous | 1, same name | MATCH |
| **E** — `cache.clear()` instead of the identity drop | another-callers | 1, same name | MATCH |

Prediction correction recorded honestly: the first draft predicted arm B and arm E would
also turn the anonymous test red. Both arms swap only the drop call and leave the
`caller_identity(...)` guard standing, so an anonymous writer never reaches them —
anonymous protection is arm D's own witness. Every arm's observed reds are a subset of
its prediction with zero extras.

## 5. Live leg (post-fix)

`.scratch/ryw-live-leg.py` against the restarted private API on 127.0.0.1:8732
(`.scratch/walk-board.db`), at 2026-10-27T15:52:45Z. Caller A owns
`opponent-walk-strong-dunt-YWz8`; caller B is a freshly registered account reading its
own `/careers` list. Every verdict is the response's own `x-cache` header.

| Step | Request | Observed |
| --- | --- | --- |
| 1 | A `GET /careers/{slug}` (warm) | 200, **MISS**, played 2 |
| 2 | B `GET /careers` (warm) | 200, **MISS**, total 0 |
| 3 | B `GET /careers` again | 200, **HIT** — the near tier is serving B |
| 4 | A `POST /careers/{slug}/play` | 200 |
| 5 | A plain `GET /careers/{slug}` (no `no-cache`) | 200, **MISS**, played **3** — the write's drop; pre-fix this step replayed played 2 from the cache |
| 6 | A `GET /careers/{slug}` again | 200, **HIT**, played 3 — the re-cached answer is the post-write one |
| 7 | B `GET /careers` after A's write | 200, **HIT** — B's entries survived A's drop |

All seven checks PASS. The pre-fix control is §1's own measurement on the same door.

## 6. CI attribution during this unit

- The `api` job's **Types** step was red on master from `f4aa59a` onward: that commit
  added `for row in appearances:`, and mypy bound `row` as `CareerAppearance`, poisoning
  the dict loop below it (8 errors in `app/services/simulation/ledger.py`, a file the
  cache unit never touched). Fixed in **`28473e4`** ("the appearance loop keeps its own
  row name") by renaming the appearance loop's variable; `mypy app` green on 157 files,
  and the ledger/career tests (67) pass.
- The `web` job's **Namespace-ownership gate** is red on master for a reason this unit
  does not own: `7f17b30` committed the `notifications` namespace without declaring its
  owner. The one-line declaration already sits in the concurrent lane's uncommitted
  worktree copy of `qa-namespace-ownership.mjs`; per the shared-worktree rules this unit
  does not touch another lane's modified files and records the red as foreign.

## 7. Disclosures

- The **anonymous-write branch has no live leg**: `POST /careers/{slug}/play` requires
  auth, so an anonymous 2xx write is not reachable through that door. Its witness is the
  unit test (4) and arm D.
- The **Redis tier's drop is witnessed by delegation review plus the unit tests**; this
  unit runs no live-Redis integration leg. The delegation is one line
  (`self._fallback.drop_identity(identity)`), and the shared store's immunity to private
  answers is the already-tested `test_response_cache_privacy.py` property this design
  leans on.
- After A's write, **B can still read a pre-write answer for up to the TTL** (step 7 is
  a HIT by design). Read-your-writes promises the writer their own write, not
  cross-caller freshness; the alternative — sweeping the shared store on every write —
  would couple one caller's write to every other caller's cache and delete public
  answers that are still true.
- The drop is scoped to the near tier of the process that handled the write. A
  multi-worker deployment holds one near tier per worker; RFC 9111 §3.5 keeps private
  answers out of the shared tier, so no other worker can be holding this caller's
  private answer — the scoping argument, not an implementation accident.

## 8. Reproduce

```bash
cd apps/api
../../.venv/Scripts/python.exe -m pytest tests/test_response_cache.py --tb=short -q
../../.venv/Scripts/python.exe -m mypy app
PYTHONIOENCODING=utf-8 ../../.venv/Scripts/python.exe ../.scratch/run-cache-arms.py
# live leg: start the private API on 8732 with .scratch/walk-board.db, then
PYTHONIOENCODING=utf-8 ../../.venv/Scripts/python.exe ../.scratch/ryw-live-leg.py
```
