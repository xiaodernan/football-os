# M11 §30 — joint retrieval: the graph half of an answer (verification record)

Spec §30 asks for "RAG + Knowledge Graph joint retrieval". The audit had retired the older "no table,
no route, no service" sentence for the projection and its doors and left exactly one clause open, measured two ways
at 2026-10-04: `git grep -li knowledge_graph -- apps/api/app/services/knowledge` answered nothing at all, and
**0 of the 18** `queries` in `apps/api/evals/golden_rag.json` naming a committed team or competition. This unit lands
the **anchoring half** of that clause and retires both measurements by re-taking them — the scan the first one cites
now answers `git grep -li knowledge_graph -- apps/api/app/services/knowledge` → 1 file, `graph_join.py`.

## What shipped

| path | role |
| --- | --- |
| `apps/api/app/services/knowledge/graph_join.py` | the seam: `anchors(db, question)` returns the committed nodes whose **full label** the sentence names, each with the relations the projection reads for it; `reason_lines()` renders them |
| `apps/api/app/services/knowledge/answer.py` | one `if usable:` block appends those lines to `reasons` — the graph is consulted **only on the branch the retriever already cleared** |
| `apps/api/evals/golden_joint.json` | 8 joint cases (each names a stored node), 3 near misses (a football word, half a label, no world vocabulary), 1 refusal control |
| `apps/api/tests/test_knowledge_joint.py` | 9 cases over those three populations |

The channel is `reasons`, not a new response key. `docs/api/openapi.json` is held uncommitted by
another lane (+116/−0 at this writing) and #79's gate reads that file against the in-process app, so a
shape change here would be a contract regeneration this working copy cannot honestly produce. `reasons`
is already published and already rendered — `apps/web/app/knowledge/KnowledgeAsk.tsx` prints it under
"Why this answer (or refusal)" — so the joint facts reach a reader with no new door and no new key.

## Measurements (all on a `git archive HEAD` plane, `D:\r84_plane`, no `.git`)

* Baseline `tests/test_knowledge_joint.py`: **9 collected / 0 red**.
* Regression over `tests/test_knowledge_rag.py`, `tests/test_knowledge_graph_census.py`,
  `tests/test_world.py`: **90 collected / 0 red** — the RAG floors' own derivation gate is untouched by
  this change and still passes.
* Probe over the 8 joint cases through `answer.ask(persist=False)`: **answered = 8/8**,
  **answered with a graph line = 8/8**. The first case's anchor (team `vireford-miners`) reads
  **258 stored relations** and reports **4 fact lines**.
* Census re-taken on the plane: `git grep -li knowledge_graph -- apps/api/app` → 6 files, one more than the same
  scan answered at `2f3007a`, and `git grep -li knowledge_graph -- apps/api/app/services/knowledge` → 1 file, the
  new `graph_join.py`, where `2f3007a` answered none.
* `git grep -li golden_joint -- apps/api/app` → 0 files: no door, service or model under the app tier names the joint
  golden set, so `apps/api/tests/test_knowledge_joint.py` is its only reader. Stated as a measurement rather than a
  complaint — an eval that gates a seam does not need a door to earn its keep, and §30's recall hop is the half that
  would put one there.
* No whole-suite leg is claimed here, and no PostgreSQL leg: the engine on this machine is still dead
  (`docker version` fails on the `dockerDesktopLinuxEngine` pipe), so every figure above is SQLite.

## Killing arms (predicted before the run, judged by junit case names)

| arm | mutation | predicted red | measured | verdict |
| --- | --- | --- | --- | --- |
| A1 | drop the full-label coverage clause in `graph_join.anchors` | `test_a_football_word_that_is_not_a_full_label_anchors_nothing` | exactly that one, 9 collected | MATCHED |
| A2 | `answer.ask()` consults the graph on the refusal branch too (`if usable:` → `if True:`) | `test_a_refusal_that_names_a_stored_node_still_refuses` | exactly that one | MATCHED |
| A3 | strip `[{DEMO_MARK}]` from the reason line | `test_anchor_ceiling_and_fact_shape` | exactly that one | MATCHED |

A2 is the arm that matters for the floors. Every ordinary out-of-scope question anchors nothing, so
wiring the hop into the refusal branch would look harmless; the refusal control question names a
stored club **and** misses the corpus, so it is the only input that can tell "the hop was not asked"
apart from "the hop was asked and agreed". With A2 applied the answer still refuses but carries a
`graph:` line, and the case names that line.

## Design decisions, and what they cost

* **Whole-label coverage, not term overlap.** `search_world` scores any shared word, so "when should
  my team press" would anchor whatever club mentions pressing in its summary. Anchoring therefore
  requires every term of the node's label to appear in the question; "how does Vireford press high"
  names a mention, not an entity, and anchors nothing. The cost is real: a question that says
  "the Miners" or "Vireford" alone gets no graph line. Recorded here rather than hidden because the
  near-miss population is what pins that cost.
* **Anchors are nodes the projection addresses, not search hits.** Each candidate must
  `project.resolve()` to a stored row, so the graph half cannot report an entity the walk has no edges
  for, and `project.node()` supplies the label and canonical path — one label builder, no copy.
* **Ceilings from the seam.** `MAX_ANCHORS = 3`, `MAX_FACTS_PER_ANCHOR = 4`,
  `MAX_FIGURES_PER_FACT = 3`. The projection's own `MAX_DEPTH / MAX_EDGES / MAX_NODES` govern the
  walk; these govern how much of it a single answer prints.
* **Every line discloses the world as synthetic.** `reason()` ends in `[synthetic demo world]`, the
  rule §80 already puts on every world row, because a graph fact is a demo number just as a stat is.

## Still open in §30

The hop that **widens recall** — a graph edge bringing a passage into the context that BM25 and cosine
missed — is not built, but the blocker is no longer the retriever's floors. It is structural: the corpus
and the world share almost no name vocabulary. Measured at `ba947e0` by the new gate case
`TestHopSubstrate::test_no_committed_passage_carries_a_stored_entity_label`: **330** player/team/competition
labels, **138** chunk bodies (heading stripped), **0** whole-label containment hits, and only **2** labels
sharing even one word with any body ("Braehaven Elite League", "Ravhull FC" — both generic terms like
"league"/"fc"). A draft hop (kept in `.scratch/r86_graph_recall_draft.py`, never shipped) produced 4 pulls
over the 8 joint questions; every one was attributed to the neighbour `match "Matchday 1 game 1 · not played"`,
whose label is composed of generic words. With deterministic sorted neighbour ordering, the population is
**0 of 8**. The feature was reverted rather than landed with an over-claiming disclosure.

Building the hop requires either a corpus ingestion pipeline that tags passages with entity IDs (a new column
on `KnowledgeChunk` populated by a named-entity linker), or a separate index mapping entity labels to chunk IDs.
Until such a substrate exists, the anchoring half (#84) is the full extent of §30's joint clause: the graph adds
facts to an answer the retriever already cleared, and adds nothing to a refusal. See
[SPEC_30_RECALL_HOP_SUBSTRATE_VERIFICATION.md](SPEC_30_RECALL_HOP_SUBSTRATE_VERIFICATION.md) for the measured
numbers and the six-run witness.

## Reproduce

```
.venv/Scripts/python.exe .scratch/r84_witness.py     # plane: baseline + regression + probe + census + 3 arms
cd apps/api && python -m pytest tests/test_knowledge_joint.py tests/test_knowledge_rag.py -q
```
