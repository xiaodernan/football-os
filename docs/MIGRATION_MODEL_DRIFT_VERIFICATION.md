# Migration-and-model drift verification

ROADMAP Phase 9 items 40 and 41. Date: 2026-11-04.

Two units, one defect class. Item 40 is the repair of a landing that reverted a landed unit; item 41 is the gate
that makes the half of it no test could see — a migration that builds a column no model declares.

## 1. What happened: a landing carries its plane's stale bytes

`c0d376c` ("the wire's own blocks now close their census") carried **22 paths**. Two of them are that unit's own
work: `apps/web/scripts/qa-wire-readers.mjs` (+20/−10) and section 20 of `docs/I18N_ARC_VERIFICATION.md` (+59/−0),
the RTL record whose bytes had landed at `cd82dcd`. The other **twenty** were not. They answered HEAD's item-36
bytes — the objectives-that-pay surface `0cf34c1` shipped and `40762fa` re-cut — with **pre-item-36 text**, taken
from a checkout older than `0cf34c1`:

| the reverted path | what it lost |
| --- | --- |
| `apps/api/app/models/__init__.py` | `AWARD_KINDS`'s `"objective_bonus"`, `OBJECTIVE_BONUS_EFFECT`, and `CareerBudgetAward.stage` with the `uq_career_award_stage` key |
| `apps/api/app/services/simulation/career.py` | `pay_objective_bonuses`, called from `close_season` (−54 lines) |
| `apps/api/app/services/simulation/market.py` | `OBJECTIVE_BONUS_BY_KIND`, `objective_bonus_report`, the wire's `totals.bonus_rows` and `RULES["objective_bonus"]` (−183/+25) |
| `apps/api/tests/test_career.py` | `TestObjectiveBonuses` — 9 cases (−196/+14) |
| `apps/api/tests/test_transfers.py` | `objective_bonus` in `RULE_KEYS`, `bonus_rows` in the `totals` equality |
| `apps/web/...` six files | the ledger row, the balance sentence's second income term, `MarketView["totals"]["bonus_rows"]`, the `bonus_if_closed_now` block |
| `apps/web/messages/{en,zh,zh-TW}.json` + `README.md` | 5 keys per locale, and the README rows back to `3988 of 4033` |
| `docs/M13_OBJECTIVE_BONUS_VERIFICATION.md`, `PLAN.md`, `docs/ROADMAP_NEXT.md` | the item's own record, section and bullet (−73, −31, −30) |
| `docs/SPEC_COVERAGE_AUDIT.md`, `ROADMAP.md` | the audit's `migrations=50` → `49`, in both carriers `test_spec_audit_currency.py` reads |

What the plane did **not** carry is the point: `apps/api/migrations/versions/0049_objective_bonuses.py` stayed
where it was. So HEAD held a revision that adds a column and swaps a unique key, and a model that declares
neither.

## 2. What the suite could see, and what it could not

Run against a clean `git worktree` at `c0d376c`, the five files that judge this surface answered **2 failed, 148
passed**:

* `test_spec_audit_currency.py::test_the_audit_s_declared_figures_answer_for_the_committed_tree` —
  `AUDIT_FIGURES says 49 migrations; apps/api/migrations/versions holds 50 committed .py files`.
* `test_locale_claims.py::test_the_readme_table_states_the_coverage_the_catalogues_actually_have` —
  `the zh row counts a population of 4033; `en.json` holds 4053 keys`.

Both reds are figures against files, and both exist because a claim was pinned to **the commit** rather than the
checkout — the second one is the gate `e8fa569` landed the same morning, which is how a reverted README was caught
at all. What did **not** red is the schema: every test that builds its database with `create_all` gets the
model's schema and never asks what the chain builds, and nothing in `apps/api/tests` ran the chain and compared
it to `Base.metadata`. `scripts/schema_drift.py`, the one drift probe the repo ships, compares `String(n)`
*widths* against a **live** database — it cannot see a column that exists on one side only, and it is not in the
suite.

## 3. Item 40 — the repair

