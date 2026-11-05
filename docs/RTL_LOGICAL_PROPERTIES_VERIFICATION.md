# Six horizontal declarations, and the gate that was green in only one tree

ROADMAP Phase 6 item 50. Date: 2026-11-06.

`qa-rtl-readiness.mjs` answers **6/7 failed=1** on a plane detached at `c87dba8` and **7/7** in the shared tree —
the same commit, the same gate, one finding apart. Item 49 had just removed line endings as an explanation, so this
time the difference is the working tree against `HEAD`: the cure was sitting uncommitted in the shared tree while
`HEAD` still carried six physical declarations. That is the whole unit — land those six lines — and the interesting
work is proving what they do, which a file-only gate cannot say.

| where the gate ran | bytes it read | verdict |
| --- | --- | --- |
| plane `.scratch/wt-rtl50` at `c87dba8` | the committed CSS | **6/7 failed=1**, six findings named |
| shared tree, before this landing | same commit + the six lines uncommitted | 7/7 |
| plane, after the six lines | the cured CSS | **7/7 failed=0** |

## 1. The six, and what the gate's population is

The gate's own census: every committed `.css` under `apps/web` (**11** stylesheets), comments stripped, five shapes
refused — a horizontal offset (`left`/`right`), a horizontal margin/padding/border, a physical corner radius, physical
text alignment, and a float. The six it was refusing:

| file:line | committed | landed |
| --- | --- | --- |
| `app/coach/coach.css:61` | `text-align: left;` | `text-align: start;` |
| `app/knowledge/knowledge.css:168` | `border-left: 2px solid var(--accent-dim);` | `border-inline-start: 2px solid …` |
| `app/knowledge/knowledge.css:169` | `padding-left: 0.6rem;` | `padding-inline-start: 0.6rem;` |
| `app/knowledge/knowledge.css:248` | `text-align: left;` | `text-align: start;` |
| `app/training/training.css:27` | `border-left: 2px solid var(--accent-dim);` | `border-inline-start: 2px solid …` |
| `app/training/training.css:28` | `padding-left: 0.6rem;` | `padding-inline-start: 0.6rem;` |

`git diff --stat` over the plane is **3 files, 6 insertions, 6 deletions, 4 hunks** — nothing else moved. And the
three files the shared tree held uncommitted are, after folding line endings, **byte-identical** to the three landed
here (121 / 261 / 56 lines), so this landing converges the two trees instead of introducing a third variant of the
same stylesheet.

## 2. The arms

Each arm edits one input, runs the gate, restores (`.scratch/item50-css.py --restore` reverses the six lines
exactly; it asserts one occurrence per pattern before it writes, so the census and the script cannot drift apart).

| arm | input | rc | verdict |
| --- | --- | --- | --- |
| base | the cured tree | 0 | **7/7** |
| A | `coach.css:61` back to `left` | 1 | 6/7, 1 finding at `coach.css:61` |
| B | only `knowledge.css:168`–`:169` back | 1 | 6/7, findings at both lines — one per line |
| C | a `margin-right: 4px` planted in a file the gate already reads | 1 | refused at `training.css:32` — a shape the tree does not currently carry |
| D | a `padding-left` inside a CSS comment | 0 | 7/7 — the scanner reads declarations, not lines, which is what §"population" claims |
| E | `padding-inline-end` kept | 0 | 7/7 — the logical spelling on the *other* side is not a finding |
| F | a `border-top-left-radius: 4px` planted | 1 | refused at `knowledge.css:246` |
| G | all six restored at once — the parent's tree | 1 | 6/7, the six findings in full |
| post | tree restored and re-run | 0 | **7/7** |

Arm H is a finding about the gate, not about the six lines: a planted file with **two** horizontal declarations on
one line and **three** shapes on the next yields **one finding per line**. The scanner counts line × shape, so a
line carrying `padding-left` and `margin-right` is reported once. Filed as roadmap row 53; it does not weaken the
base verdict, which is a refusal over the whole population, not a count.

