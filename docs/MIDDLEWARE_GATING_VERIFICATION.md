# Middleware gating: which routes a signed-out reader reaches

Measured on plane `0d026cd` + this worktree (Next.js 15.5.25, node v24). Three claims, each carried by an
artifact named below rather than by this prose:

1. a share link for a CV and a share link for a clip both answered **HTTP 307 to `/login`**, in all three locales;
2. behind that wall, `/video/shared/{token}` answered **HTTP 500** for every anonymous reader;
3. nothing in the repository could see either fact, so both are now guarded by a static gate
   (`apps/web/scripts/qa-middleware-gating.mjs`) that calls middleware's own decision function.

## The defect

`middleware.ts` lists `PROTECTED_PREFIXES` and matches them as **prefixes** (`pathname === p || pathname.startsWith(p + "/")`),
so `/video` reached down into `/video/shared/<token>` and the entry `/portfolio` — added later, in `ed74226` — reached
into `/portfolio/shared/<token>`. `PUBLIC_EXCEPTIONS` was consulted with `Set.has(pathname)`, an **exact** lookup, so an
exemption could never have answered for a page one dynamic segment deep even if someone had listed it there.

The project already states the rule the code violated, in `apps/api/app/api/v1/boards.py:260`:

> The public door is `/tactics/shared/{token}` on purpose: a share link must never sit under the session-gated
> `/tactics/boards` path, or the person it was sent to meets a login wall.

`/tactics/shared` survived only because nobody listed `/tactics` as protected. The two surfaces that were listed met
the wall their own design rules out.

## The census that found it

`.scratch/i18nprobe/gate-census.mjs` walks every `apps/web/app/**/page.tsx`, decides whether the page gates *itself*,
and compares that to the middleware's lists. Its first version classified a page as private only when it matched
`currentUser()`, and reported 5 MISGATED rows — three of them (`/history`, `/progress`, `/settings`) were **false
accusations**: those pages gate themselves by redirecting on the API's 401 instead of reading the session locally.
The predicate now recognises both spellings, and each spelling has a witness clause in the shipped gate so the
narrowing cannot come back unnoticed. At the fixed predicate the census reads:

```
pages scanned: 59 | gates itself: 38 | public: 21
PROTECTED_PREFIXES: 20 | PUBLIC_EXCEPTIONS: 1 → 3
problem rows: 2
  MISGATED  /portfolio/shared/:x   — no path to /login, gated via /portfolio
  MISGATED  /video/shared/:x       — no path to /login, gated via /video
```

Four `UNREFRESHED` rows surfaced on the way (`/`, `/login`, `/register`, `/knowledge` read `currentUser()` without a
prefix of their own) and are recorded as **not** this defect: each of them serves a signed-out reader on purpose, and
the worst they do is render the anonymous version to a reader whose token has just died.

## The fix

`PUBLIC_EXCEPTIONS` is now a set of **prefixes**, matched by the same expression shape `PROTECTED_PREFIXES` uses, and
carries `/club/rules`, `/portfolio/shared`, `/video/shared`. The doc comment names the structural property that earns
an entry — the page never reads a session and has no path to `/login` — because an exemption keyed on a pathname is a
hiding place for the next route given the same name.

## The second defect the wall was hiding

With the 307 gone, the page rendered — and crashed:

```
TypeError: Cannot read properties of undefined (reading 'frame_count')
  at .next/server/app/video/shared/[token]/page.js
```

`app/video/shared/[token]/page.tsx` typed its read as `VideoReport`, the owner's shape (`asset` / `analysis` /
`detections` / `stages` / `job`), while `GET /video/shared/{token}` has always returned a **flat ten-field summary**
(video.py:374-385) with no `asset` key at all. `report.asset` was `undefined` on every request; the middleware had
been returning 307 ahead of the render, so no reader ever reached the line. The page now declares the door's actual
shape as `SharedClip`, renders the record the door discloses, and says plainly that the footage and the sampled frames
are served to the account that uploaded them. `docs/M5_WEB_VERIFICATION.md:169` claimed the page "renders the clip
publicly" — that claim is corrected in the same commit, because it was false at every commit that carried it.

Chosen deliberately: **no API route was widened**. Making the shared door disclose the analysis and detections would
have matched the board precedent (`read_shared` returns the whole renderable row) and would have fixed the page's
timeline panels too, but it decides what a token-holder may see about somebody else's upload — a disclosure question,
not a crash fix. It stays open, recorded at the end of this file.

## The shipped gate

`apps/web/scripts/qa-middleware-gating.mjs` — static, no browser, no server, no port. It slices
`const PROTECTED_PREFIXES … function isProtected …` out of `middleware.ts`, transpiles that region with the repo's own
TypeScript, and **calls the shipped function** on every page route, so changing the matching logic — not just the
lists it reads — moves the verdict. Six checks, each able to refuse alone: the region compiled to a callable; the
walked population is ≥ 40 and contains all three share routes; both session spellings have a witness page; no public
page is gated (`MISGATED`); no exempted page gates itself (`EXEMPTED-WHILE-PRIVATE`); no exception matches a route
that does not exist (`STALE-EXEMPTION`).