`21bbf86` restores the twenty blobs exactly as `e8fa569` held them and keeps the lane's own two paths. Nothing was
edited by hand: a restore, so the question "is the feature back as it was graded?" has the answer "byte for byte,
yes". Verified on the plane before publishing, and on it after:

* the six API files that judge this surface — `test_career`, `test_transfers`, `test_spec_audit_currency`,
  `test_openapi_contract_currency`, `test_locale_claims`, `test_simulation` — **208 passed** (5:35);
* `ruff check app tests` clean, `mypy app` **161 source files, no issues**, `tsc --noEmit` rc=0;
* the file-only web gates: `qa-wire-readers` **12/12**, `qa-locale-completeness` 2/2, `qa-key-drift` 4/4,
  `qa-token-drift` 2/2, `qa-unused-keys` 3/3, `qa-i18n-literals` 9/9, `qa-shared-keys` 4/4, `qa-field-labels` 2/2,
  and `qa-gate-inventory` **194/194** — the lane's own inventory figure survives the restore, because the two
  paths that carry it were never in the reverted set.

The repair also had a second-order effect worth naming: item 38's record and plan rows were written on a plane at
`e8fa569`, and landing them as they stood would have dropped `## 20` — the RTL record — exactly as `c0d376c` had
dropped item 36. They were rebased onto `21bbf86` first (additive only: 101 insertions, 0 deletions) and landed as
`d188aef`.

**The whole API suite on the repair.** `.scratch/wt-revert`, a clean `git worktree` detached at `21bbf86`, run with
`-o addopts= -p no:randomly`: **1 failed, 2148 passed, 4 skipped, 330 warnings in 2214.38 s (0:36:54)**
(`.scratch/item40-suite.log`). The population is the one item 38 measured — 2149 passed + 4 skipped — so the
restore neither lost nor gained a test, which is what a byte-for-byte restore should do.

The one red is `test_ci_trigger.py::test_every_workflow_that_runs_on_push_covers_the_branch_the_run_is_about`, and
it is not about the repair: `_pushed_branch()` falls back to `git rev-parse --abbrev-ref HEAD`, which answers
`HEAD` on a detached checkout, and the case asserts the branch it can name is a real one. Every landing in this
project is graded on a detached plane, so on that instrument the gate reddens unless the run is handed a fabricated
CI environment — which is the shape item 38's post-landing suite actually ran under
(`GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master` prefixing the command), a fact its record did not carry and §7
files as an item. Untouched by both landings, the same case answers green on the shared tree, which is on `master`.

## 4. Item 41 — the gate

`apps/api/tests/test_migration_model_drift.py`. One probe, four clauses.

**The probe** runs in a subprocess with its own `DATABASE_URL` pointed at a temporary SQLite file — so the
checkout's `.env`, the suite's test database and the dev database are all out of the picture — runs the committed
chain with `alembic command.upgrade(config, "head")`, and asks alembic's own `compare_metadata` what would have to
change to move the migrated schema to `Base.metadata`. The revisions it reads are the committed tree's; the models
it reads are the committed tree's. One run serves all four cases (`@cache`), and the whole file costs **10.9 s**.

**The clauses**, each able to fail alone, so the first red names the shape:

1. no revision builds a column the models have stopped declaring — the reverted-unit clause, and its message
   names *which revision* shipped the column by reading the committed sources for the ones that name both the
   table and the column;
2. every column a model declares is built by a revision — the unwritten-migration clause, the ordinary direction;
3. the tables agree in both directions;
4. anything else `compare_metadata` can name — constraints, indexes — the catch-all.

## 5. The witness

| arm | tree | what it plants | verdict |
| --- | --- | --- | --- |
| W | `c0d376c` — the real reverted commit, not a plant | nothing; the drift is what landed | **2 failed / 2 passed**: clause 1 `1 column(s) … [('career_budget_awards', 'stage')] … [('stage', ['0049_objective_bonuses.py'])] — a landing that reverted the model without reverting the migration`; clause 4 names `uq_career_award_stage` out and `uq_career_award_season` back |
| base | `1877db5`, clean | nothing | **4 passed** in 10.9 s |
| A1 | same plane, `CareerBudgetAward.zz_item41_probe` added to the model | a column with no revision | clause 2 alone: `1 column(s) the models declare are built by no revision: [('career_budget_awards', 'zz_item41_probe')]`; the other three cases green |
| A2 | same plane, `ZzItem41Table` / `zz_item41_table` appended | a table with no revision | clause 3 alone: `no revision builds 1 table(s) the models declare ['zz_item41_table']`; the other three cases green |
| R | `21bbf86`, the repair | nothing | the chain and the models answer **0 differences** — the `DRIFT none` figure item 36's record walked by hand is now a committed claim |

