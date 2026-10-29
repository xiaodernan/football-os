# M13 verification — the board's wage ceiling, stated and enforced

ROADMAP Phase 2 item 6's last open limb was a wage limit the balance cannot stand in for. It landed as
commit `1a0ef84` (2026-10-30): `careers.wage_ceiling` (migration `0044`), stated when the career is opened,
enforced by `buy` and `loan`, previewed on every read, and rendered on the form, the finance panel and each
transfer listing.

Date: 2026-10-30.

## 1. The object, and why it is stated rather than derived

A career's balance says what is *left*, not what the board will let the club commit. Sales income walks the
balance back up; it does not move the board's tolerance for a wage bill, and a cash-rich career can still be
one wage away from its cap. So the ceiling is its own column, not a function of the balance.

It is **stated** when the career is opened (`CareerIn.wage_ceiling`, the same units as the budget) and `0`
means the board sets none. The first version derived it at creation as `floor(budget / 10)`; that version was
dropped before landing because the engine's own arithmetic makes it inert: a signing's fee consumes the
balance, and its weekly wage is `round_5(asking / 500)` of the same asking — so a bill of `budget / 10` could
only be reached by spending roughly fifty budgets in fees. A derived cap that can never be reached is a
sentence, not a limit; a stated one binds the moment a manager states a low one.

Migration `0044` adds the column with `server_default="0"` and no invented backfill: a career opened before
the column holds *no* cap, which is the truthful reading of a row whose manager was never asked.

## 2. Where it binds

