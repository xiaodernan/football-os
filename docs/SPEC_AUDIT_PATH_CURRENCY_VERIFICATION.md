# #81 — the verdict ledgers' path citations are recomputed, and §38's PDF sentence is retired

Recorded 2026-10-04 over `862359e`. Everything below was read off an artifact: a plane (`git archive 862359e`, no
`.git`), the gate's own junit, or `git ls-tree` / `git show` / `git log` at that ref.

## What this unit found, and where it came from

The unit found its own subject by accident: while writing the handoff after #80, I re-read the §38 row **I had just
landed** and checked it against the tree. It was false in three of its clauses.

| claim in the row `862359e` shipped | measured state of the committed tree at `862359e` |
| --- | --- |
| `services/portfolio/{cv,pdf,sharing}.py` | `git ls-tree -r --name-only HEAD -- apps/api/app/services/portfolio/` answers `__init__.py`, `cv.py`, `sharing.py`. `git log -- apps/api/app/services/portfolio/pdf.py` answers **no commit at all** — the file exists only as another lane's untracked work. |
| "an owner-authenticated PDF built from the same read" | `git show HEAD:apps/api/app/api/v1/portfolio.py \| grep -c -i pdf` → **0**. The committed contract's portfolio block is 5 paths / 6 operations (`/cv`, `/rules`, `/share`, `/shares`, `/share/{token}`) and none of them is a PDF door. HEAD's `apps/api/requirements.txt` names no PDF renderer. |
| "a printed `limitations()` list" | no name `limitations` exists in committed `cv.py`. What the build prints is `UNFILLED_REASONS`, `LIMITATION` and `PUBLIC_OUTPUTS` — and `PUBLIC_OUTPUTS["pdf"]` opens with **"not in this build"**. |

The row also linked `docs/M10_PORTFOLIO_VERIFICATION.md` as its evidence, and that document *at HEAD* states that of
§38's three permitted outputs the PDF "still does not exist". The ledger contradicted the artifact it cited.

`ROADMAP.md` carried the same claim in two more places: the M10 narrative paragraph "**§38's PDF output then landed**
(measured 2026-09-29)" with its `GET /portfolio/cv.pdf` door, 150/194/63 contract figures and a 38,769-byte document,
and the unowned-modules item "**§38 Football Career Portfolio** — landed … and an owner-authenticated PDF rendered
from the same read". That narrative was committed by `251a990`, whose subject line is an M5 frame-overlay follow-up —
the prose entered the repository on a sweep, without the code it describes.

**Corrections made here**, in the same commit as the gate so HEAD is green rather than red with a new accusation:

* the audit's §38 row now names the three committed service modules, the 5 paths / 6 operations, `UNFILLED_REASONS`
  and `LIMITATION` by their real names, states the PDF absence with the four measurements above, and its verdict
  column reads **partial — CV, projection and share link landed; the PDF output did not**;
* the ROADMAP narrative sentence keeps the other lane's numbers (they are a measurement of *something*) and gains the
  re-read that says which state they describe: a working copy, not this repository;
* the unowned item became an unchecked `- [ ]` naming the PDF as §38's open clause, its bullet citing the four
  measurements, and the sentence above the list re-counted itself: "**has a door except two**". That is C5 doing its
  job — a ledger whose cardinal stops matching its own list cannot land.

## The case, and why a citation gate needs this shape

**C6** `test_every_repository_path_the_verdict_ledgers_cite_is_committed` — every repository path the two *verdict*
ledgers cite (the audit's §A table, and ROADMAP's "Spec modules no milestone owns" section) resolves against the
committed tree.

* **Population is derived from the claim, not from an exemption table.** A token is a repo citation when it is
  backtick-quoted, contains a `/`, has no space, colon, `@` or bracket, and does not start with `/` (route templates
  are doors, not files). Measured on the landing state: **26 tokens → 35 expanded candidates**.
* **A brace group is one member list over one segment.** `{__init__,cv,sharing}.py` expands member by member. A token
  carrying *two* groups is **refused**, not cartesian-expanded: the case declines to decide what an ambiguous
  citation means. Measured today: 0 committed tokens carry two groups, so the policy costs nothing — and A5 keeps it
  reachable.
* **Resolution accepts a committed file, a committed file under the cited directory (`services/club/answers.py`
  matches `apps/api/app/services/club/answers.py`), a directory containing a committed file (`services/scouting`), or
  a `dir/**` glob whose prefix has a committed file.** The directory clause binds the *whole* segment sequence, which
  is what makes A3 decisive: `answers.py` exists in `services/club/`, so a basename-only rule would let
  `services/knowledge/answers.py` through.
* **Two floors, both from the same scan**: the walk must contain the audit itself (`assert AUDIT in tree` — an empty
  or mis-rooted walk cannot pass), and the token list must be non-empty (`"the scan read nothing, which is not a
  pass"`). On a `.git`-less plane the walk skips dot-prefixed and vendored directories, because `.scratch` holds
  planes extracted from git and one plane resolving another's citation would be a false green.

**Reverse control, measured before the arms ran** (`.scratch/r81_c6_probe.py`): fed HEAD's *own* ledger bytes against
HEAD's tree, C6 finds 23 tokens → 33 candidates → **1 unresolved: `services/portfolio/pdf.py`**. The new judge names
the site the old ledger shipped. That is the strongest single piece of evidence in this unit, and it is why the case
was written before the prose was believed.

