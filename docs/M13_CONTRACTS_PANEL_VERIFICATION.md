# M13 verification — the career's deal book, rendered

`career_view["contracts"]` landed in `90739d7` (M13 Phase 2): every held deal's expiry projected from
the terms the market stored, a flag inside a 3-round warning window, and the squad's age profile with
its retirement flag. The API answered with it on every career read — and `apps/web/app/career/[slug]/page.tsx`
never read it, and `apps/web/lib/types.ts` had no type for it. This increment renders the block: the
standing figures, the two-branch deal table, and the age profile, in all three locales.

Date: 2026-10-28.

## 1. What the block publishes

Everything is recomputed from `career_squad_moves` and the squad's stored ages on the request; no
expiry is ever written back. Nothing in this build expires or renews a contract — the book is a
projection, stated as such on every row and in the block's `note`.

| Field | Meaning |
| --- | --- |
| `current_round`, `season_rounds` | the round about to be played, and the season horizon the projection multiplies by |
| `deals`, `expiring_soon` | held-deal count, and how many sit inside `warning_rounds` |
| `total_weekly_wage`, `expiring_weekly_wage`, `units` | the wage bill the book carries, and the slice inside the window |
| `warning_rounds` | `EXPIRY_WARNING_ROUNDS = 3` |
| `rows[]` | player, effective kind (`buy` / `loan` / `loan_out`), weekly wage, `signed_round`, `contract_years`, `expiry_round`, `rounds_remaining`, `expiring_soon`, and the `basis` the projection read |
| `age_profile` | squad size, mean, median, five age bands, `retirement_age = 35`, and named `retirement_risk` entries |
| `formula`, `note` | the arithmetic and what it does not promise |

A permanent deal's expiry is `signed_round + contract_years × season_rounds − 1`; a loan's is the
`loan_until_round` it was agreed at. `rounds_remaining` counts from the round about to be played; a
row with no stored length projects nothing and says so in `basis`.

## 2. What the page prints

`components/CareerContracts.tsx` is a server component wired into the career page between the finance
book and the fixture list. It prints the wire figures and the API's own strings; the page does no
arithmetic of its own, so the book cannot drift from the terms the market stored.

* A key/value grid for the round line, deals held, the full wage bill, the wages inside the warning
  window, and the warning window itself.
* The deal table — empty-state title when `deals` is 0 — with one row per deal: player, kind badge
  (`permanent` / `loan in` / `loan ended`), weekly wage, signed round, projected expiry round,
  rounds remaining (with the `expiring` badge when flagged), and the basis.
* The projection's `note` and `formula`.
* The age profile: squad size, mean, median, the retirement flag, the named risks (or the no-risk
  sentence), and the five bands as a table, closed by the profile's own note.
* `limitations.projections` as a warning notice, as the sibling panels do.

36 new keys under `careerDetail` in `en.json`, `zh.json` and `zh-TW.json`. Two headers were worded to
*avoid* duplicating existing cross-namespace values — `contractsAgeThBand` is "Age range" (not
`club.tableHeaderAgeBand`'s "Age band") and `contractsAgeThPlayers` is "Players counted" (not the
"Players" three other namespaces hold) — so the `qa-shared-keys` ceiling stays at 98 sentences / 234
bindings, which may only fall. The player column reuses the namespace's existing `thPlayer`.

`apps/web/messages/README.md`'s population table moved with the catalogues: 3750 keys, 3705
translated in each Chinese file, the same 45 named fallback tokens — and `qa-locale-tokens.mjs`
checks the table against the catalogues, so the figures are derived, not typed.

## 3. The live walk — one clause buy, one loan, one empty career

Built with `next build` and served by `next start -p 3213` with `API_INTERNAL_URL=http://127.0.0.1:8732`,
against a private API on 8732 backed by `.scratch/walk-board.db` (a copy of the QA SQLite database).

