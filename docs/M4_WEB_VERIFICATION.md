# M4 Tactical Lab — web surface verification (spec §11–§13, §62, §80)

Date: 2026-09-22 · Tier: `apps/web` · Evidence run: `202609220437` (**151/151 browser assertions**, 57 PNGs in
`docs/screenshots/`; one React hydration warning recorded, see §5.6) against a **production build** served on `:3211`,
API on `:8731` (pgvector). Backend evidence: [`M4_VERIFICATION.md`](M4_VERIFICATION.md); pattern followed:
[`M3_WEB_VERIFICATION.md`](M3_WEB_VERIFICATION.md).

Two increments are covered here: the read-only pages for the 50 authored systems, and the interactive half that
followed — the phase player, the draggable board and the token share link.

## 1. What landed

| Route | File | Reads | What it refuses |
| --- | --- | --- | --- |
| `/tactics` | `app/tactics/page.tsx` | `/tactics/status`, `/tactics` (paged, `formation`/`temperament`/`search`), plus the first row's detail so the sample board is a real one | a value without its formula; a filter's result presented as the catalogue |
| `/tactics/{slug}` | `app/tactics/[slug]/page.tsx` | `/tactics/{ident}`, `/tactics/{ident}/counterfactual`, `/tactics?formation=` | a stored conclusion; a defending board that is a second drawing rather than a transform |
| `/tactics/compare?a=&b=&phase=` | `app/tactics/compare/page.tsx` | `/tactics/compare` + both details | itself being indexed; an invented row when only one side is chosen |
| `/tactics/boards` | `app/tactics/boards/page.tsx` | `/boards` + the 50 systems for the picker | a signed-out visitor (middleware and the page both bounce to /login); it is not in the sitemap and `robots.txt` disallows it |
| `/tactics/boards/{slug}` | `app/tactics/boards/[slug]/page.tsx` + `components/BoardEditor.tsx` | `/boards/{ident}`, then `/boards/{ident}` PATCH, `/share`, `/revoke`, `DELETE` | recomputing metrics in the browser: the numbers shown are the server's last save, and the page says so while there are unsaved changes |
| `/tactics/shared/{token}` | `app/tactics/shared/[token]/page.tsx` | `/boards/shared/{token}` | an owner identity, an edit affordance, or a place in the index |

Two namespaces, deliberately: the web pages live under `/tactics/boards`, the API's user-board routes live under
`/api/v1/boards`, and a shared link (`/tactics/shared/{token}`) is public while its owner's editor is not — which is
why the share URL could not simply be a `/tactics/boards/...` path.

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

Twenty-seven desktop assertions and four new mobile surfaces (run total **151/151**, 57 PNGs): catalogue fully served to a
signed-out visitor · all 50 systems advertised in the sitemap and neither query page · `PROJECT AUTHORED` present and
`DEMO DATA` absent on `/tactics` · the API's disclaimer repeated verbatim · eight formulas plus one real
eleven-player board on the index · the nav entry · both phases drawn from the same eleven roles (22 dots) · every
measurement repeating its rule (16 formula cells) · the graded verdicts on the page being the API's own strings
character for character · the transform stated with its own numbers · `Article` structured data whose URL is the
canonical · arrows exactly equal to the payload's moved positions with all eleven before-positions hollow ·
`space_behind` rising exactly 8.00 m when the back line is raised 8 m · an invented change refused by name with the
six real ones listed · the comparison measured on both sides, `noindex`, and differing where the vocabulary claims it
differs · an unknown slug answering 404.

Four of them police the cited analysis: the page renders exactly as many cited statements as the API returned (4 of 6,
with the other 2 refused) · every `citation.ref` the page turns into a link is fetched and must answer 200, so a
passage that does not exist fails the run rather than decorating the page · the refused topics appear with the text of
the gate that refused them · and the panel is labelled `EXTRACTIVE · NO AI KEY` with no `AI-generated` string anywhere
on it.

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

