# RTL readiness — the audit that stands before any Arabic or Hebrew locale

Measures the tree on 2026-11-06 (re-verified 2026-11-07; re-measured end to end on 2026-11-23 under Item 315,
which is where the value judging, the weighting and the mirror pairs in §1 and §2 come from). Every number is
taken, not asserted; reproduce with the commands named. **No right-to-left locale ships until the checklist below is closed.** This document is the
audit; `qa-rtl-readiness.mjs` is the gate; `docs/I18N_ARC_VERIFICATION.md` §20 records the structural
half. Both RTL locales this audit prepared for have shipped since it was written (`ar` §55, `he` §57) — the checklist below is what they were held to.

## What is already true (and gate-able)

| Fact | Evidence |
| --- | --- |
| No horizontal declaration is physical anywhere in the CSS population | `node apps/web/scripts/qa-rtl-readiness.mjs` — 32 files, 15 checks, 0 findings |
| `<html dir>` moves with the locale | the same gate reads the `<html>` tag as a tag; `textDirection("ar") === "rtl"` verified by Transpiling and calling the shipped helper |
| Both font stacks end in a generic family | same gate (`--font` → `sans-serif`, `--mono` → `monospace`) |
| A `:lang(ar), :lang(he)` reset zeroes `letter-spacing`/`text-transform` | same gate, added 2026-11-06 and weighted in Item 315; 112 tracking declarations across 24 stylesheets cannot break cursive joining |
| Body line-height is 1.55 | `styles/globals.css` — at the usable threshold; 1.6+ recommended for Arabic-heavy pages (see below) |
| The catalogue layer is direction-agnostic | next-intl resolves keys the same in any script; ICU handles bidi-neutral runs |

## The audit, measured

### 1. Physical/logical CSS

The six stylesheets that carried physical properties were rewritten (§20 of the verification
record): `globals.css`, `world.css`, `tactics.css`, `knowledge.css`, `coach.css`, `training.css`.

`qa-rtl-readiness` re-reads the whole population every run — **32 stylesheets, 15 checks, 0 findings**.
Since Item 315 the gate judges the *value*, not only the property name: eight shapes are physical by
name (horizontal offsets, margin/padding/border, corner radii, `text-align`, `float`) and three are
judged by what they resolve to — `box-shadow` (every layer's first length, `var()` expanded four
levels deep), `transform` (`translate`/`translateX`/`translate3d` only), and `background-position`.
Property and keyword spellings are matched case-insensitively, because CSS is: `transform: TranslateX(9px)`
is the same declaration to a browser as to the scan, and the witness plants the camel spelling so the hole
cannot quietly re-open. A declaration that paints nothing is not a finding: `box-shadow: none` declares no
layer, and a shadow whose horizontal offsets are all zero moves nothing in either direction. What is left is
either cured, exempted by value (28 zero-offset shadows), named in `EXEMPT` with a reason pinned to the bytes
at a file and line — 7 of them: the detection ring's centring transform, the progress shimmer's two stops, the
empty-state pulse's two stops and the skeleton's two `fo-breathe` stops — or answered by its own mirror. The
four newest exemptions are percentages resolved against a negative free space (`background-size` larger than
the box), where a decreasing percentage moves the image *right*; direction is not an input to the property, so
both writing modes resolve the same track, and the gradients are symmetric — a sweep with no reading order in
it to invert.

**Six `translateX` offsets ship, and four of them are directional — so they are mirrored, not exempted.**
A mirror pair is charged differently from an exemption: the base rule stays direction-agnostic, the
counterpart is scoped to `[dir="rtl"]` at equal weight (`:where()` carries it), and the two used offsets must
be exact opposites. The gate reads both lines' bytes, judges both with the same value judge it uses on the
population, and refuses a pair whose signs agree, whose magnitudes differ, whose counterpart is not scoped
rtl in *every* compound of its selector list, or whose answer sits before the thing it answers:

| pair | ltr | rtl | what it is |
| --- | --- | --- | --- |
| `atlas.css:73 ↔ 81` | `translateX(3px)` | `translateX(-3px)` | the atlas door steps into itself |
| `atlas.css:110 ↔ 117` | `translateX(4px)` | `translateX(-4px)` | the arrow inside it — composed, 7 px out of the reading edge |
| `manual.css:88 ↔ 95` | `translateX(3px)` | `translateX(-3px)` | the manual's door arrow |
| `globals.css:582 ↔ 599` | `translateX(-120%)` | `translateX(120%)` | where the card sheen parks |
| `globals.css:588 ↔ 602` | `fo-sheen from −120%` | `fo-sheen-rtl from +120%` | the sweep's first endpoint |
| `globals.css:589 ↔ 603` | `fo-sheen to +120%` | `fo-sheen-rtl to −120%` | the sweep's last endpoint |

A keyframe cannot be answered by a second declaration the way a rule can — two `from` blocks interpolate
against each other instead of selecting — so the RTL sweep is a second `@keyframes fo-sheen-rtl` whose name the
RTL half of the `animation` shorthand has to actually reach. The gate charges that handoff: a `fo-sheen-rtl`
nobody names is a finding, not a promise.

**The rails moved to the row's start edge (Item 315).** Five declarations drew a 3 px inset
`box-shadow` on the left of a marked table row — `.tr--podium-1..3 td:first-child` in `globals.css`,
`tr[data-leader]` in `gazette.css`, `tr[data-champion]` in `timeline.css`. Measured in Chrome on the
shipped bytes (`node .scratch/rtl315-measure.mjs`, pixel read-back of the rank cell):

| build | dir | rail painted on | rank-cell text shift vs a plain row | head vs body first column |
| --- | --- | --- | --- | --- |
| master (`inset 3px` shadow) | ltr | left ✓ | 0.00 px | 0.00 px |
| master | rtl | **left ✗** — the podium rail sat inside the row, the gazette/timeline rail left the rank cell entirely | 0.00 px | 0.00 px |
| cured (`border-inline-start: 3px`, reserved on `th` and `td`) | ltr | left ✓ | 0.00 px | 0.00 px |
| cured | rtl | **right ✓** | 0.00 px | 0.00 px |

The reserve is what keeps the cure free: the 3 px is paid on every first cell, head included, so the
whole column sits 3 px further in (119.59 → 122.59 px) and nothing moves relative to anything else.
Arms H and I of `.scratch/item315-arms.py` put the physical shadow back at those two sites and the
gate goes red on both.

**The hover geometry, measured at five instants and in both directions** (`node .scratch/rtl315-sheen2.mjs`,
Chrome 1xx, an empty `.player-card` so the only luminance in the shot is the sheen itself; the used transform
matrix read from the resolved pseudo-element, animation frozen per instant):

| instant | master ltr | master rtl | cured ltr | cured rtl |
| --- | --- | --- | --- | --- |
| park (t = 0) | −360 px | −360 px | −360 px | **+360 px** |
| t = 212 ms | −66.81 px | −66.81 px | −66.81 px | **+66.81 px** |
| t = 425 ms | +217.73 px | +217.73 px | +217.73 px | **−217.73 px** |
| t = 637 ms | +331.38 px | +331.38 px | +331.38 px | **−331.38 px** |
| t = 850 ms | +360 px | +360 px | +360 px | **−360 px** |
| keyframe running | `fo-sheen` | `fo-sheen` | `fo-sheen` | **`fo-sheen-rtl`** |
| band first visible | 21.4% from the left | 78.6% from the left | 21.4% from the left | **33.8% from the right** |
| atlas door nudge | +3 px | +3 px | +3 px | **−3 px** |
| atlas arrow nudge | +4 px | +4 px | +4 px | **−4 px** |
| composed travel | +7 px | +7 px | +7 px | **−7 px** |
| manual door arrow | +3 px | +3 px | +3 px | **−3 px** |

Twelve measured claims (five per-instant offsets, two travel directions, two entry edges, three hover shapes):
ten of them false on master, none false on the cured tree. The sweep's *travel*
mirrors — the offset is the exact negative at every instant, and the band enters from the reading-start edge
instead of turning up already 78.6% across the card. What deliberately does **not** mirror is the stripe's own
lean (`115deg`) and the position of its brightest column inside its own box (0.437 of the box width): that is
where the light sits, not which way the reader goes, so no claim here pretends otherwise — and the probe's
first version did pretend, and its own table showed the luminance sample was measuring the card's text rather
than the sheen. Same for the manual arrow: the first probe never hovered it, and reported `0 px` in four of
four rows while its claim rang green. Both are the hollow-measurement class, and both are why the numbers in
this table are read from the used matrix.

