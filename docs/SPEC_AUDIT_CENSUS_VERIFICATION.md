# §82 — the audit's door-and-page censuses get a reader (`docs/SPEC_COVERAGE_AUDIT.md` §A, landed over `8b68b0f`)

## 1. What was measured before any case existed

`docs/SPEC_COVERAGE_AUDIT.md`'s §A table is the project's verdict ledger: its heading promises "measured evidence", and
#80/#81 gave readers to two of its columns (the `git grep … → N files` citations, and every repository path it cites).
The column between them — the counts of *doors* and *pages* — was read by nothing. The probe
(`.scratch/r82_probe.py`, `.scratch/r82_probe2.py`, then the gate's own `published_censuses()`) recomputed every one of
them against `git show 8b68b0f:docs/api/openapi.json` (160 paths / 205 operations) and
`git ls-tree -r --name-only HEAD -- apps/web/app` (56 `page.tsx`).

| row | what the row published | what the committed contract/pages answer | verdict |
| --- | --- | --- | --- |
| 16–18 | `` `tactics*` (6 doors)` ``, `` `boards*` (5) ``, `` `simulate*` (4) `` | tactics **7 paths / 7 ops**, boards 5 paths / 8 ops, simulate 4 paths / 6 ops | tactics false; boards and simulate match paths only |
| 20 | `` `careers*` (5) `` | 6 paths / 8 operations | false — matches neither number |
| 21 | `` `challenges*` (4) `` | 4 paths / 4 operations | agrees (both numbers, so the missing unit cost nothing here) |
| 22 | `` `transfers*` (8) `` | 8 paths / 8 operations | agrees (same reason) |
| 35 | 8 paths / 12 operations under `/api/v1/community`, plus `(contract 137/176)` | 8/12 ✓; the whole-contract triple is 160/205 | census ✓, total stale |
| 36 | 7 paths / 11 operations under `/api/v1/creator`, plus `(11 doors, 1 public; contract 144/187)` | 7/11 ✓; 144/187 is `ab2d4c8`'s total | census ✓, total stale |
| **38** | 5 paths / 6 operations "in the committed contract" | 5/6 ✓ — but spelled in a shape the grammar did not read (§3.2) | census ✓, spelling moved |
| 39–41 | `33 paths under /api/v1/club*`, `5 /club* pages` | **36 paths / 56 operations**; **4** `/club*` pages | both false |
| 4 | `` `world/*` pages (8) `` | 8 pages | ✓, second word order |

Seven of the table's counts were attached to a route family **without saying whether they counted paths or
operations**; two of those seven matched neither number the contract answers, and one of them (careers' `5`) was
beside three other unit-less counts that each happened to match one of the two numbers. That is the actual defect this
unit closes: not "the numbers were wrong" but "a number you cannot recompute is a number no reader can keep honest".
The `contract 137/176` / `contract 144/187` pair is the same class one level up — each is a real measurement of a past
commit (`9c6c6af` and `ab2d4c8`, both re-read here) printed inside a table whose heading is present tense.

## 2. The corrections (prose, no code path changed)

* rows 16–18, 20, 21, 22 now print `**N paths / M operations** under \`/api/v1/prefix\`` for each family — unit stated,
  both numbers recomputed;
* row 38's census moved into the same canonical shape (`**5 paths / 6 operations** under \`/api/v1/portfolio*\``), so
  §38's doors are gated rather than merely asserted;
* row 36's `(11 doors, 1 public; contract 144/187)` became `, one of them public,` — the operation count it duplicated
  is now the census it belongs to, and the stale triple is gone;
* row 35 lost its `(contract 137/176)`; row 39–41 became `**36 paths / 56 operations**` and `4 \`/club*\' pages`, both
  carrying the re-read date and ref.

## 3. The gate: `apps/api/tests/test_spec_audit_currency.py` C7 and C8

**C7 `test_every_door_and_page_census_in_the_module_table_recomputes`** accepts exactly two shapes, each of which
names its own referent:

* `(\d+) paths / (\d+) operations` followed by `under \`/api/v1/…\`` (the `**` of the ledger's bold is tolerated —
  without it the scan reads 0 censuses, which is arm A6);
* `N \`/family\` pages` **or** `` `/family` pages (N) ``, where the family does not start with `/api/v1`.

A prefix census is `len([p for p in contract["paths"] if p.startswith(prefix.rstrip("*"))])` paired with the number of
method keys under those paths; a page family counts committed `apps/web/app/**/page.tsx` at or under the family's
stem. Both read the **committed** tree (`git show HEAD:` / `git ls-tree HEAD`, and the filesystem walk on an extracted
plane) — never the shared working copy, which right now holds another lane's uncommitted `docs/api/openapi.json`.

**C8 `test_the_module_table_publishes_no_count_that_has_no_reader`** refuses three enumerated spellings inside §A:
`(N doors)`, a bare `(N)` immediately after a `/api/v1/…` token, and `contract N/M`. It refuses them because there is
nothing to recompute them against, and it names the reason in each message.

**Floors come from the same scan**: `MIN_DUAL_CENSUSES = 10`, `MIN_PAGE_CENSUSES = 3` are the counts
`published_censuses()` returns for the corrected ledger. The first draft of this unit pinned 10 by hand *before*
measuring, measured 9, and the measurement is what found that §38's census was spelled outside the grammar — the row
was canonicalized rather than the grammar widened, which is the difference between a gate that reads the ledger and a
gate that tolerates a shape it never checks.

## 4. Reverse control — the new judge run over HEAD's unedited ledgers

`.scratch/r82_reverse.py` builds a second `git archive 8b68b0f` plane with **only** the gate file overlaid, so the
audit and ROADMAP are the shipped bytes. Result: collected 8, red 2, `rc=1`.

* C7 named the floor: "the §A table yields 2 … where `8b68b0f` yields 10", printing the two censuses it did read
  (`/api/v1/community` 8/12, `/api/v1/creator` 7/11). The scan, run directly, also printed the `/club*` page claim of 5
  against 4 and the `33 paths` claim against 36 — inside the case that page mismatch sits **behind** the floor, so the
  first red hid a second false figure. Recorded rather than reordered.
* C8 named `['6', '11']` (the two `(N doors)`), and the scan shows the bare-after-route set
  `[('/api/v1/careers*', '5'), ('/api/v1/challenges*', '4'), ('/api/v1/transfers*', '8')]` and the stale triples
  `[('137', '176'), ('144', '187')]`.
* The other six cases stayed green on those bytes — the unit adds readers, it does not move the goalposts of C1–C6.

## 5. The witness (`.scratch/r82_arms.py`, predictions in `.scratch/r82_predictions.md` first)

Nine runs on the `8b68b0f` plane, each re-based from `.scratch/r82_base/` so mutations cannot compound; judged by the
**case names** the junit reports and, where several arms redden one case, by the **message fragment** the gate prints.
`runs=9 mismatches=0`.

| run | mutation | predicted red | actual | verdict |
| --- | --- | --- | --- | --- |
| control | none | none (8 collected, 0 red) | none | MATCHED |
| A1 | club path census 36 → 35 | C7, names `/api/v1/club* is published as 35 paths` | same | MATCHED |
| A2 | `/tactics/*` pages 6 → 5 | C7, names `the table says 5 '/tactics/*' pages` | same | MATCHED |
| A3 | row 20 back to the bare `(5)` | C7 (floor 9/10) **and** C8 (`[('/api/v1/careers*', '5')]`) | both, both fragments | MATCHED |
| A4 | row 36 regains `(11 doors, 1 public;` | C8 only (`['11']`), C7 stays green because the 7/11 census survives | same | MATCHED |
| A5 | row 35 regains `(contract 137/176)` | C8 only (`[('137', '176')]`) | same | MATCHED |
| A6 | `CENSUS_DUAL` loses `(?:\*\*)?` | C7, floor message reports `yields 0 … len([])` — the narrow-scan arm proves the floor, not the numbers | same | MATCHED |
| A7 | row 39–41 gains the spelled sentence `Five tables back this tier.` | designed green | green | MATCHED |
| A8 | the *producer* moves: an `options` operation added to one `/api/v1/club…` path (paths pinned at 160, ops +1) | C7 only, `answers 36 paths / 57 operations`; C1/C2 stay green because a triple of paths/routes/migrations does not move | same | MATCHED |

A7 is the disclosure, not a freebie: it states that spelled numerals ("Five tables", row 30's "Three committed doors")
are outside this grammar. Converting them would mean deciding whether "Three committed doors" counts paths or
operations — which is precisely the ambiguity C8 refuses to inherit.

Two prediction-side defects were chased rather than smoothed: the hand-pinned floor of 10 (see §3) and a docstring
first drafted as "four rows … three of those numbers matched neither", which the inventory above disproved (five rows,
seven counts, two matched neither). A third defect was the landing script's own: its stand-down guard compared the
40-hex `git rev-parse HEAD` against the 7-hex ref the witness planes were built from, so it refused a move that had
not happened — the guard fired on the wrong side and was fixed to compare prefixes, which is the shape every later
landing of this project should use (a guard that cannot pass is as blind as one that cannot fail).

## 6. What this unit does not claim

* It does not gate the **ROADMAP's milestone narrative**. Measured in #81, that prose holds 73 path candidates of which
  11 do not resolve and 10 legitimately (`.scratch` witness artifacts, mid-pattern globs, prose fragments); the same
  argument covers its per-tier door counts ("thirteen doors under `/api/v1/club`"), each of which is dated to its own
  step. Those sentences are history; §A is the ledger of the present.
* It does not gate a door's **visibility**: row 36's "one of them public" and row 30's route enumerations are carried
  by `tests/test_authorization_census.py`, which counts tenant-naming doors from the route table, not from prose.
* It does not regenerate `docs/api/openapi.json`. The contract at HEAD (160/205) is the population C7 recomputes; the
  working copy's uncommitted +116 lines belong to another lane and enter no figure here.
* No whole-suite leg is claimed for the +2 cases. The freshest suite figure is still #78's SQLite-only
  `1430 / 1 failure / 0 errors / 2 skipped`, taken before #79–#81; the PostgreSQL engine on this machine is dead
  (`docker version` fails on a stale named pipe), so no PG number is printed by this unit at all.

## 7. Reproduce

```bash
# the eight cases over the committed state (the shared tree's dirty openapi.json is not read)
cd apps/api && ../../.venv/Scripts/python.exe -m pytest tests/test_spec_audit_currency.py -p no:cacheprovider

# the corrected ledger's 13 censuses and the three refusal scans
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .scratch/r82_preflight.py

# the new judge over HEAD's unedited ledgers (expect: collected 8, red 2)
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .scratch/r82_reverse.py

# control + 8 arms over a fresh `git archive 8b68b0f` plane (expect: runs=9 mismatches=0)
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .scratch/r82_arms.py
```

Run before the commit lands, the second and fourth commands answer for a plane that has the corrected audit and the
new cases; run in the shared working copy after the commit, the same eight cases answer for `8b68b0f` plus this unit's
own commit, and the answer is identical: 8 collected, 0 red.
