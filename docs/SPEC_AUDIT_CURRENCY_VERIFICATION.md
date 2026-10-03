# #80 — the spec-coverage audit gets a reader (2026-10-04)

`docs/SPEC_COVERAGE_AUDIT.md` is the project's own ledger of what the spec asks for and what the tree answers. It
calls its evidence *measured*, and every row carries a `git grep` citation with a published file count. Nothing in
`apps/api/tests` recomputed any of it, so the ledger could only get older in the direction of understatement, and
the two documents that quote it (`ROADMAP.md`) drifted with it.

## The four lies, measured at `4b9f4b1`

| claim as published | what the committed tree answers |
| --- | --- |
| `ROADMAP.md` quotes `(126 contract paths, 47 page routes, 21 migrations)` in the present tense | **160 / 56 / 26** |
| §30 row: *"no table, no route, no service"*, citing `→ 0 files` | `knowledge_graph` names **5** committed files under `apps/api/app`; `/api/v1/graph/rules`, `…/nodes/{kind}/{slug}` and `…/{slug}/neighborhood` are in the contract landed at `3651587` |
| §38 row: *"no route, no page, no service"*, citing `→ 0 files` | `portfolio` names **8** committed files across `apps/api/app` and `apps/web/app` |
| `ROADMAP.md`: *"Everything in §4–§42 has a door **except two**"* | its own list below that sentence holds **one** unchecked item |

The first three are the loud kind — a module that shipped still advertised as missing, which is how a ledger loses
its readers. The fourth is the quiet kind: a sentence counting the items it introduces, wrong by one because the
item was checked off and the prose was not re-read.

## The gate

`apps/api/tests/test_spec_audit_currency.py`, 5 cases, one clause per way a ledger can rot:

| short | case | catches what the one before it cannot |
| --- | --- | --- |
| C1 | `test_the_audit_s_declared_figures_answer_for_the_committed_tree` | the three headline figures against the tree: contract paths from `docs/api/openapi.json`, page routes from committed `apps/web/app/**/page.tsx`, migrations from committed `apps/api/migrations/versions/*.py` |
| C2 | `test_the_roadmap_quotes_the_audit_s_current_figures_not_an_older_snapshot` | the *summary* document lagging the *source* document — a stale snapshot nobody can see, because both numbers look plausible on their own |
| C3 | `test_every_cited_scan_in_the_audit_answers_with_the_count_its_row_publishes` | a citation whose pattern, population or count no longer matches a re-run of the same scan |
| C4 | `test_the_module_table_covers_its_declared_section_range_exactly_once` | a spec section silently unmapped from the table, or mapped twice, against the range the table's own heading declares |
| C5 | `test_the_roadmap_sentence_counts_the_items_it_introduces` | prose counting its own list — the cardinal is parsed (`one`/`two`/…) and compared with the checkboxes under that heading |

Everything is read from the **committed** tree: `git show HEAD:…` / `git ls-tree -r HEAD` when a `.git` is present,
and the extracted tree itself on a plane (`git archive`) that has none. One policy, exercisable on both planes, and
never the shared working copy — measured at landing time, 30 tracked files carry uncommitted edits in this working
copy and 28 of them are not this unit's, including `docs/api/openapi.json` itself at **+116/−0**; a gate that read
those bytes would publish a figure no commit has ever answered with.

C3 reads `→ N file(s)`, singular included. Measured over the audit as committed today the widened pattern still
finds the same 3 citations (5 / 0 / 8), so it opens no new obligation — it closes a hiding place: a count of 1
written "→ 1 file" is the natural English for a single hit and would otherwise never be read.

