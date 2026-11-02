# M13 verification — the career page's signing window (item 5, web half)

The API has published `career_view["window"]` since 2026-10-28 (`transfer_window()`, 2026-10-27),
and on 2026-11-02 (`4847472`) the block began counting the rounds a window covers —
`window_from_round`, `window_to_round`, `played_in_window`, `signing_rounds_left`. Nothing read
those four fields. This unit prints the block on `/career/[slug]`, between the deal book and the
fixture list, so the page answers "may this career sign in the round about to be played?" without a
trip to `/market`.

Date: 2026-11-02.

## 1. What the block publishes

| Field | Meaning |
| --- | --- |
| `state`, `round`, `round_in_season`, `season_index`, `season_rounds`, `season_source` | the round a deal would use, the season it falls in, and where the season's length was read |
| `windows` | the season's ranges as `{from_round, to_round, label}`, already clipped and merged by the API |
| `in_window`, `window_from_round`, `window_to_round` | the label and range the next round falls inside; empty and `null` when closed |
| `played_in_window`, `signing_rounds_left` | rounds of that range already stored as fixtures, and rounds still signable (this one included); both `0` when closed |
| `opens_at_round`, `opens_at_season`, `opens_in_rounds` | the next opening, present when the round sits outside every range |
| `formula` | `WINDOW_FORMULA`, including the sentence that the round's generated fixture is read from the world, never rewritten |

## 2. What the page prints

`apps/web/components/CareerWindow.tsx` is a server component wired in once, under
`CareerContracts`. It takes the translator, `view.window` and `limitations.projections`, and prints
only the wire's figures:

* An eyebrow naming the round, the season and the state, then six key/value rows: the next round, the
  season and its source (the source printed as the API's own machine string), the containing range
  (`rounds {from}–{to}` or an em-dash), the rounds already played in it, the signing rounds left, and
  the next opening (or the wire's own "the next deal falls inside it" when open).
* The season's ranges as a three-column table (first round, last round, label); the row whose label
  equals `in_window` carries the live badge, so the highlight is a string comparison, not arithmetic.
* A closed-window notice naming the next opening and the rounds until it, shown only when the state
  is closed and the wire published an opening.
* The API's formula under the label `The window's arithmetic`, and the page's `projections`
  limitation as a warning notice.
* The empty branch: when `windows` is empty (no horizon), a titled block says the API reads the
  window open rather than closed, plus the API's own reason for that shape.

21 keys were added to `careerDetail` in `en.json`, `zh.json` and `zh-TW.json` (327 → 348 keys per
locale; catalogue population 4012 → **4033**). Every new English value is distinct from every other
namespace's value, so `qa-shared-keys` stays at exactly **234 bindings / 98 rows**. No key was added
to `market`, whose catalogue another lane is editing. `messages/README.md` now states **3988 of
4033** in both Chinese rows.

## 3. The live walk — one closed career, one open career

Built with `next build` (clean) and served by `next start -p 3215` with
`API_INTERNAL_URL=http://127.0.0.1:8732`, against a private API on 8732 whose SQLite is
`.scratch/walk-window.db` — a copy of the previous M13 walk database, advanced 0041 → 0048 by
`alembic upgrade head`. The careers are the two development walk's own:

* **Closed:** `highlights-walk-played-braa-R58n`, round 9 of a 14-round season, no window contains
  round 9 (ranges are 1–4 and 6–8). The page prints `closed`, both counts `0`, and the next opening
  at season 2 round 1, six rounds away.
* **Open:** `highlights-walk-fresh-dunt-uQAK`, round 1, inside "the opening window" (rounds 1–4).
  The page prints `open`, `played_in_window = 0`, `signing_rounds_left = 4`, and no closed notice.

`.scratch/window-walk.py` logs in, reads both `GET /careers/{slug}` answers and writes
`.scratch/window-expect.json`; `.scratch/check-window-page.py` fetches the rendered HTML with the
walk cookie, extracts the panel by its title, and rebuilds every expected sentence from the
committed catalogues and every figure from the expect file. **114/114 checks, 0 red** over
`en` / `zh` / `zh-TW` × the two careers: the eyebrow, all six rows, three headers, both range rows
with their API labels, the formula, the limitation, the state-specific notice, and the absence of
the other branch's notice.

One intermediate run was red in six checks, all the formula row: React's server renderer separates
adjacent text nodes with `<!-- -->`, and the checker's tag stripper turned that comment into a
space (`arithmetic :`). The fix was in the checker (strip comments before other tags), not the
panel. The walk JWT expired between runs (a 307 loop the checker surfaced); the token was refreshed
by re-login against the same account, and no figure was retyped.

## 4. Gates

| Gate | Result |
| --- | --- |
| `pytest tests/test_transfers.py::TestTransferWindow` | 9 passed (the block this page reads) |
| `npm run typecheck` | 0 errors |
| `npm run lint` | no warnings or errors |
| `npm run build` | clean |
| `qa-i18n-literals`, `qa-unused-keys`, `qa-icu-messages`, `qa-locale-completeness`, `qa-shared-keys` | all passed; 4033 keys per locale, 0 unused, ceiling held at 234 / 98 |
| `qa-population-floor`, `qa-locale-content` | passed; baseline 3600 → 4033 |
| rendered walk | 114/114 checks, 0 red |

## 5. Disclosures

* **The shared worktree carries another lane's uncommitted keys.** The market lane had 25 uncommitted
  `market` keys in `messages/*.json` while this unit's walk ran, so the working tree's population
  read 4058 and `qa-locale-tokens` / `test_locale_claims` red on that difference. This unit's commit
  stages its own 21 `careerDetail` keys on HEAD's catalogues (4012 → 4033) and states 4033 / 3988 in
  the README, which is the figure the committed tree holds; the two gates recompute that number from
  the committed bytes, not from this shared worktree.
* **No no-horizon career exists in the walk database**, so the empty branch is rendered by the
  component but not walked. Its wire shape is the API's own zero-horizon return, exercised by
  `TestTransferWindow`.
* **The season length reads 14 rounds here.** The development walk stopped at round 8 because the
  world table then held fewer clubs; the window judges the horizon the world holds at read time. It
  is the same horizon the season board and the deal book receive in the same payload.
* **The walk is an HTML walk, not a screenshot session.** It asserts the rendered server output with
  the same cookie a browser would send; no visual pass was taken on this unit.

## 6. Reproduce

```bash
cd apps/api && python -m pytest tests/test_transfers.py::TestTransferWindow -q
cd apps/web && npm run typecheck && npm run lint && npm run build
cd apps/web && API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3215
python .scratch/window-walk.py && python .scratch/check-window-page.py
```
