# §60 Authorization census — every 403 this API answers comes from a code the table knows

Spec §60 lists `Authorization` and `RBAC` among the platform's must-haves; §51 settled that one refusal code means
one HTTP status. Both were being *nearly* obeyed, in a way nothing in the suite could see. This document records
what was measured, on which plane, and what is still open.

## 1. The pre-state, measured at `f928640`

* `services/club/answers.py` assembles `ANSWERS` from the tier modules listed in `TIERS`. At `f928640` that table
  held exactly **one** code answering 403 — §39's `insufficient_role`. The case in `tests/test_club_answers.py`
  asserted that it was the only one, and the assertion was true: it read the assembled table.
* Meanwhile `app/` raised 403 from **five sites outside any tier**: `api/v1/auth.py:86`, `api/v1/auth.py:110` and
  `core/security.py:104` with `account_inactive`, and `core/security.py:112` and `api/v1/knowledge.py:212` with a
  bare `forbidden`. Two codes, neither registered, five doors, zero test cases between them.

So the ledger said one 403 and the territory said three. The general shape of the defect: **a guard that enumerates
the ledger cannot catch a router that never writes to it.** The census therefore reads its population off the
source tree, not off a declaration.

## 2. What landed

`core/security.py` now owns the platform's 403 vocabulary:

| name | answer | raised by |
| --- | --- | --- |
| `INSUFFICIENT_ROLE` = `insufficient_role` | 403, with `held`, `required`, `roles` | `role_refusal()` — a standing below the door |
| `ACCOUNT_INACTIVE` = `account_inactive` | 403 | `inactive_refusal()` — the account is switched off |
| `FORBIDDEN_CODES` | — | the frozenset of the two, registered in the assembly |

§49 asks for one name that publishes the code, guards the door that uses it and builds the answer, so no raise site
can spell a third. `require_roles()` — the helper that used to mint `forbidden` — was deleted rather than repaired:
no router imported it (measured repo-wide, two hits, both its own definition and its `__all__` entry). A second way
to refuse a standing, used by nobody, is how the first way spread.

`services/club/answers.py` adds `security` to `TIERS`. A services-only ledger cannot see the routers, which is
precisely how five sites went unnoticed for six milestones.

`api/v1/auth.py`: login and refresh raise through `inactive_refusal`.

## 3. The door that asked for a standing nobody can hold

`/knowledge/ingest` gated on `("admin", "staff", "operator")`. `staff` and `operator` name nothing in either
vocabulary the platform has: `core/security.ROLES` holds seven account standings, `services/club/access.py` holds
six *tenant* standings, and `staff` is real only as a §39 announcement **audience** — a predicate over a roster,
not a standing an account can hold. They were genuinely unreachable rather than merely unlisted: `RegisterIn.role`
is a `Literal` of six values, so the door that creates accounts cannot create a `staff` one either.

A door naming an unreachable standing does not leak. It silently means *only the reachable half of the list is a
policy*, and the day somebody adds a `staff` account role the door's meaning changes under the person who did not
edit it. So the list is checked by `standing_check()` at import time:

```python
INGEST_STANDING: Final = standing_check(("admin",))
```

The mistake becomes a crash in the developer's face rather than a sentence in front of a caller.

## 4. Numbers, with their plane

