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

## Reproduce

    git archive <landing-ref> | tar -x -C /tmp/plane79
    cp scripts/export_openapi.py apps/api/tests/test_openapi_contract_currency.py # onto the plane
    python /tmp/plane79/scripts/export_openapi.py --out /tmp/plane79/docs/api/openapi.json
    (cd /tmp/plane79/apps/api && python -m pytest -q tests/test_openapi_contract_currency.py)
    python .scratch/r79_arms.py   # the 7-run witness
