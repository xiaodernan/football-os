# M13 verification — the career's finance book, rendered

The API half of ROADMAP Phase 2 item 6 landed in three commits: `a11d965` composed the wage bill and the
balance into a runway and a signing preview, `6b864d6` walked the balance in round order and cross-checked
each ledger row's stored `budget_after`, and `3c47b56` put the same signing arithmetic on each transfer
listing. `career_view["affordability"]` has published that block on every read since — and
`apps/web/app/career/[slug]/page.tsx` never read it. This increment renders it: the standing figures, the
runway, and the timeline with its per-row agreement, in all three locales.

Date: 2026-10-27.

## 1. What the block publishes

Everything is recomputed from `career_squad_moves` and `career_wage_charges` on the request; no counter is
stored.

| Field | Meaning | When it is interesting |
| --- | --- | --- |
| `remaining` | `budget − fees paid − wages charged` | always |
| `weekly_wage_bill`, `wage_players` | the wage charge the career is carrying, and by how many players | always |
| `wage_runway_rounds` | `max(0, floor(remaining ÷ weekly_wage_bill))` | **`null`** when the bill is zero — the balance sets no wage-driven limit |
| `formula`, `note` | the derivation and what the figures do not promise | always |
| `timeline.entries` / `entries_shown` / `truncated` | how many ledger rows exist, and how many the block carries (limit 8) | a long career |
| `timeline.opening_balance` / `closing_balance` | `career.budget` and the running figure after the last row | always |
| `timeline.rows[]` | round index, kind, label, signed delta, recomputed `balance`, stored `budget_after`, `agrees` | always, when entries > 0 |
| `timeline.disagreements` | rows where the recomputed balance differs from the figure stored when the row was written | should be 0; a non-zero count is the whole point of the check |

## 2. What the page prints

`components/CareerFinance.tsx` is a server component. It prints the wire figures and the API's own
`formula` strings; the page does no arithmetic of its own, so the runway and the timeline cannot drift from
the balance they were derived from.

* A key/value grid for the remaining balance, the weekly bill, the wage-player count, the runway (or the
  sentence that there is no wage limit), and the runway formula.
* The block's `note`, in muted text.
* The timeline: round, entry (kind badge plus label), signed movement, recomputed balance, stored figure,
  and an **agrees / disagrees** badge per row.
* A summary naming `shown / entries`, the opening and closing balances and the units; a truncation notice
  when the API had to cut rows; a disagreements notice when any row fails the check, otherwise the
  all-agree sentence.
* The timeline formula, then `limitations.projections` as a warning notice.

The zero-deal `signing` block is deliberately **not** printed. With no prospective deal passed, it is the
arithmetic for a fee of 0 and a wage of 0 — true, and empty. The transfers page owns the real preview; that
rendering is still open (see §7).

## 3. The live walk — one signing, two rounds

Built with `next build` and served by `next start -p 3211` with `API_INTERNAL_URL=http://127.0.0.1:8732`,
against a private API on 8732 backed by a copy of the QA SQLite database advanced to head with
`alembic upgrade head`. The career `finance-walk-braa` was opened at the world's budget ceiling
(10,000,000), signed the cheapest affordable listing (Xaniel Kastan, fee 668,250, weekly wage 1,335), and
played rounds 1 and 2.

The expected figures below were read from the API response first, then asserted against the rendered HTML —
never typed into the check by hand:

| Round | Entry | Movement | Recomputed balance | Stored `budget_after` | Agrees |
| --- | --- | --- | --- | --- | --- |
| 1 | buy Xaniel Kastan | −668,250 | 9,331,750 | 9,331,750 | yes |
| 1 | wages for 1 player(s) | −1,335 | 9,330,415 | 9,330,415 | yes |
| 2 | wages for 1 player(s) | −1,335 | 9,329,080 | 9,329,080 | yes |

Standing figures: remaining **9,329,080**, weekly bill **1,335**, wage players **1**, runway **6,988**
rounds. Three entries, three shown, opening 10,000,000, closing 9,329,080, **0 disagreements**.

**31 checks, all passing, in `en` and `zh`.** They cover: the panel title and eyebrow; every standing
figure; the runway sentence; each entry label; each stored and recomputed figure; exactly one agreement
badge per row; no disagreement badge; the summary sentence with both balances and the units; the all-agree
sentence; both formulas; the projections limitation; the structural carriers
`<th scope="col">Running balance</th>` and `<th scope="col">Stored after</th>`; the Chinese renderings
(余额能覆盖什么, 工资跑道, 按此账单还能撑 6988 轮, 滚动余额, 一致) carrying the same figures; and the absence
of each locale's strings in the other.

## 4. The zero branch

A second career was opened with a 100,000 budget, no signings and no rounds. The API answered
`weekly_wage_bill == 0`, `wage_runway_rounds is None`, `timeline.entries == 0`.

The page then prints the zero-bill sentence in place of a runway, the empty-timeline title and body, no
agreement badge, no timeline table, and the career's 100,000 credits; the Chinese strings render, and the
English ones are absent from the Chinese page. **9 checks, all passing.**

One check had to be fixed before it could be trusted: the first version asserted that the string
"Running balance" was absent from the empty page, and it was not — the page embeds the whole message
catalogue, so the key's English value is present in the HTML even when the table is not rendered. The
check now asserts the table's structural carrier (`<th scope="col">Round #</th>`) instead, and the
populated-page run gained the matching positive assertion. This is the same class of false green that
`qa-i18n-literals` exists to prevent on the shipped side: search for the markup, not the string.

