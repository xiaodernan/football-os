# §83 — every API route citation in the verdict ledger gets a reader

Unit: **#83**. Gate: `apps/api/tests/test_spec_audit_currency.py`, case **C9**
(`test_every_api_route_citation_in_the_verdict_ledger_resolves`). Ledger under audit:
`docs/SPEC_COVERAGE_AUDIT.md`. Plane for every number below: `git archive ad9b841` extracted to
`.scratch/r83_plane` (no `.git`, so the filesystem walk *is* the committed state) with my four paths overlaid;
readings from the shared working copy are labelled as such. The working copy currently holds another lane's
uncommitted `docs/api/openapi.json` (+116/−0) — none of the figures below come from it; the contract every claim is
checked against is HEAD's, measured at **160 paths / 205 operations**.

## What was claimed, and what the committed contract answers

The audit maps 30 spec modules to "measured evidence", and part of that evidence is a route citation: a backticked
`/api/v1/…` token in a row whose verdict says *landed*. Until this unit nothing read those tokens. `#80` recomputed
the file counts behind `git grep` citations, `#81` recomputed the repository *paths*, `#82` recomputed the door/page
*censuses* — but a census says "N paths / M operations under a prefix" and is checked as a prefix, while a citation
says "this door exists" and can only be checked as a path.

Measured over HEAD's ledger with C9's own helpers (plane reading, `.scratch/r83_probe4.py`):

| ledger | citations resolve | parameterized | negated | census referents excluded | defects open |
| --- | --- | --- | --- | --- | --- |
| `ad9b841` as committed (uncorrected) | 31 | 4 | 1 | 10 | **3** |
| the same grammar over the corrected ledger | **49** | **12** | **1** | **10** | **0** |

The two columns are **candidate** counts, not token counts. `ad9b841`'s ledger holds **28** backticked `/api/v1/…`
tokens, **10** of which are the referents of a C7/C8 census phrase and are excluded, leaving **18** read tokens that
expand into 31 resolvable candidates (the three malformed ones contribute none). The corrected ledger holds **37**
tokens — the four rewritten citations fan out — with the same **10** excluded and **27** read, expanding through
brace enumerations into the **49** candidates the table reports.

## The four defects, and what each one was hiding

All four are in the ledger's own words; all four were true-looking rows in a table whose heading is present tense.

1. **§9–12** `` `/api/v1/coach/{ask,plan,today,history,drills/{slug}/knowledge}` `` — one brace group whose last
   member carries a *second* brace. Expanding it literally would fabricate the path
   `/api/v1/coach/drills/{slug}/knowledge` under a head segment `{ask,plan,today,history,drills/`; there is no
   reading that keeps the enumeration and the nested door both honest.
   → `` `/api/v1/coach/{ask,plan,today,history}`, `/api/v1/coach/drills/{drill_slug}/knowledge` ``
2. **§13–14** `` `/api/v1/video/{upload,{id},analyse,file,frames/{i},jobs}` `` — same conflation, and the parameter's
   name is wrong twice over: the contract spells the video id `{ident}` and the frame index `{index}`.
   → `` `/api/v1/video`, `/api/v1/video/upload`, `/api/v1/video/{ident}/{analyse,file,jobs}`,
   `/api/v1/video/{ident}/frames/{index}` ``
3. **§B** `` `/api/v1/video/{id}/jobs` `` — a parameterized citation whose *door* the contract publishes and whose
   *parameter* it does not: `PARAMETER-NAME … names ['{id}'] where the contract spells that door [('{ident}',)]`.
   → `` `/api/v1/video/{ident}/jobs` ``
4. **§B 61–62** `` `/progress/export`, `/progress/player-data` `` — API doors spelled as web routes. Both are
   committed API paths (`/api/v1/progress/export`, `/api/v1/progress/player-data`); as written, no reader could
   check them at all.