One helper, `_require_wage_headroom` in `apps/api/app/services/simulation/market.py`, is called by `buy` and
`loan` immediately after the affordability check, so the two doors cannot disagree about the same cap. A
career with `0` passes; a bill exactly at the ceiling is within it; one credit over is refused with
`409 wage_ceiling_exceeded` (registered in the market tier's `CONFLICT_CODES`, hence in `ANSWERS`) and the
figures that decided it:

| Field | Meaning |
| --- | --- |
| `weekly_wage_bill` | the standing bill before the deal |
| `proposed_weekly_wage` | the wage the deal would add |
| `new_weekly_wage_bill` | the bill after the deal |
| `wage_ceiling` | the board's stated cap |
| `wage_headroom` | `ceiling − bill`, floored at 0 — what the deal had to fit into |
| `formula` | `WAGE_CEILING_FORMULA`, the same string `RULES["wage_ceiling"]` publishes |

The refusal is raised before any row is written: the listing stays open and the ledger's move count does not
change. The bill reads the career's own squad moves, so a sale frees the headroom at once even though the fee
itself arrives against the next round.

## 3. Where it is previewed

The same ceiling is published beside the arithmetic it constrains, so a page prints a verdict instead of
deciding one:

* `budget_position` — `wage_ceiling`, `wage_headroom` (`null` when there is no cap; signed, so an overrun is
  negative).
* `affordability_view` — the two above plus `within_ceiling` for the bill as it stands, and the ceiling is
  passed into the signing preview.
* `signing_impact` — `wage_ceiling`, `wage_affordable` (`null` when no cap) and `wage_headroom_after`
  (signed). Every transfer listing's `signing` block carries these, computed from the same function.
* `RULES["wage_ceiling"]` — the formula, printed by `GET /api/v1/transfers/rules`.
* `AFFORDABILITY_FORMULA` gained the sentence that a signing is also wage-affordable only at or under the
  ceiling — the published derivation now matches what the doors enforce.

## 4. The doors and the pages

* `POST /api/v1/careers` accepts `wage_ceiling` (default `0`, `ge=0`, `le=BUDGET_CEILING`);
  `GET /api/v1/careers/options` publishes `wage_ceiling_units`.
* `apps/web/components/CareerForm.tsx` states it beside the budget, with a help sentence; the field posts
  `Number(...) || 0`.
* `apps/web/components/CareerFinance.tsx` prints the ceiling (or the sentence that the career has none) and,
  when there is one, the headroom.
* `apps/web/components/MarketTools.tsx` prints each listing's cap verdict in its After-signing cell —
  "wage ceiling ok, N left" or "over the wage ceiling by N".
* Three new key pairs in `career`, `careerDetail` and `market` carry those sentences in `en`, `zh` and
  `zh-TW`; the catalogue README's recomputed figures moved to **3,919 of 3,964** in both locales.

## 5. Evidence

| Check | Result |
| --- | --- |
| `pytest tests/test_wage_ceiling.py tests/test_transfers_api.py` | **30 passed** (12 pure/DB + 18 wire, including a not-on-the-door helper that plants a low cap on the row) |
| `pytest tests/test_spec_audit_currency.py tests/test_career.py tests/test_wage_ceiling.py` | **54 passed** |
| `pytest tests/test_locale_claims.py` (worktree) | **7 passed** — the README figure is recomputed, not typed |
| `tsc --noEmit`, `next lint` (worktree) | clean |
| 16 static message gates (`qa-i18n-literals`, `qa-unused-keys`, `qa-key-drift`, `qa-locale-*`, `qa-shared-keys`, `qa-token-drift`, `qa-namespace-ownership`, `qa-population-floor`, …) | **16/16 OK** |
| `alembic upgrade head` on a copy of the QA database | `0043 -> 0044` applies; the walk database then serves |

### The live walk — `.scratch/walk-ceiling.py`, **58/58**

Against a private API on `:8732` over `.scratch/walk-ceiling.db` (a copy of the QA database advanced to
head) and the production build on `:3219`. The career was opened with a stated ceiling of **2,000 credits a
round** and a 4,000,000 budget; the market's twelve offers carried wages
`[1335, 1335, 1780, 1995, 2100, 2150, 2565, 2675, 2745, 2810, 2850, 3100]`.

Measured, in order:

* `options.wage_ceiling_units` says `career credits per round`; a fresh career's affordability block carries
  the stated ceiling and the whole of it as headroom; every listing's `wage_affordable` is exactly
  `wage <= 2000` (4 fit, 8 do not).
* Buying the cheapest wage (1,335) is allowed; the budget block's headroom becomes exactly `2000 − 1335`;
  the career view's affordability block agrees.
* Buying the next 1,335-wage listing is refused `409 wage_ceiling_exceeded` with bill 1,335, proposed 1,335,
  new bill 2,670, ceiling 2,000, headroom 665, and the published formula; the listing stays open and the
  move count stays 1.
* Selling the first frees the bill to 0 and the headroom to 2,000; the same listing is still open; the retry
  is allowed and the headroom ends at `2000 − 1335`.
* A career opened without a ceiling holds `0`, publishes `wage_headroom: null` and `wage_affordable: null`,
  and its market page prints no cap verdict on any row.
* A third career's market page prints exactly one cap verdict per listing (12 cells), split 4 "ok" / 8
  "over", matching the API's own count; the `zh` and `zh-TW` pages print the translated verdict; the career
  page prints "Board wage ceiling 2,000 career credits" and the headroom row, and the Chinese pages print
  their own labels; the form prints the ceiling field in all three locales.

The RSC flight payload duplicates catalogue strings, so the rendered counts are taken from the parsed
`data-wage-ceiling` cells, not from a substring count over the page source.

### The browser pass

Driven in the in-app browser against the same build (the browser was hidden, so this pass is DOM-level: no
screenshot). Logged in as a fresh account, completed onboarding, then:

* `/career` printed the ceiling field with its label ("工资上限 (0 = 不设限)") and help sentence; the form
  was filled with budget 4,000,000 and ceiling 500 and submitted from the button.
* The season page (`/career/browser-ceiling-braa`) printed «董事会工资上限 500 career credits» and
  «工资上限余量 500 career credits», with the affordability formula's new ceiling sentence.
* The market page, opened from its button, printed twelve cap verdicts — all over, because every wage
  exceeds 500 — each equal to `wage − 500` (835, 835, 1,280, 1,495, 1,600, 1,650, 2,065, 2,175, 2,245,
  2,310, 2,350, 2,600).
* Clicking a non-rival listing's sign button produced the refusal notice verbatim:
  `wage_ceiling_exceeded — signing Corand Ruceek would take the weekly wage bill to 3,100 career credits,
  over the board's 500 ceiling`, followed by the published formula. A rival listing clicked first answered
  `rival_will_not_sell` — the clause rule runs before the cap, as the doors order them.

## 6. What this does not claim

* **No door changes a ceiling after the career is opened.** The stated cap is fixed at creation; the wire
  tests and the unit tests plant a different value by writing the row, and that is how the refusal branches
  are exercised. A settings door would need its own answer for what a manager may raise it to, and it does
  not exist yet — the limitation is listed here rather than implied away.
* A career that predates migration `0044` holds `0`: no cap, not a cap of zero credits.
* The cap constrains the **bill**, not a single player's wage, and it does not change how wages are charged —
  `pay_wages` still charges every held deal each round, and the ceiling can only refuse a *new* deal.
* It does not stop a career from running its balance to zero within its cap, and it does not replace the
  balance check: both must pass.
* `wage_headroom` in the refusal is the room *before* the deal (floored at 0); `wage_headroom_after` in a
  preview is the signed figure after it. They answer different questions and are named differently.

## 7. Reproduce

```bash
# the tests
cd apps/api && python -m pytest tests/test_wage_ceiling.py tests/test_transfers_api.py -q

# the private API over a copy of the QA database, advanced to head
cp apps/api/var/qa12.db .scratch/walk-ceiling.db
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-ceiling.db" python -m alembic upgrade head
DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-ceiling.db" uvicorn app.main:app --host 127.0.0.1 --port 8732

# the shipped site on a free port
cd apps/web && npm run build
API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3219

# the walk (API :8732, web :3219), 58 checks
python .scratch/walk-ceiling.py
```
