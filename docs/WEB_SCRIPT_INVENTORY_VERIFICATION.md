# §75 — the web tier's scripts, accounted for: a census that every invocable file is either gated or proven exempt

Unit #77, landed over `f80ee25`. Every figure below names the plane it was measured on, and the witness ran with its
predictions written to disk first (`.scratch/r77_predictions.md`), which is why two of them are recorded as misses.

## What landed

* `apps/web/scripts/qa-gate-inventory.mjs` — 218 lines, 39 checks. Pure `node:fs`: no browser, no server, no port,
  so it belongs in `scripts/check.sh` and CI rather than in the walk schedule it counts.
* `scripts/check.sh` +7/−0 (a `Web: script-inventory gate` section after #76's refusal-shape gate).
* `.github/workflows/ci.yml` +5/−0 (a `Script-inventory gate (who checks the checkers)` step in the `web` job, before
  `Types`, so it can fail a build earlier than the type-check does).

No `.py` path is in this changeset, which is why no whole-suite leg is reported here: the claim is scoped to that
derivation (`git status --porcelain -- '*.py'` lists 16 modified files, every one of them another lane's).

## The census, measured

The population is `readdirSync` of `apps/web/scripts` filtered to invocable spellings: **14 files** — 12 `.mjs` plus
`verify-production.sh` plus this census itself. Before this unit, **1** of them was named by a runner
(`qa-error-shape.mjs`, #76); before #76, 0.

**Filtering to `.mjs` was a hiding place, and the draft said so before it shipped.** The first census of this unit
(`.scratch/r77_census.py`, working copy at `e07fcfb`) reported "12 scripts", which was true of its enumerated
spelling and false of the claim it was about to protect. `verify-production.sh` is the most consequential invocable
file in the directory — it runs `npx tsc --noEmit`, `npm run lint`, `npx next build`, serves the fresh build on
`$QA_PORT`, proves the port answers before it walks, and exits 1 or 3 — and nothing in `scripts/`, `.github/`, or the
package manifest names it. A "every web gate is accounted for" census that reads only `.mjs` would have certified
that absence.

Exemptions are predicates over the file's own bytes, re-measured every run, never a bare name:

| reason | holds when | files |
|--------|-----------|-------|
| `live-tier` | the file names a browser driver **and** binds a base URL/port, or inherits both from the script it invokes | 11 |
| `report-only` | the file never sets an exit status | 1 (`probe-hydration.mjs`) |
| gated | a runner invokes it | 2 (`qa-error-shape.mjs`, this census) |

`verify-production.sh` proves `live-tier` through its child: its own bytes bind `QA_BASE` and `127.0.0.1` and drive
the browser by invoking `node scripts/visual-qa.mjs`, so the tier need is true of its behaviour and false of its
literals. That inheritance is a fixpoint pass over the delegation edges, and arm **A10** kills the pass and watches
exactly one file lose its exemption.

## Two design defects this unit found in its own draft, and fixed before landing

1. **A prose mention counted as gating.** `namedBy` first read `gate.text.includes(name)`, so a comment or a step
   label quoting `scripts/qa-carry.mjs` would mark that file gated while running nothing — the census would have
   certified the one thing it exists to prevent. The shipped form requires a call (`node …scripts/NAME`), and arm
   **A12** writes the mention into `check.sh` as a comment and comes back green at 39/39, which is the witness that
   the tightening holds. The same tightening deleted a false `5c` firing: the census's own runner labels contain
   `scripts/check.sh`, which under the loose pattern made the census a "wrapper" of the runner it audits.
2. **A reason that reads a missing fact key is falsy, not loud-by-design.** The first run of the shipped file printed
   `passed=30 total=54 failed=24`: `REASONS` read `f.needsBrowser` where `direct()` builds `f.browser`, so `live-tier`
   evaluated `undefined && undefined` for all 11 files claiming it, and each opened check 3 (claim does not hold) and
   check 4 (no gate, no proven reason) = 22 reds on top of the 2 genuine ones. Fixed by naming the row shape once;
   the re-run printed exactly the written prediction (`total=43 failed=2`, reds `4` and `8` on the census file). This
   failed *closed* — a silent census with an empty ledger was the alternative — and arm **A11** reintroduces the typo
   to show what it costs: 22 reds, each named.

## The witness: 12 arms + a reach pair + control, predictions first

Plane `D:\足球项目\.scratch\plane_r77inv_084031` (`git archive f80ee25` + the three shipped paths overlaid; every arm
re-bases those bytes before mutating, so arms cannot compound). Launcher `.scratch/r77_arms.py`, artifact
`.scratch/r77_arms3.out`. A verdict is `MATCHED` only when the red **labels** agree as a set (check id + the script
named), plus `failed`, `total`, and the process exit code — a count can match while reddening different clauses.

| arm | mutation | predicted (red labels / failed / total / rc) | observed | verdict |
|-----|----------|----------------------------------------------|----------|---------|
| `control` | none | — / 0 / 39 / 0 | 0 / 39 / 0 | MATCHED |
| `A1_both_runners_degate_errorshape` | drop the call from `check.sh` **and** `ci.yml` | 4 + 7 on `qa-error-shape.mjs` / 2 / 38 / 1 | same | MATCHED |
| `A1b_one_runner_only` | drop it from `check.sh` only | none / 0 / 38 / 0 | 0 red | MATCHED |
| `A2_name_the_report_only_script` | invoke `probe-hydration.mjs` from `check.sh` | 2 + 6 on it / 2 / 40 / 1 | same | MATCHED |
| `A3_wrong_claim_on_a_gated_file` | ledger `qa-error-shape.mjs: [live-tier]` | 3 only / 1 / 39 / 1 | same | MATCHED |
| `A4_phantom_runner_name` | invoke `scripts/qa-phantom.mjs` | 5 (`qa-phantom.mjs`) / 1 / 40 / 1 | same | MATCHED |
| `A5_narrow_the_population_filter` | population to `.mjs` only | 1 / 1 / **36** / 1 | 1 / 36 / 1 | MATCHED (round 1 said 37) |
| `A5b_wrapper_targets_a_sh_still_inherits` | add a `.sh` wrapper + ledger entry, shipped pattern | none / 0 / 42 / 0 | 0 red | MATCHED |
| `A5c_wrapper_pattern_restricted_to_mjs` | same wrapper, `INVOKES` without the `.sh` alternative | 3 + 4 on `wrapper.sh` / 2 / 42 / 1 | same | MATCHED |
| `A6_wrong_claim_on_an_exempt_file` | ledger `visual-qa.mjs: [report-only]` | 3 + 4 / 2 / 40 / 1 | same | MATCHED |
| `A7_census_exempts_itself` | ledger `qa-gate-inventory.mjs: [live-tier]` | 2 + 8 / 2 / 39 / 1 | same | MATCHED |
| `A8_census_removed_from_runners` | drop the census from both runners | 4 + 8 / 2 / 38 / 1 | same | MATCHED |
| `A9_self_exempt_and_ungated` | A7 **and** A8 together | 8 only / 1 / **37** / 1 | 1 / 37 / 1 | MATCHED (round 1 said 38) |
| `A10_inheritance_loop_gone` | fixpoint pass runs zero times | 3 + 4 on `verify-production.sh` / 2 / 40 / 1 | same | MATCHED |
| `A11_fact_key_gone` | `live-tier` reads `f.needsBrowser` | 3 + 4 over the 11 `live-tier` files / 22 / 50 / 1 | same | MATCHED |
| `A12_prose_mention_does_not_gate` | a comment naming `scripts/qa-carry.mjs` | none / 0 / 39 / 0 | 0 red | MATCHED |

`SUMMARY runs=16 matched=16 not-matched=0`, and `rc` tracked `failed` in all 16: green arms exit 0, red arms exit 1,
so the gate fails a build through the same mechanism #76's does (CI reads the exit code, not the `CHECKS` line).

**Both round-1 misses were in my denominator, not in the gate**, and both landed on the clause the arm is about —
recorded as written rather than smoothed over:

* `A5` said 37 because I subtracted the two row-level checks and forgot that dropping `verify-production.sh` from the
  population also drops its delegation, which was the population's **only** `5c` firing (`tally=… 5c absent …`).
* `A9` said 38 because I copied `A8`'s total. `A9`'s whole point is that `A8`'s extra firing does **not** happen: a
  census carrying a reason its own bytes "prove" is covered, so check 4 stays silent and only check 8 reddens. The
  one-clause difference between `A8` (2 reds) and `A9` (1 red) is what makes check 8 load-bearing rather than
  decorative, and it is the only thing standing between a census and self-exemption — the census contains the
  browser/server tokens it looks for, so its own `live-tier` predicate is true of it.

## What the census does *not* claim

* It does not claim the 11 `live-tier` scripts were run. It claims they are *named, read-only classified*, and that
  no file can join the directory unaccounted for.
* Check 5 keys on "some runner invokes it" — arm `A1b` shows one carrier is sufficient and two are redundant, so no
  individual line in `check.sh` or `ci.yml` is itself decisive. That is a property of the design (either runner
  failing the build is enough), not a gap, and it is why the two runners carry the same command.
* It reads only three runner files plus the directory. A runner added elsewhere (a scheduled workflow, a compose
  entrypoint) is outside its population until it is one of the two named here; adding a third carrier is a one-line
  change to `GATES`, and a `GATES` entry whose file is missing reddens check 1b.

## Reproduce

```bash
cd apps/web && node scripts/qa-gate-inventory.mjs        # CHECKS passed=39 total=39 failed=0, exit 0
INVENTORY_TALLY=1 node scripts/qa-gate-inventory.mjs     # the per-check-id breakdown used to chase the two misses
PYTHONIOENCODING=utf-8 python .scratch/r77_arms.py       # 16 runs, predictions in the launcher, MATCHED table
```

The arms run against a plane, not this working copy; nothing they do can touch a file another lane is editing.