The career `opponent-walk-cycle-braa-05Qm` (round 10 of the walk account) opened its market. The
cheapest listing's plain-price buy was refused with `rival_will_not_sell` — Haldwick Sporting shares
the career's competition and only the release clause moves them — so the buy went through the clause
(`clause = asking × 1.5`), which is itself part of the walk's record. Then a 2-round loan.

The expected figures below were read from the API response first, written to
`.scratch/contracts-expect.json`, and asserted against the rendered HTML by
`.scratch/check-contracts-page.py` — never typed into the check by hand:

| Deal | Kind | Weekly wage | Signed | Projected expiry | Remaining | Basis | Flagged |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Elum Eldtis | `buy` (permanent) | 1,335 | 10 | 17 | 8 | `1 year(s) × 8 rounds` | no |
| Xaniel Kastan | `loan` (loan in) | 1,335 | 10 | 11 | 2 | `the loan's agreed last round` | **yes** — inside the 3-round window |

The arithmetic the page prints but does not perform: the buy's `10 + 1 × 8 − 1 = 17`, remaining
`17 − 10 + 1 = 8`; the loan's `11 − 10 + 1 = 2`.

The age profile on the same career: 17 squad members, mean 27.2, median 27, retirement flag at 35,
bands 3 / 4 / 5 / 2 / 3 (sums to 17), and one named risk — Xaniel Kastan, the loaned 36-year-old.

A second career, `opponent-walk-strong-dunt-YWz8`, holds no deals: the page shows the empty state
("No deals on the book", eyebrow "0 held · 0 inside the warning window") while the squad's ages still
render, because the profile comes from the stored squad and not from the deals.

`.scratch/check-contracts-page.py`: **46 checks, 0 red** over `en`, `zh`, `zh-TW` and the empty
career — figures, badges, bases, band counts, risk names, the panel's own words in both Chinese
catalogues, and the zeroed eyebrow.

## 4. Gates

| Gate | Result |
| --- | --- |
| `tsc --noEmit` | 0 errors |
| `eslint` on the three touched files | clean |
| `qa-shared-keys.mjs` | passed — ceiling held at 98 sentences / 234 bindings |
| `qa-key-drift.mjs` | 4/4 checks passed |
| `qa-locale-tokens.mjs` | 5/5 — re-derived 3750 keys / 3705 translated from the catalogues and matched the README's table |
| `qa-i18n-literals.mjs` | 8/8 — every key call supplies the values its message needs |

## 5. Disclosures

* The walk's buy went through a release clause, so the fee the ledger carries is `asking × 1.5`; the
  deal book reads wages and terms, not fees, so the clause does not appear in the panel. The plain
  price would print the same rows.
* `loan_out` (a loan that has run past its agreed last round while the player is still held) has no
  live row in this walk — the walk's loan is still inside its window. The kind label and the
  `expiry_round = null` branch exist in the component; `expiry_round = null` itself has no live row
  either (both signed deals carry stored lengths). Both spellings are one `t()` away from the tested
  paths and no arithmetic of the page's own depends on them.
* `contractsRoundValue` renders the API's own `current_round of season_rounds` figures; when a career
  is past its first season the global round can exceed the per-season horizon (this walk printed
  "10 of 8"). That is the API's published pair, not the page's arithmetic, and the API's `basis`
  string beside each row is what explains the projection.
* The `notifications` OpenAPI staleness that had every `api` CI run red since `7f17b30` was cured in
  `d9f3d98` (the gate's own regeneration command, +156 lines, nothing else). The `web`
  namespace-ownership red remains foreign (the lane's own declaration, still uncommitted there).

## 6. Reproduce

```bash
# the private API (already running on 8732 with .scratch/walk-board.db)
DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-board.db" uvicorn app.main:app --port 8732

# the shipped site
cd apps/web && npm run build
API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3213

# the walk
python .scratch/contracts-setup.py          # signs the buy + loan, writes contracts-expect.json
python .scratch/check-contracts-page.py     # 46 checks against the rendered HTML
```
