# Issue #111 / #114 · assert-message rendering — verification

The suite reports its own failures with `assert <cond>, <message>`. Two shapes of message operand throw the answer
away between the process and the terminal, and both were in use here. The sentence this unit is built on:

**a red case whose verdict is elided on the way to the screen is a red case nobody can fix, so the message operand
has to be a `str` that provably fits on one line.**

Everything below is measured. Every figure names the plane it was read on and the ref it was read at, because this
repository is shared with a concurrent writer whose uncommitted bytes are not this unit's evidence.

* Gate: `apps/api/tests/test_assert_message_forms.py` (6 cases)
* Converted population: `apps/api/tests/*.py`, `apps/api/app/*.py`
* Landed: conversion `71d6850` (38 sites in 14 files); this commit adds the last 2 sites (`test_boards.py`, freed by
  the gallery lane's `862079a`), the gate, and this record

---

## 1. The two loss mechanisms, reproduced at the shipped command form

Both were first proved on a plane outside this repository (#112). The leg below re-proves them at the settings the
published commands actually use — `python -m pytest <file> -q --tb=line -rf` with the repo interpreter
(`.venv/Scripts/python.exe`, CPython 3.13.14) — and it proves the *other* half too, which no static reading can:
that the shapes #114 converts to still deliver the verdict.

`.scratch/r114_render_leg.py` (run as `python .scratch/r114_render_leg.py D:/r114-render`, 2026-10-17) writes one
failing case per shape, one shape per run — `--tb=line` prints `path:lineno: <message>` with no case name in it, so
attributing four failures sharing one report would be reading a guess. Each message carries the same two markers, one
on the first row of a 40-row collection and one on row 38:

| message operand | rows that reached the terminal | rendered message length | head marker | tail marker | predicted |
| --- | --- | --- | --- | --- | --- |
| `assert ok, (problems, rows)` | **12 of 40** | 245 chars | seen | **invisible** | head seen, tail invisible |
| `assert ok, 'prose: ' + '\n'.join(rows)` | **1 of 40** | 102 chars | seen | **invisible** | head seen, tail invisible |
| `assert ok, f'prose: {rows!r}'` | **40 of 40** | 657 chars | seen | seen | head seen, tail seen |
| `assert ok, 'prose: ' + ' \| '.join(rows)` | **40 of 40** | 614 chars | seen | seen | head seen, tail seen |

`4 shapes / 4 MATCH`. The two loss mechanisms, as the terminal shows them:

* **A non-`str` message goes through pytest's repr window.** The rendered line above is 245 characters and its body
  is `(['ROW_00_HEADMARK', 'ROW_01_row', … 'ROW_05_row', ...], [...])` — the window keeps the head and the tail of
  the *repr* and replaces the middle with `...`, in every traceback style including the repo's default `-q`. So
  `assert not rows, (name, got, wanted)` — the shape 29 of these sites used — is a red case whose answer was
  discarded on the way out.
* **A `str` message with a newline is clipped to its first line** by `--tb=line`, the style three published leg
  commands use (`docs/M8_ACADEMY_VERIFICATION.md:376-377`, `docs/M9_COMMUNITY_VERIFICATION.md:112`,
  `docs/M12_PRODUCTION_HARDENING_VERIFICATION.md:369`). 1 of 40 rows survived. `-rf` restores neither: the short
  summary line is derived from the same rendered message, and above it printed `AssertionError: (['ROW_00_HEA...`.

**The leg's own first run missed, and the miss is on the record.** Its first version put the head marker on
`ROW_01`, predicted "seen", and measured "invisible" — a MISMATCH. The mechanism was right and the fixture was
wrong: `ROW_01` is the message's *second* line, so the clip removed it. Re-anchored to `ROW_00`, all four shapes
matched. The reading that came back was stronger than the prediction: the clip is exactly at line 1.

The table above was re-measured on 2026-10-18 from the very script this section cites, at repo HEAD `862079a`: all
four rows reproduced byte-for-byte (12/40, 1/40, 40/40, 40/40 markers and 245/102/657/614-character rendered
messages). A reproduce command that points at a file which no longer measures what the table says is not a reproduce
command.

## 2. The population the rule had to govern

`.scratch/r113_census.py` walks the committed tree — files enumerated with `git ls-tree -r HEAD`, bytes read with
`git show HEAD:<path>` — never the shared working copy. Same numbers, one row per shape, both refs:

| reading | `fe32570` (before) | `71d6850` (after 38 sites) | the landing plane (this commit) |
| --- | --- | --- | --- |
| committed `.py` files walked | 213 (68 tests + 145 app) | 213 (68 + 145) | 214 (69 + 145) |
| `assert` statements | 4813 | 4813 | 4859 |
| carrying a message operand | 1374 | 1374 | 1411 |
| **`BAD:*` — provably not a `str`** | **36** (29 tuple, 6 list-comp, 1 set-comp) | **2** (both tuple, `test_boards.py`) | **0** |
| **`CLIPPED:*` — provably newline-bearing** | **4** (all `binop-add`) | **0** | **0** |
| offenders / carriers | 40 in 15 files | 2 in 1 file | **0 / 0** |
| `single-line:fstring` (`!r` throughout) | 19 | **53** | 63 |
| `single-line:binop-add` (` \| `-joined) | 1 | **5** | 12 |
| `single-line:constant` | 616 | 616 | 629 |
| `UNPROVABLE:*` (name, attribute, subscript) | 380 | 380 | 385 |
| `unknown-lines:*` (newline not decidable statically) | 318 | 318 | 322 |
| invisible to the walk (`UNPROVABLE` + `unknown-lines`) | 698 of 1374 | 698 of 1374 | **707 of 1411** |

The third column is not a re-read of `HEAD`: it is the walk over `git archive` of `862079a` plus the two files this
commit changes, which is the state the gate has to be green on the moment it lands. The population grew because a
concurrent lane landed `test_boards.py`'s gallery work and a 69th test module — the gallery lane did **not** convert
its two tuple messages, so #114 converted them here (see §3). `.scratch/r118_scan_reading.py D:/r118-plane` prints
this column by importing the shipped gate and calling its own `scan()`, because a floor read from a second loop is
not the floor the gate enforces. The walk inside that reading counts **the gate's own file**: 17 asserts, all 17 of
them carrying a message (8 `single-line:fstring`, 7 `binop-add`, 2 `constant`), which is why the `single-line:*`
rows move more than the converted-site count alone would explain.

`4859 = 3448 messageless + 1411 with a message`, and the buckets sum to the assert count exactly — that balance is
itself a clause of the gate, because a message operand that went unclassified would make every number above a
reading of less than the tree.

The last two rows are the honest ceiling on what any gate of this kind can promise: **707 of the 1411 messages on the
landing plane (698 of 1374 at `71d6850`) are invisible to a syntax walk**, because `response.text`, `rows[0]` or
`str(x)` are neither provably a `str` nor provably newline-free. The gate counts and publishes those; it does not
refuse them. A rule that refused them would be a tax disguised as a proof.

## 3. The conversion

38 of the 40 offenders, in 14 files, landed as `71d6850` (38 insertions / 41 deletions). The 2 that remained are
`test_boards.py`'s non-finite-coordinate and per-account-ceiling messages, which #114 left alone while a concurrent
lane held that file modified with uncommitted gallery work; the gate's ledger named them by identity instead of
pretending they were clean. `862079a` landed that lane's work, the file went clean, and this unit converted both
sites: the ceiling message reads `f"board {index!r} of 24 was not created; the answer read {response.text!r}"`, so
`response.text` — which the walk cannot type — goes behind `repr()` and becomes provable. The ledger is now empty
and `BAD:*` is 0 in the committed tree.

The identity keying paid for itself at that moment: the gallery lane's commit shifted the two sites from lines
104/156 to 106/158, and the ledger row still read them at count 2 because it names a file, a shape and a count,
never a line number.

`.scratch/r114_convert.py` splices one statement at a time and refuses to write unless every check passes:

* one file's sites are applied **bottom-up** by line number, so a splice at line 559 cannot shift the line the next
  entry cites, and the file's bytes stay in memory across its own sites;
* the file's line ending is detected first and a file that mixes LF with CRLF is refused outright, because a
  splice that emitted bare `\n` into a CRLF file would silently rewrite the whole tree's shape (7 of these files
  are CRLF on disk — measured with the reader that consumes them, not with a shell `grep`);
* the cited line number is re-read from the bytes rather than trusted, an anchor string has to appear in the
  statement that number names, and the tested expression is re-parsed and compared by `ast.dump` — **a message
  conversion that changed the condition is a different unit**;
* the result is re-parsed, re-classified, and must come back `single-line:*`, and a final per-file residual scan
  refuses to keep a file that still holds a `BAD:`/`CLIPPED:` message below the site it touched;
* every interpolation the splicer introduces gets `!r`, which is what makes an f-string message *provable*
  newline-free (`repr()` escapes newlines for the strings and containers these sites carry). Nothing was written on
  a run where any check failed — the first such refusal cost 38 candidate edits and left the tree untouched.

## 4. The gate, and the six things it decides

| case | refuses |
| --- | --- |
| `test_no_message_operand_is_provably_not_a_string` | any `BAD:*` message not named by the exemption ledger |
| `test_no_message_carries_a_newline_in_its_own_syntax` | any `CLIPPED:*` message not named by the ledger |
| `test_the_exemption_ledger_names_sites_that_exist` | a ledger row that outlives its sites, and a carrier no row names — and, because the ledger is now empty, the same check run on a three-way plant (agreeing, stale, unledged) so an empty ledger cannot rot into a silent one |
| `test_the_walk_reads_the_population_it_claims` | floors `214` files / `4859` asserts / `1411` messages, the buckets-vs-asserts balance, and the per-file-vs-global balance |
| `test_the_converted_carriers_still_hold_their_shape` | 18 (file, shape) pins over the 15 converted carriers |
| `test_the_classifier_judges_every_shape_it_claims_to` | 25 synthetic sites, one per declared verdict, plus "no declared verdict unexercised" and "no verdict in the tree outside the declared vocabulary" |

The fourth case is what makes the others readable: a scan that quietly narrowed would report "0 offenders" forever,
so finding nothing has to be louder than finding something dirty.

## 5. Three witness batteries, and the holes they opened

A battery mutates the gate's own plane and predicts which cases go red *before* running. Plane: `D:/r114-plane`, a
`git archive` of `71d6850` (521 extracted files, reconciled against `git ls-tree -r HEAD`: 521 committed, 68 of them
`apps/api/tests/*.py`) plus the gate file; no `.git`, so the gate falls back to the documented filesystem walk and
the plane *is* the committed state.

**Battery 1** (`.scratch/r116-arms-battery1.txt`): 8 arms, **7 MATCH, 1 MISMATCH**, both baselines green, all 8
restores clean. The mismatch was the informative one. `A3-join-separator` converted both `" | ".join(offenders)`
separators in `test_answer_census.py` to `"\n".join(` and predicted that `single-line:binop-add` would fall under
its repo-wide floor of 5. It stayed green. Measured on the plane afterwards: the bucket reads **11**, not 5, because
**the gate's own 6 joined messages are inside the population it walks** — `71d6850` holds 5 joins across the repo and
the plane holds 11. A floor the gate's own text outruns cannot see an edit-back, so the pin became per-carrier:
17 (file, shape) floors, 41 f-strings + 5 joins over the 14 files #114 converted. At landing the table is 18 rows over
15 carriers — `test_boards.py` joined it when its two sites converted (§3).

**Battery 2** (`.scratch/r116-arms.txt`) runs against that gate, with predictions rewritten for the new pins and one
arm added for the regression battery 1 could not reach: **9 arms, 9 MATCH**, both baselines green, all 9 restores
clean, exit 0.

| arm | mutation | predicted red | red set |
| --- | --- | --- | --- |
| A1 tuple-back | `test_world.py:216` reverts to its old list comprehension | BAD, LED, CERT | MATCH |
| A2 newline | a `single-line:constant` message in `test_response_cache.py` grows a `\n` | CLIP, LED | MATCH |
| A3 join-separator | both `test_answer_census.py` joins become `"\n".join(` | CLIP, LED, CERT | MATCH |
| A4 narrow | `POPULATION` loses `apps/api/app/` | POP | MATCH |
| A5 ledger-deleted | the `test_boards.py` row is removed from `EXEMPTIONS` | BAD, LED | MATCH |
| A6 ledger-stale | the gallery lane lands: its two tuples convert, ledger untouched | LED | MATCH |
| A7 classifier | the `!r` branch of `has_newline` returns `None` instead of `False` | SELF, CERT | MATCH |
| A8 new-shape | a planted `assert ok, name if rows else other` (`IfExp`) | SELF | MATCH |
| A9 edit-back | one `!r` dropped, leaving a legal bare interpolation | **CERT alone** | MATCH |

A2 is the arm that distinguishes a file with a pin from one without; A9 is the one battery 1's floor could not
express: a message that stays a `str` and stays one line to the walk's eye, so no shape clause fires, no carrier
appears in the rows, no count moves — only the per-carrier pin notices.

Every arm restores the file it touched and re-runs the gate to prove the plane is clean again, and every run asserts
its denominator (`passed + failed == 6`) before it reads a red set.

**Battery 3** (`.scratch/r118_arms.py`) is the one that measures the gate **as it lands**: plane `D:/r118-plane`,
`git archive` of `862079a` plus this unit's two files, so the exemption ledger is empty, the floors read
214/4859/1411, and `test_boards.py` carries the two conversions. Two arms had to be re-aimed because reality moved:
battery 2's A5 deleted a ledger row that no longer exists, and its A6 replayed a conversion that has already
happened. Run 1 (`.scratch/r118-arms-run1.txt`, exit 1): **8 MATCH, 1 MISMATCH**. Run 2
(`.scratch/r118-arms-run2.txt`, exit 0): **9 arms, 9 MATCH**, both baselines green, all 9 restores clean.

| arm | mutation | predicted red | red set |
| --- | --- | --- | --- |
| A1 tuple-back | `test_world.py`'s converted message reverts to its list comprehension | BAD, CERT, LED — see the miss below | MATCH |
| A2 newline | a `single-line:constant` message grows a `\n` | CLIP, LED | MATCH |
| A3 join-separator | both `test_answer_census.py` joins become `"\n".join(` | CERT, CLIP, LED | MATCH |
| A4 narrow | `POPULATION` loses `apps/api/app/` | POP | MATCH |
| A5 stale-row | a row is **added** to `EXEMPTIONS` naming a site the walk cannot find | LED | MATCH |
| A6 boards-revert | `test_boards.py`'s two conversions go back to `(bad, problems)` / `(index, response.text)` | BAD, CERT, LED | MATCH |
| A7 classifier | the `!r` branch of `has_newline` returns `None` | CERT, SELF | MATCH |
| A8 new-shape | a planted `assert ok, name if rows else other` (`IfExp`) | SELF | MATCH |
| A9 edit-back | one `!r` dropped in `test_club_organizations.py` | CERT | MATCH |

**A1's first prediction missed, and the miss is on the record.** It predicted {BAD, LED} and measured
{BAD, CERT, LED}. The arm replaces one of `test_world.py`'s two `single-line:fstring` messages, so that carrier's pin
drops 2 → 1 and `CERT` fires — which is precisely what a per-carrier pin is for. The gate was right; the prediction
was written as though an edit-back could only be charged by the shape clause. A6 is the same lesson at the other
file: reverting `test_boards.py` goes red in three cases, not one.

A5 and A6 are the two directions the empty ledger needs. With no rows in it, the agreement clause reads nothing on
the real tree, so battery 3 charges it from outside (A5: a stale row) *and* the case itself now runs the check on a
three-way plant (agreeing, stale, unledged) so an empty ledger cannot silently become a blind one.

## 6. Reverse control: the same gate against the ref before the cure

The **shipped** gate file, copied into a worktree at `fe32570` (the parent of the conversion) and run there. The disk
there holds none of the converted sites, so this is the gate judging the tree it was written against, not the tree it
landed in:

```
5 failed, 1 passed in 28.25s        # exit 1
FAILED ::test_no_message_operand_is_provably_not_a_string     → 36 of the 36 BAD sites unledged, `test_boards.py:104/156` among them
FAILED ::test_no_message_carries_a_newline_in_its_own_syntax  → the 4 CLIPPED `binop-add` sites
FAILED ::test_the_exemption_ledger_names_sites_that_exist     → 15 carriers no ledger row names
FAILED ::test_the_walk_reads_the_population_it_claims         → "the walk reads 213 committed files … below the 214 the census measured"
FAILED ::test_the_converted_carriers_still_hold_their_shape   → 16 of the 18 pins unmet (213-file tree, 0 converted sites)
```

Only the classifier self-test passes, and it should: it judges synthetic sources, not this tree. The previous version
of this section recorded `4 failed, 2 passed` — the second pass was the population case, which it accepted because
its floors were still low enough to fit a pre-cure tree. Raising them to 214 files made the floor clause refuse this
tree too, so the control is stronger than the one it replaces: the gate now fails on the *size* of the population as
well as on its shapes. The two pins that stay satisfied at `fe32570` (`test_error_answer_shape.py`'s join,
`test_spec_audit_currency.py`'s 4 f-strings) are shapes those files already held before this unit touched them — a
pin on a carrier that had some of the shape anyway is a weaker witness than one that starts at zero, which is why
the battery in §5 still mutates each carrier rather than trusting the floor.

The same file run at `862079a` plus this commit's two files is `6 passed` (§7).

## 7. Legs

| leg | plane | reading |
| --- | --- | --- |
| the gate, as it lands | `D:/r118-plane` — `git archive` of `862079a` plus this commit's two files | **6 passed in 13.83s**, exit 0 |
| the landing census, through the shipped `scan()` | same plane | 214 files / 4859 asserts / 1411 messages / `BAD` 0 / `CLIPPED` 0 / 707 invisible |
| ruff over `test_assert_message_forms.py` + `test_boards.py` | working copy | `All checks passed!`, exit 0 |
| the two loss mechanisms, at the shipped command form | `D:/r114-render` | 4 shapes, 4 MATCH (exit 0) |
| witness battery 1 | `D:/r114-plane` | 7 MATCH / 1 MISMATCH, exit 1 |
| witness battery 2 | `D:/r114-plane` | 9 arms 9 MATCH, exit 0 |
| witness battery 3, run 1 | `D:/r118-plane` | 8 MATCH / 1 MISMATCH (A1's prediction), exit 1 |
| witness battery 3, run 2 | `D:/r118-plane` | **9 arms 9 MATCH**, both baselines green, 9 clean restores, exit 0 |
| reverse control, shipped gate against the pre-cure ref | worktree at `fe32570` | **5 failed, 1 passed in 28.25s**, exit 1 |
| whole API suite, SQLite | worktree at `71d6850` + gate file | **1652 passed, 2 skipped in 820.97s (13:40)**, exit 0 |
| whole API suite, SQLite | at the commit that lands this file | owed — a docs-only follow-up records it here |
| PostgreSQL leg | — | owed, recorded below |

The conversion's own suite leg ran at `71d6850`, before `test_boards.py` was freed and converted and before this file
moved from 17 pins to 18; it is kept as the reading it is, not re-labelled as a leg of this commit. The gate adds no
runtime to the suite beyond its own six cases, and the two `test_boards.py` conversions change message text only —
the conditions they guard are byte-identical (`ast.dump` comparison is a clause of the converter, §3).

The suite's first reading on that plane was `1 failed, 1651 passed, 2 skipped`. The single red was
`test_openapi_contract_currency.py::test_the_exporter_derives_the_contract_from_the_tree_and_reproduces_the_committed_bytes`,
naming 426358 committed bytes against 411051 serialised. Both numbers are the same JSON: `core.autocrlf=true` made
the fresh checkout of `docs/api/openapi.json` CRLF (15307 `\r\n`, one per line) while the exporter writes LF and the
HEAD blob is LF (`git show HEAD:docs/api/openapi.json` measures 411051 bytes, 0 CRLF — and the main working copy
carries the same LF bytes). Normalising the plane's copy to the blob's bytes made that file `4 passed in 13.80s`,
and the whole suite was re-run over the corrected plane to produce the number in the table. **The red was an
artifact of the plane, not of the tree** — a fresh worktree on this host is not byte-faithful to HEAD, and any
whole-suite leg run in one has to normalise the artifacts its gates read.

## 8. Reproduce

```
python .scratch/r113_census.py                # repo HEAD basis, buckets + floors
python .scratch/r114_render_leg.py D:/r114-render    # 4 shapes, 4 MATCH — runs pytest in the directory it is given
git archive HEAD | tar -x -C D:/r118-plane    # a sibling dir; never under the repo root, or the walk counts it
cp apps/api/tests/test_assert_message_forms.py apps/api/tests/test_boards.py D:/r118-plane/apps/api/tests/
cd D:/r118-plane/apps/api && python -m pytest tests/test_assert_message_forms.py --tb=line -rf   # 6 passed
python .scratch/r118_scan_reading.py D:/r118-plane    # the landing census through the shipped scan()
python .scratch/r118_arms.py                  # battery 3: 9 arms on D:/r118-plane, 9 MATCH
python .scratch/r116_arms.py                  # battery 2: 9 arms on D:/r114-plane — rebuild it the same way first
cd apps/api && python -m pytest --tb=line -rf   # whole API suite
```

The reverse control is the gate file copied into a worktree at `fe32570` and run there —
`git worktree add D:/r114-wt-parent fe32570`, then `cp apps/api/tests/test_assert_message_forms.py` into
`D:/r114-wt-parent/apps/api/tests/` and run the shipped command from `apps/api`. Expect `5 failed, 1 passed`.
Running the gate in the shared working copy is **not** a leg: until this commit lands, `git show HEAD:` still answers
`test_boards.py`'s two tuple messages, so a working-copy run is red about bytes that are on their way out.

**Everything under `.scratch/` is host-local** — `git ls-files .scratch` answers 0 — so the commands above are the
*shape* of each measurement, not an artifact a reader can check out. The shipped, tracked legs are the gate itself
(`apps/api/tests/test_assert_message_forms.py`) and the two `--tb=line` commands; §1's table and §2's columns can be
re-derived from those without any scratch file, which is the property that makes them evidence rather than notes.

## 9. Opened by this unit, not closed

* **707 messages stay outside the proof** (`UNPROVABLE:*` 385, `unknown-lines:*` 322, measured on the landing plane;
  698 of 1374 at `71d6850`). The commonest carrier is `response.text` — a `str` at runtime and a syntax hole to the
  walk. Closing them means a convention (`assert isinstance(x, str)` first, or a helper that renders the message),
  not a scanner. `test_boards.py` alone holds 16 of them (`UNPROVABLE:Attribute` 10, `unknown-lines:fstring` 5,
  `UNPROVABLE:Subscript` 1) — converting its two `BAD` sites did not make that file provable, only less blind.
* **The whole-suite and PostgreSQL legs at this commit** are owed (§7). The conversion is text-only in its conditions,
  so the risk these legs carry is a *message* a test asserts about another test's output, not a behaviour change.
* **`docs/M8_ACADEMY_VERIFICATION.md` §"Reproduce"** publishes two `--tb=line` legs over `test_club_academy.py`, and
  at `fe32570` that file's counts-gate message was `"...disagrees with the door:\n" + "\n".join(...)` — so the logs
  those commands produced carried the header sentence and none of the verdict tags. Corrected in this commit with
  the date on which the reading changed.
* **One doc-reading currency module is red at `e4b19c3`, and a second one is red only in the shared working copy.**
  Running them as a pre-check on the records this commit writes found both, and they needed separating:
  `test_spec_audit_currency.py` refuses the audit table's declared page census — **"AUDIT_FIGURES says 59 page
  routes; apps/web/app has 61 committed page.tsx"**, and 6 `/tactics/*` pages where the committed tree holds 8. That
  reading is HEAD-basis on both sides (`git show HEAD:` for the table, `git ls-tree -r HEAD` for the pages) and so is
  a defect at `e4b19c3`: the gallery lane's pages landed without the census that quotes them.
  `test_openapi_contract_currency.py`'s four reds are **not**: `answers()` is `app.openapi()` imported from the disk,
  while `committed()` reads the disk's copy of `docs/api/openapi.json`, and the traces routes it names live only in
  this lane's **uncommitted** `app/api/v1/agents.py` — `git show HEAD:` counts **0** occurrences of `traces` there,
  the working copy counts **9**, and the contract counts 0. No clean plane reproduces that red, which is the same
  attribution #110 had to make for the gallery lane's `boards.py`. Both are queued as #115 work — the audit census
  because it is a stale document, the contract because it goes red the moment the agents lane lands — and neither is
  fixed here, because this commit's evidence would stop naming the tree it was measured on.
* **A fresh worktree is not byte-faithful to HEAD on this host** (§7). Anything that gates artifact bytes has to say
  which plane it read, and legs that run in a worktree have to normalise first.
