# M13 verification — the minutes-based development curve, rendered

`career_view["development"]` also landed in the career-view depth batch (M13 Phase 2,
`development_view` in `apps/api/app/services/simulation/career.py`): per player, the stored
appearance minutes and the world's training load fed through the engine's saturating development
curve, with the before/after/delta attribute dicts keyed by the attribute's machine name. The API
recomputes it from `career_appearances` on every read and never writes it back, so the stored squad
the rest of the page reads keeps its own attributes. This increment renders the block: the curve's
own constants, the top players by minutes, and each player's moved attributes, in all three locales,
with an explicit empty branch for the career that has not kicked off yet.

Date: 2026-10-28.

## 1. What the block publishes

| Field | Meaning |
| --- | --- |
| `players_developed`, `total_minutes` | how many players have appearance rows, and the minutes they sum to |
| `top_developed` | up to 11 players, minutes descending then name ascending; each row carries `minutes`, `training_units`, `effective_minutes`, `potential`, and `before`/`after`/`delta` dicts over all 27 attribute keys |
| `tau`, `rate` | the curve's own constants (3000 minutes, 0.18) |
| `development_formula`, `note` | the curve the engine applies and what the projection does not promise |
| `data_origin`, `is_demo_data` | as every career block carries |

The curve: `value + (potential − value)·(1 − e^(−minutes/τ))·rate`, with
`effective_minutes = match_minutes + 0.5·training_load_units`, each attribute climbing toward the
player's stored potential from his stored (or floored, 40) value and saturating so it never crosses
potential. The page prints the API's own formula string; it does no arithmetic of its own.

## 2. What the page prints

`components/CareerDevelopment.tsx` is a server component wired into the career page directly under
the season's story (`CareerHighlights`) and before the board projection. It prints the wire figures
and the API's own strings:

* A key/value grid: players with appearances, minutes on the pitch (en-GB grouped), the curve's τ
  and rate — the constants the projection actually used, not a restatement of the docs.
* For a career with appearances, a seven-column table — player, position, match minutes, training
  load, effective minutes, potential ceiling, movement. The movement cell is built from the wire's
  own `delta` dict: `attribute_machine_name spaced before→after` for every nonzero delta, joined
  with `·` — e.g. `ball control 43→44 · first touch 41→43`. The attribute names are the wire keys
  printed spaced (the player-page idiom), not new catalogue keys. A row whose deltas are all zero
  prints an em-dash.
* The API's `note` and `development_formula` under the table.
* The empty branch: "No development projected yet" plus the API's own reason. By design — matching
  the deal book's shape — the empty branch prints no formula paragraph: the formula explains what
  would have been applied, and there is nothing it applied to.
* `limitations.projections` as a warning notice, as the sibling panels do.

10 new keys under `careerDetail` in `en.json`, `zh.json` and `zh-TW.json`, worded to avoid
duplicating existing values (the value "Potential" is taken by five existing keys, so the ceiling
column reads "Potential ceiling"). The other column headers reuse `thPlayer`, `thPosition`,
`thTrainingLoad` and `thTimelineChange` from the namespaces that already own them, so the
`qa-shared-keys` ceiling stays at exactly **234 bindings / 98 rows** (it may only fall).

`apps/web/messages/README.md`'s population table moved with the catalogues: **3791 keys, 3746
translated** in each Chinese file, the same 45 named fallback tokens — and `qa-locale-tokens.mjs`
checks the table against the catalogues, so the figures are derived, not typed.

## 3. The live walk — one full-season career, one untouched career

Built with `next build` (clean) and served by `next start -p 3215` with
`API_INTERNAL_URL=http://127.0.0.1:8732`, against the private API on 8732 (the same walk database
the previous M13 panel units used).

`.scratch/development-walk.py` reused the highlights walk's two careers and **played the played
career on to the end of its eight-round season**, because the walk's first attempt exposed a real
property of the curve, not a harness bug: at three played rounds (720 minutes each) the saturating
curve had not moved a single attribute — every one of the 11 top rows printed an em-dash, a correct
rendering of a projection that had (correctly) produced no movement yet. A panel whose only visible
content at that point is dashes witnesses nothing about the movement cell, so the walk plays the
season out; the final state has 7,920 total minutes and every top row carries 1–24 nonzero deltas
(Balyn Qelmann, 720 minutes, 23 moved attributes, starting `ball control 43→44`). The walk script
now asserts `moved_rows > 0` before writing expectations.

The expected figures were read from the API response first, written to
`.scratch/development-expect.json`, and asserted against the rendered HTML by
`.scratch/check-development-page.py` — never typed into the check by hand, every sentence
interpolated from the committed catalogues, every movement string rebuilt exactly as the component
builds it. `.scratch/check-development-page.py`: **111 checks, 0 red** over `en`, `zh`, `zh-TW` ×
the played and the untouched career — the eyebrow's player count, the four key/value figures
(τ prints `3000` — the wire's `3000.0` interpolates as the JS number it is), the seven headers, all
11 played rows' six figure cells and movement cells, the note and formula, the empty branch's title
and reason, and two structural pins on the empty branch: no table, and no formula paragraph. Three
intermediate runs were red and each red was the check's own needle, fixed in the check, not the
panel: the en τ label's ASCII parens are regex groups unless escaped; the multi-word header
containment was accidentally regex-escaped; and the formula check had to move to the played branch
once the component's branch shape (formula under the table only, per the deal-book precedent) was
confirmed.

The walk JWTs expired between runs (`/login?...&expired=1`, a 307 loop the checker surfaced); the
tokens were refreshed by re-login against the same walk accounts, recorded in the expect file — no
figure was retyped in the process.

## 4. Gates

| Gate | Result |
| --- | --- |
| `tsc --noEmit` | 0 errors |
| `next build` | clean |
| `qa-shared-keys.mjs` | ceiling held at exactly 234 bindings / 98 rows |
| `qa-locale-tokens.mjs` | re-derived 3791 keys / 3746 translated from the catalogues |
| rendered walk | 111 checks, 0 red (both branches × three locales) |

## 5. Disclosures

* **master's api CI job is red from a foreign batch, not cured here.** `bb712f0` (the market's two
  signing windows) left 13 mypy errors in `market.py` (lines 495–514, `window` first bound as int
  then reassigned to the transfer-window dict). The file carries that lane's uncommitted edits in
  the shared worktree, so this unit does not touch it; the red is the foreign batch's to cure, and
  this unit's files are web-only (the web job is unaffected).
* The walk's played career reached season end (round 8 of 8), so its `development` block reflects a
  complete season. The three-round zero-movement reading above is recorded because it is a real
  property of the τ=3000 curve at short-season minute totals, not a rendering defect — a shorter
  career would legitimately print all dashes for part of its season.
* `top_developed` is capped at 11 by the API; this walk's squad is small enough that all appearance
  holders fit, so the cap's truncation branch is untested here — it is the API's own slice, and the
  page prints whatever rows it receives.
* The momentum/`rate` figures print as the wire's own JS numbers (`0.18`, `3000`); the τ label
  carries the U+03C4 glyph in all three catalogues, verified in the rendered Chinese panels.

## 6. Reproduce

```bash
# the private API (already running on 8732 with .scratch/walk-board.db,
# a copy of the QA SQLite database advanced to head)
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-board.db" \
  uvicorn app.main:app --host 127.0.0.1 --port 8732

# the shipped site
cd apps/web && npm run build
API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3215

# the walk (tokens in the expect file; refresh by re-login if expired)
python .scratch/development-walk.py          # replays the season if expectations are missing
python .scratch/check-development-page.py    # 111 checks against the rendered HTML
```
