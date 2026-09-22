# M4 Tactical Lab — web surface verification (spec §11–§13, §62, §80)

Date: 2026-09-22 · Tier: `apps/web` · Evidence run: `202609220157` (**136/136 browser assertions**, 54 PNGs in
`docs/screenshots/`, zero browser console errors) against a **production build** served on `:3211`, API on `:8731`
(pgvector). Backend evidence: [`M4_VERIFICATION.md`](M4_VERIFICATION.md); pattern followed: [`M3_WEB_VERIFICATION.md`](M3_WEB_VERIFICATION.md).

## 1. What landed

| Route | File | Reads | What it refuses |
| --- | --- | --- | --- |
| `/tactics` | `app/tactics/page.tsx` | `/tactics/status`, `/tactics` (paged, `formation`/`temperament`/`search`), plus the first row's detail so the sample board is a real one | a value without its formula; a filter's result presented as the catalogue |
| `/tactics/{slug}` | `app/tactics/[slug]/page.tsx` | `/tactics/{ident}`, `/tactics/{ident}/counterfactual`, `/tactics?formation=` | a stored conclusion; a defending board that is a second drawing rather than a transform |
| `/tactics/compare?a=&b=&phase=` | `app/tactics/compare/page.tsx` | `/tactics/compare` + both details | itself being indexed; an invented row when only one side is chosen |

`/tactics/{slug}` is the last route shape §80 lists that the site did not serve, and `sitemap.ts` gained its 50 entries
**in the same commit** as the page. `/tactics/compare` is `noindex, follow` and is not advertised, for the same reason
`/world/search` is not: a question is not a document.

Shared parts: `components/pitch.tsx` (the board), `components/tactics.tsx` (authored badge, band legend, metric table,
verdicts, change navigation, system card), `styles/tactics.css`, and the `TacticsStatus` / `SystemBrief` /
`SystemDetail` / `CounterfactualResponse` / `CompareResponse` types in `lib/types.ts`.

## 2. The board is drawn from metres

`components/pitch.tsx` is a **server component** — plain SVG, no canvas, no chart library, no client JS. Its `viewBox` is
the pitch itself: 68 × 105 with the markings from Law 1 (centre circle r 9.15, penalty area 40.32 × 16.5, six-yard box
18.32 × 5.5, penalty spot 11 m, goals 7.32 m wide and drawn outside the goal line). A player at `{x: 26, y: 24}` is
plotted 26 m left/right and 24 m up the pitch, so the distance you can measure on screen with a ruler is the distance the
API measured in `metrics_in`.

* Dots are coloured by band, and the legend is drawn from the same four values the payload carries.
* When a counterfactual is open, the **before** positions render hollow and each moved player gets an arrow — so the change
  is visible as a displacement, not asserted in prose. `?change=…` is a URL, so the arrow can be shared.
* Text uses the metre coordinate system too (`font-size: 2.5px` = 2.5 m tall glyphs), which is why the labels stay legible
  and proportional at 375px instead of collapsing.

## 3. Honesty rules this surface enforces

- **Authored, not demo.** `AuthoredBadge` renders `PROJECT AUTHORED` from `data_origin === 'project-authored'` and
  `is_demo_data === false`, and the API's disclaimer — "no tracking data" — is printed in the same strip. The knowledge
  corpus set this precedent; the tactics catalogue follows it, and the QA walk asserts the label is present so a future
  refactor cannot quietly fold authored content into "DEMO DATA".
- **No measurement without its formula.** `MetricTable` prints the `formula` column for all eight measures on both phases;
  the assertion counts the formula cells and rejects any that is shorter than a sentence, so the column cannot be
  satisfied with a dash.
- **Both boards are one structure.** The page states the transform with its own numbers (`block_depth`, `press_line_y`) and
  asserts both phases carry the same eleven roles; the API's `transform_note` is what produced that sentence.
- **The counterfactual is recomputed.** The page shows what the API measured just now (`recomputed: true`), and if any
  position had to be clamped back onto the grass, the page says so with the count instead of silently shortening the arrow.
- **An unknown `?change=` is refused by name**, listing the six that exist; an unknown slug is a 404; a half-chosen
  comparison explains itself rather than rendering an empty table.

