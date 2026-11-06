# New-surface compliance — the checklist every feature slice follows

A *new surface* is any interface slice that adds reader-facing copy: a page, a panel, a component, an
email, a refusal, a notification. This is the list a slice must pass before it is shown to a reader,
derived from the gates this project actually runs. The catalogue work is part of the slice, not a
follow-up task.

**Measure everything on the working tree, record everything in `I18N_ARC_VERIFICATION.md`, then
commit.** A green echo is not evidence; the gate named beside each item is the evidence.

## Before writing copy

1. **Know the namespace.** Read `apps/web/messages/README.md` for the ownership ledger and the
   namespace list. A new surface maps to an existing namespace almost always; a new namespace needs an
   ownership row in `qa-namespace-ownership.mjs` **and** a purpose — it lands in the same commit.
2. **One sentence, one key — never assembled from parts.** No sentence is built from fragments; every
   message is a whole ICU message with its own placeholders. (§9 of the verification record explains
   why the parts-table was deleted.)
3. **Integers in messages → ICU plurals**, not `{s}` hacks or `plural:` arguments. (The
   `market.fieldingReads` incident, §22: English hand-rolled `goalkeeper{plural}`; it rendered right
   only because the call site remembered to pass `plural`. It is now a real ICU plural.)

## The landing checklist

| # | Gate / step | Command | The verdict it must give |
| --- | --- | --- | --- |
| 1 | parallel catalogues | edit `en.json`, `zh.json`, `zh-TW.json` together | same keys, same shape, in all three |
| 2 | key existence & values | `node apps/web/scripts/qa-i18n-literals.mjs` | 0 literal sites; every key asked for is held; every placeholder supplied |
| 3 | placeholder agreement | `node apps/web/scripts/qa-icu-messages.mjs` | 2/2 — no key asks for different placeholders in different catalogues |
| 4 | plural completeness | `node apps/web/scripts/qa-plural-select.mjs` | 2/2 — CLDR categories present, no empty branch |
| 5 | dead keys | `node apps/web/scripts/qa-unused-keys.mjs` | 0 asked-for-by-nothing; a new dead key lowers nothing, it raises the floor |
| 6 | parity | `node apps/web/scripts/qa-locale-completeness.mjs` | 2/2 — namespaces equal in all three |
| 7 | fallback | `node apps/web/scripts/qa-locale-fallback.mjs` | every English key non-empty in zh and zh-TW |
| 8 | tokens | `node apps/web/scripts/qa-locale-tokens.mjs` | 5/5 — a value identical in every catalogue must be a **named** technical token; README table recomputed if the population moved |
| 9 | same-sentence wording | `node apps/web/scripts/qa-locale-tokens.mjs` (check 5) | 0 / 0 — identical English held under two keys is one wording everywhere |
| 10 | translation quality | `node apps/web/scripts/qa-translation-quality.mjs` | no untranslated English in Chinese copy, punctuation per locale, no mojibake, no literal-structure |
| 11 | shared-key discipline | `node apps/web/scripts/qa-shared-keys.mjs` | 4/4 — divergences named in the ledger (with the reason the two contexts differ), ceilings only fall |
| 12 | key drift | `node apps/web/scripts/qa-key-drift.mjs` | 4/4 — same-context groups all in the reviewed ledger; ceilings only fall |
| 13 | ICU parse | `node apps/web/scripts/qa-icu-messages.mjs` check 1 | every message parses |
| 14 | namespace ownership | `node apps/web/scripts/qa-namespace-ownership.mjs` | 2/2 — every namespace owned, with a purpose |
| 15 | copy gate floor | item 2 already covers; keep the floor at **0** | — |
| 16 | the **walk** | the surface's live-tier walk, or `visual-qa.mjs` locale sweep | the page renders in Chinese with no English residue; no `MISSING_MESSAGE` in the tier logs |
| 17 | the **record** | append the slice's section to `docs/I18N_ARC_VERIFICATION.md` | figures measured, not asserted |
| 18 | the **gate** | any new `qa-*.mjs` is in both `scripts/check.sh` and `.github/workflows/ci.yml` | inventory stays 194/194 |
| 19 | the **witness** | a scratch input that reds the gate | ships in the same commit when a verdict shape changes |

## Cross-locale rules of thumb

- **Chinese needs no plural inflection** — but the same key in English still needs the ICU plural
  branches; zh carries `other` with the whole noun phrase.
- **Placeholders keep their names in every catalogue.** `{count}` stays `{count}`; translators translate
  around it, not it.
- **An identical-in-all-three value must be a named token** (acronyms, units, API field names printed
  as themselves). If a new one appears, add it to `qa-locale-tokens.mjs`'s list with its reason — never
  leave an identical sentence unnamed.
- **A sentence held by two keys is one sentence.** The em-dash belongs to the sentence, not to the key;
  differing wording for one English sentence is a translation defect, not a style choice.
- **The API's English is the API's English.** Quoting it is allowed; translating it is not.
  Mechanical parity for refusal codes lives in `apps/api/tests/test_locale_claims.py` and the web
  tier's `lib/refusals.ts`.

## When a gate refuses

1. First ask whether the gate can see the defect. (2026-11-06 found four that could not — §22 — and
   two of them passed because they measured nothing.)
2. If the gate is blind, fix the gate (with a witness), not the tree.
3. If the gate is right, fix the tree in all three catalogues **in the same slice**, and re-run every
   gate — parity is not a local fix.
4. If the fix is a legitimate divergence, name it in the ledger with the reason, in the same commit.
5. Record what changed in `I18N_ARC_VERIFICATION.md` and, if figures moved, in the README pin.