6. **One React `#418` hydration warning, recorded and not reproducible.** The walk printed
   `Minified React error #418 … @ /tactics/4-3-3-press-high` once during the 140-check run. Probes since: the same route
   on the same production build, signed out → no console output; the same route on `next dev` (where React names the
   mismatched node and prints the diff) → no warning. `scripts/probe-hydration.mjs` is the throwaway that runs either
   probe. It is recorded rather than dropped, and the harness tags console errors with the route they happened on
   precisely so that a recurrence is localisable: a hydration mismatch that only appears mid-walk, after other pages
   have hydrated in the same browser session, points at session state or a previous document, not at this page's markup.

7. **The pages called the wrong namespace, and the API's 404 made it worse.** `/tactics/boards` asked the server for
   `/tactics/boards`, which matched the catalogue route `/tactics/{ident}` and answered *"No such tactical system in
   this database"* — technically true, actively misleading, and the reason the failure looked like a missing system
   rather than a wrong path. The pages now call `/api/v1/boards`, and that route answers `wrong_path` with the real
   location, so a future mix-up names itself.
8. **A persistence check that failed because reads were cached.** The walk compared the stored board before and after a
   save and saw no difference — because the second `fetch` was served from the browser's cache, not the database. The
   read is now `cache: 'no-store'` and the check reports *which index* changed, so a real save-and-reload is proven
   (dragged midfielder: 55 → 64.5 m) rather than a stale copy agreeing with itself.
9. **A leak test that could never pass.** `!/@\w/.test(html)` was meant to catch a leaked email and matched the page's
   own `@media` CSS instead. It now checks for the specific values that would be a leak (this run's account address and
   display name), which is the claim the check actually makes.
10. **Two harness-order bugs.** The shared board's mobile pass ran *after* the link was revoked, so it visited a
    deliberately dead URL; and it called `mobileSurface`, which is declared later in the walk, producing a
    temporal-dead-zone abort that discarded the rest of the run. Both are fixed by doing the 375px pass inline, while
    the link is live, and returning to the editor afterwards. `clickByText` also now reports what the page said when a
    control is missing — which is how #7 was found instead of left as `No button containing "Create and edit"`.

## 6. Reproduce

```bash
cd apps/web && bash scripts/verify-production.sh      # tsc, next lint, build, serve :3211, prove the build, QA, release
curl -s "http://127.0.0.1:3211/tactics/4-3-3-press-high?change=raise-back-line" | grep -c "tac-formula"
curl -s http://127.0.0.1:3211/sitemap.xml | grep -c "<loc>"   # 1034 (983 + the index + 50 systems)
```

## 7. What this does not claim

* **The board is editable, and stays private until you share it.** §65's drag/draw/save/share is met: eleven draggable
  players, saved coordinates (a dragged midfielder measured 55 → 64.5 m between the page and the database), a revocable
  token link, and a delete that takes the link with it. What it is *not*: collaborative (one owner, no co-editors),
  listable (there is no public gallery — that is M9's consent story), or drawn from scratch (a board always starts as a
  copy of one of the 50 systems; adding or removing a player is not offered, because eleven is what the measurements
  assume).
* **The animation interpolates two stored phases.** That is what the data supports and what the stamp says —
  `SIMULATION` plus AI_POLICY §2's sentence, asserted present in the walk. It is not a match timeline, and there is no
  event feed to animate against until M5 or M6 provides one.
* **No model opinion, and no borrowed authority.** The analysis panel on `/tactics/{slug}` is extractive: each statement
  sits beside the passage that supports it and the measurement that prompted it, and the two topics the corpus cannot
  support — width in attack, and how high a team sits — are printed as refusals naming the gate that stopped them.
  Those are real gaps in `data/knowledge`, carried in `ROADMAP.md` as corpus work to be re-measured with the RAG eval,
  not tuned away by rewording a question until it scores well enough to cite an off-topic passage.
* **Not real football.** No club, competition or match is represented; the coordinates were written here. Every page prints
  the disclaimer, and `/tactics/{slug}` has no image assets to license.

## 8. §13's 3D pitch — the same metres, projected (2026-09-30)

