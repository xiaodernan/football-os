# M13 verification — objectives that pay

ROADMAP Phase 9 item 36. Date: 2026-11-04.

A career's objectives were prose. `objectives_of` compared the season's own sums against the targets the
manager set and the board printed `met` or not; the boundary's verdict read points-per-round and paid a
grant sized by rounds and points. Nothing the manager chose at the opening changed the balance. This item
adds the second half: **every objective a closed season met is paid, as a row of its own beside the
grant**, so the targets a manager sets are money and not only a sentence.

## 1. The arithmetic, and the four rules

One authored table in `apps/api/app/services/simulation/market.py`, stated beside the formula that uses it:

```
OBJECTIVE_BONUS_BY_KIND = {
    "wins":            30,000
    "points":          40,000
    "goal_difference": 25,000
    "unbeaten":        50,000
}                                       145,000 if all four are met
```

The rates are sized against the other board money: the four together pay **145,000**, a little under one
full season's grant (14 rounds x 8,000 + 25 points x 2,500 = **174,500**), so a season that meets
everything the board asked is a good season's extra income rather than a reset button. Points are what the
verdict itself reads, so they are priced highest of the three sums; a win target is largely a points target
by another name, a goal-difference target is the margin around them, and an unbeaten run is a streak rather
than a sum — the one kind the board cannot project — so it is priced above all three.

`objective_bonus_report(objectives=, verdict=, units=)` is pure and holds the whole rule:

- **met means `actual >= target`**, read from `objectives_of`'s report — the same rows the board prints, so
  the money cannot disagree with the prose the manager saw;
- **a target of zero or less pays nothing**, because nothing had to be met;
- **one row per met objective**, with the objective's kind as the award's `stage`, which is what
  `uq_career_award_stage` (career_id, season_index, kind, stage) holds one of per season;
- **a `challenge` verdict pays nothing**, because that window is judged by the challenge's own reward. The
  exemption is stated in this one function, so the boundary that pays and the page that projects cannot
  drift apart on it.

An objective that is not met (or a season that met none) writes no row, so a page never has a zero to
explain. `pay_objective_bonuses` performs the write; `objective_bonus_report` is what both the boundary and
the seasons projection call.

## 2. When it is written, and in what order

`close_season` (career.py) pays inside its own transaction, in one order:

1. the boundary decision row is added;
2. `pay_season_grant` writes the grant (item 24);
3. `pay_objective_bonuses` writes one row per met objective, **in objective-kind order**
   (`goal_difference`, `points`, `unbeaten`, `wins`);
4. the competition move and `session.commit()`.

The order matters twice. `SessionLocal` runs with `autoflush=False`, so a pending award is invisible to
`budget_position`: the pay loop flushes before each balance read, and the row stores a running balance that
includes the grant and every bonus written before it. And because ids are random tokens (`new_public_id`),
no ordering may rest on the id: the kind order is the stage order, and `budget_timeline` and `ledger_of`
both sort boundary rows by it.

**A migration at HEAD.** The award table's first migration (`0047_career_budget_awards`, unchanged here)
created one grant per season (`uq_career_award_season`) and had no `stage` column, so a per-objective row
could not be told apart from a second grant. `0049_objective_bonuses` adds
`stage VARCHAR(80) NOT NULL DEFAULT ''` and swaps the unique key to
`uq_career_award_stage (career_id, season_index, kind, stage)`: on SQLite through
`batch_alter_table(recreate="always")` (which drops the old key and creates the new one in the table's
rebuilt definition), directly on Postgres; the downgrade drops the key and the column. No backfill — every
stored row is a grant, and `''` is the stage a grant is written with. A fresh SQLite through
`alembic upgrade head` reports head **0049**, the column present, and `alembic compare_metadata` against
`Base.metadata` **DRIFT none**. `objective_bonus` joins `season_grant` in `AWARD_KINDS` on this tree; the
concurrent cup lane adds `cup_prize` in its own uncommitted slice, and this item neither reads nor requires
that kind.

## 3. Where it is published

- `budget_position` — `received_objectives`, `objective_rows`, `objective_detail`
  (`season 1 goal_difference: 25,000 · season 1 points: 40,000 · ...`, sorted by season then stage), and
  `remaining` = `budget + received + granted + received_objectives - spent - wages_paid`. `BUDGET_FORMULA`
  already sums `budget_awards.amount` wholesale, so the printed arithmetic covers the new kind unchanged.
