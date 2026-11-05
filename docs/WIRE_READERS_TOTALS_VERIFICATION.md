# Wire-readers totals census verification

ROADMAP Phase 6 item 42. Date: 2026-11-05.

`apps/web/scripts/qa-wire-readers.mjs` documented fourteen checks and ran twelve. Its header described a census of
the `totals` block — keys counted against the type, every field read on the page or through the seam, an exemption
ledger with the same staleness discipline as the view's — and named `components/MarketTools.tsx` as the seam the
census follows. None of that existed in the body: the script declared `TOOLS_TSX` and `FLOOR_TOTALS_KEYS` and read
neither (**one declaration, zero uses, each**), and the run answered `CHECKS passed=12 total=12`. Item 41's sweep
found it and filed it
([MIGRATION_MODEL_DRIFT_VERIFICATION.md](MIGRATION_MODEL_DRIFT_VERIFICATION.md) §7); this unit writes the census the
prose promised and measures what it refuses.

## 1. The defect, and the input that shows it

The block is real: `market_view()` answers `totals` with seven counts and `MarketView["totals"]` declares all seven.
`MarketTools.tsx` is real too — 19,969 bytes, and it reads `totals.listed` off the prop the market page hands it.
What was missing is any clause that *looks*.

That is measurable, and the measurement is the unit's differential. Both runs below are the same plane, the same
tree, the same absent keys — only the script differs:

| input | the parent's script (`ef649ef`) | the cured script |
| --- | --- | --- |
| one `totals` key deleted from the wire (`"listed": len(open_rows),`) | rc=0, `CHECKS passed=12 total=12 failed=0` — nothing refused | rc=1, **14/15**, clause 12: `wire 6 vs type 7 — declared, published by nothing: listed` |
| three deleted (`wage_rows`, `grant_rows`, `bonus_rows`) | rc=0, **12/12** — nothing refused | rc=1, **11/15**: clause 2 (floor: `totals=4` under `FLOOR_TOTALS_KEYS=5`), 12 (`wire 4 vs type 7`), 13 (`nothing asks: wage_rows`), 14 (`wage_rows — the budget block publishes the same len(charges)…`) |

So the roadmap row's sentence — *the same deletion answers 12/12* — is true at the parent and false now, and the
gate the prose named is the gate the body runs.

Writing the census is not the whole of the unit, because a census that computes refuses things. Read straight off
the bytes, the seven `totals` keys split three ways: `listed` is read through the seam, `signed` and `withdrawn` are
read by the page, `moves` and `wage_rows` are copies of the `budget` block the page already prints, and
`grant_rows` and `bonus_rows` were read by nothing anywhere in the web tier.

## 2. The census

Three checks, in the shape the file's other clauses already have:

- **12** — the wire's `totals` keys against `MarketView["totals"]`, both directions, by name. The population comes
  from the same scan that produced the view's own keys (`children.totals`, depth two of the one dict literal), so a
  key that moved out of the block moves this census's population with it rather than escaping it.
- **13** — every declared `totals` field is read on the page, or read in `MarketTools` **and** reached through a seam
  that is itself a predicate: `totals={view.totals}` in the page and `totals: MarketView["totals"]` in the
  component's props. A component reading a block nobody sends it is exactly the blind page this gate was written
  for, so the handoff is re-measured every run rather than assumed.
- **14** — a `totals` exemption the bytes stopped earning is stale.

The two exemptions are authored, not derived — a ledger generated from the predicate that would satisfy it could
never go stale, and clause 14 would grade nothing. Each row re-measures three legs: the key is still published in
`totals`, `budget_position` still publishes the same name, and the page still reads `budget.<name>`:

| key | the fact the reason states | legs |
| --- | --- | --- |
| `moves` | `market_view` computes `len(rows)` twice, and the spent `Stat`'s hint prints the `budget` copy (`page.tsx:70`) | wire 22-key budget scan ∩ totals, `budgetReads ∋ moves` |
| `wage_rows` | the same `len(charges)` in both blocks, and the wage notice prints the `budget` copy (`page.tsx:81`) | as above, on `wage_rows` |

`grant_rows` and `bonus_rows` had no such reason — the `budget` copies of them (`grant_rows`, `objective_rows`) are
themselves read by nothing, and their amounts are what the footer prints — so the census refused them and the unit
had to decide which way to be right.

## 3. The readers the refusal bought

