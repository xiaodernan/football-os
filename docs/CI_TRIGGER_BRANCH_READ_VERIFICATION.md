# CI trigger branch-read verification

ROADMAP Phase 9 item 43. Date: 2026-11-05.

A gate that can only be made green by telling the machine something it does not know stops being a claim about
the tree. This unit is the branch read in `apps/api/tests/test_ci_trigger.py`, found because the suite on the
repair plane (`21bbf86`) answered 1 failed / 2148 passed / 4 skipped — the first time this project's own
instrument, rather than a planted arm, produced the red.

## 1. What the gate read, and what that did to a plane

`test_every_workflow_that_runs_on_push_covers_the_branch_the_run_is_about()` asks each workflow with a `push`
trigger whether its branch patterns cover "the branch the run is about". On GitHub the answer is in the event
(`GITHUB_REF_NAME`, or `GITHUB_BASE_REF` for a pull request). Locally it read

    git rev-parse --abbrev-ref HEAD          # → "master" on a branch, "HEAD" when detached

and then asserted the answer was a branch name. A detached checkout answers the literal `HEAD`, so the assert
failed — and every landing of this project is graded on a detached `git worktree`, because the shared working
tree carries concurrent lanes' uncommitted bytes and can never be a landing source (§1 of
[MIGRATION_MODEL_DRIFT_VERIFICATION.md](MIGRATION_MODEL_DRIFT_VERIFICATION.md)).

Two consequences, both measured:

* **The suite is red on the instrument.** At `21bbf86`: 1 failed / 2148 passed / 4 skipped in 36:54
  (`.scratch/item40-suite.log`), the single failure this case, on a plane whose tree is the commit being graded.
  Nothing about the repair was wrong; the checkout's shape was.
* **Green required a fabricated environment.** The same suite answers rc=0 on a detached plane when the command
  carries `GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master`. That is exactly how item 38's post-landing verdict —
  recorded as "on a checkout detached at `e8fa569` itself: the same 2,149 passed, 4 skipped, 330 warnings, rc=0"
  — was reached, and its record did not name the prefix. A reader comparing the two logs would have found one
  green and one red at populations that differ by nothing, and no way to tell why.

The second is the reason this is worth a unit rather than a workaround note: the project's records are claims,
and a claim whose reproduction needs an undocumented environment variable is not reproducible.

## 2. The cure

`_pushed_branches(root)` answers in three steps, in this order:

1. **the event**, if there is one — `GITHUB_BASE_REF` for a `pull_request`, `GITHUB_REF_NAME` for a `push`,
   each still asserted to be present when its event arrived;
2. **the checked-out branch**, when `rev-parse --abbrev-ref HEAD` names one — the shared tree and any lane
   branch, unchanged from before;