| measurement | plane | result |
| --- | --- | --- |
| `pytest tests/test_authorization_census.py tests/test_club_answers.py` | detached worktree of `0da4c85`, per-run SQLite | **98 tests / 0 failures / 0 errors / 0 skipped**, 90.324s, rc=0 |
| `pytest` over the §60 files plus `test_knowledge_rag.py` | shared working copy, per-run SQLite, 04:22 | **123 tests / 0 failures / 0 errors / 0 skipped**, 386.887s, rc=0 |
| `mypy app` | shared working copy | Success: no issues found in 109 source files, rc=0 |
| `ruff check app tests` | shared working copy | All checks passed!, rc=0 |
| `ANSWERS` rows | `0da4c85` tree, in-process import | 126 rows; the codes answering 403 are exactly `account_inactive`, `insufficient_role` |
| `security.FORBIDDEN_CODES` vs the table's 403 set | same import | equal |
| inline `"code": "…"}` literals | shared working copy at 05:19 | 79 literals over 18 modules; 53 distinct codes; 52 outside the table — see §7 |
| whole-suite legs over `0da4c85` | `.scratch/wt_c60@0da4c85`, both engines, sequential | **met on both: 1362 tests / 0 failures / 0 errors / 1 skipped / rc=0 on each engine.** SQLite leg junit 2380.760 s (wall 2400.79 s), PostgreSQL leg junit 3039.332 s (wall 3047.96 s). Red case names per leg: none |

Both legs came in exactly on the prediction the runner printed before it started: 1362 / 0 / 0 / 1 / rc=0
per engine, where 1362 is what `--collect-only -q` counted over 37 modules on that plane and 1350 + 11 census
cases + 1 extra `club_answers` case is the same number from the other direction. Nothing was adjusted to meet
it. The single skip is the pre-existing
`tests/test_scout_search.py::TestPublishedArithmetic::test_each_sorting_orders_the_survivors_by_its_published_key[need_fit]`
("need_fit is ranked against a career and tested with one"), and it is the same skip on both engines, so the
two legs agree case name by case name on what ran, what was skipped, and what failed.

The two subset readings are different populations, so both are listed rather than reconciled: the 123-test reading
includes `test_knowledge_rag.py`, and was taken before the concurrent edit described below.

## 5. The census caught a real one before it was committed

While this landing's mutation probe was mid-leg, a second agent's `/auth/account` route was written into
`app/api/v1/auth.py`. It raises `status.HTTP_403_FORBIDDEN` with `{"code": "invalid_password"}` — a third 403
holder, and a code no answer table registers. The case that bans a third holder went red on it, unprompted:
nothing had to be taught about the new file and no allow-list had to be widened, because the population is read off
the tree. A router that never writes to the ledger is in the census the moment it is saved.

That route is not part of `0da4c85` (see §7), so the commit ships green, and the named gap is open for whoever
lands it: register the code with its own builder in `core/security.py`, or raise through a builder that already
exists. It is also a second question for §51 — the platform elsewhere answers a wrong password with 401
`invalid_credentials`, and this door answers it with 403.

## 6. Mutation probe

Result on the clean plane, `.scratch/probe_c68b.py`, five arms, both controls, per-run SQLite inside the worktree:

| | value |
| --- | --- |
| control before | 98 tests / 0 failures / 0 errors / 0 skipped, rc=0, 90.324s |
| control after | 98 / 0 / 0 / 0, rc=0, 58.426s |
| survivors (arms that went green) | **none** |
| `tree_drift` after all five restores | `{}` — every mutated file hashed back to its snapshot |
| `restore_ok` / exit code | True / `PROBE_RC=0` |

| arm | mechanism destroyed | reds | predicted | outcome |
| --- | --- | --- | --- | --- |
| B1 | `standing_check` never raises (`if unknown:` → `if False:`) | 1 | 1 | matched exactly |
| B2 | `/knowledge/ingest` mints `{"code": "forbidden"}` with a raw status again | 4 | 4 | matched exactly |
| B3 | `admin` joins the registrable `Literal` | 1 | 1 | matched exactly |
| B4 | a third 403 code in `FORBIDDEN_CODES` with no builder | 2 | 4 | caught, 2 cases missed — see below |
| B5 | a tier spends 403 with a code outside the vocabulary | 4 | 3 | caught, 1 case I forgot to list |

