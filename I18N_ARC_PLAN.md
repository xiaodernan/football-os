# I18N Arc — living plan

Measured on the working tree **2026-11-07** (`3db6075`, with the in-flight M13 batch uncommitted —
the arc's own record lives in `docs/I18N_ARC_VERIFICATION.md` §20–§31, which is the honest ledger of
this arc; this file is a plan, never the evidence). Every figure below is re-derived by the gate named
beside it.

## Where the arc stands

| Gate | Verdict (working tree / committed) |
| --- | --- |
| `qa-i18n-literals.mjs` | 9/9 — 0 English literal sites; 4328 key calls |
| `qa-unused-keys.mjs` | 3/3 — floor 0 holds both on the working tree and the committed tree (it found the `nav.live` door: `d7784b2`) |
| `qa-locale-completeness.mjs` | 2/2 — discovers shipped catalogues by existence; 43 namespaces, 4269 keys (4096 committed), full parity across every locale the directory carries |
| `qa-locale-fallback.mjs` | 3/3 |
| `qa-key-drift.mjs` | 4/4 — 17 named sites in the working tree (M13 batch uncommitted); 12 in the committed tree; ceilings 112/46, may only fall |
| `qa-shared-keys.mjs` | 4/4 — 240 bindings, may only fall |
| `qa-shared-keys-witness.mjs` / `qa-key-drift-witness.mjs` | 8/8 / 10/10 — verified on both trees |
| `qa-icu-messages.mjs` | 2/2 — 12807 messages parse; placeholders agree, now real (§22) |
| `qa-icu-coverage.mjs` | 1/1 |
| `qa-plural-select.mjs` | 2/2 — CLDR-enforced (en `one`/`other`; zh/zh-TW `other`; Arabic six wired and dormant); 87 plurals on the working tree |
| `qa-locale-tokens.mjs` | 5/5 — both the working-tree pin (4269/4224) and the committed-tree pin (4051/4096) recomputed |
| `qa-locale-content.mjs` | 3/3 |
| `qa-locale-formatting.mjs` | 2/2 — format population read for real |
| `qa-translation-quality.mjs` | 4/4 on the shipped tree; dormant Arabic arms verified arm-by-arm (§26) |
| `qa-translation-freshness.mjs` | 2/2 — `.gate-baseline 3bbf857→d7784b2`; CI uses the event diff (recorded in §25) |
| `qa-population-floor.mjs` | 3/3 — may only grow |
| `qa-rtl-readiness.mjs` | 8/8 |
| `qa-namespace-ownership.mjs` | 2/2 |
| `qa-gate-inventory.mjs` | 194/194 on both trees |
| `qa-wire-readers.mjs` | 18/18 on the full working tree; **12/18 on the committed tree — six named reds, one owner (the uncommitted M13 milestone). See §24/§25.** |
| `I18N_ARC_VERIFICATION.md` | §22 (blind gates), §23 (live walk), §24 (corrections), §25 (CI forensics), §26 (dormant Arabic), §27 (held notes), §28 (battery discovers), §29 (/capabilities discovers), §30 (state at f7e2563), §31 (Hebrew arm landed) |
| `ab82384` CI | api green (two single-test causes cured: `ff521d9` runner-graded fallback; `161fc75` stale audit figures — the `/live` pages outgrew `AUDIT_FIGURES`); web all green through `Wire-readers`; `npm ci` EUSAGE (rendered by a local-side `--legacy-peer-deps` de-sync) cured at `db6e9a3`; the sole remaining red anywhere is `Wire-readers`, owned by the milestone |

## The goal

Every string a reader sees is in the reader's language; every gate in the suite that can see it says
so; and the day a locale that does not exist today is added, the cost is one catalogue, not a rewrite.

## The arc, in phases

