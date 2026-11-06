# I18N Arc — living plan

Measured on the current tree (2026-11-06, with the uncommitted live-surface milestone in it). Every
number below is re-derived by the gate named beside it; this file is a plan, never the evidence.

## Where the arc stands

| Gate | Verdict |
| --- | --- |
| `qa-i18n-literals.mjs` | 9/9 — 0 English literal sites over 155 `.tsx` files, 4328 key calls, 0 floors, placeholder supply green |
| `qa-unused-keys.mjs` | 3/3 — 0 dead keys; 4202 judged here, 67 delegated to the API's refusal test |
| `qa-locale-completeness.mjs` | 2/2 — 43 namespaces, 4269 keys, full parity `en`/`zh`/`zh-TW` |
| `qa-locale-fallback.mjs` | 3/3 — every English key non-empty in both Chinese catalogues |
| `qa-unused-keys.mjs` / `qa-key-drift.mjs` | 4/4 — 17 same-context drift sites, all named; ceilings 112/46 (reviewed 2026-11-06) |
| `qa-shared-keys.mjs` | 4/4 — 240 bindings across 101 rows; 10 named divergences; may only fall |
| `qa-shared-keys-witness.mjs` / `qa-key-drift-witness.mjs` | 8/8 / 10/10 — the red paths, verified |
| `qa-icu-messages.mjs` | 2/2 — 12807 messages parse; placeholder agreement across locales, now real |
| `qa-icu-coverage.mjs` | 1/1 — catalogue placeholder parity across the three catalogues, now real |
| `qa-plural-select.mjs` | 2/2 — **87 plurals** checked against CLDR (en `one`/`other`; zh/zh-TW `other`) |
| `qa-locale-tokens.mjs` | 5/5 — 45 named identical tokens; README pin 4269/4224; floor 0 |
| `qa-locale-content.mjs` | 3/3 — 28 deliberate locale differences, tracked |
| `qa-locale-formatting.mjs` | 2/2 — real population read: 0 formatted args in the catalogue today |
| `qa-translation-quality.mjs` | 4/4 — no English in Chinese copy, punctuation, encoding, literal-structure |
| `qa-translation-freshness.mjs` | green against `.gate-baseline` |
| `qa-population-floor.mjs` | 3/3 — 3600 → 4269, may only grow |
| `qa-locale-tokens.mjs` | the catalogue's own table states the figures the catalogues hold — pin recomputed |
| `qa-rtl-readiness.mjs` | 8/8 — no physical horizontal CSS; `dir` from `textDirection(locale)`; font stacks end generic; the `:lang(ar)/:lang(he)` letter-spacing reset is required |
| `qa-namespace-ownership.mjs` | 2/2 — 43 namespaces, every one owned (`live` → `core`, 2026-11-06) |
| `qa-gate-inventory.mjs` | 194/194 — every invocable script named by a runner or explained |
| `qa-wire-readers.mjs` | 18/18 — market wire, window, ranges, constants, totals, **moves[]** reconciled (19/16/3/33/10/37 keys) |
| `I18N_ARC_VERIFICATION.md` | §22 — the four ICU gates that were vacuous, found and fixed |

Live-tier walks run through `scripts/run-walks.mjs`; the visual walk through
`apps/web/scripts/visual-qa.mjs`. Their verdicts live in `docs/I18N_ARC_VERIFICATION.md`.

## The goal

Every string a reader sees is in the reader's language; every gate in the suite that can see it says
so; and the day a locale that does not exist today is added, the cost is one catalogue, not a rewrite.

## The arc, in phases