A fifth row, **§9–12** `` `/trainings/{drills,sessions/{id}/complete}` ``, carries defects 1 *and* 4 at once: no
`/api/v1` prefix, and a brace inside a brace. It is therefore **outside C9's population** — the case cannot retire a
citation it cannot see — and was rewritten into the grammar rather than left as an uncheckable claim:

```
`/api/v1/trainings/{drills,sessions}`, `/api/v1/trainings/drills/{drill_id}`,
`/api/v1/trainings/sessions/{session_id}/complete`
```

The row's verdict (*landed*) was true all along, and stays true: measured at `ad9b841` there is no
`apps/web/app/trainings/` directory committed, while the contract answers four `/api/v1/trainings/…` doors —
`drills`, `drills/{drill_id}`, `sessions` (GET+POST), `sessions/{session_id}/complete`. `{drill_id}` and
`{session_id}` are the contract's own parameter names, which is the only reason C9 accepts them.

## The grammar

A `/api/v1/…` token in the audit resolves in exactly one of five ways, and C9 refuses the two shapes that have no
single reading:

| shape in the ledger | how it is read | arm that kills it |
| --- | --- | --- |
| a bare door `` `/api/v1/graph/rules` `` | membership in the contract's `paths` | A2 (`NO-SUCH-DOOR`) |
| a family `` `/api/v1/club*` ``, or a `*` on one member of an enumeration (`/api/v1/scout/{…,shortlists*}`) | at least one committed path starts with the stem | (shares A2's resolver) |
| a parameterized door `` `/api/v1/graph/nodes/{kind}/{slug}` `` | path-shape match **and** every parameter name equals the contract's spelling | A1, A7 (`PARAMETER-NAME`) |
| an enumeration `` `/api/v1/video/{ident}/{analyse,file,jobs}` `` | expanded member by member, then each member through the three clauses above | A1, A3 |
| a citation the prose introduces as absent (`No`/`never` within 30 chars) | *no* committed door equal to it **or under** it | A4 (`CLAIMED-ABSENT`) |
| `{…{…}…}` — a brace inside a brace | refused: `CONFLATED` | A3 |
| two comma-bearing groups in one token | refused: `MULTIPLE-ENUMERATIONS` | (unpopulated: no row writes one) |

**Exclusion.** A token that sits inside a C7/C8 census phrase — `N paths / M operations under \`X\``,
`N \`X\` pages`, `` `X` pages (N) `` — is skipped, because there it is a **prefix**, not a path. Dropping that
exclusion is arm A5, and it is load-bearing rather than convenient: the resolved population grows from **49 to 57**
candidates (measured **45 → 53** on the bytes before the `/trainings/…` row was rewritten in, so the same +8 either
way) and two of the added tokens red as `NO-SUCH-DOOR` — `/api/v1/community` and `/api/v1/creator`, families holding
**eight** and **seven** committed doors respectively, neither with a bare collection door. Those rows are not wrong;
they are census referents, and C7 already recomputes their figures.

**Floors.** `MIN_ROUTE_CITATIONS=49`, `MIN_PARAMETER_CITATIONS=12`, `MIN_NEGATED_CITATIONS=1`,
`MIN_CENSUS_REFERENTS_SKIPPED=10`. All four are the counts the gate's own scan produces over the ledger it lands
with — read out of the case's own assertion messages by `.scratch/r83_measure3.py` (set a floor to 10⁹, let the
gate print its number), never hand-regexed from a terminal. The label in the red message names `§83` instead of a
commit hash on purpose: the corrected bytes land in this file's own commit, so the ref that holds them is whatever
commit introduced the case.

## Witness — 10 runs, 10 MATCHED, 0 mismatches