B4's two missed cases are the most instructive number on this page. They compare the table's 403 set with
`security.FORBIDDEN_CODES` — and B4 *mutates that same constant*, and the table is assembled from it, so the two
sides move together and the equality cannot fail. The prediction was wrong about what those clauses guard. They are
not tautologies: B5 diverges a **tier** from the vocabulary, and both of them went red there. So the property
"a code is registered with nobody to build it and nobody to reach it" is guarded by the two clauses that did fire —
the same-scan floor (2 status literals against 3 registered codes) and the parametrised reachability case, which
collected a **99th test** for the new code and then failed it, because the parameter list is derived from the
constant rather than written twice. B5's extra red was
`test_club_answers.py::test_no_tier_answers_403_with_a_code_outside_the_platform_vocabulary`, a clause this landing
wrote and the prediction forgot: the same property is guarded from two files, one per plane.

### The three cases the first probe left unkilled, and the arms that closed them

Enumerated from the control XML rather than asserted: of the census's 11 cases, 8 appeared in at least one arm's
red list. Three did not, so their witnesses were unproven — not broken, just never knocked on. `0da4c85` is
therefore not the end of the measurement: `.scratch/probe_c68c.py` ran three more arms on the same worktree plane
(`DRIFT {}`, control 98 tests / 0 failures / 0 errors / rc=0 at 48.960s, same again after), and each killed exactly
what it was written to kill:

| arm | mechanism destroyed | reds | predicted |
| --- | --- | --- | --- |
| C1 | `current_user`'s inactive guard (`if user is None or not user.is_active:` → `if False:`) | 1 | 1 |
| C2 | **pair**: guard disabled *and* `INGEST_STANDING = standing_check(("admin", "staff"))` | 2 | 2 |
| C3 | `if user.role not in INGEST_STANDING:` → `if True:` — the door refuses even an admin | 1 | 1 |

Across both probes: **8 arms, 0 survivors, and 11 of 11 census cases appear in some arm's red list** (computed as
the union of the arms' `actual` arrays against the case names collected from the control XML, not by hand).

C2 is the one worth reading twice. A single-file arm cannot prove that case: with `standing_check` live, naming
`staff` crashes the module at import, the test file never collects, and the arm reports *zero reds* — which looks
identical to "the guard held" and means only "nothing ran". The mutation had to be disabled-first-and-then-invented,
so the case is what fails rather than the import.


## 7. Open items, kept as items

* **The 403 the census found.** `api/v1/auth.py`'s `invalid_password` — see §5. Unlanded as of `0da4c85`.
* **52 codes outside the table.** The same scan that polices 403 reports 79 inline `{"code": …}` literals across 18
  modules, 53 distinct codes, of which 52 are not in `ANSWERS` — `invalid_credentials`, `token_expired`,
  `unauthenticated`, `rate_limited`, `not_found`, `ai_budget_exhausted` and the per-tier validation sentences. §51
  says one code one status assembled from one table; the M1–M7 routers predate that rule and have not been
  retro-fitted. This is the largest remaining §51/§60 debt in the API and it is recorded rather than rounded away.
* **Erasure answered as "switched off".** `current_user` and `/auth/refresh` test `user is None or not
  user.is_active` and raise `account_inactive` for both. A deleted account and a disabled one get the same sentence.
  The platform's own §61 answer for a deleted account is that it is not there; this needs a decision, not a patch.
* **`docs/M2_VERIFICATION.md` and `docs/M6_VERIFICATION.md`** carried published response samples showing the old
  `forbidden` answer; both now annotate what the door answers instead.

## 8. How `auth.py` was committed while another run owned part of it

`0da4c85` includes `api/v1/auth.py`, and the working copy of that file contains a route this landing does not ship.
A normal `git add` would have committed the other run's in-flight work. So the file went into the index by itself:
`git show f928640:…auth.py` → three byte-level replacements (the import line, and both `account_inactive` raise
sites, the latter asserted to match exactly twice) → `git hash-object -w` → `git update-index --cacheinfo`. The
resulting commit carries the HEAD file plus this landing's hunks and nothing else; the working copy keeps the other
run's 47 lines untouched. The check that makes this safe is a diff of the staged blob against the working file: one
line removed (their import rewrite) and 47 added (their route), no more.