`node scripts/qa-middleware-gating.mjs` → `59 pages | 38 read or redirect to a session | 34 gated | green`, exit 0.
`scripts/qa-gate-inventory.mjs` accounts for the new file without a ledger entry: `browser=false server=false
gates=[scripts/check.sh,.github/workflows/ci.yml]`.

## Witness: 8 runs, 8 matched

`.scratch/i18nprobe/arms-gating.mjs`. Each arm splices one line, runs the gate, requires the predicted RED row by
**name**, then byte-restores and re-hashes; it also re-reads each carrier before every arm and aborts if a concurrent
writer moved it.

| run | mutation | predicted RED | result |
|-----|----------|---------------|--------|
| A1 | drop `/video/shared` from the exemption set | `MISGATED /video/shared/sample-token` | MATCHED (1 red) |
| A2 | restore the exact-set lookup `PUBLIC_EXCEPTIONS.has(pathname)` | both share routes `MISGATED` | MATCHED (2 reds) |
| A3 | add an exemption for `/creator/shared`, a route no page occupies | `STALE-EXEMPTION /creator/shared` | MATCHED (1 red) |
| A4 | widen `/club/rules` to `/club`, exempting a self-gating area | `EXEMPTED-WHILE-PRIVATE /club` | MATCHED (3 reds) |
| A5 | make the gate's redirect spelling never fire | `PREDICATE no page matched` + `/history` `/progress` `/settings` | MATCHED (5 reds) |
| A6 | make the gate's `currentUser()` spelling never fire | `PREDICATE no page matched \`currentUser()\`` | MATCHED (1 red) |
| A7 | break the walk so it finds no page | `POPULATION 0 pages scanned` + the three share routes absent | MATCHED (10 reds) |
| C0 | run the gate on `HEAD:apps/web/middleware.ts` — the file before this fix | both share routes `MISGATED` | MATCHED (2 reds) |

`SUMMARY runs=8 matched=8 not-matched=0`.

A4 was **not** matched on its first run, and the miss was the gate's own bug, not the arm's: check 5 computed its
`under` list with `${p}/` only, so the route that *is* the prefix (`/club`) had no evidence and exempting the whole
club area looked like a one-page change instead of a nine-page one. The gate was fixed to match a prefix the way
`isProtected` does; the arm's expectation was tightened at the same time to require the row for the route `/club`
specifically, since a row about any `/club/…` child would have passed the old gate too.

C0 is the control that decides whether the defect was real: the shipped gate, run against the middleware exactly as it
stood before this work, names both share surfaces. Nothing about the bug is asserted from prose.

## Live read

`.scratch/i18nprobe/d-read.mjs` reads all eight wired surfaces × three locales on a fresh build
(`next start -p 8825`, `API_INTERNAL_URL` → my own uvicorn on 8734), and for each row asserts HTTP 200, `<html lang>`
equal to the requested locale, the rendered `<a class="muted world-back">` text equal to `← ` + the catalogue's value
for that locale, the anchor's `href` equal to the destination that key names, and one still-literal English neighbour
per page — the neighbour is what proves the read is per-element rather than a wholesale fallback.

- before the middleware fix: **18 green, 6 red of 24**, all six the two shared pages at HTTP 307;
- after the middleware fix, before the page fix: `/portfolio/shared` green ×3, `/video/shared` **red ×3 at HTTP 500**;
- after both: **24 green, 0 red of 24**.

Tokens were minted through the API's own doors (`d-prep.mjs`: register → `/portfolio/share` → `/video/upload` →
`/video/{id}/share`), not inserted into the database, so the plane exercised the same paths a real share link takes.

## Also measured on this plane

`npm run typecheck` 0 errors; `npm run build` exit 0; the nav sense gate
(`.scratch/i18nprobe/d-sense.mjs`, which derives the key→href table from HEAD's `components/Nav.tsx`) reads
**8 of 8 files sense green**, and its own reverse control still refuses a label aimed at the wrong destination.
`npm run lint` exits 1 on this worktree for one reason only: `app/knowledge/[slug]/page.tsx:38 'tc' is assigned a value
but never used` — a file another writer holds uncommitted. `git show HEAD:…` of that same file uses `tc(`, so the red is
the in-progress edit, not this landing, and it was left alone.

## Open, recorded rather than decided

- **What a video share link should disclose.** The board door discloses a full renderable row and the CV door a
  selected set of sections; the clip door discloses a summary and the page now tells the truth about it. If the intent
  is "hand someone your analysed clip", the door has to carry `analysis` + `detections` and the bytes need a
  token-authenticated route of their own — a disclosure decision, and it should be made as a decision.
- **Four surfaces read `currentUser()` with no prefix of their own** (`/`, `/login`, `/register`, `/knowledge`):
  correct for a signed-out reader, but a signed-in reader whose access token dies mid-visit sees the anonymous home
  page instead of their own. Whether the home page deserves token forwarding is a separate question from this one.
