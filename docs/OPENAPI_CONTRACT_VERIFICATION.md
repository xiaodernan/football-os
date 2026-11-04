# #79 — the committed OpenAPI contract, gated against the committed app (2026-10-03)

`ROADMAP.md:215` states, in the present tense: *"`docs/api/openapi.json` remains the contract the web tier codes
against."* Nothing in `apps/api/tests` read that file. The numbers in it were maintained by hand at each export, and
the exporter did not read the tree either.

## The defect, measured at `3651587`

| reading | paths | operations | component schemas |
| --- | --- | --- | --- |
| `git show 3651587:docs/api/openapi.json` (committed) | 149 | 193 | 63 |
| `app.openapi()` of the same commit, in-process | **160** | **205** | 63 |

The set difference is one-directional: **12 operations added, 0 removed**, and the schema-name sets are identical, so
the drift is invisible to a gate that only counts components. The contract this unit lands is
**160 paths / 205 operations / 63 schemas**, derived from the tree by the new exporter rather than typed.
The missing routes, by tier:

* `graph` ×3 — `/api/v1/graph/rules`, `/api/v1/graph/nodes/{kind}/{slug}`, `…/{slug}/neighborhood`
* `simulation/aggregates` ×3 — `…/rules`, `…/league/{competition_slug}`, `…/player/{player_slug}`
* `video` ×5 operations on 4 paths — `POST/DELETE …/{ident}/share`, `GET /api/v1/video/shared/{token}`,
  `POST …/{ident}/link-player`, `POST …/{ident}/link-match`
* `careers` ×1 — `GET /api/v1/careers/{ident}/ledger`

Six of those eleven paths are the two tiers `3651587` itself wired up (the mount finding recorded in
`docs/ERROR_SHAPE_WEB_VERIFICATION.md`): a router can ship, be tested, be mounted, and still never enter the artifact
that describes the surface, because no reader reconciles the two. Line-wise the regeneration is purely additive —
4 hunks, all inserts (583 lines), 0 lines removed — which is what makes the fix safe to land on a shared branch.

## Why it drifted: the exporter scraped a running server

`scripts/export_openapi.py` fetched `{base}/api/v1/openapi.json` over HTTP with `--base` defaulting to
`http://127.0.0.1:8731`. Port 8731 is a **shared** port on this machine, so the committed contract was a property of
whichever process happened to hold it. That has already cost the project once (a default run wrote 86 paths over a
126-path file, −4535 lines). The unit now:

* builds the spec in-process from `app.main.app.openapi()`, after `sys.path.insert(0, apps/api)`;
* **proves the imported `app` package lives inside this repository** (`is_relative_to`) and refuses otherwise, so an
  editable-install `.pth` elsewhere cannot answer for the tree;
* writes LF explicitly (`newline="\n"`), because the gate below compares bytes and a host newline policy must not be
  able to make a correct artifact look wrong;
* takes `--out PATH` so the derivation can be run without touching the committed file.

`--base` is gone rather than ignored: a flag that is accepted and unused is a lie about capability.

## The gate

`apps/api/tests/test_openapi_contract_currency.py`, 4 cases, one clause per shape of drift so the first red names the
kind rather than the presence:

| short | case | catches what the one before it cannot |
| --- | --- | --- |
| P1 | `test_the_contract_lists_every_route_the_app_answers_and_no_route_it_does_not` | a route shipped and never exported, or a listed route the app no longer answers |
| P2 | `test_the_contract_counts_each_verb_on_each_route_the_way_the_app_answers_it` | a second verb on an already-listed path (the `POST`/`DELETE` share pair above) |
| P3 | `test_the_contract_declares_the_same_component_schemas_the_app_does` | a renamed or dropped schema |
| P4 | `test_the_exporter_derives_the_contract_from_the_tree_and_reproduces_the_committed_bytes` | the exporter drifting from the artifact — it runs the shipped script and demands byte equality, plus LF |

`check.sh:20` (`cd apps/api && python -m pytest`) and CI's two pytest steps invoke the file, so it is gated without a
runner edit. Landing state: **4 passed / 0 failed / 0 errors**, measured on a `git archive` plane of the commit being
landed on, with the regenerated contract overlaid.

## Witness

`7` runs (control + 6 arms) on `plane_w79_*`, `.scratch/r79_arms.py`, verdicts taken from the case names that went red
in each run's own junit — never a count, never an exit code — against predictions written into the launcher before the
first run: `SUMMARY runs=7 matched=7 not-matched=0`.