Spec §13 asks for 2D **and** 3D, and until this the roadmap carried "3D pitch" as an open item while only the 2D
board shipped. The 3D view is a **projection, not a renderer**: every point goes through two lines of arithmetic
applied to the same `x`/`y` metres the 2D board reads, and there is no scene graph, no camera and no dependency.

```
gx = x + 34          gy = 105 − y
screen_x = (gx − gy) × cos30 + 105 × cos30
screen_y = (gx + gy) × sin30
```

It is drawn as SVG, as a `<details>` on `/tactics/{slug}` beside the two phase boards, so it opens without client
state and stays in the document for a reader with no JavaScript. The lawn, the centre circle and the penalty arcs
are the 2D frame's own Law 1 measurements, sampled in metres and projected point by point — a circle on the grass
is an ellipse in this projection, and computing that ellipse separately would be a second piece of maths to keep in
step with the first.

**The claim, and how it was measured.** Not that it looks three-dimensional — that every dot is the page's own
printed formula applied to that dot's own metres. Each marker publishes the metres it was projected from
(`data-metres-x`/`-y`) beside the point it landed on (`data-iso-x`/`-y`), and the `<svg>` publishes the constants
it used (`data-iso-constants`); the walk recomputes each point from the metres and the constants and compares. A
drawing that had drifted as a whole could not pass by agreeing with itself.

Run on the production build of 2026-09-30, `QA_BASE=http://127.0.0.1:3218`:

```
237/237 checks passed. Screenshots: 71 -> docs/screenshots/

PASS  a system page draws both phases from the same eleven roles — 2 phase boards · 22 dots, plus the player's own eleven
PASS  the 3D board is the printed projection of the 2D board's own metres, dot by dot — 11 markers · every dot recomputed from its metres
PASS  and it shows the same eleven the 2D board shows, in the same order — 11 roles match the API's own phase_in
PASS  the projected lawn fits inside its own viewBox, so no part of the pitch is silently cut off — corners inside viewBox -6 -8 162 100
```

**Two bugs the arithmetic caught, one of them before any build.** The first draft's own comment claimed the
projected diamond ran to `y 69.5`; recomputing the four corners from the transform gives `(0, 52.5)`,
`(58.89, 86.5)`, `(149.82, 34)`, `(90.93, 0)` — so the `viewBox` as written clipped the bottom 8.5 units off the
pitch. A clipped `viewBox` is invisible when it is wrong: it still renders, still looks like a pitch, and silently
loses the far touchline. That is why the fourth check above exists — it holds the four projected corners inside
the `viewBox`, which is a property of the arithmetic rather than of the picture. The second was the board count:
the pre-existing check asserted `2` boards and `22` dots, and a third figure on the page moved both; it now
excludes the projected view and counts the two phase boards, while the 3D view is held by its own three checks.

**What this does not claim.** There is no camera, no depth buffer and no lighting, so nothing here shows what a
player would see — it is the plan view bent into a diamond, and the page says so in a sentence of its own. The
3D view is a second *reading* of the board, not a second source of truth: the metres it projects are the ones the
2D board already carries.

**Re-measured 2026-10-21, after §81's copy arc, and the arc had broken the walk's own reach.** The walk
creates a board, drags a player on the lawn and reads the dot's `cy` back; it read the same number before and
after, twice, on the same build. The page's own geometry said why: the dot sat at **y 1009** in a **900px**
window — the board editor's form grew above the lawn when the arc put the tier's sentences back — so the
pointer landed on the page instead of on the pitch and the drag never began. A walk that reads a box and then
moves the mouse to it does not notice that the box left the window. It now scrolls the dot into view first,
reads the box after the scroll, and says so in a check of its own: *"the lawn the walk drags on is inside the
window it drags in — the dot is at y 450 of a 900px window"*. The drag then moved the player (`cy 50 → 40.5`),
the board section ran to the end for the first time in a while, and the **3D** checks in this section stayed
green throughout — the projection is still the printed projection of the board's own metres.

Two more of the walk's reads were stale the same way, and both are now read from the page's own words rather
than from a shape the arc changed: the season page's challenge notice is one catalogue sentence now (the
scenario's slug and the round window are *in* it), and the walk reads them there.
