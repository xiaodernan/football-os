# §85 — the file-count citations get one reader for every ledger that publishes one (verification record)

`docs/SPEC_COVERAGE_AUDIT.md` calls its evidence *measured*; #80 gave a reader to the counts behind its `git grep`
citations, #81 to its paths, #82 to its door/page censuses and #83 to its route citations. All five of those readers
walk **one** document. The counts live in more than one, and while writing §84's own record the same class of claim
appeared twice more — in `ROADMAP.md` and in `docs/M11_JOINT_RETRIEVAL_VERIFICATION.md` — in spellings no reader
could parse, with numbers that had already gone stale.

## What the measurement found (before any edit, at `e61ff07`)

| question | answer |
| --- | --- |
| committed markdown files the walk reaches | 75 |
| files carrying a citation in the parsed grammar | 1 — the audit, 3 citations, all three recompute |
| lines publishing a file count beside a `git grep` command, in a shape the grammar cannot read | **2** |
| what those two claims said | `ROADMAP.md`'s §30 bullet: "…answers 0 files, so `retrieval.py` never reads the graph"; `docs/M11_JOINT_RETRIEVAL_VERIFICATION.md`: "…→ 0 files (re-read 2026-10-04)" |
| what the same scan answers today | 1 file (`graph_join.py`, landed at `e61ff07`) — so both numbers are stale, in present tense, in the two ledgers that carry the project's verdicts |
| recomputation of the three claims the audit already publishes | 6 / 1 / 8 — unchanged, all still correct |

The stale pair is the interesting part. Both sentences were honest when written: each recorded a measurement taken
*before* the seam landed. Neither said "before". A count that was true of a past tree and is printed in present tense
is how a ledger starts lying about a module that has since been built — and §30's ROADMAP bullet is exactly where a
reader looks to find out whether the joint retrieval exists.

## What shipped

| path | change |
| --- | --- |
| `apps/api/tests/test_spec_audit_currency.py` | C3's population is now **derived from the walk**: every committed markdown file carrying a parsed citation is a carrier, and a carrier without a registered floor goes red rather than quiet. Two new clauses share the case: a refusal (a file count beside a `git grep` command that the grammar does not cover is refused, not guessed) and a void-directory belt (every directory a citation names must hold at least one committed file, so a published zero can never mean "read nothing"). The failure message's number agreement is fixed ("committed file(s)"), and `committed_text` is memoised so the wider walk costs one read per file rather than one per citation. |
| `ROADMAP.md` | §30's unowned bullet now publishes `→ 1 file` and names the file, then states the open half as what the scan does *not* return: `retrieval.py`. §84's row got its two counts rewritten into the grammar. The §85 row records this unit. |
| `docs/M11_JOINT_RETRIEVAL_VERIFICATION.md` | its "0 files" line re-taken at the ref that closed it, plus `golden_joint -- apps/api/app` → 0 files stated as a measurement with its directory named, so the app-tier gap has a reader too. |

Floors are what the gate's own scan returns over the landed bytes — `{audit, ROADMAP, joint record}` = `3 / 3 / 4`,
10 parsed citations in total, read out of `file_count_claims()` on the plane rather than hand-counted with a second
regex. Case count stays **9**: C3 widened in place, it did not split.

## Killing arms

Predictions were written to `.scratch/r85_predictions.md` before the first run; every row is judged on the junit case
*name* and on the `failure` **message attribute**, because four of these arms predict which sentence of the one case
fires — count, refusal, belt, floor, or unregistered carrier. Plane: `git archive e61ff07` extracted to `D:\r85_plane`
(no `.git`), with my bytes for the gate and the three documents overlaid; every arm re-based from those bytes first.

| id | mutation | predicted red, predicted message | measured |
| --- | --- | --- | --- |
| REV | the new judge over HEAD's unedited ledgers | refusal, naming both `ROADMAP.md:471` and the joint record's line | MATCHED — "2 published file count(s) sit beside a `git grep` command… `ROADMAP.md:471`… docs/M11_JOINT_…" |
| CTL | none | 9 collected, 0 red | MATCHED, 9/0 red |
| A1 | audit §30 row 6-file citation → 7 | count sentence, "recomputes to 6 committed file(s); the row publishes 7" | MATCHED, exactly that message |
| A2 | `ROADMAP.md` §84 row 1-file citation → 2 | count sentence, "recomputes to 1 committed file(s); the row publishes 2" | MATCHED, exactly that message |
| A3 | §84 row's directory → `…/knowledgex` **and** its published count → zero, so the arithmetic passes at 0 = 0 | the **belt** sentence ("names no committed file under that path"), not the count sentence | MATCHED — "…`knowledgex` names no committed file under that path, so the row's 0 is not a count of anything" |
| A4 | floors table narrowed to two ledgers, joint record unregistered | "no floor here", naming the joint record as a carrier nobody reads | MATCHED — "…with no floor here, so nobody recomputes them: ['docs/M11_JOINT_RETRIEVAL_VERIFICATION.md']" |
| A5 | parsed grammar made plural-only (`files?` → `files`) | refusal, because the singular claims leave the grammar | MATCHED on the sentence, **missed on the arithmetic**: predicted three singular claims would strand, the scan found five (`ROADMAP.md:472`, §84's row, the audit's §30 row, two in the joint record). The gate's population was right and my mental count was not, so the number in the prediction is the thing corrected |
| A6 | §84 row's two citations back into HEAD's prose | ROADMAP floor sentence ("parses to 1 … arrived reading 3") | MATCHED, exactly that message |
| CTL2 | every path re-based from my bytes after the six arms | 9 collected, 0 red | MATCHED, 9/0 red |

`SUMMARY matched=9 runs=9 floors_match=True`, exit 0, read out of `.scratch/r85_arms.out`.

## What this unit does not claim

* It cannot retire a count that names neither a command nor a directory. `docs/M11_JOINT_RETRIEVAL_VERIFICATION.md`
  still has history prose of that shape ("…where HEAD measures 5"), and a phrasing like "6-file" dodges both readers
  as written. The refusal is a grammar, not a mind-reader: it fires on the spelling ledgers actually use.
* The floor table is protected only indirectly. A4 proves that dropping a *carrier* from the walk goes red because
  the carrier set comes from the tree; nothing here can prove that a future lane will not lower a floor, only that a
  floor reached its number from this scan and says so.
* No whole-suite leg, and no PostgreSQL leg: the engine on this machine is still dead, and the working copy is held
  dirty by another lane's portfolio and security files, so a suite total would name neither plane honestly.

## Reproduce

```
python -m pytest apps/api/tests/test_spec_audit_currency.py -q          # 9 cases, reads the committed tree
```

The gate reads `git show HEAD:…` where a `.git` exists and the walked tree on an extracted plane, so one policy
answers both. Witness chain: `.scratch/r85_witness.py` → `.scratch/r85_arms.out`.