| arm | mutation | predicted red | observed |
| --- | --- | --- | --- |
| control | regenerate from the tree, run the gate | none (4 passed) | MATCHED |
| A1 | land the stale committed contract (149 paths) | P1 P2 P4 | MATCHED — P3 stays green, which is the proof that a path-counting gate would have missed nothing here but a schema-only gate would |
| A2 | delete one verb from a multi-verb path in the contract | P2 P4 | MATCHED — P1 green: the path key survives |
| A3 | rename one component schema in the contract | P3 P4 | MATCHED |
| A4 | restore the HTTP-scraping exporter | P4 | MATCHED — the claim asserted is content equality with the tree, which a scrape cannot guarantee whether or not a server answers |
| A5 | delete the exporter's `newline="\n"` | P4 | MATCHED on this host; the arm is host-policy-dependent by nature, which is why the *artifact* pins LF rather than the test assuming it |
| A6 | remove `app.include_router(graph.router, prefix=api)` from the app | P1 P2 P4 | MATCHED — the app-side half: the contract listing more than the app answers |

A1–A3 and A5 attack the artifact, A6 attacks the app, A4 attacks the mechanism. Every one of them is load-bearing on
its own clause; the three designed-greens (P3 in A1/A2, P1 in A2, P1-P3 in A4/A5) are what show the cases are not one
assertion four times.

## What this unit does not claim

* It does not claim the working copy is green. `docs/api/openapi.json` in the shared working tree carries another
  lane's uncommitted edits; the contract landed here was **derived from HEAD's app and staged index-only**, and that
  lane's file is untouched. Running the suite in a copy whose contract predates its own routes will go red at P1/P2/P4
  — that is the gate, and `python scripts/export_openapi.py` is now a deterministic way out.
* It does not claim a whole-suite leg for the +4 cases. The leg figure published in `.scratch/r78_leg_summary.txt` is
  measured over the commit *before* this file exists, so the population claim here is `+4 cases`, not a total.
* It does not retype the older `docs/M*_VERIFICATION.md` contract counts (149/193, 150/194, 144/187, 129/164 …). Those
  are readings of the file as of their own commits; they are historical, not current-state claims, and only
  `ROADMAP.md:215`'s present-tense sentence is load-bearing.
* `spec_from_tree()`'s `is_relative_to` refusal has **no arm**, because `sys.path.insert(0, API)` makes our tree win
  first and a foreign `app` cannot be reached from a test on this plane. It is a belt, stated as such.

## Follow-up (2026-10-23): the gate read the checkout's newline policy, not the artifact

The byte case compared `CONTRACT.read_bytes()` with the exporter's output directly. That is right for the
artifact and wrong for the checkout: this repository has no `.gitattributes`, and with `core.autocrlf=true`
(the setting on the Windows host this project is developed on) a fresh checkout turns the committed LF blob
into CRLF on disk.

**Measured.** A clean `git worktree` at `394cd10` (the commit that landed the trace door): the contract on disk
was **484939 bytes / 17305 CRLF pairs**, the exporter wrote **467634 bytes / LF**, and the case failed at
`assert b'{…' == b'{…'` with *equal content* — the same shape the 2026-10-06 PLAN row recorded and predicted
would recur. Regenerating fixes that working copy; it does nothing for the next clone, which checks out CRLF
again.

**Fix.** The case normalises the checkout side (`replace(b"\r\n", b"\n")`) before comparing; the separate
assertion that `export_openapi.py` itself wrote no CRLF is unchanged, so the artifact's own newline is still
pinned. The message now says the line endings were normalised and prints both lengths.

**Witness, in order.**

* The old case on the untouched CRLF worktree: 1 failed (`the committed contract is 484939 bytes, the tree
  serialises to 467634`), which is the defect reproduced.
* The fixed case on the same worktree, contract still 484939 bytes / 17305 CRLF: **4 passed**.
* The five documentation gates on that worktree (`test_openapi_contract_currency`, `test_spec_audit_currency`,
  `test_answer_census`, `test_authorization_census`, `test_trace_store`): **38 passed, rc=0**.
* A one-byte content arm on the same CRLF plane — `"openapi": "3.1.0"` → `"3.1.1"`, same byte count — still
  reds the exporter case, so normalisation does not blunt the content comparison.
* The shared working tree: same five gates **38 passed, rc=0**; `ruff check` clean; the tracked contract and
  app bytes are unchanged.

**Not claimed.** No `.gitattributes` was added; the gate tolerates a translated checkout rather than changing
what git writes. This file is the only committed text artifact in `apps/api/tests` compared byte-for-byte
(`grep read_bytes` over the suite finds only video fixtures besides it), so no other gate was changed.

## Follow-up (2026-11-04): the gate read the checkout, not the commit

