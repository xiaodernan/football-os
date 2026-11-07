# RTL readiness — the audit that stands before any Arabic or Hebrew locale

Measures the tree on 2026-11-06 (re-verified 2026-11-07). Every number is taken, not asserted; reproduce
with the commands named. **No right-to-left locale ships until the checklist below is closed.** This document is the
audit; `qa-rtl-readiness.mjs` is the gate; `docs/I18N_ARC_VERIFICATION.md` §20 records the structural
half.

## What is already true (and gate-able)

| Fact | Evidence |
| --- | --- |
| No horizontal declaration is physical anywhere in the CSS population | `node apps/web/scripts/qa-rtl-readiness.mjs` — 11 files, 0 findings |
| `<html dir>` moves with the locale | the same gate reads the `<html>` tag as a tag; `textDirection("ar") === "rtl"` verified by Transpiling and calling the shipped helper |
| Both font stacks end in a generic family | same gate (`--font` → `sans-serif`, `--mono` → `monospace`) |
| A `:lang(ar), :lang(he)` reset zeroes `letter-spacing`/`text-transform` | same gate, added 2026-11-06; sixteen tracked declarations in the stylesheets cannot break cursive joining |
| Body line-height is 1.55 | `styles/globals.css` — at the usable threshold; 1.6+ recommended for Arabic-heavy pages (see below) |
| The catalogue layer is direction-agnostic | next-intl resolves keys the same in any script; ICU handles bidi-neutral runs |

## The audit, measured

### 1. Physical/logical CSS

The six stylesheets that carried physical properties were rewritten (§20 of the verification
record): `globals.css`, `world.css`, `tactics.css`, `knowledge.css`, `coach.css`, `training.css`.
`qa-rtl-readiness` re-reads the whole population every run; 11 files, 0 findings.

### 2. Tracking and case-transform (the Arabic-breaking pair)

The stylesheets carry **16 `letter-spacing` declarations** (11 in `globals.css`, 5 in `world.css`;
none elsewhere; `node apps/web/scripts/qa-rtl-readiness.mjs` counts them implicitly by refusing a
missing reset, and `Select-String` over the stylesheets reproduces the list). Arabic letters join cursive; tracking breaks the join and renders disconnected
letterforms. `text-transform` has no counterpart in Arabic or Hebrew. The reset in `globals.css`

```css
:lang(ar), :lang(he) { letter-spacing: normal; text-transform: none; }
```

covers every declaration without splitting them from their Latin use, and the gate refuses a tree
without it.

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
- **Punctuation:** Arabic uses `،` and `؟`; the translation pass will carry them.
  `qa-translation-quality.mjs` checks Chinese punctuation; the Arabic equivalent is a milestone item
  (it has no pass for Arabic yet).
- **Bidi:** ICU messages with mixed runs (`"{score} مجريات"`) rely on the bidi algorithm; numbers are
  weak-directional and resolve correctly in practice. Rule: never embed invisible LRM/RLM in the
  catalogue; a message that needs one is written the wrong way — rewrite it.

### 6. The `.num` / `mono` figure classes

`tabular-nums` and mono stacks are direction-agnostic; they hold digits and Latin notation, whose
bidi behaviour is stable. No change.

### 7. Layout under mirroring — what the gate cannot see

The gate judges CSS. Eyeball remains for: badges overlapping icons that imply direction,
`justify-content` used for alignment, `transform: translateX(...)` animations (search shows **no**
`translateX` usage; single static transforms only), and shadows/gradients with directional light.
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
   The Arabic milestone still owes: authoring `ar.json`, running the pass on its full population, and every
   `ar` message passing all six plural categories and all five quality checks. The Hebrew milestone owes the same.
   **Cured 2026-11-08, and the counts above are the pre-cure ones:** the gate is now **nine** checks, and its
   scratch fixture is a shipped witness, `qa-translation-quality-witness.mjs` (**11/11**). Both script rules
   were still the weak point — they printed the same clean sentence for a tree with no `ar.json` and for an
   `ar.json` that is a byte copy of `en.json` (measured on the pre-fix bytes at `0a7a9da`: 6/6 green, 4224
   messages that never became Arabic). Each rule now names the population it judged, dormancy says
   `dormant` in the line and again in a trailer after the tally, a shipped-but-unjudged catalogue is a finding,
   and a fourth catalogue outside `KNOWN_LOCALES` is charged by filename. See §40 of
   `I18N_ARC_VERIFICATION.md`. The exemption set is read from `qa-locale-tokens.mjs` rather than copied.
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
7. **CI registers the new locale** (matrix or shard as the pipeline prefers), and
   `test_locale_claims.py` passes with the new population — the pin will move with it.
8. **No RTL locale is added to `i18n/locales.ts` before 1–7 are green.** The gate already refuses a
   tree whose `<html dir>` disagrees; adding `ar` early fails loudly, which is the point.

## What is deliberately not claimed

- No RTL locale exists today; nothing in this document renders Arabic or Hebrew.
- The 9 JSX arrow sites listed in §3 were all retired 2026-11-07 — the raw glyphs are gone, the catalogue carries the directional copy, and the gates keep new JSX-text arrows out. See §3 of this document.
- Arabic is the harder script (joining + six plurals); Hebrew is the simpler pass (no case, two plurals: one/two/other — `qa-plural-select` winds both, dormant-by-absence). Both stay behind the same checklist.
