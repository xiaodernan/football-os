# I18N Arc — living plan

Measured on the current tree (2026-11-03). Every number below is re-derived by the gate named beside it;
this file is a plan, never the evidence.

## Where the arc stands

| Gate | Verdict |
| --- | --- |
| `qa-i18n-literals.mjs` | 9/9 — 0 English literal sites over 145 `.tsx` files, 4063 key calls, 8 translator props bound |
| `qa-locale-completeness.mjs` | 2/2 — 42 namespaces, 4026 keys, full parity `en`/`zh`/`zh-TW` |
| `qa-locale-fallback.mjs` | 3/3 — every English key non-empty in both Chinese catalogues |
| `qa-unused-keys.mjs` | 3/3 — floor 0 dead keys |
| `qa-icu-messages.mjs` | 2/2 — every message parses, placeholders agree across locales |
| `qa-icu-coverage.mjs` | 2/2 — every source placeholder declared |
| `qa-translation-quality.mjs` | 4/4 — no English in Chinese copy, punctuation, encoding, literal-structure checks |
| `qa-locale-tokens.mjs` | 5/5 — 45 named identical tokens, English catalogue holds no Chinese |
| `qa-key-drift.mjs` | 4/4 — 13 named sites, hall ceilings 99 sentence / 42 key |
| `qa-shared-keys.mjs` | 4/4 — 98 value-shared names, 9 named divergences |
| `qa-token-drift.mjs` | 2/2 |
| `qa-namespace-ownership.mjs` | 2/2 — 42 namespaces, every one owned |
| `qa-population-floor.mjs` | 3/3 |
| `qa-translation-freshness.mjs` | green against `.gate-baseline` |
| `qa-api-strings.mjs` | 3/3 — refusal boundary wired, every refusal translated |
| `qa-error-boundary.mjs` | 2/2 |
| `qa-locale-content.mjs` | 3/3 — 28 deliberate locale differences |
| `qa-locale-formatting.mjs`, `qa-plural-select.mjs` | green |
| `qa-gate-inventory.mjs` | 188/188 — every invocable script named by a runner or explained |
| `qa-wire-readers.mjs` | 12/12 — market wire, types and page reconciled (top-level blocks) |

Live-tier walks are run through `scripts/run-walks.mjs`; the visual walk through
`apps/web/scripts/visual-qa.mjs`. Their verdicts live in `docs/I18N_ARC_VERIFICATION.md`.

## Queue (in order)

### 1. Wire-readers: reconcile the blocks inside a block
The gate reconciles `MarketView`'s top-level keys, but not the blocks those keys hold. The API publishes
`totals.cup_prize_rows` and the web `totals` type does not declare it — a published field no reader can
reach, invisible to the dead-key gate (it judges catalogue keys, not response fields). Extend the census
to `totals`, `constants` and `moves[]` element types, and either type the field or name it as deliberately
unread.

### 2. New-surface compliance
Every feature slice that adds reader-facing copy lands with:
- keys in all three catalogues (parity, fallback, quality, tokens, ICU);
- no literal sites (copy gate floor stays 0);
- placeholder coverage for every call;
- namespace ownership row when a namespace is added;
- a walk check when the copy is visible.

### 3. RTL preparation (structural, documented)
The catalogue layer is direction-agnostic; the layout is not. Audit `styles/globals.css` and the shell for
physical properties (`left`, `right`, `margin-left`, …) and record a migration list to logical properties,
plus the font stack and numeral policy an Arabic/Hebrew catalogue would need. No locale ships until the
structure is ready, but the audit is gate-able and can start now.

### 4. Gate-inventory hygiene
Keep the inventory at 100%: every new `qa-*.mjs` is registered in **both** `scripts/check.sh` and
`.github/workflows/ci.yml` in the same commit that adds it.

## Working rules

- A floor is a statement about the gate before it is a statement about the tree; when a gate refuses,
  first ask whether it can see the class of defect it claims to judge.
- A gate change ships with a witness (a scratch input that makes it red) whenever the verdict shape
  changes.
- Every slice: measure, record in its own doc, commit, push. No slice is "done" on a green echo.
