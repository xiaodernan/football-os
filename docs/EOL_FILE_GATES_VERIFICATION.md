# File-only gates read bytes, and a checkout is not the tree

ROADMAP Phase 6 item 49. Date: 2026-11-06.

Thirty of this project's web gates are *file-only*: no server, no browser, no port — they read source and catalogue
bytes and assert predicates over them. Every one of them read those bytes raw. On this host a `git worktree` checkout
and the shared working tree are therefore **different inputs to the same gate**, and the difference is invisible in
the repository and visible in the verdict: `qa-a11y-witness.mjs` answers **11/16 failed=5** on a plane and
**16/16 failed=0** on the same commit's bytes in the shared tree.

That single line has been quoted in this project's landing records for weeks without anyone asking why the number
moved. The answer is the unit.

## 1. Why a plane is not the tree

    git config core.autocrlf          → true
    ls .gitattributes                 → No such file or directory
    git show master:apps/web/styles/globals.css | CR pairs → 0    LF count → 275
    .scratch/wt-eol49/apps/web/styles/globals.css  | CR pairs → 275

The repository holds LF; `core.autocrlf=true` with no `.gitattributes` means every checkout materialises CRLF, one
pair per line, and the shared working tree — written by tools over months rather than by `git checkout` — stayed LF.
So the blobs and the shared tree agree and the landing plane disagrees with both, on every text file, by exactly one
byte per line.

A gate that anchors on a single line never notices. A gate that anchors across a line — a template literal holding
`\n`, a rule written over three lines — notices, and what it notices depends on where the reader stood.

## 2. The census, and the two shapes of harm

Every file-only gate (the split is `qa-gate-inventory.mjs`'s own rule: a script naming a base URL or `fetch(` is a
live gate and is not in this population) was counted for raw text reads:

| | count |
| --- | --- |
| file-only gates | **30** |
| `readFileSync` sites in them | **61** |
| sites that folded line endings before this unit | **0** |
| sites folded by this unit | **60** |
| sites left raw on purpose | **1** — `qa-share-preview.mjs:219` reads a PNG's bytes, and folding binary is a bug |

The harm came in two shapes, and only one of them was loud:

- **`qa-a11y-witness.mjs` — a verdict that moves.** Its arms mutate a copy of the shell and *assert the anchor was
  found*: `const after = before.replace(from, to); if (after === before) throw new Error("arm anchor not found …")`.
  Five arms anchor across lines — the skip link's three-line element, the `:focus-visible` rule, the same rule again
  for source order, the `prefers-reduced-motion` block, `aria-current` in `Nav.tsx` — so on CRLF bytes none of the
  five found its anchor, five checks that should have gone red for the right reason went red for the wrong one, and
  the gate refused with rc=1 where the LF tree passed it 16/16.
- **`qa-a11y.mjs` — a verdict that stays and a number that lies.** The same offsets it compares ("the skip link is
  rendered before the nav") are byte positions in a file whose lines each gained a byte: it printed
  `PASS 5 … — 2293 < 2393` on the plane and `PASS 5 … — 2231 < 2328` on LF. The claim held in both, so no gate went
  red and no record noticed the two runs were not runs of the same bytes.

## 3. The cure

One clause at each read, in the gate itself, with no shared module and no new file:

    (readFileSync(path, "utf8").replace(/\r\n/g, "\n"))

Applied by script to every site whose call ends in a `"utf8"`/`"utf-8"` argument, in all 30 gates, 60 sites, each
file re-parsed with `node --check`. The fold is the identity on LF bytes, which is why the cure is safe to make
before anyone decides what the repository's policy *should* be: it removes the dependency on the checkout instead of
betting on one answer.

The a11y witness needed nothing further: it builds a fixture with `copyFileSync` and then reads it through the same
folded calls, so a CRLF fixture arrives to the arms as LF and every anchor is found again.

## 4. The measurement

Four runs of the whole file-only population, two scripts × two line endings, each gate's captured stdout+stderr
compared after masking every path (so a printed plane directory cannot count as a difference):

| scripts | tree bytes | gates refusing | gates printing different bytes between the two trees |
| --- | --- | --- | --- |
| parent `3cd9b3f` | CRLF | 3 — `qa-a11y-witness`, `qa-rtl-readiness`, `qa-wire-readers` | **2** — `qa-a11y-witness`, `qa-a11y` |
| parent `3cd9b3f` | LF | 2 — `qa-rtl-readiness`, `qa-wire-readers` | (that is the comparison) |
| cured | CRLF | 2 — `qa-rtl-readiness`, `qa-wire-readers` | **0** of 30 |
| cured | LF | 2 — `qa-rtl-readiness`, `qa-wire-readers` | **0** of 30 |

The claim is the last cell twice: after the fold, the same thirty gates print the same bytes on a CRLF checkout and
on an LF one. Before it, two of them did not — one of them by moving its exit code.

`qa-rtl-readiness` and `qa-wire-readers` are red in all four rows and are not this unit's: the first is committed
physical CSS with the logical fixes uncommitted (roadmap row 50), the second is a typed block ahead of the published
one (row 51). Line endings were never the reason either was red, and the fold did not change them.

`tsc --noEmit` and `next lint` are clean over the cured plane; the 60 edits are inside `scripts/qa-*.mjs`, which is
not in the tsconfig program, and ESLint reports nothing.

## 5. What this does not claim

It does not decide the repository's line-ending policy. A `.gitattributes` with `text=auto eol=lf` would remove the
class at the source instead of at each read, and it is the right thing — but it changes the bytes `git status` sees
for every working-tree file that is CRLF today, in a shared tree other lanes are standing in, and that blast radius
is its own unit. Filed as roadmap row 52 with the measurements in §1 as its evidence.

It does not fold the *live* gates, and they are not in this population: they read what a server answers, and a
server's JSON has no line endings. `qa-gate-inventory.mjs`'s rule made the split; nothing here was inferred from
filenames.

It does not prove the other twenty-eight gates have multi-line anchors today — the census counts reads, not needles.
What it proves is weaker and more useful: none of them can ever again *silently* depend on the checkout, because the
bytes they read no longer contain a carriage return on the way in. `qa-a11y.mjs` is the demonstration that a gate can
differ between trees without changing its verdict, which is why the fix went to all 60 sites rather than the two
gates that showed.

## 6. Reproduce

    git worktree add --detach .scratch/wt-eol49 3cd9b3f
    # apps/web/node_modules must be a junction with a RELATIVE target:
    #   cd .scratch/wt-eol49/apps/web && cmd /c "mklink /J node_modules ..\..\..\..\apps\web\node_modules"
    python -c "print(open('apps/web/styles/globals.css','rb').read().count(b'\r\n'))"   # 275: the plane is CRLF

    PYTHONUTF8=1 .venv/Scripts/python.exe .scratch/item42-webgates.py wt-eol49        # after: 2 refused
    # the four-arm table: .scratch/eol-out/{parent_CRLF,parent_LF,cured_CRLF,cured_LF}/<gate>.txt
    # the twins are wt-eol49lf (cured scripts, LF) and wt-eol49lf-parent (parent scripts, LF);
    # wt-eol49crlf-parent is the parent scripts on a CRLF tree.
    # verdict: gates printing different bytes between trees — parent 2/30, cured 0/30