## 5. Catalogue and gates

Twenty-four keys were added to each of `en.json`, `zh.json` and `zh-TW.json` (the finance panel, its
figures, the timeline table, the summary, both empty states and both formulas); §7 then adds eight
listing keys per locale. With the finance unit alone the catalogue held **3,624 keys**, **3,579** of them
translated (the other 45 fall back to English); with §7 it holds **3,632** / **3,587**. The table in
`messages/README.md` carries the current counts, and `qa-locale-tokens` check 4 together with the API's
`test_locale_claims.py` recompute the population from the catalogues, so a stale README fails.

The English values were chosen to stay unique catalogue-wide, because `qa-shared-keys` compares values:
`Movement` rather than `Change` (the latter is already `tactics.deltaChange`), and no sentence was reused
between namespaces. The gate stayed at **234 namespace bindings across 98 rows, ceiling 234**.

Gates run at the tree this record describes:

| Gate | Result |
| --- | --- |
| `npx tsc --noEmit` | clean |
| `next build` | succeeded; page served and walked |
| `qa-locale-tokens` | 5/5 |
| `qa-shared-keys` | 4/4 — 234 bindings / 98 rows, ceiling 234 |
| `qa-shared-keys-witness` | 8/8 |
| `qa-key-drift` | 4/4 |
| `qa-key-drift-witness` | 10/10 |
| locale completeness, ICU coverage/messages, plural/select, content, formatting, i18n literals, unused keys, token drift, namespace ownership | green |

## 6. Reproduce

```bash
# API: a private database advanced to head
cp apps/api/var/qa12.db .scratch/walk.db
DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk.db" \
  .venv/Scripts/python -m alembic -c apps/api/alembic.ini upgrade head
DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk.db" \
  .venv/Scripts/python -m uvicorn app.main:app --port 8732

# Web: a production build against that API
cd apps/web && API_INTERNAL_URL="http://127.0.0.1:8732" SITE_URL="http://127.0.0.1:3211" \
  npx next build && npx next start -p 3211
```

The walk's page checks lived outside the tree (`apps/web/scripts` has no committed finance walk): register,
open a career at the budget ceiling, open the market, buy the cheapest affordable listing, play two
rounds, then fetch `/career/{slug}` with the `fo_access` cookie and `fo_locale=en` / `fo_locale=zh` and
assert the figures from the API response. The API-side invariants are committed instead:
`tests/test_affordability.py` (the pure helpers), `tests/test_career.py` (`TestAffordability`, the empty
zero state) and `tests/test_transfers.py` (`TestLedger`, the stored-balance check).

## 7. The transfers board: what signing would do

`listing_row` has carried a `signing` block since `3c47b56`; the page did not read it. This unit closes
that: `Listing` in `lib/market.ts` now imports the `SigningImpact` shape from `lib/types.ts` and carries
`signing`, and `MarketTools` gains an **After signing** column between *Offers* and *Deal*. It is a new
column at the end of the data cells, so the existing market walk's index-based reads (cells 0–10) are
untouched.

Each cell prints the listing's own block and decides nothing:

* the verdict (`covered` / `over budget`, from `fee_affordable`);
* the balance the fee would leave (`leaves {amount} {units}`) or how far short the price is
  (`short {amount} {units}`, the absolute value of the negative balance);
* the new weekly wage bill (`bill {amount}`);
* the runway at that bill (`runway {rounds}`, or `no wage limit` when the block's
  `new_wage_runway_rounds` is `null`).

The Sign button's disabled state was already driven by `affordable`, which the API computes as the same
comparison as `fee_affordable`; the walk asserts the two agree rather than assuming it.

Eight keys were added to each locale, taking the catalogue to **3,632 keys / 3,587 translated** (the
`messages/README.md` table carries those counts). English values were kept unique catalogue-wide, so the
shared-key gate stayed at **234 bindings / 98 rows**.

The live walk opened the market on two careers:

| Branch | Career | Listings | First row (API → rendered) |
| --- | --- | --- | --- |
| wages already on the books | `finance-walk-braa` (balance after one signing and two rounds) | 12, all affordable | `covered`, leaves 7,754,080 career credits, bill 3,435, runway 2,257 |
| 100,000 budget | `signing-walk-braa` (fresh, no signings) | 12, all priced above the balance | `over budget`, short 1,475,000 career credits, bill 2,100, runway 0; Sign disabled |

**156 checks, all passing.** For every one of the 24 listings the check reads the cell back out of the
served HTML and compares all four figures plus the verdict and the button state against the API response
saved by the walk; it also asserts the structural header in both languages, one fully translated cell per
branch, and that each locale's header is absent from the other page. `tsc --noEmit` and `next build` are
clean; `qa-locale-tokens` 5/5, `qa-shared-keys` 4/4 (234 / 98), its witness 8/8, `qa-key-drift` 4/4 and
its witness 10/10, with the remaining catalogue gates green.

## 8. Not claimed by this increment

* **The `no wage limit` sentence was not exercised live.** Every listed player carried a wage, so the new
  bill was always positive and the runway was a number; the `null` branch is rendered but unproven here.
* **There is no budget ceiling.** A balance is what is left; a hard cap on what may be committed is a
  different object and does not exist.
* **The truncation and disagreement branches of the career timeline were not exercised live.** The walk had
  three entries and zero disagreements; the API tests pin the disagreement count, and the truncation
  notice is untested against a career long enough to trigger it.
* **Neither page does arithmetic or stores anything.** They print the API's figures and formulas; a change
  to the derivation is a change to `market.py`, and the pages follow without an edit.