## 4. What the browser walk adds

Thirteen desktop assertions and four new mobile surfaces (run total **136/136**, 54 PNGs): catalogue fully served to a
signed-out visitor · all 50 systems advertised in the sitemap and neither query page · `PROJECT AUTHORED` present and
`DEMO DATA` absent on `/tactics` · the API's disclaimer repeated verbatim · eight formulas plus one real
eleven-player board on the index · the nav entry · both phases drawn from the same eleven roles (22 dots) · every
measurement repeating its rule (16 formula cells) · the graded verdicts on the page being the API's own strings
character for character · the transform stated with its own numbers · `Article` structured data whose URL is the
canonical · arrows exactly equal to the payload's moved positions with all eleven before-positions hollow ·
`space_behind` rising exactly 8.00 m when the back line is raised 8 m · an invented change refused by name with the
six real ones listed · the comparison measured on both sides, `noindex`, and differing where the vocabulary claims it
differs · an unknown slug answering 404.

At 375px the index, the detail page, the counterfactual and the comparison each hold with zero horizontal overflow, and
all 11 navigation links stay visible.

## 5. Defects the walk caught (all real, all fixed here)

1. **Two components, two vocabularies, one fact.** `/tactics` asked for a provenance badge and got
   `SOURCE · PROJECT-AUTHORED` from `OriginBadge`, because the lab had also grown its own `AuthoredBadge` saying
   `PROJECT AUTHORED`. The QA's assertion is what surfaced it. There is now one badge — `OriginBadge` decides between
   `DEMO DATA`, `PROJECT AUTHORED` and `SOURCE · x` — and `AuthoredBadge` is deleted. A second badge for the same
   column is exactly how labelling drifts back in.
2. **`.badge--authored` had no CSS.** `/knowledge/{slug}` had been rendering that class unstyled since M2 — it looked
   like a badge because badges have a border, not because anything declared its colour. Added to `styles/globals.css`
   and to the class-vocabulary comment at the top of that file.
3. **The board clipped its own players.** The `viewBox` gave 1.5 m of margin while a dot is 2.9 m in radius, so a
   player on the touchline was drawn in half — and the "own goal line" caption sat *below* the viewBox and never
   rendered at all. Now ±38 m horizontally with room for the goal boxes and both captions.
4. **A check that could only fail.** The first version compared `disclaimer.slice(0, 60)` against `innerText`, which
   re-breaks a long paragraph at each visual line — a passing page scored as a failure. The assertion is now two
   checks (labelled correctly; disclaimer present with whitespace collapsed), and the label check additionally asserts
   the page never says `DEMO DATA`, which is the part that actually matters for authored content.
5. **A borrowed number on the index.** The metrics table initially filled measures the list payload doesn't carry with
   values from the *status* sample — two systems in one table. It now shows one named system's own eight measures, and
   `MetricTable` renders an absent value as "not on this card" instead of inventing one.

## 6. Reproduce

```bash
cd apps/web && bash scripts/verify-production.sh      # tsc, next lint, build, serve :3211, prove the build, QA, release
curl -s "http://127.0.0.1:3211/tactics/4-3-3-press-high?change=raise-back-line" | grep -c "tac-formula"
curl -s http://127.0.0.1:3211/sitemap.xml | grep -c "<loc>"   # 1034 (983 + the index + 50 systems)
```

## 7. What this does not claim

* **The board is not editable yet.** §65's M4 gate says drag/draw/save/share: this surface *renders* authored boards and
  recomputes named changes. A user drawing their own eleven players needs an owned `tactic_boards` row, an owner and a
  share token — that is the next increment, and until it exists there is no user-generated tactic anywhere on the site.
* **No animation yet.** The two phases are stored as one structure plus a documented transform, which is exactly what an
  interpolation needs, but nothing tweens between them on screen.
* **No AI tactical commentary.** The verdicts are measurements graded against the catalogue's own quartiles, with the
  percentile quoted in the sentence; no model writes them, and no claim here is checked against a knowledge-corpus
  principle. `AI_POLICY.md` §5 says so plainly.
* **Not real football.** No club, competition or match is represented; the coordinates were written here. Every page prints
  the disclaimer, and `/tactics/{slug}` has no image assets to license.