W is the arm this unit was built for: it is not a plant, it is the commit that shipped the defect, and the gate
reds there with the revision file's name in the message. A1 and A2 are the synthetic direction — each names the
clause that carries it and leaves the other three green, which is what "each fails on its own clause" is worth.

## 6. Reproduce

    git worktree add --detach .scratch/wt-drift c0d376c
    cp apps/api/tests/test_migration_model_drift.py .scratch/wt-drift/apps/api/tests/
    (cd .scratch/wt-drift/apps/api && python -m pytest -o addopts= -q -p no:randomly tests/test_migration_model_drift.py)
    # 2 failed on the reverted commit; 4 passed at master
    python .scratch/item41-arm-a1.py   # plants a model column, writes its verdict to a file (the host console is GBK)
    python .scratch/item41-arm-a2.py   # plants a model table, same shape

## 7. What this does not claim

It does not compare types or widths — `compare_type` on SQLite reports reflection noise, and widths are
`scripts/schema_drift.py`'s claim against a live database, which this file neither re-derives nor replaces. It
grades SQLite only; a pgvector index migration owns (`ix_chunk_embedding_hnsw`) is not in the population this
probe can see. And it cannot see the *other* half of `c0d376c`: twenty paths of service code, tests, web
components and catalogue keys were reverted too, and none of it is a schema — the two gates that red on that
commit red because a figure disagreed with a file. What makes a reverted unit loud in general is a different gate,
and this unit files it rather than pretending to be it.

**Found on the way, filed, not fixed.** Two things, and both are claims this unit's own measurements leaned on.

*Item 42.* `c0d376c`'s own path — `qa-wire-readers.mjs` — documents four populations and checks 12, 13 and 14 over
the `totals` block, naming `components/MarketTools.tsx` as the seam a census follows. The shipped script declares
`TOOLS_TSX` and `FLOOR_TOTALS_KEYS` and never reads either: **1 declaration each, 0 uses**, and the run answers
`CHECKS passed=12 total=12` — the eleven checks and 3b it had before. The file exists (19,969 bytes) and its
`totals` block is real; the census of it is prose.

*Item 43.* A gate that can only be made green by a fabricated environment is a claim about the run, not about the
tree. `test_ci_trigger.py`'s local branch read answers `HEAD` on a detached checkout and then refuses it (§3), so
the full suite on the plane every landing is graded on is red unless the command carries
`GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master`. Item 38's record says its post-landing suite ran "on a checkout
detached at `e8fa569`" — true, and incomplete without the env prefix, which is why it answered rc=0. The cure is
to ask git which branch contains the commit (`git for-each-ref --contains`) instead of asking the checkout what it
is called, and, when no branch answers, to skip naming why rather than to redden the instrument or to be told a
lie about the machine.

**Landing.** `f5d6abf` carried the gate — one path, 8,354 bytes, parent `1877db5` — and is green on the four
commit-reading gates beside it (`test_migration_model_drift`, `test_spec_audit_currency`, `test_locale_claims`,
`test_openapi_contract_currency`: **24 passed in 63.45 s** on a clean worktree detached at the commit). This
record, its roadmap bullet and the `PLAN.md` section landed as `265e7a7`, and the same five gates answer
**30 passed in 153.69 s** there (`test_assert_message_forms.py` joins them, because a new test file is a new
population of assertion messages).

## Follow-up (2026-11-05): the same reversal was armed in the shared index

Writing §3's suite line meant reading the shared tree again, and the census
(`.scratch/shared-index-census.py`, output in `.scratch/shared-index-census.txt`) found the §1 defect one command
away from repeating itself — not in a landing, but in the workspace every landing is cut from.