## Witness — 8 runs, judged by case name *and* by what the report names

Five of the seven arms redden the same single case, so a count of red cases cannot tell them apart. Each arm also
carries a predicted **message fragment**, and the runner refuses when the fragment is absent.

| run | mutation (applied to plane bytes, all three files re-based pristine at every arm's top) | predicted reds | predicted message | observed |
| --- | --- | --- | --- | --- |
| control | none | — | — | `tests=6 failures=0 errors=0` MATCHED |
| A1 | §37 `services/achievements.py` → `services/achievementz.py` | C6 | `achievementz` | MATCHED |
| A2 | §38 brace group regains `pdf` | C6 | `services/portfolio/pdf.py` | MATCHED |
| A3 | §29 `{ingest,retrieval,answer}.py` → `…answers}.py` | C6 | `services/knowledge/answers.py` | MATCHED |
| A4 | ROADMAP §38 bullet's requirements citation renamed to an uncommitted file | C6 | `requirements-devx.txt` | MATCHED |
| A5 | §39–41 path token rewritten to carry two brace groups | C6 | `brace groups` | MATCHED |
| A6 | append a citation the tree *does* hold: `apps/api/migrations/versions` | **(green by design)** | — | MATCHED |
| A7 | the audit's `## A.` heading renamed to `## Z.` so the scan reads nothing | **C4 and C6** | `the table this gate reads moved` | MATCHED |

`SUMMARY runs=8 matched=8 not-matched=0` (`.scratch/r81_arms.out`; junits `.scratch/junit_r81_*.xml`).

Two defects surfaced on the **prediction** side, and the record keeps them:

* The first round refused before A4 ran: the patch target `HEAD's \`apps/api/requirements.txt\` names no` hit **twice**
  in `ROADMAP.md` — I had written that exact phrase into both of my own inserts. The runner's exactly-one-hit guard
  earned its keep; the arm's carrier was re-pointed at the unowned bullet only.
* A4's first carrier was chosen by guessing and went **green**: `apps/api/requirements-dev.txt` *is* committed
  (`git ls-tree -r --name-only HEAD -- apps/api/` shows it alongside `requirements.txt`). That is a prediction defect
  — the arm's *purpose* (prove the ROADMAP half of the population is read) still holds, and the accidental green is
  itself a measurement: C6 accepts a citation that resolves, which is A6's designed-green property arriving by
  surprise. The carrier is now a name the tree does not hold, chosen after listing it.

## Why the milestone narrative is not gated

Measured over the whole `ROADMAP.md`: 73 expanded candidates, 11 that do not resolve, and 10 of those 11 are
legitimately outside the tree — `.scratch/leg_p38_summary.txt`, `.scratch/r78_leg_summary.txt`, `.scratch/plane_pgarm_041638`,
`.scratch/vqa/walk.log` (witness artifacts, deliberately never committed), a mid-pattern glob, and prose fragments
(`ADR`, `var`, a markdown link). Gating that file would require an exemption table, and an exemption table is a
hiding place: any future false citation can be added to it. So C6's claim is scoped to the two ledgers that carry
*verdicts*, and the M10 narrative's PDF paragraph is corrected by prose and by this record instead.

## What this unit does not claim

* **No door/route citation is gated.** The retired narrative also asserts `GET /portfolio/cv.pdf`; resolving `/…`
  tokens against the contract is the next unit's design, and it has to handle prose door lists
  (`/api/v1/tactics*` (6 doors), `/world/*`) before it can be honest.
* **No whole-suite leg.** One case added: the gate is 6 cases, measured on the landing plane as
  `tests=6 failures=0 errors=0` and again after the commit through the git reader. #78's leg
  (`1430 tests / 1 failure / 0 errors / 2 skipped`, SQLite only — the PostgreSQL engine is dead on this machine)
  predates this file.
* The `- [x]` → `- [ ]` move is a *ledger* judgement: §38's module is owned and its CV/link half is committed; the
  item now tracks the one clause the tree does not hold.
* Nothing here touches `apps/api/app/services/portfolio/**`, `app/api/v1/portfolio.py`, `apps/web/app/portfolio/**`,
  `lib/portfolio.ts`, `docs/M10_PORTFOLIO_VERIFICATION.md` or `requirements.txt` — all of them are a concurrent
  lane's live work, and the PDF they are building may well make this record's §38 row stale. When it does, the fix is
  to re-read the tree, not to edit the wording: C6 reddens a row that names a file the tree does not have, and
  `PUBLIC_OUTPUTS["pdf"]` is where the build's own answer lives.

## Reproduce

```
.venv/Scripts/python.exe .scratch/r81_c6_probe.py          # HEAD's bytes (1 survivor) vs landing bytes (0)
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .scratch/r81_arms.py   # 8 runs on a .git-less plane over 862359e
cd apps/api && ../../.venv/Scripts/python.exe -m pytest tests/test_spec_audit_currency.py -q   # 6 passed once this unit is committed
```

That last command reads the *committed* state, so run before this commit it answers **5 passed / 1 failed**, naming
`services/portfolio/pdf.py` — the same reading the probe records above, from the other side of the commit.