Plane `.scratch/r83_plane` (`git archive ad9b841` + my paths), runner `.scratch/r83_runs.py`, artifact
`.scratch/r83_arms.out`, raw log `.scratch/r83_witness3.log`, per-arm junit `.scratch/junit_r83_<arm>.xml`.
Every arm re-bases the three files from pristine plane bytes at the top of the arm; arms do not compound. An arm is
judged by the **case names** its own junit reports red and by a **fragment of the assertion message** (`failure`'s
`message` attribute only — never the traceback body, which echoes the source and would make every tag look present).

| run | mutation | reds | message the gate actually printed (excerpt) |
| --- | --- | --- | --- |
| CTRL | none (corrected ledger) | none | — (9 collected / 0 red) |
| RC2 | HEAD's uncorrected ledger + the new gate | C9 | `31 of the ledger's route citations resolve` + `CONFLATED` ×2 + `PARAMETER-NAME /api/v1/video/{id}/jobs` |
| A1 | doc: video enumeration re-spelled `{ident}` → `{id}` | C9 | `46 … resolve` + `PARAMETER-NAME /api/v1/video/{id}/analyse` (and `/file`, `/jobs`) |
| A2 | doc: `/api/v1/graph/rules` → `/api/v1/graph/edges` | C9 | `48 …` + `NO-SUCH-DOOR /api/v1/graph/edges … publishes nothing at or under it` |
| A3 | doc: brace-inside-brace reinstated (`{upload,{id},analyse}`) | C9 | `46 …` + `CONFLATED /api/v1/video/{upload,{id},analyse} … mixes a path parameter with the door literals` |
| A4 | doc: `No /api/v1/agents` → `No /api/v1/community` | C9 | `49 …` + `CLAIMED-ABSENT /api/v1/community … publishes 8 door(s) under it: ['/api/v1/community/follows/{member}', …]` |
| A5 | gate: the dual census stops being excluded | C9 | `57 …` + `NO-SUCH-DOOR /api/v1/community` and `NO-SUCH-DOOR /api/v1/creator` |
| A6 | doc: §27's citation loses its prefix (`/api/v1/scout/compare` → `/scout/compare`) | C9 | `the audit yields 48 resolvable route citations where §83 yields 49` / `assert 48 >= 49` |
| A7 | **contract**: `/api/v1/graph/nodes/{kind}/{slug}` → `{node_kind}` in `docs/api/openapi.json` | C9 | `47 …` + `PARAMETER-NAME` on **both** graph tokens |
| A8 | doc: cite `/api/v1/video/shared/{token}` — a committed door no row cited before | none (designed green) | — |

C1..C8 stayed green in all ten runs, including A5 (which moves two tokens between the populations of two cases: C7
keeps recomputing their `N paths / M operations` figures whether or not C9 also reads them as doors) and A7 (which
edits the *producer*, so the ledger is shown to follow the contract rather than quote it).

## Prediction-side defects, kept as findings

The predictions were written before the runs, in `.scratch/r83_predictions.md` (three rounds; rounds 2 and 3 amend
round 1 rather than replace it).

* **A hole caught while designing A4, fixed before any arm ran.** The first implementation resolved a *negated*
  citation as one exact door. Re-hanging `No /api/v1/agents` onto `No /api/v1/community` would then have **survived**
  — that family has no bare collection door while it holds eight. An absence claim about a family was being answered
  by a lookup of one path. A negated candidate now counts any door equal to it or under it, and A4 is the arm that
  proves the clause fires.
* **A `CONFLATED` refusal retires a token before its inner spelling is read.** I predicted the reverse control would
  name `{slug}`; it cannot, because the malformed token is refused at the shape check and never expanded. The
  correction to `{drill_slug}` came from reading the contract, not from a red message. This is a real limit of the
  grammar and it is written into the case's docstring rather than smoothed away.
* **The reverse control cannot name a prefix-less citation.** I predicted it would name the two `/progress/…` doors;
  a token without `/api/v1` is outside the population by design, so correcting them **removes an ambiguity** rather
  than **fixing a red**. Same reasoning decided §9–12's `/trainings/…` token.
* **Round 3's four floors were predicted before being measured** (49 / 12 / 1 / 10, 0 defects) and all four came out
  as written; A5's population (57) and A6's floor message (`yields 48 … where §83 yields 49`) were likewise predicted
  with the new numbers, which is the only reason the floor change can be told apart from a grammar change.

## Non-claims

* **ROADMAP.md's 14 `/api/v1/…` tokens are not gated.** Measured: they are per-step historical figures ("contract
  144/187 at the §36 landing"), `(N doors)` counts in a narrative, or `/api/v1/…` used as a **metavariable** inside
  grammar prose. Reading them as door claims would red rows that describe a past commit rather than the current tree.
* **Bare web-route tokens (`/coach`, `/training/[slug]`) are not gated.** A page and a door can share a spelling and
  only the prefix disambiguates; a page-family claim is C7's business, and §81's path gate already resolves the
  repository paths.
* **`MULTIPLE-ENUMERATIONS` has no arm.** No row in the ledger writes a token with two comma-bearing groups, so the
  clause cannot be made red by a realistic edit; it is a refusal, and the record says it is unpopulated instead of
  counting it as witnessed.
* **No whole-suite leg is claimed by this unit.** It adds one case to one file; the PostgreSQL engine on this
  machine is dead, and the freshest suite figure remains #78's SQLite-only `1430 passed / 1 / 0 / 2`.

## Reproduce

```bash
# the gate over the committed tree (git reader): 9 cases, 0 red
cd apps/api && ../../.venv/Scripts/python.exe -m pytest tests/test_spec_audit_currency.py -q -p no:cacheprovider