| Phase | Content | State |
| --- | --- | --- |
| P0 Catalogue foundation | one key per sentence, `en` fallback, zh/zh-TW parity, copy gate, dead-key gate, 45 named tokens, refusal catalogue (2026-10-22), ownership ledger (§16) | **done** |
| P1 Wire-readers census | moves[] element type reconciled (`Move` 37 keys; constants/totals/window census) — **done** (2026-11-06) | **done** |
| P2 Live surface compliance | `nav.live`/`live.*` keys: ownership row declared (`core`), token alignment (`Play a fixture` unified), emission rules, ceilings reviewed and ratcheted (112/46, 240), witnesses re-anchored, witnesses green on both trees, README pin recomputed twice (working-tree pin and committed-tree pin) | **done** — the milestone's own walk recorded its green sections 2026-11-07; the nav door landed (`d7784b2`) |
| P3 Live milestone walks | the match-replay pages in a production build: 312/316 on 2026-11-07 — Live section green, notifications tray green, erasure green, 1,779-URL probe green; the four reds belong to another lane (career/season checks; sweep coverage-gate ordering) | **done by the milestone's lane (2026-11-07)** — §23 records |
| P4 ICU census hardened | the four ICU gates were vacuous — fixed 2026-11-06 (§22): real placeholder agreement, real plural completeness, a real catalogue parity check, one check retired with its reason written | **done** |
| P5 RTL readiness | logical CSS, `dir` from `textDirection(locale)`, font stacks end generic, `:lang(ar)/:lang(he)` reset gated (§20, gate 8/8); item 1 done 2026-11-07 (nine JSX arrows moved out of the render path); item 2 decided (keep stack, Noto covers Arabic/Hebrew via platform substitution); item 3 landed (qa-plural-select discovers ar, Arabic six CLDR enforced, dormant); item 4 landed (qa-translation-quality Arabic pass: punctuation, mojibake, script assertions — verified arm-by-arm, dormant); item 5 gate-half landed (qa-locale-completeness discovers catalogues) | **structural gate + Arabic pre-work landed; items 6+ (Arabic walk, ar.json) blocked on P7** |
| P6 New-surface compliance | every slice ships with the full checklist — parity, fallback, quality, ICU, tokens, 0 literal sites, namespace ownership, live-tier walk, gates green — `NEW_SURFACE_COMPLIANCE.md` | **protocol in force** (applies to every slice since 2026-11-06) |
| P7 Locale expansion (ar, he) | each locale: full catalogue, CLDR plural rules (AR: zero/one/two/few/many/other), numerals policy, bidi handling, manifests, walks under `dir=rtl`, CI registration; **not a catalogue drop — a milestone** | **researched; not started; waits on P6 + the M13 milestone landing (it is the slice that closes `Wire-readers`)** |
| P8 Cross-arc maintenance | the API's refusal catalogue stays in step (`test_locale_claims.py`), OpenAPI claims stay current, catalogue parity holds as surfaces appear | **ongoing** |
| P9 Hygiene & permanence | any new `qa-*.mjs` registered in **both** `scripts/check.sh` and `.github/workflows/ci.yml` in the same commit; a witness ships with every verdict-shape change; every slice records its figures in `I18N_ARC_VERIFICATION.md` and pushes | **ongoing — and this session it grew two teeth**: the committed-tree pin and witness anchors distinguish committed vs working tree explicitly (§24/§25) |

## Queue (in order)

0. **CI holds green as lanes land.** The 2026-11-07 forensics (§25) closed three api causes and one
   web-installer de-sync; `Wire-readers` closes on the milestone's landing. Each lane may not excuse a
   red by citing another lane's pending change — a red anywhere is named, or the milestone owes the fix.
1. **The M13 milestone lands.** It owns Wire-readers (§24/§25) and the 173 in-flight catalogue keys.
   Its own records (`docs/M13_WIRE_READERS_TOTALS_VERIFICATION.md` and siblings) confirm the gate —
   once it lands, CI web goes green through the wire gate and the last named red closes. Owner: the
   milestone's lane, not this arc. The README pin recomputes when it does (checklist item).
2. **Walk the live surface orchestrate** — recorded already (§23; 312/316, four reds attributed to
   another lane).
3. **RTL milestone, when it is owed.** `docs/RTL_READINESS.md` lists the acceptance items — fonts,
   plural categories, punctuation, bidi policy, catalogue parity, walks under `dir=rtl`, CI registration.
   Item 1 closed 2026-11-07; items 2–5 landed 2026-11-07 (font decision item 2; plural arms 3; quality
   arms 4; parity discovery 5; Arabic gates §26, `af06f60`/`9e89acb`/`f7e2563`/`c852a42`); the whole battery
   discovers catalogues by existence (§28); the API's `/capabilities` discovers them too (§29); the arc's standing
   at f7e2563 is recorded. The milestone inventory lives in §27; state-of-the-arc in §30. Do not ship `ar` or
   `he` before all the items are green.
4. **The discipline.** Every new slice follows `NEW_SURFACE_COMPLIANCE.md`; gate verdict-shape changes
   ship with witnesses; the verification doc grows a section per slice, push every time.

## Working rules

- A floor is a statement about the gate before it is a statement about the tree; when a gate refuses,
  first ask whether it can see the class of defect it claims to judge. (2026-11-07 found four that could
  not; see §22. §25 shows the same in the CI window: a stale figure in the audit's machine-readable line.)
- A gate change ships with a witness (a scratch input that makes it red) whenever the verdict shape
  changes. Both drift witnesses were re-anchored the same day their parents moved.
- Where a check cannot be made honest against the tree's own tools, it is retired with its reason on
  record, and the stronger holder of the same contract is named. `qa-i18n-literals` (4328 calls) holds
  the source-side placeholder contract; `qa-i18n-literals` wins.
- Every slice: measure, record in its own doc, commit, push. No slice is "done" on a green echo.
- The tree the gates judge is the working tree; the tree a reader sees is the commit — the claims test
  holds them in step (§21). Both pins (working and committed) are recomputed and recorded; the day they
  disagree is a merge of two honest measurements, not a contradiction (§24).