Landing state: **5 passed / 0 failed / 0 errors**, measured twice — on a `.git`-less landing plane (HEAD + this
unit's overlay) and again after the commit through the git half of the policy. `scripts/check.sh:20`
(`cd apps/api && python -m pytest`) and CI's two pytest steps invoke the file, so it is gated without a runner edit.

Both readings come from the runner's own junit, not from stdout. `apps/api/pyproject.toml`'s
`[tool.pytest.ini_options] addopts = "-q"` composes with a command-line `-q` into `-qq`, and `-qq` prints the dots and
**no summary line at all** — measured on the landing plane as `rc=0`, stdout `"..... [100%]\r\n"`, nothing after it.
A check written against that prose would have refused a green gate; the invocation is part of the measurement.

## Witness

`.scratch/r80_arms.py`, 8 runs (control + A1..A7) on `plane_r80_*` over `4b9f4b1`, verdicts taken from the case
names that went red in each run's own junit — never a count, never an exit code — against predictions written into
`.scratch/r80_predictions.md` before the first run.

| arm | mutation | predicted red | observed |
| --- | --- | --- | --- |
| control | overlay the corrected ledgers, run the gate | none (5 passed) | MATCHED |
| A1 | audit `AUDIT_FIGURES contract_paths=160` → `159` | C1, C2 | MATCHED |
| A2 | ROADMAP's triple → `144/56/26` | C2 | MATCHED |
| A3 | §30 row's `knowledge_graph -- apps/api/app` citation `→ 5` → `→ 0` | C3 | MATCHED |
| A4 | delete the audit table row for §19 | C4 | MATCHED |
| A5 | ROADMAP "except one" → "except two" | C5 | MATCHED |
| A6 | append a **true** citation (`graph_edges -- apps/api/app` → 1 file) | none — by design | MATCHED |
| A7 | audit **and** ROADMAP both say `159` (consistent, both wrong) | C1 | MATCHED |

Round 1 ran control + A1..A6 and read `runs=7 matched=6 not-matched=1` (`.scratch/r80_arms_round1.out`). The single
mismatch was on the **prediction** side, not the gate side: A1 was predicted `{C1}` and reddened `{C1, C2}`. The
mechanism is that C2 never hardcodes `160` — it reads the audit's own `AUDIT_FIGURES` line as its reference — so a
figure written wrong in the audit is wrong in C2's eyes too. Predicting from the arm's *idea* ("a number in the
audit") instead of from *which cases read that line* is the same failure mode recorded for the AI Career OS #186
witness. The observed red set is the correct one, so A1's prediction was amended and **A7** was added, because round
1 exposed a real hole: **C1 had no sole-witness**. Only an arm that keeps the two documents in agreement can red C1
while C2 stays green — and that pair (A2 → C2 alone, A7 → C1 alone) is what proves agreement is not truth: two
documents that agree on `159` still answer to the tree. Round 2: `runs=8 matched=8 not-matched=0`.

A6 is the designed-green: it publishes a count that a re-run of the scan confirms (1 — `knowledge_graph/verbs.py`,
whose single mention of `graph_edges` is the sentence saying the table does not exist), and C3 stays green. Its
carrier was chosen by measurement after a preflight killed the first draft: `graph` over
`apps/api/app/services/knowledge` recomputes to **1** committed file (`chunking.py`, matched through the substring
in "paragraph"), so the citation originally planned for that arm would have red C3 and been filed as a surviving
mutation for the wrong reason.

## What this unit does not claim

* It does not claim a whole-suite leg for the +5 cases. #78's leg over `3651587` is the nearest baseline:
  `1430 tests / 1 failure / 0 errors / 2 skipped`, `collect=1430`, wall 1016s, SQLite-only (the Docker engine was
  dead at launch, so no PG leg ran) — and it predates this file, so the population claim here is `+5 cases`, not a
  new total. That leg's one red is another lane's
  `tests/test_portfolio.py::TestTheSectionsAreTheSpecs` case; 26 of the 27 reds the mount finding predicted were gone
  on that plane, which is what makes the attribution a measurement in both directions.
* It does not gate "maps all 30 product modules". The master spec is not a committed artifact, so 30 cannot be
  counted against anything in the tree. C4 gates what the tree *can* answer: the table covers the §-range its own
  heading declares, exactly once.
* It does not gate the §30 row's *remaining* gap. `0 of the 18` golden RAG queries name a committed team or
  competition, so the joint RAG↔graph hop has no measured case yet; that figure is prose with a date, deliberately
  not a gate, because it would rot with the world generator. The real remaining §30 work is a corpus↔world linkage
  tier, not a recall-widening bolt-on.
* It does not edit `apps/api/app/services/knowledge_graph/**` or `app/api/v1/graph.py` — another lane's live work.

## Reproduce

    python .scratch/r80_arms.py        # the 8-run witness, plane-local, prints MATCHED/MISMATCH per arm
    git archive 4b9f4b1 | tar -x -C /tmp/plane80
    cp apps/api/tests/test_spec_audit_currency.py docs/SPEC_COVERAGE_AUDIT.md ROADMAP.md # onto the plane, same paths
    (cd /tmp/plane80/apps/api && python -m pytest -q tests/test_spec_audit_currency.py)

## Currency of this record

The "5 passed / 0 failed" figures above describe the file as it stood at `862359e`. #81 added a sixth case to the same
file — C6, every repository path the two verdict ledgers cite must resolve against the committed tree — and retired
the §38 row this record's prose still quotes. Read `docs/SPEC_AUDIT_PATH_CURRENCY_VERIFICATION.md` for the sixth
case, its 8-run witness and the §38 measurements; the five cases recorded here are unchanged and still green.
