# M13 verification — the board pays a season, and the market spends it

ROADMAP Phase 7 item 24. Date: 2026-11-02.

A career's budget was a one-way door. `career.budget` was written once when the career opened and moved
only when money left it: a fee on `buy`/`loan`, a wage charge every round it played. Sales walked money
back in, and nothing else did. So a second season always began with less of it than the first, and a
career long enough to cross a boundary — which Phase 2 items 8 and 9 made possible — was spending down
toward a market it could no longer enter. This item adds the first row whose money *arrives*.

## 1. The arithmetic, and the one verdict that pays nothing

Three authored constants in `apps/api/app/services/simulation/market.py`, stated beside the formula that
uses them:

```
SEASON_GRANT_PER_ROUND = 8,000      per round the season actually played
SEASON_GRANT_PER_POINT = 2,500      per point the season actually earned
PROMOTION_GRANT        = 150,000    when that season's verdict is `promoted`

grant = rounds x 8,000 + points x 2,500 (+ 150,000 if promoted)
```

`season_grant(rounds=, points=, verdict=, units=)` is pure and holds the whole rule, including the one
exemption: **a `challenge` verdict pays nothing whatever its record**, because that run is judged by the
challenge's own reward. The exemption is stated in that single function, not at the call sites, so the
boundary that pays a grant and the page that projects one cannot drift apart on it. A grant of `0` writes
no row, so a season with nothing to pay for leaves no zero for a page to explain.

The figures are authored rather than derived for the same reason the wage ceiling was: a constant derived
from the budget would be paid out of the budget it came from and would change nothing. They are sized
against the market they are meant to feed — measured on the live board this walk plays against, the
cheapest listing's `current_price` is **668,250**, its release clause **1,002,375**, and its loan **100,238**
(15 % of the asking price). One closed season at a tier-2 pace pays **152,000**, which is a loan and some,
and roughly a quarter of the cheapest outright signing. That is the honest claim: a season's grant keeps a
career in the market, it does not buy it a first-class player.

## 2. When it is written

`close_season` (career.py) pays inside its own transaction: the boundary row is added, `pay_season_grant`
adds the award, and the single `session.commit()` that follows makes both visible together. A career
either has its verdict and its money or has neither — there is no window in which the season closed and
the grant did not arrive.

`uq_career_award_season` (career_id, season_index) makes *one grant per season* a property of the schema,
the same way `uq_career_season_index` does for the decision. `test_a_second_hand_written_grant_for_the_same_season_is_refused`
plants a duplicate by hand and reads back `IntegrityError`, so the rule cannot become one coin flip if
`close_season` is ever called twice on the same boundary.

The table is `career_budget_awards` (migration `0047`, 14 columns, `ix_budget_award_career_round`), the
ledger's third table after `career_squad_moves` and `career_wage_charges`, and it stores its own running
`budget_after` like the other two. It is its own table and not a column on `career_seasons` because the
season row is a *decision* and deliberately caches no figure; money that changed the balance belongs with
the rows that changed it.

`.scratch/check0047.py` builds a fresh SQLite through `alembic upgrade head` and diffs the reflected table
against `Base.metadata`: **`DRIFT: none`**, head at `0047`.

## 3. Where it is published

Every read that already answered "what does this career have" now answers it with the money that arrived:

- `budget_position` — `granted`, `grant_rows`, `grant_detail` (`season 1: 152,000`), and `remaining` =
  `budget + received + granted - spent - wages_paid`. The formula string it prints names
  `sum(budget_awards.amount)` so a reader can add the balance up from the rows.
- `budget_timeline` — a grant is rank **2** within its round, after the move (0) and the wage charge (1),
  because that is the order the three are written in. The walk's running balance reproduces each stored
  `budget_after` to the cent; a disagreement is counted, never hidden.
- `market_view` — the grant is appended as a ledger row in the moves table's own shape (`award_row`), so
  money arriving is printed by the same table that prints money leaving: `side`/`cash` = `in`, the name is
  `board grant for season N`, the `detail` is the basis string, `effect` is `AWARD_EFFECT`.
  `totals.grant_rows` counts them, and `constants` publishes the three figures. `RULES["grant"]` prints the
  formula, so the rule census judges it like the other rules.
- `affordability_view` — the same awards feed both the position and the timeline, one query, and it
  publishes `granted` / `grant_rows`.
- `seasons_view` — each closed season carries its `grant` beside the verdict it was paid for (amount,
  units, basis, promotion, budget_after, round_index, formula), or `null` when it paid none; and the season
  being played carries `grant_if_closed_now`, the same pure arithmetic over the rounds it has already
  stored. That block is a projection and nothing writes it: the test asserts the awards table is still empty
  and `granted` is still 0 after reading it.

## 4. What the web tier prints

- `components/CareerSeasons.tsx` — a seventh column, `seasonsThGrant`, on the closed-seasons table: the
  amount with the career's own units and the basis string beneath it, an em-dash for a season that paid
  nothing. A new grid row `seasonsGrantNowLabel` prints the projection. Money and units are composed at the
  call site, the way `CareerFinance` and the market ledger already compose every other figure, so no
  template key is needed.
