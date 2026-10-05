# M11 §30 — joint retrieval: the graph half of an answer (verification record)

Spec §30 asks for "RAG + Knowledge Graph joint retrieval". The audit had retired the older "no table,
no route, no service" sentence for the projection and its doors and left exactly one clause open,
measured two ways: `git grep -li knowledge_graph -- apps/api/app/services/knowledge` → **0 files**
(re-read 2026-10-04), and **0 of the 18** `queries` in `apps/api/evals/golden_rag.json` naming a
committed team or competition. This unit lands the **anchoring half** of that clause and retires both
measurements by re-taking them.

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
* Census re-taken on the plane, `*.py` under `apps/api/app` naming `knowledge_graph`: **6** where HEAD
  measures **5**; under `app/services/knowledge`: **1** (`graph_join.py`) where HEAD measures **0**.
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
missed — is not built, deliberately: it is the half that has to move `MIN_DISCRIMINATIVE_MATCHES = 2`
or `MIN_DISCRIMINATIVE_COVERAGE = 0.40`, and those floors are derived from `golden_rag.json` by
`test_the_answerability_floors_sit_inside_the_measured_gap`. Widening them means re-measuring that
file, which is §33's composite task and §64's benchmark work; §30's row stays `partial` for that
reason, not because the anchoring half is missing.

## Reproduce

```
.venv/Scripts/python.exe .scratch/r84_witness.py     # plane: baseline + regression + probe + census + 3 arms
cd apps/api && python -m pytest tests/test_knowledge_joint.py tests/test_knowledge_rag.py -q
```