## 3. The witness: what the six lines actually do

A file-only gate can say a declaration is physical; it cannot say what changes when it stops being. Two runs,
deliberately independent.

**(a) The rule blocks alone.** `item50-fixture.py` lifts the four shipped blocks verbatim out of the three
stylesheets, writes a `.phys-*` twin for each with the old physical spelling, and paints both in a `dir="ltr"` panel
and a `dir="rtl"` panel. 4 of 4 classes **agree in ltr** and **diverge in rtl**: the band moves from
`0px 0px 0px 2px` to `0px 2px 0px 0px`, the padding from `9.6px / 0px` to `0px / 9.6px`, and the text shifts
11.59 px on a band and 14.00 px on a chip.

**(b) The app itself.** Built (`npm run build`, exit 0), served (`npx next start -p 3117`), with the API from the
same commit on a scratch SQLite database (`alembic upgrade head` to `0049`, `uvicorn` on 8731), one account
registered, one career opened and **one player profile created** — without the player, `/coach` answers its own
`no_player` 409 by redirecting to `/onboarding` and the chips never paint. Then, in the live document, each element
was measured as shipped, and again as a clone carrying the pre-cure physical declaration in its place, in `ltr` and
in `rtl`.

| element the app painted | ltr | rtl shipped | rtl with the old declaration |
| --- | --- | --- | --- |
| `.drill-card__point` — 24 of them, `/training` | band `0px 0px 0px 2px`, padding `9.6px/0px`, text `11.59` from the start — **identical to the physical twin** | band `0px 2px 0px 0px`, padding `0px/9.6px`, text `11.59` from the start | band stays `0px 0px 0px 2px`, text `0` from the start — the accent is on the far side |
| `.kn-cite__quote` — 4, after one real ask on `/knowledge` | as above, identical | as above | as above |
| `.coach-chip` — 5, `/coach` | 4 text lines, every line `10.59` from the start | every line `10.59` from the start | the ragged lines sit `10.59` from the **left**, i.e. from the end |
| `.kn-filter-chip` — 6, `/knowledge` | 2 lines (`match-analysis` breaks at the hyphen), identical | both lines `10.59` from the start | the ragged line `10.59` from the left |

`item50-app-report.py` reads those three JSONs and asserts the claims above: **CHECKS passed=22 total=22 failed=0**.

Three things only the real document could tell:

- **`.chip` is `display: inline-flex`**, so `text-align` does not move a chip's label at all unless the label *wraps*.
  Measured on a single-line chip, `start` and `left` paint the same box and the same ink, and a forced `width: 5em`
  did not reproduce the wrap because it changed the flex item's basis. The chip arms above therefore measure the chip
  whose label breaks — `match-analysis`, two lines — and the coach chips, which break into four and five. The
  declaration is real, and its effect is conditional in a way the stylesheet does not show.
- **`Range.getClientRects()` returns one rect per bidi *run*, not per line box.** The first pass reported the word
  "I" inside "What should I train today?" as a line hugging the *end* edge in rtl. Grouping the rects by `top` and
  taking each line's union is what the `10.59` figures above come from; the earlier reading was an artifact of the
  probe, not of the page.
- **the accent colour travels with the band.** In rtl the shipped elements' `border-right-color` is
  `rgb(23, 184, 120)` — `--accent-dim` — for all six rows, so what moves is the whole band, not a bare edge.

## 4. The suites

- the file-only population, all 30 gates, on the cured plane: **29 passed / 1 refused**, `npm run typecheck` PASS,
  `npm run lint` PASS (`item50-webgates-final.log`). Before the six lines the same run refused **2**; the refusal
  that remains is `qa-wire-readers`, roadmap row 51, and was never this unit's.