- `components/CareerFinance.tsx` and `app/career/[slug]/market/page.tsx` print whatever rows the ledger
  holds, so the grant arrives there with no new panel: the timeline row with its stored-balance agreement
  badge, and the market ledger row with its fee, balance and basis.
- The market ledger's contract cell now treats a grant the way it treats a wage — an em-dash. Money
  arriving signs no contract; before this it printed `0 years`.
- `lib/types.ts` gains `SeasonGrant` and `SeasonGrantProjection`; `lib/market.ts` types `granted`,
  `grant_rows`, `grant_detail`, `totals.grant_rows` and the three constants.
- Copy: 2 new `careerDetail` keys in each of `en.json`, `zh.json`, `zh-TW.json`, inserted in alphabetical
  position line-by-line (`python` script, CJK spelled by code point so nothing was re-encoded on the way in).

## 5. Gates and tests, as run

| gate | result |
| --- | --- |
| `pytest tests/test_career.py::TestSeasonGrants` | 12 tests |
| `pytest tests/test_transfers.py::TestBoardGrants` | 4 tests |
| `pytest -k "season or grant" tests/test_career.py`, `tests/test_transfers.py` | **34 passed, rc 0** |
| `ruff check` on `market.py`, `career.py` | All checks passed |
| `mypy market.py` | no issues |
| `tsc --noEmit`, `eslint` on the four changed files | rc 0 |
| `qa-wire-readers.mjs` | **12/12** |
| `qa-unused-keys.mjs` | **3/3** — 0 keys asked for by nothing, floor 0; 3,962 judged, 66 delegated |
| `qa-token-drift.mjs` | **2/2** — 45 named tokens stable, 0 unnamed identical values |
| `qa-locale-completeness` / `qa-population-floor` | **2/2** and **3/3**, en=zh=zh-TW=4,028 **on that working tree** — the commit that holds this item carries 4,012 each (§9) |
| `qa-icu-messages` / `qa-icu-coverage` / `qa-key-drift` / `qa-namespace-ownership` / `qa-translation-freshness` / `qa-shared-keys` | all rc 0 |
| `.scratch/check0047.py` | DRIFT: none |

The token-drift gate reds on the first attempt: a `seasonsGrantNowValue` of `{amount} {units}` is
byte-identical in all three locales, and the gate's rule is that such a value is either a named technical
token or a composition the source should do itself. Naming it would have meant editing the i18n lane's
`scripts/qa-*.mjs`; the codebase's own idiom for money plus units is to compose it at the call site, so the
key went away instead. `qa-unused-keys` holds the floor at 0 both before and after.

## 6. The live walk

`.scratch/walk-grant.py` — fresh alembic-built SQLite, uvicorn on `:8791`, a career opened with
`budget: 0` on the lowest league's weakest club, and every assertion re-derived from the constants the same
response publishes. Two runs, two different generated worlds, both **exit 0**:

| | run 1 | run 2 |
| --- | --- | --- |
| club / league | Braeford Athletic, Braehaven Elite League (tier 2) | same |
| season 1 record | 14 rounds, 14 points | 14 rounds, 4-4-6, 16 points, GD −4 |
| verdict | `stayed` | `stayed` |
| grant | **147,000** = 14 × 8,000 + 14 × 2,500 | **152,000** = 14 × 8,000 + 16 × 2,500 |
| loan it then paid | 90,110 (Zeek Drosttis) | 90,110 |
| standing after the loan | 56,890 | 61,890 |
| season 2 round 1 | 55,690 after a 1,200 wage | 60,690 after a 1,200 wage |
| timeline | 3 rows, `['season_grant', 'loan', 'wage']`, **0 disagreements** | same |

The same walk proves the hole it closes: **before** the boundary the identical 90,110 loan is refused,
because 0 cannot pay it; after the boundary the same listing is signed from the grant alone. The projection
arm is exercised by the two runs together — run 1's career stood on one won round at a 3.000 pace and
projected **165,500** (8,000 + 3 × 2,500 + the 150,000 promotion bonus), run 2's stood on one drawn round
and projected **10,500** with no bonus.

## 7. The browser read

`next dev` on `:3100` against the API on `:8731`, signed in as the walk's own manager, locale
`简体中文`, on `/career/grant-walk-braa` and `/career/grant-walk-braa/market` — the figures above as they
rendered, read from the DOM the server produced:

- the closed row: `第 1 个赛季 · 2026 | Braehaven Elite League · 第 2 级 | 第 1–14 轮 · 共 14 轮 | 1.143 |
  留级 | 152,000 career credits / 14 round(s) × 8,000 + 16 point(s) × 2,500 | 没有移动`, under the header
  `… | 判定 | 董事会拨款 | 下一赛季`;