3. **otherwise the commit's own history**: `git for-each-ref --contains HEAD --format=%(refname:short)
   refs/heads/`, taken against the branch this project publishes to. That branch is `origin/HEAD`'s target where
   the checkout has a remote — the same read that found the original defect (`origin/HEAD -> origin/master`,
   while `ci.yml` triggered on `main`) — and elsewhere `master`, then `main`, then the single local branch.

If the published branch does not carry the commit, the case **skips** and names what it looked for: the refs that
do carry it, or none. A run graded on such a plane is not a run of a published branch, and an assert there would
have reddened the instrument instead.

The resolver is not trusted because it is convenient. The case
`test_the_branch_fallback_answers_on_a_detached_checkout_and_names_why_when_it_cannot` builds a throwaway repository in a temporary directory — with `commit.gpgsign` and
`core.hooksPath` pinned off so a host's signing cannot fail a commit that has nothing to do with what is graded —
and asserts all four shapes: on a branch → that branch; detached at a commit the published branch carries → that
branch (the landing-plane shape); on a side branch → the side branch, because the checked-out branch is the
run's own answer and the fallback never overrules it; detached at a commit no published branch carries → nothing.
That last pair is what makes the skip above a statement about the commit rather than about git.

## 3. The witness

Every arm ran on `.scratch/wt-ci`, a clean `git worktree` detached at `265e7a7`, with `GITHUB_*` removed from the
child environment (`env -u GITHUB_EVENT_NAME -u GITHUB_REF_NAME -u GITHUB_BASE_REF`, and the parent's own
environment held none: `[]`). `.scratch/item43-arms.py` writes the verdicts to
`.scratch/item43-arms.txt` as UTF-8, because this host's console is GBK and these lines are quoted.

| arm | input | verdict |
| --- | --- | --- |
| base | the cured file, whole | **8 passed** in 9.50 s, rc=0 — the trigger case *answered* `master`, it did not skip |
| W | HEAD's own reader, written beside the cure as `tests/_zz_item43_old.py` and run alone on the same tree | **1 failed**: `assert ('HEAD' and 'HEAD' != 'HEAD')` |
| W | the cured case, same tree, same moment | **1 passed** in 4.33 s |
| A1 | `ci.yml`'s push trigger rewritten `[master]` → `[main]`, cure in place | **1 failed**: `ci.yml runs on push to ['main'], but this run is about 'master'` — the catch the gate was written for still reds, through the new fallback |
| A1 | workflow restored | **1 passed** |
| A2 | a plane detached at `9a35ff2`, an unreferenced `commit-tree` child of master (`refs containing it: ['<none>']`) | **7 passed, 1 skipped**, the reason printed with `-rs`: `this checkout is detached at a commit that the branch this project pushes ('master') does not carry — git for-each-ref --contains HEAD answers [] — so no push event would ever name a branch for this run` |

W is the differential the unit turns on: one input, two readers, red and green. A1 is the arm that asks whether
the cure blunted the gate, and it does not: the fallback resolves `master`, and a trigger that names a branch no
push carries is still refused. A2 is the skip path, shown with its reason rather than asserted away.

## 4. The suite with no fabricated environment

Re-measured on the cure's own commit, on a plane with nothing in its environment to fabricate:

    .scratch/wt-ci  detached at ef649ef  (the cure)
    env | grep -c '^GITHUB_' → 0
    python -m pytest -o addopts= -q -p no:randomly tests
    → 2154 passed, 4 skipped, 330 warnings in 2990.83s (0:49:50), exit=0   (.scratch/item43-suite.log)

The case that was the only red at `21bbf86` is not skipped into greenness here: §3's base arm shows it *answering*
`master` through step 3 of the resolver, and this run is the same file over the same tree. What changed between the
two lines is the reader, not the environment — the earlier red needed no prefix to produce it, and this green needs
no prefix to allow it.

The populations differ: 2148 passed at `21bbf86` (item 40's measurement) against 2154 here. One of the six is this
unit's own new case, measured exactly — `test_ci_trigger.py` went 7 → 8 in §3. The other five arrived with the
commits that landed between the two measurements, and this file does not re-attribute them; a reader who wants the
split should collect at each commit rather than trust a subtraction made here.

What item 38's line needed and this one did not is the point of the unit: that run was reached with
`GITHUB_EVENT_NAME=push GITHUB_REF_NAME=master` on the command line. §1 supplies the prefix the record omitted, and
§6's command is the one that reproduces a green without it.

## 5. What this does not claim

It does not make a detached plane a published branch. On a checkout the published branch does not carry, the
trigger claim is not graded — it is skipped, loudly, and §3's A2 row is the place that shows the reason rather than
a tally line. It does not touch the other cases in the file: the lint target's population, its argv, the step's
working directory and the `pull_request` trigger are all read exactly as before, and `GITHUB_*` still wins when
GitHub really is the caller. And it does not retroactively make item 38's suite line wrong — 2,149 passed and 4
skipped is what that command produced; what the record lacked was the prefix, which §1 now supplies.

The class it does not close: any gate whose local fallback asserts on the *shape* of the checkout reddens every
plane. `grep` over `apps/api/tests`, `apps/web/scripts` and `scripts/*.sh` finds no other read of
`--abbrev-ref` or `GITHUB_*`, and the `.git`-less fallbacks in `test_locale_claims.py`,
`test_openapi_contract_currency.py` and `test_spec_audit_currency.py` all grade a *file*, not a ref, so a detached
checkout is the same input as an attached one for them. If a future gate reads `HEAD`'s name, it inherits this
finding.

## 6. Reproduce

    git worktree add --detach .scratch/wt-ci 265e7a7
    # the cure lands at ef649ef; the parent's reader is what W grades
    git -C .scratch/wt-ci show HEAD:apps/api/tests/test_ci_trigger.py > .scratch/wt-ci/apps/api/tests/_zz_item43_old.py
    cd .scratch/wt-ci/apps/api
    env -u GITHUB_EVENT_NAME -u GITHUB_REF_NAME -u GITHUB_BASE_REF \
      python -m pytest -o addopts= -q -p no:randomly tests/test_ci_trigger.py tests/_zz_item43_old.py
    python .scratch/item43-arms.py   # the four arms; verdicts go to .scratch/item43-arms.txt as UTF-8