The 2026-10-23 follow-up decided *which newline* the artifact arrived with and left the larger question open:
**which tree**. `committed()` parsed `docs/api/openapi.json` from disk and `answers()` booted the app from disk,
so both inputs came from the working copy. For the app that is unavoidable; for the contract it is the wrong
tree, because the contract is a committed artifact — every §80/§81 gate and every "contract: N paths / M
operations" line in `docs/*_VERIFICATION.md` quotes the blob, and a checkout whose contract was regenerated while
its routes stayed uncommitted is a mixed tree the gate was certifying as current.

**The instance is live, not synthetic.** `apps/api/app/api/v1/careers.py` and `transfers.py` on the shared
working tree answer two routes no commit holds — `/api/v1/careers/{ident}/cup` and
`/api/v1/transfers/{ident}/renew` — and the disk contract had been regenerated to match: **220 paths / 282
operations** against the commit's **218 / 280**, 497,932 bytes against the blob's 492,817. HEAD's gate answers
**4 passed** on that tree: it reads the disk contract, boots the disk app, and the two agree with each other
about a surface no commit has ever published. The same four cases, with the artifact side sourced from
`git show HEAD:docs/api/openapi.json`, answer **4 failed**, each on its own clause — 2 routes the app answers and
the contract does not list, the same 2 as `(path, verb)` pairs, `CupIn` and `RenewIn` missing from the committed
`components.schemas`, and the exporter's 497,932 bytes against the blob's 492,817.

**Fix.** `committed()` now parses `committed_bytes()`: the HEAD blob when the checkout carries a `.git`, a
normalised disk read when it does not — the same `_git` + `@cache` sourcing `test_spec_audit_currency.py` and
`test_locale_claims.py` use. The app side stays live by necessity, which is what makes the case a *pre-commit*
alarm: it reds while the drift is still cheap to cure (run the exporter in the same commit as the route) instead
of after the landing, which is when `3651587` found it.

**Three arms on a clean worktree** (`.scratch/wt-contract`, detached at `e8fa569`), HEAD's bytes written beside
the candidate as `tests/_zz_item39_old.py` so one tree runs both sources; every prediction written before the
run, and the plane left with the one modified path the landing carries.

| arm | the checkout says | the commit says | HEAD's gate | this file |
| --- | --- | --- | --- | --- |
| baseline | clean | self-consistent | `4 passed` | `4 passed` |
| W (the shared tree, above) | cup + renew routes, contract regenerated to 220 / 282 | 218 / 280, no such routes | `4 passed` | `4 failed`: 2 routes, 2 pairs, `CupIn`/`RenewIn`, 492,817 vs 497,932 |
| A1 | the contract alone is dirty — a `/api/v1/zz-item39-probe` path the app does not answer | unchanged | `3 failed / 1 passed`: 1 listed but not answered, the `('…probe', 'get')` pair, `492,979 bytes` against the tree's 492,817 | `4 passed` |
| A2 | a route planted in `meta.py` **and** the contract regenerated beside it (493,608 bytes) | unchanged | `4 passed` | `3 failed / 1 passed`: 1 route the app answers, the probe pair, `492,817` against `493,608` |

A1 and A2 are the two directions of the same mixed tree, and each is red for exactly one of them: A1 is an
artifact edited without an app, which the old gate punished for the right reason in the wrong tree; A2 is an app
edited and the artifact regenerated on disk, which the old gate passed outright — that is the `3651587` drift,
shipped green. The one case that stays green in A2 is the schema census, and it stays green for the right
reason: the probe takes no request body, so no component is added on either side.

**Not claimed.** The app side cannot be sourced from the commit — `app.openapi()` needs this process's imported
app — so a run on a lane-divergent checkout reds for the *checkout's* routes; that is the pre-commit alarm doing
its job, not a statement that HEAD is inconsistent, and the record says so rather than hiding it. The `.git`-less
fallback grades disk again, by design, as the newline follow-up left it. And nothing here makes the exporter
independent of the app: it derives the contract from the tree it runs in, which is the point of the byte case and
the reason it cannot be pinned to a blob of the app's own output.

**Landing note.** `f10e232` carried the reader — one path, the test file — and this file's paragraph above is the
record after it, written on the same plane the arms ran on. The shared tree's two uncommitted routes are still
uncommitted; the gate reds for them on that tree and will green the moment the routes and the regenerated
contract land together.

## Reproduce

    git archive <landing-ref> | tar -x -C /tmp/plane79
    cp scripts/export_openapi.py apps/api/tests/test_openapi_contract_currency.py # onto the plane
    python /tmp/plane79/scripts/export_openapi.py --out /tmp/plane79/docs/api/openapi.json
    (cd /tmp/plane79/apps/api && python -m pytest -q tests/test_openapi_contract_currency.py)
    python .scratch/r79_arms.py   # the 7-run witness