| Phase | Content | State |
| --- | --- | --- |
| P0 Catalogue foundation | one key per sentence, `en` fallback, zh/zh-TW parity, copy gate, dead-key gate, 45 named tokens, refusal catalogue (2026-10-22), ownership ledger (§16) | **done** |
| P1 Wire-readers census | `MarketView`'s keys → window block → signing ranges → constants → totals → **moves[] element type** (`Move`: 37 keys, both directions, 14 exemptions re-measured every run) | **done** |
| P2 Live surface compliance | `nav.live`/`live.*` keys: ownership row, token alignment (`Play a fixture` unified), drift ceilings reviewed and ratcheted (112/46, 240), witnesses re-anchored, README pin recomputed 4269/4224 | **done on the tree; uncommitted with the milestone** |
| P3 Live milestone walks | the match-replay pages on a production build: register-screenshot, locale sweep, `MISSING_MESSAGE` read of the tier logs; §23 records it with the commit | **queued** (check.sh stays the gate; the walks do not block the catalogue) |
| P4 ICU census hardened | the four gates that parsed ICU with string types were vacuous — fixed on 2026-11-06 (see §22): real placeholder agreement, real plural completeness, a real catalogue parity check, and one check retired with its reason written | **done** |
| P5 RTL readiness | structural, gate-able, done (§20): logical CSS, `dir` from `textDirection(locale)`, no physical horizontal declarations; **typography audit** in `docs/RTL_READINESS.md` — what Arabic/Hebrew require before a locale ships | **audit written; no RTL locale ships yet** |
| P6 New-surface compliance | every slice that lands reader-facing copy lands with the full checklist in `docs/NEW_SURFACE_COMPLIANCE.md`: 3-catalogue parity, fallback, quality, ICU, tokens, 0 literal sites, namespace ownership, live-tier walk, gates green | **protocol written; applies to every slice from here** |
| P7 Locale expansion (ar, he) | each new locale: full catalogue, CLDR plural rules (Arabic: zero/one/two/few/many/other), font stacks, numerals policy, bidi handling of LTR inserts, walks and visual QA under `dir=rtl`, CI registration. **Not a catalogue drop — a milestone.** | **researched in RTL_READINESS; not started** |
| P8 Cross-arc maintenance | the API's refusal catalogue grows with the API (test_locale_claims.py holds it in both directions); OpenAPI claims test; catalogue parity kept as surfaces appear (M13 milestone uses it) | **ongoing** |
| P9 Hygiene & permanence | every new `qa-*.mjs` registered in **both** `scripts/check.sh` and `.github/workflows/ci.yml` in the same commit; a witness (a scratch input that reds the gate) ships with any change to a gate's verdict shape; every slice records its figures in `I18N_ARC_VERIFICATION.md` and commits | **ongoing** |

## Queue (in order)

1. **Commit the record.** §22 landed; the plan you are reading is the index. The live-surface
   milestone rides the tree as it is — its gates are green, its commitment is its own (§22's landing
   note says so).
2. **Walk the live surface on a production build.** The replay pages, the feed, the report link;
   the locale sweep and `MISSING_MESSAGE` read. Record in §23 with the commit.
3. **RTL milestone, when it is owed.** `docs/RTL_READINESS.md` lists what Arabic/Hebrew need —
   fonts, plural categories, punctuation, bidi policy — and the acceptance checklist. Do not ship
   `ar` or `he` before the checklist is closed; the cost of doing it early is a locale the gates
   cannot certify.
4. **Discipline.** Each new feature slice follows `docs/NEW_SURFACE_COMPLIANCE.md`; gate changes
   ship with witnesses; the verification doc grows a section per slice.

## Working rules

- A floor is a statement about the gate before it is a statement about the tree; when a gate refuses,
  first ask whether it can see the class of defect it claims to judge. (2026-11-06 found four that
  could not; see §22.)
- A gate change ships with a witness (a scratch input that makes it red) whenever the verdict shape
  changes. Both drift witnesses were re-anchored the same day their parents moved.
- Where a check cannot be made honest against the tree's own tools, it is retired with its reason on
  record, and the stronger holder of the same contract is named. `qa-i18n-literals` (4328 calls) is
  the honest holder for source-side placeholders.
- Every slice: measure, record in its own doc, commit, push. No slice is "done" on a green echo.
- The tree the gates judge is the working tree; the tree a reader sees is the commit — the claims
  test holds them in step (§21).