The footer sentence at the bottom of the ledger panel is the balance as the page tells a reader to check it:
`stated + received + in board grants + in objective bonuses − spent − in wages = remaining`. Item 36 added the two
income terms as amounts. The counts those amounts are sums *of* were on the wire and nowhere on the page, which is
the unauditable shape: a sum with no row count beside it, while the row detail is published two keys away and also
unread. The cure is one placeholder per term, in all three catalogues:

    + {amount} in board grants {rows, plural, one {over # season} other {over # seasons}}
    + {amount} in objective bonuses {rows, plural, one {across # award} other {across # awards}}

with `zh` `董事会拨款（{rows, plural, other {# 个赛季}}）`, `zh-TW` `董事會撥款（{rows, plural, other {# 個賽季}}）`
and the bonus terms `（{rows, plural, other {# 笔}}）` / `（{rows, plural, other {# 筆}}）` — plural categories per
locale as `qa-plural-select.mjs` requires them (`one`+`other` for `en`, `other` only for both Chinese locales).

Writing them is scripted (`.scratch/item42-catalogue.py`) for two reasons this host makes a habit of: the strings
are spelled with code points so no CJK reaches the tool through a GBK console, and every glyph a new value adds is
refused unless it already appears in that locale's file. The first run caught two wrong code points this way —
U+64A8 播 written where the file uses U+64A5 撥, and U+8D5B 赛 where `zh-TW` writes U+8CFD 賽 — and left the file
untouched rather than land a traditionalised-Chinese typo. Line endings are read and written raw.

`qa-market.mjs` parses that sentence to re-add it, so the walk's regex took the two fragments in the same commit
(`(?: over [\d,]+ seasons?)?`, `(?: across [\d,]+ awards?)?`) with the capture groups unchanged — the walk still
asserts the identity from the figures the DOM prints, now with the row counts in the line.

## 4. The arms

`.scratch/item42-arms.py` edits one input, runs the whole census, records what refused, and restores. Every arm ran
on `.scratch/wt-readers`, a clean `git worktree` detached at `ef649ef`, with the plane's `apps/web/node_modules`
pointed at the shared install; verdicts are UTF-8 in `.scratch/item42-arms.txt` because these lines are quoted.

| arm | input | verdict |
| --- | --- | --- |
| base | the cured tree | **15/15** rc=0; 13 prints `reads: page=bonus_rows, grant_rows, signed, withdrawn MarketTools=listed seam=held` |
| W | one `totals` key gone from the wire | **14/15**, clause 12 names `listed` |
| T | `listed` deleted from the type's totals literal | **14/15**, clause 12: `published, typed by nothing: listed` |
| R | the footer stops passing `rows` for the grant term | **14/15**, clause 13: `nothing asks: grant_rows` |
| S | `totals={view.totals}` → `totals={{ ...view.totals }}` — the reads all survive, the seam does not | **14/15**, clause 13: `seam=MISSING — the page no longer hands the block to MarketTools under the MarketView["totals"] prop` |
| L | `budget_position` renames its `"moves"` copy to `"move_count"` | **13/15**: clause 14 `moves — the budget block publishes the same len(moves)…` **and** clause 13 `nothing asks: moves` |
| F | three `totals` keys deleted from the wire | **11/15**: clauses 2, 12, 13, 14 |

S is the arm that shows the seam is a predicate and not a comment. L is the arm that shows an exemption is a fact:
the ledger row did not survive the rename, and the key it was excusing went straight back to the refusing column.
R and T show clause 13 and 12 judging different things — a read that stops, and a type that stops matching the
wire. `.scratch/item42-oldscript.py` is the §1 differential.

## 5. The suites

Each line ran on a clean `git worktree` plane — never in the shared tree, which carries other lanes' uncommitted
bytes — and the command is the one §8 prints.

| what ran | where | verdict |
| --- | --- | --- |
| the census, base and six arms | `.scratch/wt-readers` detached at `ef649ef` | §4's table: base **15/15** rc=0, each arm red on the clause its own input attacks |
| the parent's census over two of the same inputs | as above | **12/12 failed=0** on both, against the cure's 14/15 and 11/15 (§1) |
| every file-only web gate, then typecheck and lint | as above | **30 pass / 2 fail**; `tsc --noEmit` clean, `next lint` clean (`.scratch/item42-webgates-wt-readers.txt`) |
| the API's locale-and-contract subset | as above | **30 passed** in 168.23 s: `test_locale_claims.py`, `test_openapi_contract_currency.py`, `test_spec_audit_currency.py`, `test_assert_message_forms.py`, `test_migration_model_drift.py` (`.scratch/item42-api.log`) |
| the API's career-and-transfers regression | `.scratch/wt-repair` detached at `f642c0a`, union census installed | **139 passed** in 33.80 s (`test_career.py`, `test_transfers.py`; `.scratch/repair-api.log`) |
| the market walk, live over two tiers | API :8772 + `next start` :3249 | **146/146 checks**, `--- market: exit 0`, 7 screenshots (`.scratch/item42-walk.log:172`) |
| the footer in a browser | API :8795 + `next start` :3255 | **18/18 failed=0** (`.scratch/item42-footer.txt`) |

The two refused file-only gates are not this unit's and are not waved through; they are measured on both trees and
filed as items 49 and 50. `qa-a11y-witness` answers **11/16 failed=5** on the plane — five arms printing *arm anchor
not found* — and **16/16 failed=0** in the shared tree, where the same files carry the same bytes in LF: the plane's
`styles/globals.css` holds 275 CRLF pairs, the shared tree's 0, and the anchors are multi-line strings.
`qa-rtl-readiness` answers **6/7 failed=1** on the plane and **7/7** in the shared tree, because the six physical
declarations it names (`app/coach/coach.css:61`, `app/knowledge/knowledge.css:168,169,248`,
`app/training/training.css:27,28`) are committed while their logical fixes are sitting uncommitted in the shared
tree. One of those two is an artifact of the checkout and one is real debt; neither is a `totals` sentence.

The footer witness is the half the census cannot reach. A read the census counts is a property access in a source
file, so §2's argument that `grant_rows` and `bonus_rows` deserve readers is only true on a page once something paints
them. `.scratch/item42-footer.mjs` drives one career through the page's own proxy: the lowest tier's strongest club,
four objectives at target 1 and a budget of 10,000,000, a board opened and a loan signed in season 1 round 1 — the
loan is there on purpose, because `moves` and `wage_rows` are the two keys §2 exempts as copies, and a career that
only ever received money would paint two zeros and prove nothing — then 14 rounds to cross the boundary and be paid
a grant and objective bonuses, then the footer read out of the DOM in all three catalogues.

The expected strings are not typed here. `arms(raw)` splits a catalogue value's `{rows, plural, …}` and takes the
unit after each `#`, and `label(raw)` takes the text between `{amount}` and the next placeholder, so an edit to
`messages/*.json` moves the witness with it instead of breaking it. The run's own population line:

    FOOTER WALK career=footer-walk-brat club=Braehurst Town moves=1 wage_rows=4 grant_rows=1 bonus_rows=4

and the assertion that names the two counts the exemptions argued about, verbatim:

    PASS  the totals block publishes the counts the footer is about to print — grant_rows 1, bonus_rows 4

All 18, in the order they run:

    a manager registers through the same proxy the login form uses · the lowest league has a club this account can
    manage · a career opens with all four objectives at target 1 · the board opens in the season-1 window · a loan is
    signed for 90,115 out of the budget the career opened with · the season crossed its boundary (14 rounds played) ·
    the boundary paid a grant and at least one objective bonus · the market door answers its owner · the two copies
    of the budget counts are non-zero on this career · the totals block publishes the counts the footer is about to
    print · the English footer prints footerGranted with the count the wire publishes (1 season) · and the amount
    beside it is the ledger's own (+ 164,500 in board grants) · the English footer prints footerBonuses with the
    count the wire publishes (4 awards) · and the amount beside it is the ledger's own (+ 145,000 in objective
    bonuses) · the spent stat prints the moves count the budget block publishes (1 move) · the wage notice prints the
    charge count the budget block publishes (4 rounds) · the Chinese footer carries the same count for footerGranted
    (1 个赛季) · the Chinese footer carries the same count for footerBonuses (4 笔)

`MISSING_MESSAGE` in the web tier's own log for the whole run: **0**.

## 6. The repair: two lanes, one file

The census landed at `f642c0a` — and `f642c0a` was a revert. Its plane was detached at `ef649ef`, so the six paths it
published carried `ef649ef`'s bytes for everything except the files this unit edited. A concurrent lane had landed
`29fbe4c` in between, which added checks 15–17 (the `moves` row's element type, its own 12-row ledger, its own
`FLOOR_MOVE_KEYS`) to the same script, and advanced `apps/web/lib/market.ts` and `PLAN.md` and this document's
neighbour `docs/CI_TRIGGER_BRANCH_READ_VERIFICATION.md` in the other direction. The landing tool cannot see any of
that: it reads the parent from `refs/heads/master` at call time and takes only the listed paths from the source
plane, so an old plane silently rewrites whatever a newer lane moved.

Measured, the two versions of `qa-wire-readers.mjs` over the same committed tree:

| script | checks run | verdict | refuses |
| --- | --- | --- | --- |
| this unit's (`f642c0a`) | 15 | **12 passed / 3 failed** | 9, 12, 13 |
| the concurrent lane's (`036089f`) | 15 | **11 passed / 4 failed** | 9, 15, 16, 17 |
| the union (`.scratch/wt-repair` @ `f642c0a`) | 18 | **12 passed / 6 failed** | 9, 12, 13, 15, 16, 17 |

The union is the only one of the three that contains both lanes' work, and its failure set is the *sum* of theirs —
nothing either lane proved red is hidden by the merge, which is the property the revert destroyed. Both sides' reds
are the same drift seen from two ends: `29fbe4c` typed five `Move` fields, two `totals` keys and five constants that
the committed `market.py` does not publish, so clause 12 and 15 read `type 9 vs wire 7` and `wire 25 vs type 30` on
the same tree. Grade the union against the shared tree's uncommitted API instead and the red set is **the same six
check numbers in the other direction** — `constants=33`, `moves=33`, `totals=10` published against 19/30/9 typed
(12/18 again, `.scratch/repair-merged-sharedapi.log`). No committed state of this file is green until one lane lands
the wire and the other lands the type over each other rather than under each other; that claim, and the three
measurements behind it, are item 51.

What the repair changes is the file, not the argument: `FLOOR_MOVE_KEYS` and `FLOOR_BUDGET_KEYS` and
`FLOOR_TOTALS_KEYS` all stand, check 2 now refuses a scan that found no move row as well as one that found no
totals or budget block, and checks 12–14 and 15–17 keep their numbers and their own ledgers. The header's population
list is the union too, so the prose no longer describes a census half of which exists — the defect this record opened with.

## 7. What this does not claim

It does not census the `budget` block, and the union census's own print says that block is the same finding at a
larger scale. Measured on the merged script over `f642c0a`: `budget_position` publishes **22** keys,
`MarketBudget` declares **24**, the market tier reads **14** of them, and the refusals split three ways —
`wage_ceiling` and `wage_headroom` are published by the wire and typed by nothing; `gate_detail`, `gate_rows`,
`received_gate` and `received_sales` are declared by the type and published by nothing; and ten declared keys are
read by nothing — the four just named plus `grant_detail`, `grant_rows`, `objective_detail`, `objective_rows`,
`wage_detail`, `wage_rounds`. Over the shared tree's uncommitted API the same scan prints `budget=44`. Filed as
item 48, in the shape 12–14 and 15–17 already have: both directions by name, then reads, then an authored ledger
whose rows are predicates.

A read the census counts is a property access in a source file, not a painted pixel: it refuses a field nobody asks
for, and it cannot promise the value reached a browser. That half is `qa-market.mjs`'s, and §3 is why the walk was
re-run rather than quoted from item 36.

It does not make the *other* nested blocks safe. `constants` has been censused since item 36 and `totals` and the
moves row now; `career`, `market`, `need`, `squad`, `listings` and `deals` publish nested shapes the census does not
judge, and the file's own scope note says so.

## 8. Reproduce

    git worktree add --detach .scratch/wt-readers ef649ef
    # the plane needs the shared install: apps/web/node_modules is a junction to D:\足球项目\apps\web\node_modules
    cd .scratch/wt-readers/apps/web && node scripts/qa-wire-readers.mjs
    python ../../.scratch/item42-arms.py        # seven arms, verdicts to .scratch/item42-arms.txt
    python ../../.scratch/item42-oldscript.py   # the parent's census over the same two inputs
    python ../../.scratch/item42-webgates.py wt-readers   # every file-only web gate, plus typecheck and lint

    # the repair's own measurement (union census over the committed tree, then over the shared tree's API)
    git worktree add --detach .scratch/wt-repair f642c0a
    cp .scratch/merge-probe.mjs .scratch/wt-repair/apps/web/scripts/qa-wire-readers.mjs
    cd .scratch/wt-repair/apps/web && node scripts/qa-wire-readers.mjs          # 12/18, reds 9,12,13,15,16,17
    QA_WIRE_API="D:/足球项目/apps/api" node scripts/qa-wire-readers.mjs          # 12/18, the same six in the other direction