`node .scratch/item315-arms.py` runs the gate **21 times against 21 planted states** — 18 that must turn it red
while printing the exact sentence the record quotes, and 3 that must leave it green, because a declaration that
paints nothing (`box-shadow: none`, `transform: none`) or a newly tracked rule the weighted reset already
answers is not a defect. Six of the red arms attack the mirror machinery (a counterpart flipped to the same
sign, P; rewritten into `opacity`, Q; scoped to `[dir="ltr"]` in one compound of its selector list, R; a
mirrored keyframe declared but never named, S; endpoints that agree in sign, U; endpoints that answer different
instants, V), and one attacks the spelling: a camel `TranslateX(9px)` the case-insensitive judge must still
charge (T). All 21 pass, and the closing BASE read shows the plane back to 15/15 once they are undone.

### 2. Tracking and case-transform (the Arabic-breaking pair)

The stylesheets carry **112 letter-spacing declarations that set tracking, across 24 stylesheets**
(counted by `qa-rtl-readiness` itself, which also refuses a tracked declaration that carries
`!important`). The reset is one rule in `globals.css`:

```css
:lang(ar), :lang(he) { letter-spacing: normal !important; text-transform: none !important; }
```

It is weighted because it has to be. `:lang(ar)` matches every element whose language inherits to
Arabic, but the tracking sites sit on classes — `.gazette__table th`, `.table th`, `.stat__label`,
`.nav__brand` — and a class rule beats an html-level rule both as specificity and as inheritance.
Measured at lang=ar on master's bytes (`node .scratch/rtl315-tracking.mjs`, computed style of nine
real selectors): the gazette head kept **1.4848 px** and its `uppercase`, the board head **1.184 px**,
the stat label **1.3824 px**, the brand **-0.3 px** — five of nine sites still tracked, and only the
sites that already had a hand-written `:lang(ar)` counterpart read `normal`. On the weighted rule all
nine read `letter-spacing: normal; text-transform: none`, and **every one of them is unchanged at
lang=en**, byte-for-byte the same computed values. The weight is the file's own idiom: the
reduced-motion block below it weights four declarations for the same reason — a promise has to beat
every author rule, including the ones not written yet.

Arabic letters join cursive; tracking breaks the join and renders disconnected letterforms.
`text-transform` has no counterpart in Arabic or Hebrew. The gate refuses a tree whose reset is
missing *or unweighted*, so the claim cannot rot back into a paragraph.


### 3. Directional arrows and glyphs

Two distinct populations, and they are handled differently by rule:

**a. Arrows written in JSX (not in the catalogue) — all fixed by 2026-11-07** (the list grew to nine on re-inventory; the ninth, `graph/page.tsx`'s kind-button arrow, was missed by the original census and is a direction-aware CSS marker now):

| file | site | action |
| --- | --- | --- |
| `app/history/page.tsx` | 162, 166, 171, 175 | the raw glyphs are gone; the text comes from `tc("previousPage")` / `tc("nextPage")`, whose arrows the catalogue carries per locale |
| `components/world.tsx` | 92 | `← {back.label}` is gone; a direction-aware `world-back::before` marker (`←` in ltr, `→` in rtl) |
| `components/world.tsx` | 205, 210 | `← {t("previousPage")}` / `{t("nextPage")} →` are gone; the catalogue text carries the arrow |
| `app/knowledge/KnowledgeAsk.tsx` | 46 | the raw trailing `→` removed; the catalogue line holds its own direction |
| `app/graph/page.tsx` | 155 | `fwd-arrow` CSS marker: `→` in ltr, `←` in rtl (`tactics.css`) |

**b. Arrows in the catalogue — each language writes its own direction, and that is fine.**
  `backToAcademy` / `backToLibrary` (`← Back to…`), `movementPath` (`{from} → {to}`), and the
  transition notations (`{before} → {after}`, `{value} → {next}`, `levelTo`, `trainingRow`,
  `squadRow`, `ChangesFirstLast`, `academyThStored`) — notation, not layout; bidi-neutral in
  practice, and each script decides its own glyph. No change required for those.

**Rule for the first RTL milestone:** (a) sites are migrated into the catalogue (the sentence
carries its own direction — Arabic writes `→` for back) or are direction-aware CSS markers; none remain as raw glyphs in JSX text.
The `openPassage` and pagination catalogue keys carry their own arrows (each script writes its own direction);
the bidi algorithm renders the neutral runs correctly in practice. Do not `transform: scaleX(-1)` a raw glyph —
the same glyph is notation elsewhere.

### 4. Fonts

- `--font`: `Inter, Segoe UI, system-ui, -apple-system, sans-serif` (ends generic, per the gate).
- `--mono`: `JetBrains Mono, ui-monospace, Cascadia Mono, Consolas, monospace`.
- **None of the named faces carries Arabic or Hebrew** — Inter is Latin/Cyrillic/Greek; JetBrains
  Mono is Latin; Segoe UI (Windows) covers both; macOS/iOS resolve system-ui to faces CoreText
  substitutes for missing scripts; Android substitutes Noto. The stack works by fallback, not by
  choice, and the fallbacks are deliberate, measured and named: **Windows** \u2192 Segoe UI's AT interfaces cover both
  scripts on this machine and on the supported floor; **macOS/iOS** \u2192 CoreText serves SF Arabic/SF Hebrew through
  `system-ui`; **Android/Linux** \u2192 Noto (Alibaba/Adnoc). No new web-font is owed, no binary carries on disk, and no
  latency is added to any page before a locale exists.
- **Decision (2026-11-07), moving against the earlier reading of item 2:** the stack stays as-is, with the
  fallback mechanism recorded as the resolution path. Naming Noto Sans Arabic/Hebrew explicitly would
  require shipping subset files — a font pipeline, licence review and per-locale budget that belong to
  the milestone, not to readiness. The walk is the evidence the checklist wants, and the walk runs at the
  milestone, under `dir=rtl`: if any named face renders a bad glyph in the walk (clipped forms, wrong
  numerals, broken joins), item 2 re-opens with measured evidence from real pages — not before. Until
  then: **keep the stack, record the mechanism, walk proves it.**
- Line-height: body 1.55 — usable; **news/reader prose already runs 1.7** (`world.css`) and passes
  the Arabic threshold. Any new long-form Arabic surface should target ≥ 1.6.

### 5. Numerals, punctuation, bidi

- **Numerals: keep Western digits** (`0-9`) — the dominant practice in Arabic and Hebrew UIs; the
  catalogue's figures stay as authored. Decide finally with the first Arabic translator; do not
  transliterate numerals by default.
- **Punctuation:** Arabic uses `،` and `؟`; Hebrew uses `.` and `?`. The Arabic milestone landed 2026-11-08
  carrying its own punctuation arm in `qa-translation-quality.mjs` (both RTL script rules judge the full
  shipped populations today: 4222/4222 Arabic messages, 4221/4221 Hebrew messages, zero Latin holdouts;
  §55/§57/§63). The Hebrew catalogue in particular ships with proper Israeli typography (`דוא״ל`, `סה״כ`,
  double-angle quotations for reported speech) — see §63 of the verification record.
- **Bidi:** ICU messages with mixed runs (`"{score} مجريات"`) rely on the bidi algorithm; numbers are
  weak-directional and resolve correctly in practice. Rule: never embed invisible LRM/RLM in the
  catalogue; a message that needs one is written the wrong way — rewrite it.

### 6. The `.num` / `mono` figure classes

`tabular-nums` and mono stacks are direction-agnostic; they hold digits and Latin notation, whose
bidi behaviour is stable. No change.

### 7. Layout under mirroring — what the gate cannot see

The gate judges declarations in stylesheets. Since Item 315 it judges the *value* of three families it
used to skip (`box-shadow`, `transform`, `background-position`) and it charges a mirror pair on the same
terms it charges a finding, so the eyeball list is shorter than the one this section first wrote. The
section's original line — "search still shows no directional `translateX` in the tree" — was false when it was
written: a `git grep` taken the same day found **six** shipped `translateX` offsets, which the case-sensitive
judge had been reading as ordinary transforms. They are listed and answered in §1. What the scan still cannot
reach:

- **An inline style on a component.** `components/Nav.tsx` carries `style={{ marginLeft: "0.3rem", … }}`
  today; a stylesheet cannot see it, and no gate reads JSX style objects. It is a 0.3 rem gap, not a
  direction claim, but it is the class the walk has to keep watching.
- **`justify-content` used to imply direction**, which is a layout decision rather than a physical token.
- **Directional artwork.** A symmetric gradient carries no reading order; an SVG chevron does. The gate
  judges the former by value and neither engine judges the latter.
- **Geometry minted by JS** — the detection ring's coordinates are an inline style on the mark, which is
  why its CSS exemption says so.

The milestone covers these by page, not by rule.

## The first RTL milestone — exit criteria (all required)

1. **Directional JSX arrows (9 sites) — done 2026-11-07.** The raw arrows are gone from JSX: the history
   pagination, the world back marker and the knowledge-passage link render catalogue text or a
   direction-aware CSS marker (`.world-back::before`, `.fwd-arrow`); no literal arrow renders against the
   text flow. (Item 1 was the one the first RTL review could hold to a gate; the rest below are the milestone.)
2. **Font stack — decided 2026-11-07 (keep the stack; record the mechanism; the walk is the evidence).**
   The fallback path is named per platform class (Windows → Segoe UI AT metrics; macOS/iOS → system-ui /
   SF Arabic/SF Hebrew; Android/Linux → Noto), and the stack that ships stays exactly what the gate judges.
   The milestone re-opens this only for a walk-proven bad glyph (clipped forms, broken joins, missing
   numerals) — measured, page list, screenshots in `docs/screenshots/`, and then a subset/font pipeline
   lands with the walk that motivated it. Until the walk runs: the mechanism is recorded; nothing to ship.
3. **Arabic plural categories — the gate half done 2026-11-07; the catalogue half owed at the milestone.**
   `qa-plural-select.mjs` now discovers which locales to judge from the catalogue directory, not from a
   hardcoded triple, and `ar` carries the six CLDR categories (`zero/one/two/few/many/other`). Verified
   on the real catalogues (87 plurals, 2/2, unchanged) and on a three-case fixture: a complete six-category
   Arabic plural passes; a missing `two` reds naming the missing category; an empty branch reds too.
   Owed at the milestone: `ar.json` itself, the full population passing all six categories, and parity (item 5).
4. **`qa-translation-quality.mjs` gains the Arabic and Hebrew passes — done 2026-11-07.**
   The gate now discovers which locales to judge from the catalogue directory; `ar` joins the same four
   families of checks (untranslated English words, locale punctuation, mojibake, no-literal-English-structures)
   with Arabic-specific handling: an Arabic message ending in Latin `.`/`!`/`?` reds, and a new fifth check requires
   Arabic script in every non-technical-token message. The mojibake clause gained the byte class the Arabic
   failure needs (Latin-1 first bytes read as `Ù`/`Ú`/`Ø`) — the old pattern could not see Arabic decoded as
   Latin-1, and no seven-case arm could retire it until it did. Verified arm by arm: complete Arabic passes 5/5;
   a holdout like `Home page` reds both untranslated-English and no-script; mojibakeed Arabic reds mojibake;
   Latin `.`-ending reds punctuation; an English idiom reds untranslated-English and literal-structure.
   **Hebrew's twin (same day, same session):** Hebrew locale + Hebrew-script checking shipped 2026-11-07;
   punctuation check honours Hebrew's `?`/`!`/`.` as natural sentence endings and reds non-Hebrew full stops
   (`。`, `؟`, `！`, `？`); mojibake detects Latin-1-decoded Hebrew bytes at `Ê`–`Õ` with script absent; a
   Hebrew-script assertion mirrors the Arabic one; punctuation honours Hebrew sentence-ending marks other
   than Chinese/Arabic ones. Verified with a six-arm fixture — see §31.
   The Arabic milestone still owed: authoring `ar.json`, running the pass on its full population, and every
   `ar` message passing all six plural categories and all five quality checks. The Hebrew milestone owed the same.
   **Both paid 2026-11-08/09** — `ar` (§54/§55) and `he` (§57) were judged by these same nine checks on their full populations.
   **Cured 2026-11-08, and the counts above are the pre-cure ones:** the gate is now **nine** checks, and its
   scratch fixture is a shipped witness, `qa-translation-quality-witness.mjs` (**11/11**). Both script rules
   were still the weak point — they printed the same clean sentence for a tree with no `ar.json` and for an
   `ar.json` that is a byte copy of `en.json` (measured on the pre-fix bytes at `0a7a9da`: 6/6 green, 4224
   messages that never became Arabic). Each rule now names the population it judged, dormancy says
   `dormant` in the line and again in a trailer after the tally, a shipped-but-unjudged catalogue is a finding,
   and a fourth catalogue outside `KNOWN_LOCALES` is charged by filename. See §40 of
   `I18N_ARC_VERIFICATION.md`. The exemption set is read from `qa-locale-tokens.mjs` rather than copied.
   The two **token** gates were cured the same day (§41): both had `const LOCALES =
   ["zh", "zh-TW"]` written into their source, so the `ar.json` this milestone will land was judged by neither
   — a byte copy of `en.json` measured 5/5 and 2/2 green under those bytes — and both walked the catalogue two
   levels deep. They now discover the directory, reach every leaf at every depth, refuse on a plane with
   nothing to compare, and a shipped `ar.json`/`he.json` without a drift floor or a README row is a finding on
   the day it lands, with `qa-token-gates-witness.mjs` (10 arms) holding that shape.
5. **Catalogue parity — the gate half done 2026-11-07.**
   `qa-locale-completeness.mjs` no longer names three targets; it discovers the catalogue files in the
   directory and judges every one of them — `en`, `zh`, `zh-TW` today, four the day `ar.json` lands, with
   zero further edits. Grey-area check names were pulled into sync with the CI step name so the gate and
   the runner can't drift apart in prose; the CI step is now "every locale the directory carries".
   Verified on the real tree (43 namespaces, 4269 keys, 2/2) and on an arms fixture: a complete Arabic
   catalogue passes; a missing key reds with the key named (`tsex.c: missing in ar`); an extra key reds
   the same way (`tsex.d: extra in ar`). The milestone still owes: `ar.json` itself, a regenerated
   population count, and a re-verified full battery — parity is a floor, not a ceiling, and the gates
   that read it follow.
6. **Walk the representative pages with `dir=rtl`** — the market ledger, a career page, the nav,
   the knowledge base — on a production build; no clipped text, no broken joins, pagination and
   back arrows on the correct side. Record in `I18N_ARC_VERIFICATION.md` §23+.

   **Landed (§55, 2026-11-09).** `qa-arabic-rtl-walk.mjs` ran against a production build with a freshly seeded scratch PostgreSQL (`0001->0059`), the API up on `8760` and the production Next tier up on `3212`. Five pages walked with `fo_locale=ar`; all printed Arabic under `<html dir="rtl">`, zero `MISSING_MESSAGE`s, zero console errors — and the `/challenges` session-gated URL redirected anonymously to a correctly-rendered Arabic login page, which is the safest thing this locale could do first. Screenshots in `docs/screenshots/202611081854-*`: `arabic-home.png`, `arabic-world.png`, `arabic-knowledge.png`, `arabic-login.png`, `arabic-challenges.png`. Inventory grew by one to **221/221** (the walk is a `live-tier` gate wired into `qa-gate-inventory`).

   **Landed (§57, 2026-11-09).** `qa-hebrew-rtl-walk.mjs` — the same walk against the same production shape (`football_he_probe_i` seeded 0001→0059 then dropped; API `8760`; prod build `.next-ci` on `3212`). Five pages under `fo_locale=he`; every page printed Hebrew under `<html dir="rtl">`, zero `MISSING_MESSAGE`s, zero console errors; `/challenges` redirected anonymously to a correctly-rendered Hebrew login page. The only Latin string on the rendered home page is `M3 Football World` — the milestone's own proper name inside Hebrew copy. Screenshots `docs/screenshots/202611082102-hebrew-*.png`. Inventory grew to **222/222**. `<html dir>` follows `he` (the shared `RTL_BASE_LANGUAGES` set), and the `:lang(he)` font stack ships in `globals.css` (Noto Kufi Hebrew / Noto Sans Hebrew).

    **Walk procedure (run; the record is in `I18N_ARC_VERIFICATION.md` §55):**

   1. **Build** — `npm run build` on a tree whose `messages/` carries `ar.json`; confirm no RTL-specific
      build error and no `next-intl` missing-locale warning for `ar`.
   2. **Market ledger** — open `/world/matches` (or the market's ledger page) with `?locale=ar`:
      - No English residue in stat labels, cap names, or example placeholders
      - Table pagination renders with `next`/`previous` on the *right* side for RTL reading order
      - Back/pagination arrows point toward the start of reading (right-to-left)
   3. **Career page** — open a career detail page with `?locale=ar`:
      - No clipped text in player cards, contract panels, or badge overflow
      - No broken Arabic joins (letters connect within words)
   4. **Nav** — open the global nav with `?locale=ar`:
      - All nav entries resolve to Arabic (no `MISSING_MESSAGE`, no English fallback)
      - Nav drawer/popover opens on the correct side for RTL
   5. **Knowledge base** — open a knowledge article with `?locale=ar`:
      - Body text direction follows `dir=rtl`; embedded LTR content (numbers, English terms) does not
        break line flow
      - No clipped glyphs at paragraph edges
   6. **Logs** — capture tier logs after the walk:
      - Zero `MISSING_MESSAGE` entries for `ar`; any entry blocks the slice until fixed in the same commit
   7. **Record** — write observations to `I18N_ARC_VERIFICATION.md` §23+ (a new RTL walk section, next
      free number after §50), with page list, screenshot references, and any `MISSING_MESSAGE` entries.

   **Preconditions already met (no edit needed):** `<html dir={textDirection(locale)}>` in the root
   layout (§8 item 8); `textDirection("ar")` returns `"rtl"` (`i18n/locales.ts` §22 RTL_BASE_LANGUAGES);
   `qa-rtl-readiness.mjs` 15/15 refuses physical CSS properties that would not follow direction, refuses a
   value-judged declaration it cannot decide from the bytes, and refuses a mirror pair whose two offsets are
   not exact opposites.
7. **CI registers the new locale** (matrix or shard as the pipeline prefers), and
   `test_locale_claims.py` passes with the new population — the pin will move with it.
8. **No RTL locale is added to `i18n/locales.ts` before 1–7 are green — and both were added only after they were.** `ar` joined at §54 with the walk behind it (§55), `he` at §57 with its walk behind it; the gate refuses a tree whose `<html dir>` disagrees, and the walk proves the page agrees.

## What is deliberately not claimed

- **Both RTL locales now exist and are served: `ar` and `he`** — `locales` discovers them from `messages/` and `locales_planned` lists six (the French slice, `fr`, followed the same bar in §64: full catalogue, LTR production walk, all six in `locales_planned`). Each shipped with its full catalogue (4269 keys, parity, ICU, plural gates, token/drift/quality gates all green) and its own production `dir=rtl` walk (§55, §57); the item-6 named surfaces — the market ledger and a career detail — were walked **authenticated** with a round played through the engine (§58, §61: **12/12 pages each**, including the public `/club/rules` under both scripts and `/career/walk-manager-braa` rendered with a real gate-receipt row in the ledger). Neither ships a human editorial pass yet — Arabic's and Hebrew's catalogues are machine-authored to the project's bar and both still owe a native review before either is claimed as *edited* rather than *shipped*; neither numerals policy is finally decided.
- The 9 JSX arrow sites listed in §3 were all retired 2026-11-07 — the raw glyphs are gone, the catalogue carries the directional copy, and the gates keep new JSX-text arrows out. See §3 of this document.
- Arabic is the harder script (joining + six plurals); Hebrew is the simpler pass (no case, two plurals: one/two/other — `qa-plural-select` winds both). Both landed through the same checklist, the same gates and the same production walk shape.