- `budget_timeline` — the grant and the bonuses share tier 3 (the boundary's money), and within it the
  stage orders them; the label is `objective bonus, <kind>`, and the running balance is checked against
  every stored `budget_after` and disagreements are counted, never hidden. `TIMELINE_FORMULA` names the
  objective bonuses.
- `ledger_of` / `award_row` — a bonus is a ledger row in the moves table's own shape: `side`/`cash` = `in`,
  name `objective bonus, <kind>`, `detail` = the basis string (`goal_difference: 8 >= 1 pays 25,000 career
  credits`), `effect` = `OBJECTIVE_BONUS_EFFECT`, `stage` and `season_index` filled.
- `market_view` — `budget` carries the three position fields, `totals.bonus_rows` counts the rows,
  `constants.objective_bonus_by_kind` publishes the four rates, and `RULES["objective_bonus"]` prints
  `OBJECTIVE_BONUS_FORMULA`, so the rule census judges it like the other rules.
- `affordability_view` — `received_objectives`, `objective_rows`, `objective_detail`, read from the same
  `budget_position`.
- `seasons_view` — each closed season carries `bonuses` (amount, units, rows in kind order, formula) when
  it paid any, `null` otherwise; the season being played carries `bonus_if_closed_now`, the same pure report
  over the record it has stored so far. That block is a projection and nothing writes it.
- `limitations()["objectives"]` now states that each objective a season met is paid at the published rate,
  and that a challenge's window pays its own reward instead.

## 4. What the web tier prints

- `components/CareerSeasons.tsx` — a grid row `seasonsBonusNowLabel` prints the projection
  (`145,000 career credits` mid-season); the closed table's grant cell prints `seasonsObjectiveBonus`
  beneath the grant amount (`Objective bonuses: 145,000 career credits`). Money and units are composed at
  the call site, the way every other figure in these panels is.
- `components/CareerFinance.tsx` — a `rowFinanceObjectiveReceived` row (`Paid for met objectives`,
  `145,000 career credits`) when the ledger holds any bonus rows.
- `app/career/[slug]/market/page.tsx` — the ledger prints the rows as they are stored (name, basis,
  balance, effect); the contract cell now treats an award row as an em-dash, so a bonus no longer prints
  `0 years`; and the balance sentence gained the two income terms it had been missing:
  `stated + received + in board grants + in objective bonuses = remaining` (the grant term was absent even
  for item 24's money — the sentence only reached `received`). The terms print only when non-zero.
- `lib/types.ts` gains `SeasonObjectiveBonusRow`, `SeasonObjectiveBonuses`,
  `SeasonObjectiveBonusProjection`; `lib/market.ts` types `received_objectives`, `objective_rows`,
  `objective_detail`, `totals.bonus_rows` and `constants.objective_bonus_by_kind`.
- Copy: 5 new keys (`market.footerGranted`, `market.footerBonuses`, `careerDetail.seasonsBonusNowLabel`,
  `careerDetail.seasonsObjectiveBonus`, `careerDetail.rowFinanceObjectiveReceived`) in each of `en.json`,
  `zh.json`, `zh-TW.json`, inserted line-parallel with `python` and CJK spelled by code point.
- `scripts/qa-market.mjs` — the footer regex now reads the two income terms and adds them:
  `stated + received + board grants + objective bonuses - spent - wages = remaining`.

## 5. Gates and tests, as run

Every figure below was measured in the clean worktree that carries this commit alone (HEAD `cd82dcd` plus
this item), not on the shared working tree whose concurrent lanes add keys, rules and tests:

| gate | result |
| --- | --- |
| `pytest tests/test_career.py::TestObjectiveBonuses` | **9 tests** |
| `pytest tests/test_career.py::TestSeasonGrants` + `TestObjectiveBonuses` | **21 passed** |
| `pytest tests/test_career.py tests/test_transfers.py` | **100% pass, rc 0** |
| fresh SQLite `alembic upgrade head` | head **0049**, `stage` column present, `uq_career_award_stage` created; `compare_metadata` **DRIFT none** |
| `ruff check` on `market.py`, `career.py`, `models/__init__.py`, migration 0049, the two test files | All checks passed |
| `mypy` on `market.py`, `career.py`, `models/__init__.py` | Success: no issues found in 3 source files |
| `tsc --noEmit` | rc 0 |
| `eslint` on the five changed web files | no findings |
| `qa-wire-readers.mjs` | **12/12** — 17 view keys, 16 window fields, 19 constants typed |
| `qa-token-drift.mjs` | **2/2** — 45 named tokens stable, 0 unnamed identical values |
| `qa-unused-keys.mjs` | **3/3** — 0 keys asked for by nothing, floor 0; 3,992 judged here, 66 delegated |
| `qa-locale-completeness.mjs` | **2/2** — en = zh = zh-TW = 4,058 keys |
| `qa-icu-coverage.mjs` | **2/2** — 3,174 call(s) checked |
| `qa-plural-select.mjs` | **2/2** |
| `qa-locale-tokens.mjs` | **5/5** — the catalogue's own table now states the population it holds (4,058 / 4,013) |
| `qa-key-drift.mjs` | **4/4** — no new shared value; none of the five new values forms a same-context group |
| `qa-i18n-literals.mjs` | **9/9** — 4,096 key call(s) checked for their values |
| `qa-icu-messages.mjs` | **2/2** — 4,058 key(s) compared across 3 catalogues |
| `qa-locale-fallback`, `-content`, `-formatting`, `qa-translation-freshness`, `-quality` | **3/3, 3/3, 2/2, 2/2, 4/4** |
| 0049 round-trip on a scratch SQLite | upgrade head → downgrade 0048 → upgrade head: `stage` present, `uq_career_award_stage` in force; after the downgrade the column is gone and `uq_career_award_season` is back |

Because the commit adds a migration, the audit's machine-checked figure moved from 49 to **50**
(`docs/SPEC_COVERAGE_AUDIT.md`'s `AUDIT_FIGURES` line and the triple `ROADMAP.md` quotes beside the audit
link) — the two carriers `test_spec_audit_currency.py` reads from the commit itself.

The shared tree on which the earlier evidence runs below were made also held the concurrent cup lane, whose
two catalogue groups made `qa-key-drift` print 2/4 there and whose extra keys lifted every population
figure; none of that is in these bytes, and the table above is what this commit itself carries.

The first attempt at the footer regex is the one place this item moved a gate: `qa-market.mjs` matched a
four-term sentence, and once the page prints board money the old regex would have silently matched a
prefix and read `spent` out of the `granted` group. The groups were re-cut and the wage check moved to
group 6.

## 6. The live walk

Measured on the shared working tree on which this item's slice first ran; the same item-36 logic was then
ported onto HEAD for this commit, and the clean worktree's `TestObjectiveBonuses` re-derives the same
identities (a met objective pays, a miss pays nothing, the rows chain onto the grant in kind order, and the
timeline closes at the balance).

`.scratch/walk-bonus.py` — fresh alembic-built SQLite, uvicorn on `:8792`, a career opened with
`budget: 0` on the lowest league's strongest club and **all four objective kinds at target 1**, three rounds
played (the projection arm), then the rest of the season (the payment arm). Every figure is re-derived from
the rates the same responses publish. Two runs, two generated worlds, both **exit 0**:

| | run 1 | run 2 |
| --- | --- | --- |
| club / league | Braehurst Town, Braehaven Elite League (tier 2) | same |
| mid-season record | 2-1-0 after 3 rounds | 0-3-0 after 3 rounds |
| projection then | **145,000**, all four rows | **90,000**, `points` + `unbeaten` only |
| final record | 14 rounds, 7-6-1, GD 10, 27 points | 14 rounds, 7-5-2, GD 12, 26 points |
| verdict | `promoted` | `promoted` |
| grant | **329,500** = 14 x 8,000 + 27 x 2,500 + 150,000 | **327,000** = 14 x 8,000 + 26 x 2,500 + 150,000 |
| bonuses | **145,000** (25,000 + 40,000 + 50,000 + 30,000) | **145,000** |
| stored bonus balances | 717,220 / 757,220 / 807,220 / 837,220, each the grant's 692,220 plus the kinds before it | 709,420 / 749,420 / 799,420 / 829,420 |
| balance | **837,220** = 0 stated + 362,720 received + 329,500 grants + 145,000 bonuses - 0 - 0 | **829,420** = 0 + 357,420 + 327,000 + 145,000 |
| timeline | 8 rows, boundary rows `['season_grant', 'objective_bonus' x 4]` in kind order, **0 disagreements** | same |

Run 2 is the arm run 1 cannot be: after three draws only two objectives were met and the projection named
exactly those two; the five wins that followed paid the other two at the boundary. The projection is a read
of the record the season actually holds, not a promise of the full table.

On the landed commit's own bytes, the same walk was run against a production build of `40762fa` (re-cut
as `0cf34c1` for line endings; the bytes on disk are identical — section 9): `next build` and `next start`
on `:3212`, uvicorn on `:8744` over a fresh SQLite migrated through `0049`, and `qa-market.mjs` answered
**146/146 checks, exit 0** (7 screenshots written to the git-ignored `docs/screenshots/`). The shared tree's run had reported 144/146; both reds were that tree's uncommitted
gate-receipt feature — a round's gate money arrives as a ledger row the balance sentence does not print —
and neither red exists in this commit, which is why the clean walk is full.

The walk also asserts, on the wire: `market.budget.objective_detail` is the season/kind detail string;
`totals.bonus_rows` = 4; `rules.objective_bonus` equals the closed block's formula; the four ledger rows
carry `player_name` `objective bonus, <kind>`, `cash`/`side` `in`, zero contract years and zero wage, the
`OBJECTIVE_BONUS_EFFECT` sentence, and the same `budget_after` as the stored rows; the balance identity
above; the timeline's labels and its 0 disagreements; and that the season after the boundary projects
**0** again.

## 7. The browser read

Measured on the same shared working tree as the walk; the printed strings are the values the page derived
from that tree's API, and the item-36 rendering path ported onto HEAD is the same component code.

`next dev` on `:3100` against an API on `:8731` over a fresh `.scratch/bonus-web.db`, signed in through
the web tier's own proxy as the walk's manager, locale Chinese, on `/career/bonus-web-brat` and
`/career/bonus-web-brat/market`:

- the closed row's grant cell: `329,500 career credits` with its basis, and beneath it
  `目标奖金: 145,000 career credits`;
- the finance panel: `累计目标奖金 | 145,000 career credits`;
- the finance timeline: the boundary rows `board grant for season 1 +329,500 | 688,020 | 688,020 一致`,
  then `objective bonus, goal_difference +25,000 | 713,020 | 713,020 一致`, `points | 753,020`,
  `unbeaten | 803,020`, `wins | 833,020`, all `一致`, and the summary `每条存储数字都与滚动余额一致`;
- the market ledger's four bonus rows: names, bases (`goal_difference: 8 >= 1 pays 25,000 career
  credits`), balances `713,020 / 753,020 / 803,020 / 833,020`, contract cell `—`, and the
  `OBJECTIVE_BONUS_EFFECT` sentence;
- the market's balance sentence, English locale:
  `0 stated + 358,520 received + 329,500 in board grants + 145,000 in objective bonuses = 833,020 career
  credits, and the same number is printed beside every offer as the balance a deal has to fit inside.`
  (0 + 358,520 + 329,500 + 145,000 = 833,020; no spent or wage term because both are zero);
- the projection arm in the UI: a second career left after three rounds (1-1-1) renders
  `本季若现在收束的目标奖金 | 145,000 career credits`, re-derived from `wins 1, points 4, GD 1,
  unbeaten 2` against target 1 each.

**This is a DOM read, not a screenshot.** The in-app browser reported a 0x0 viewport and refused pointer
actions, so the page structure and every printed figure were read from the rendered markup, as the grant
record did. No colour, overflow or reflow claim is made. `.scratch/bonus-render.json` holds the seed's
figures; the strings above are quoted from the DOM.

## 8. What this does not claim

- It does not pay an objective the season missed, nor a target of zero. Those are the rule's own two
  silences and the tests assert both.
- It does not pay in a challenge window: that run is judged by the challenge's own reward, and the
  projection says so in the same sentence.
- It does not retroactively pay a season closed before this change: a closed block with no bonus rows
  prints `null` (no line), not a recomputed figure. The seasons projection only describes the season being
  played.
- It does not price the objectives against a league table: the actuals are this career's own sums, the same
  constraint every other board projection carries.
- It does not prove the whole suite on its own bytes: the full-suite verdict is recorded in section 9 on
  the commit that carries this record, against a working tree that also holds concurrent items (gate
  receipts, cup ties) whose rows appear in the walk's timeline but whose arithmetic is not this item's.

## 9. How these bytes reached master, and the verdict on them

**By a commit of this item's own, through an index of its own.** The shared working tree was carrying
several concurrent lanes (contract expiry, cup ties, gate receipts) and its index was not this item's to
commit from: a commit taken there would have carried their staged bytes, and an index built from their HEAD
would have reverted this item's later edits. The 21 paths were therefore committed through a private
temporary index (`.scratch/idx-own-wt`, driven by `.scratch/own-commit-wt.py`): parent `cd82dcd` was read
into it, the blobs were hashed from the graded worktree `.scratch/wt-bonus36` — not from the shared working
tree — `update-index --cacheinfo` placed them, `write-tree` and `commit-tree` made the commit, and a
compare-and-swap `update-ref refs/heads/master <new> cd82dcd` published it. The shared index and the shared
working tree were never read for content and never written by that run.

**The commit, re-cut once for its line endings.** The first tip, `40762fa`, was committed with the bytes as
they sit on disk, and on this checkout that is CRLF: `hash-object -w --stdin` skips the clean filter that
`git add` applies under `core.autocrlf=true`, so the 18 edited files landed as CRLF blobs against a
repository whose blobs are LF, and `git show --stat` reported 27,566 insertions against 26,741 deletions
for 886 lines of real change. The tip was unpublished (`origin/master` was still `cd82dcd`), it was this
item's own, and nothing sat on top of it, so it was replaced rather than followed by a whitespace commit:
the same 21 paths were re-hashed with `git hash-object -w --path=<path>` from the same worktree, the three
paths already LF (the migration, `test_transfers.py`, and this record) kept their `40762fa` blobs, and
`update-ref refs/heads/master 0cf34c1 40762fa` swapped the tip. `git diff -w 40762fa 0cf34c1` is empty,
and the commit's diff against its parent is **21 files, 886 insertions, 61 deletions**. The tree the suite
ran against did not move: a checkout writes CRLF to disk regardless of blob bytes, and the graded worktree
was not touched by the re-cut.

**The full suite on the commit: 2,153 tests, 2,149 passed, 4 skipped, 0 failed, exit 0.** It ran in the
clean worktree with the CI's own branch environment (`GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master`),
because the earlier pre-commit run's only red was
`test_ci_trigger.py::test_every_workflow_that_runs_on_push_covers_the_branch_the_run_is_about`, which
refuses a detached checkout (`rev-parse --abbrev-ref HEAD` = `HEAD`) — an artefact of the worktree, not of
the item; with the environment a push in CI carries, that case reads the branch it is told and passes. The
four skips are the `integration`-marked cases, which skip themselves when no live service answers. The
project's `addopts = "-q"` plus the command's `-q` makes `-qq`, which prints no tally line, so the figures
are the progress marks: 2,149 `.` and 4 `s`.

**The committed tree's own cases, read through `git show HEAD:`.** On the commit, in the clean worktree,
`tests/test_spec_audit_currency.py`, `tests/test_locale_claims.py` and
`tests/test_career.py::TestObjectiveBonuses` **25 passed**: the audit's migration figure reads 50 against
50 committed migrations, the catalogue table reads `4013 of 4058` against the catalogues it names, and the
nine bonus cases pass on the committed bytes.

**The walk on the built commit.** `apps/web` was built from the committed tree and served beside an API on
the same bytes; `qa-market.mjs` answered **146/146 checks, exit 0** (7 screenshots under the git-ignored
`docs/screenshots/`), covering the four bonus rows and their bases, the balance sentence carrying both
income terms, the finance panel's received total, and the seasons projection. The shared tree's own build
answered 144/146 at the same moment; both reds were in the gate lane's new surfaces, not in this item's.

**One index left behind, and what it means for the next commit.** Moving `master` under a shared index that
still held the lanes' pre-item snapshot made `git status` in the shared tree report the two added paths
(`0049_objective_bonuses.py` and this record) as staged deletions; a plain `git commit` taken from that
index would have deleted them from `master`. Both were restored to HEAD's entries with
`git reset HEAD -- <the two paths>` (index only, no working-tree bytes), and the migration was copied back
to the shared disk. The nineteen modified paths are still staged at the lanes' older snapshot: a lane that
re-adds its own files refreshes them, and a commit taken without re-adding would revert those paths to
their pre-item bytes. The working tree keeps the new bytes, so the cure there is `git add`, not a rewind;
this is written down because a shared index has no other reader.

**Integration: the migration chain the shared tree is carrying.** That tree's uncommitted chain
`0049_career_contract_expiry` → `0053_cup_tie_basis_width` was authored when `master`'s head was 48
migrations. `master` now owns revision `0049`, so the chain must land as `0050`–`0054` (the first file's
`down_revision` = `"0049"`), and `0051_career_cup_ties.py` must drop its own
`career_budget_awards.stage` add, `uq_career_award_season` drop and `uq_career_award_stage` create: this
item's `0049_objective_bonuses` applies all three, with `stage VARCHAR(80)`, and upgrading through the
renumbered chain with them still present fails on the duplicate column before any cup work runs. Its
`cup_prize` rows then share the widened key and the stage column this item introduced: one row per
(career, season, kind, stage) is the rule for every award kind, the grant's stage staying empty.