# the floors, read from the gate's own assertion messages over the working copy's ledger
../../.venv/Scripts/python.exe .scratch/r83_measure3.py

# the whole witness: control + reverse control (stage 1), then 8 arms (stage 2) → runs=10 matched=10
../../.venv/Scripts/python.exe .scratch/r83_runs.py 1
../../.venv/Scripts/python.exe .scratch/r83_runs.py 2
```

## §83's own record corrected — the landing script's byte check measured across two EOL planes

The commit landed as `c44b2b3` (4 paths, +340/−7, `docs/SPEC_COVERAGE_AUDIT.md` exactly 4/4), and the script then
**refused** on its last check: `HEAD:ROADMAP.md is not the bytes I wrote`. Measured, that refusal was the script's
defect, not the landing's:

* `git show HEAD:ROADMAP.md` is the **blob** plane: 632 lines, **0** CRLF.
* the worktree copy was at that moment 632 lines, **632** CRLF — because the script appended its row with
  `Path.write_text(...)`, and text mode on this host translates every `\n` to the platform line ending. The
  `clean` filter (`core.autocrlf=true`, no `.gitattributes` in the repo) then normalized it back on the way in, so
  the committed bytes are exactly what the script meant to write.

So the check compared an LF plane against a CRLF plane and called the difference a content difference. The fix is
the same one §82's record names: compare on one plane and say which.

```
HEAD blob vs worktree raw      → equal for the other three paths (all LF on disk), unequal for ROADMAP.md
HEAD blob vs worktree (CRLF→LF) → equal for all four
```

Two further notes, both measured after the fact rather than claimed before it:

* The refusal stopped the script **after** the commit, so its last two steps ran by hand: the gate through the git
  reader (`tests/test_spec_audit_currency.py`, 9 collected / 0 red, `.scratch/junit_r83_postcommit.xml`) and the
  worktree review. `git diff -- ROADMAP.md` after restoring the LF bytes is empty — the ` M` flag that appears is
  git's `LF will be replaced by CRLF` advisory on a stat-dirty file, not a content change.
* The script's `write_text` had also flipped the *whole shared* `ROADMAP.md` to CRLF on disk. Restoring
  `git show HEAD:ROADMAP.md` byte-for-byte puts the file back as the other lanes left it; that restore touches only
  a file whose content equals HEAD, which `git diff` confirms.