- `npm run build` exit 0, and the compiled stylesheet carries the landed rules:
  `.coach-chip{cursor:pointer;text-align:start;…}` and
  `.kn-cite__quote{…-webkit-border-start:2px solid var(--accent-dim);border-inline-start:2px solid var(--accent-dim);-webkit-padding-start:.6rem;padding-inline-start:.6rem…}` —
  the prefix Next's toolchain adds for the browsers that need it.

## 5. What this does not claim

It does not make the gate cover every horizontal property. A second census over the same 11 stylesheets looked for
the shapes the five rules do **not** judge (`.scratch/item50-side.py`): 2 physical `background-position`
(`app/progress/progress.css:136` `120% 0`, `:137` `-120% 0`), 1 X-axis `transform: translate(-50%, -50%)`
(`styles/video.css:20`), 6 `box-shadow` hits **whose horizontal offsets are all zero**, 0 `text-indent`, 0 inline
`direction:`. Whether a mirrored progress sweep is a bug is a design question the gate cannot ask; row 53 files it.

It does not fix the line × shape counting (arm H), and it does not claim the six lines were the only physical
declarations in the product — the gate's 7/7 is the claim about this population, on these 11 files, re-run above.

It does not put the product in right-to-left. `textDirection` returns `rtl` for base languages that are not in the
shipped locale set, so **nothing in the app paints right-to-left today**; that is roadmap row 39's lane and item 38's
locale claims, not this unit. What this unit claims is narrower and checkable: the six committed declarations no
longer contradict the direction the page is answered in, and the two measurements above show both halves of that —
identical where the product ships, correct where it would not be.

## 6. Reproduce

    git worktree add --detach .scratch/wt-rtl50 c87dba8
    cd .scratch/wt-rtl50/apps/web && cmd /c "mklink /J node_modules ..\..\..\..\apps\web\node_modules"

    # the differential, in one plane: restore the six lines, run the gate, re-apply, run again
    .venv/Scripts/python.exe .scratch/item50-css.py --restore   # 6 lines back to physical
    (cd .scratch/wt-rtl50/apps/web && node scripts/qa-rtl-readiness.mjs)   # CHECKS passed=6 total=7 failed=1
    .venv/Scripts/python.exe .scratch/item50-css.py                          # cure applied
    (cd .scratch/wt-rtl50/apps/web && node scripts/qa-rtl-readiness.mjs)   # CHECKS passed=7 total=7 failed=0
    # arms A–H and the restores: .scratch/item50-arms.txt, .scratch/item50-side.txt

    # the whole file-only population
    PYTHONUTF8=1 .venv/Scripts/python.exe .scratch/item42-webgates.py wt-rtl50   # 29 passed / 1 refused

    # the app witness: API from the same commit, the built plane served, one signed-in career
    cd .scratch/wt-rtl50/apps/api && DATABASE_URL=sqlite:///<repo>/.scratch/item50-walk.db \
      /d/足球项目/.venv/Scripts/python.exe -m alembic upgrade head && \
      DATABASE_URL=… uvicorn app.main:app --host 127.0.0.1 --port 8731
    (cd .scratch/wt-rtl50/apps/web && npm run build && npx next start -p 3117)
    PYTHONUTF8=1 .venv/Scripts/python.exe .scratch/item50-app-session.py    # account, career, player; DOM counts
    # then, in the browser on http://127.0.0.1:3117 carrying the fo_access cookie, run the two probes
    #   band kind  -> .scratch/item50-app-training.json, .scratch/item50-app-knowledge-cites.json
    #   align kind -> .scratch/item50-app-coach.json, .scratch/item50-app-knowledge-chips.json
    PYTHONUTF8=1 .venv/Scripts/python.exe .scratch/item50-app-report.py     # CHECKS passed=22 total=22 failed=0
    # the rule-block fixture, independent of the running app:
    #   .scratch/item50-fixture.py -> item50-rtl-fixture.html, probed by item50-probe-report.py -> item50-browser.txt