`git diff --cached --numstat` in `D:\足球项目` answered **26 paths**, and 24 of the 26 staged blobs are byte-for-byte
`c0d376c`'s copies: the index was still the tree as of `c0d376c`, while `refs/heads/master` — the branch that
checkout is on — had moved through six landings. For the paths landed since, the index holds no entry at all, so
`git status` prints them the way it prints a deletion: `0 187 apps/api/tests/test_migration_model_drift.py`,
`0 154 docs/MIGRATION_MODEL_DRIFT_VERIFICATION.md`, `0 71 docs/I18N_ARC_VERIFICATION.md`. A bare `git commit` in
that tree would therefore have committed a revert of items 36, 38's §21, 39, 40, 41 and 43 **without touching a
single byte of anyone's work** — which is how `c0d376c` read when it landed: not hostile, just old.

Nothing in `git status` shows this, because the shared *disk* carries the concurrent lanes' newer content
(`market.py` +1014 lines against master, `test_transfers.py` +487, `models/__init__.py` +176, the three
catalogues +72/76/77) and is reported as modified either way. It is visible only as index-against-HEAD, which is
precisely what a commit consumes.

**What was done** (`.scratch/shared-sweep-disarm.py` prints its plan, then applies it on `--apply`):

* all 26 index entries set to the blob `refs/heads/master` publishes, with `update-index --cacheinfo` — staging
  **nothing** from the working tree, so no lane's uncommitted edit entered the index and no lane's staged intent
  was discarded (the census had already shown the index held no original work: every blob in it is a published
  copy, and the two entries at "no published copy" are exactly the paths a stale snapshot cannot have);
* 8 files restored on disk to master's bytes, and only those whose own blob matched a published commit's copy or
  which were absent from the tree: the drift gate, this record, `docs/OPENAPI_CONTRACT_VERIFICATION.md`, §21 of
  the i18n record, `docs/SPEC_COVERAGE_AUDIT.md`, `test_openapi_contract_currency.py`, `test_ci_trigger.py` and
  `ROADMAP.md`. `git commit -a` stages the working tree first, so a disk that lags HEAD is how a sweep commit
  reverts something *while* looking like it adds;
* 17 files left exactly as found, because their bytes match no published commit — that is somebody's live edit,
  including `PLAN.md` and `docs/ROADMAP_NEXT.md`, into which the landed rows for items 39 (marked done, with its
  arms and its landing pair) through 43 were then **inserted** rather than written over
  (`.scratch/shared-ledger-sync.py`, which refuses to write if its own diff deletes more than the one row heading
  it meant to re-date: `docs/ROADMAP_NEXT.md -1 +52`, `PLAN.md -0 +57`).

After: `git diff --cached` answers **0 paths**, `git diff --numstat master` answers 36 (the lanes' work), and
`refs/heads/master` still reads `ef649ef`.

**What would catch a repeat, now.** §4's gate reddens clause 1 by name if a model is reverted while its migration
stays — the exact half of `c0d376c` nothing could see. `test_spec_audit_currency` holds the migration count
against the committed `versions/` directory, and `test_locale_claims` holds the README population against the
committed catalogues, so a reverted claim reds at the commit rather than in a browser. **What stays silent** is a
reverted *prose* row — a `PLAN.md` section or a roadmap bullet that disappears and takes a feature's record with
it. Nothing grades a ledger's completeness, and that is filed here rather than cured: the two carriers this
session restored by hand (`d188aef`'s rebase, `21bbf86`'s twenty blobs) both began as prose nobody could see
moving.

**Not claimed.** The census is a reading of one workspace on one host at one moment, not a committed artifact, and
no gate re-runs it — the numbers above are `.scratch/shared-index-census.txt` at `ef649ef`. The disarm changed no
commit and no lane's bytes; it re-pointed a cache. And a lane that later runs `git add -A` in the shared tree will
stage its disk content over these index entries, which is that lane's decision to make — the point was never to
freeze the index, only to stop it committing a revert nobody staged on purpose.
