# §86 recall-hop substrate verification — measured, not assumed

**HEAD `ba947e0`** ("§85: every ledger's file counts get a reader, and the two stale zeros get retired").
Witness plane `D:\r86_witness_plane`, built by `.scratch/r86_witness.py` from `git archive HEAD`.
Six-run witness **6/6 MATCHED**, judged by junit case names AND the failure message attribute.

## What this unit proves (and what it does not)

Spec §30 asks for "RAG + Knowledge Graph joint retrieval" — one answer that cites both passages and graph
edges. The anchoring half landed in #84 (`graph_join.anchors()`): when a question names a stored node, the
response carries a `graph:` reason line with the node's relations and figures. The *recall* half — an edge
pulling a passage into the context that BM25/cosine alone missed — was deliberately left unbuilt at #84,
with the claim "it would have to move `MIN_DISCRIMINATIVE_MATCHES` / `MIN_DISCRIMINATIVE_COVERAGE`, floors
derived from `golden_rag.json`". That claim is now falsified by measurement: the hop has no substrate to pull
on, because the corpus and the world share almost no name vocabulary.

### Measured numbers (at `ba947e0`, read out of the gate's own assertion messages)

| population | count | source |
| --- | --- | --- |
| player/team/competition labels in the synced world | **330** | `TestHopSubstrate::test_no_committed_passage_carries_a_stored_entity_label` floor |
| knowledge chunk bodies (heading stripped) | **138** | same case, second floor |
| whole-label containment hits | **0** | `terms <= in_body` predicate over all 330×138 pairs |
| labels sharing ≥1 word with any body | **2** | `"Braehaven Elite League"`, `"Ravhull FC"` — both share only generic words like "league"/"fc" |

The two populations are near-disjoint vocabularies: 328 of 330 entity labels share zero content words with any
passage body, and the remaining two share only boilerplate football terms that appear in hundreds of chunks. A
hop that expanded a question with neighbour labels from `project.edges_of` therefore finds nothing to match on.

### The draft hop's actual pulls (kept in `.scratch/r86_graph_recall_draft.py`, never shipped)

Over the 8 golden joint questions, the draft produced **4 pulls**; every one was attributed to the neighbour
`match "Matchday 1 game 1 · not played"`, whose label is composed of the generic words "match"/"game". With
deterministic sorted neighbour ordering (the fix applied in the draft), the population is **0 of 8**. The
feature was reverted rather than landed with an over-claiming disclosure.

## The new gate case

`apps/api/tests/test_knowledge_joint.py::TestHopSubstrate::test_no_committed_passage_carries_a_stored_entity_label`

Scans the committed corpus and the synced world, asserts three things:

1. **Absence**: no chunk body carries a stored entity label (whole-label containment).
2. **Non-vacuity floors**: at least 330 labels and 138 chunks were actually compared (read from the scan's own
   failure message when the floor is set above the count).
3. **Belt**: the two populations are not wholly disjoint — at least one label shares a word with a body (measured
   2). Without this belt, an absence over two empty sets would be trivially true.

The case retires itself loudly if a future corpus document ever names an entity: the assertion prints the exact
chunk ID and label, so the builder knows which rows give the hop substrate.

## Witness arms (6 runs, all MATCHED)

| run | mutation | predicted red | predicted message substring | result |
| --- | --- | --- | --- | --- |
| BASE | none | 10 collected, 0 red | — | MATCHED |
| REV | HEAD's pristine test file, `-k TestHopSubstrate` | 0 collected | — | MATCHED |
| A1 | `terms <= in_body` → `bool(terms & in_body)` (any-word predicate) | `test_no_committed_passage_carries_a_stored_entity_label` | `now carry a stored entity label` | MATCHED (42 false hits under any-word) |
| A2 | `SUBSTRATE_KINDS` → `("team",)` | same | `floor 330` | MATCHED (20 team labels < 330) |
| A3 | chunk scan given `.limit(1)` | same | `passage scan read 1 chunk(s)` | MATCHED |
| A4 | delete the `elif any(terms & in_body …)` branch | same | `do not overlap at all` | MATCHED |

A1 is the arm that matters: it shows the zero is carried by the whole-label predicate and not by an empty
comparison. Under the any-word predicate, **42** passages would falsely "carry" a label — a useful number for
future builders who might be tempted to widen the predicate. A2/A3 aim at the two non-vacuity floors, A4 at the
belt that pins the populations are not merely disjoint.

## What remains open in §30

Nothing blocks the recall hop on the retriever's floors. The blocker is structural: the corpus documents do not
name the entities the projection stores, so there is no shared vocabulary for an edge to pull on. Building the
hop requires either:

- A corpus ingestion pipeline that tags passages with entity IDs (a new column on `KnowledgeChunk` populated by
  a named-entity linker over the passage text), or
- A separate index that maps entity labels to chunk IDs, maintained alongside the world sync.

Until such a substrate exists, the anchoring half (#84) is the full extent of §30's joint clause: the graph adds
facts to an answer the retriever already cleared, and adds nothing to a refusal.

## Ledger updates

- `docs/M11_JOINT_RETRIEVAL_VERIFICATION.md`: "Still open in §30" section rewritten to reflect the measured
  substrate absence, not the floor claim.
- `docs/SPEC_COVERAGE_AUDIT.md` §30 row: status changed from "partial — doors and the anchoring half landed; the
  recall hop waits on §33 and §64" to "anchoring half landed; recall hop blocked on corpus-world naming substrate
  (330 labels, 138 chunks, 0 whole-label hits, 2 one-word overlaps)".
- `ROADMAP.md` §86 row appended after §85.