- the projection row: `本季若现在收束将拨出 | 10,500 career credits`;
- the finance timeline: `14 SEASON_GRANT board grant for season 1 +152,000 | 152,000 | 152,000 一致`, then
  `15 LOAN … −90,110 | 61,890 | 61,890 一致`, then `15 WAGE … −1,200 | 60,690 | 60,690 一致`, opened at 0 and
  closed at 60,690;
- the market ledger's grant row, contract cell `—` (the `0 years` it printed before the fix);
- and the career's own limitations sentence, which now states the grant rather than its absence.

**This is a DOM read, not a screenshot.** The in-app browser surface reported a 0×0 viewport, so
`take_screenshot` and pointer actions were refused; the page structure and every printed figure were read
from the rendered markup instead. No colour, overflow or reflow claim is made here. `.scratch/grant-render.json`
holds the strings as read.

## 8. What this does not claim

- It does not pay prize money from a league position. The grant is sized by *this career's* rounds and
  points because a career plays only its own fixtures and no other club's results exist to finish above or
  below it — the same constraint that made the boundary's two lines authored constants.
- It does not make a career rich. Measured on this board, one season's grant is a loan fee, not a signing.
- It does not pay a closed season retroactively: the award is written by `close_season`, so a boundary that
  ran before migration `0047` has a verdict and no grant, and the seasons panel prints that as an em-dash
  rather than inventing a payment.
- It does not prove the whole suite on its own bytes. The full suite ran on the commit that carries this
  item and its verdict is §9: 2130 of 2132 green, with the two reds named there and neither of them the
  grant's — both are the population and census figures a concurrent batch committed alongside this one.

## 9. How these bytes reached master, and the verdict on them

**Not by a commit of this item's.** All sixteen paths went into the shared index exactly as sections 5 to 7
describe them, and a concurrent lane committed the index while it held them: they reached `master` as the
file half of `c5d0979` ("docs: the catalogue table states the population it holds (4028 keys)"), whose
subject describes that lane's own table and not this feature. The cure is this section, not a rewind: the
branch was rewound and re-committed only when it is one's own history, and rewinding here would have
discarded the other lane's commit along with it. PLAN.md's landing note on `df1675e` is the same precedent
written by an earlier session that met the same sweep.

**What was proven before the tree moved, and after.** The staged tree was written out as a dangling commit
(`d33b0a2`, never a branch head) and checked out into `.scratch/wt-grant`, where it was graded on its own
bytes rather than on a working tree carrying somebody else's keys: `tsc --noEmit` rc 0, `next lint` clean,
`ruff check app tests` clean, `mypy app` clean over 161 source files, and
`pytest tests/test_career.py::TestSeasonGrants tests/test_transfers.py::TestBoardGrants` **16 passed,
rc 0**. That tree's content is `c5d0979`'s content for these sixteen paths, which is the tree the suite then
ran.

**The full suite on `c5d0979`: 2132 collected, 2130 passed, 2 failed, exit 1**
(`.scratch/full-suite-c5d0979.log`, `-p no:randomly`, run in the throwaway worktree). Neither red is the
grant's and both are the sweep's:

- `test_locale_claims.py::test_the_readme_table_states_the_coverage_the_catalogues_actually_have` — the
  `zh` and `zh-TW` rows count a population of 4028 while `en.json` at this commit holds 4012. The other 16
  keys belong to the concurrent signing-window batch and are still uncommitted, so the committed table
  states a figure only that lane's working tree can reproduce. Its own case is what catches it.
- `test_spec_audit_currency.py::test_the_audit_s_declared_figures_answer_for_the_committed_tree` —
  `AUDIT_FIGURES` says 47 migrations and the committed tree holds 48, because migration `0047` is the 48th
  file and `0534b80` moved the census to 47 the day before. The cure sits in this tree's index right now,
  as part of the batch that adds `0048` and rewrites the audit row; moving that line from under a cure
  already in flight would only produce two versions of it.

**The catalogue figure, restated on its own tree.** Section 5 read 4,028 keys per locale on a working tree
that also carried the window batch's 16 uncommitted keys. On the commit that holds this item the three
catalogues hold **4,012** each: `ed9b631` held 4,010 and this item adds 2 keys per locale. Parity across
three locales is the claim that survives the sweep; the count does not, and `test_locale_claims` above is
that sentence having a reader.

**One code point, caught by an encoding it could not survive.** The `zh-TW` draft of both new values used
U+64A8. The simplified 拨 (U+62E8) takes the traditional 撥, which is **U+64A5** — and U+64A8 is not in
Big5 at all (`chr(0x64A8).encode("big5")` raises) while U+64A5 encodes as `bcb7`. Encodability named it,
because this machine's GBK code page prints the two as the same mojibake and no local converter was
available: `LCMapStringW` with `LCMAP_SIMPLIFIED_TRADITIONAL` returns its input unchanged for these
characters. `git show c5d0979:apps/web/messages/zh-TW.json` reads U+64A5 in both values, and
`qa-token-drift`, `qa-unused-keys`, `qa-locale-completeness` and `qa-key-drift` were re-run green on it.
