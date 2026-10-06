# §87 recall-hop verification — the stored edge that pulls a passage (verification record)

Spec §30's last open half: an answer that cites both passages and graph edges, where a **stored edge widens
the answered context** with a passage BM25/cosine did not render. #84 landed the anchoring half and #86
measured the naming substrate absent, then created it (`1dd375c`). This unit lands the hop itself.

## What shipped

| path | role |
| --- | --- |
| `apps/api/app/services/knowledge/recall.py` | the scan: per anchored node, walk `project.edges_of`; a neighbour is hoppable only when a **passage body carries its full label string**; one pull per (anchor, neighbour); `exclude` is what the first pass renders (a hop never duplicates it); `scored` hits are reused, so a passage retrieval had ranked but not rendered keeps its real citation; cap `MAX_HOP_CHUNKS = 2`; order keyed to `(document slug, ordinal)` because chunk ids rotate per ingestion |
| `apps/api/app/services/knowledge/answer.py` | the integration: `assemble_context(hits, *, main=None, extra_budget=0)` renders `hits[:main]` under the unchanged 4-chunk / 3200-char budget and the remainder under `budget + extra_budget` (extra = the summed pull body length, so the reserve can never evict a pull it was granted); the hop runs strictly inside `if usable:` and strictly after `_confidence`; pull citations and digest entries carry `"via": "graph"`; a hop reason line is appended for each rendered ref only; the default `main=None` call is the original single-phase render |
| `data/knowledge/history/real-world-football-entities.md` | `## Demo World Competitions` bridge section (the four stored leagues with their measured member clubs) plus the document lead promoted to `## Overview` (its header-less lead chunk had been reddening the corpus contract since `1dd375c`) |

The refusal side is untouched: the hop is consulted only after the retrieval floors answered, and
`TestFloorsUntouched` keeps witnessing that a refusal carries no graph line (arm A3 re-proves it below).

## Measurements

* Knowledge tests, both engine legs (the PostgreSQL leg's first take in this project's records — the Docker
  Desktop engine had been down; restarted, `football_os_db` healthy on 54321): **44/44 SQLite** (46.6s) and
  **44/44 PostgreSQL** (61.3s); 18 joint (10 pre-existing + `TestRecallHop`'s 8) + 26 RAG.
* Golden-set probe against the **shipped** modules (`.scratch/r87_land_probe.py` imports `recall.pulls` and
  `answer.assemble_context` rather than keeping a local copy): **10 hops across 7 of 8 answers**; every hop
  rendered; first pass bit-identical to the single-phase render on all 8. The one answer without a hop
  (`pressing-vireford`) carries its league's bridge passage **in the first pass** — retrieval ranked it 2nd —
  which is exactly the no-duplicate contract working.
* Substrate re-measured over the final corpus: **330** labels, **155** chunks (up from 138), **46 whole-label
  hits across 24 labels** (the 20 demo teams plus their 4 leagues; the bridge section adds +24 over the 22
  measured at `1dd375c`).
* Cap witnesses: the witness league stores 5 member edges, so `MAX_HOP_CHUNKS = 2` does real work; the
  saturated fixture is asserted against the measured 2 and the constant.

## Witness arms (12 mutations; predictions written before each run)

Every arm mutates one shipped file with byte-exact replacements, runs `tests/test_knowledge_joint.py` on the
default SQLite leg, restores from a pre-arm backup and verifies the restore by sha256 — all 12 restored=True.
Round 1's comparison keyed predicted names in short form against parsed full names, so only the empty
predictions could compare equal; round 2 normalized both sides and re-ran the two arms whose old strings were
spelled `\n` against a CRLF file (`answer.py` is CRLF; `recall.py` is LF; each arm must spell its targets in
the file's own line endings).

| arm | mutation | predicted red | measured red | verdict |
| --- | --- | --- | --- | --- |
| A1 | scan predicate → the content-word subset rule (the degenerate rule the phrase rule replaced) | rule case | rule case | MATCHED |
| A2 | answer-pass `exclude` → `set()` | no-twice case | no-twice **+ rule** | MISMATCH (under-predicted; chased below) |
| A3 | hop block gate `if usable:` → `if True:` | refusal control | refusal control | MATCHED (my table named the class wrong — the case lives in `TestFloorsUntouched`) |
| A4 | `extra_budget=0` in the answer call | 5 named cases | exactly those 5 | MATCHED |
| A5 | pull citations unmarked (`via` removed) | 5 named cases | exactly those 5 | MATCHED |
| A5b | digest entries unmarked | a-hopped case | a-hopped **+ first-pass** | MISMATCH (under-predicted; chased below) |
| A6 | `_normalise` loses its casefold | none (designed survivor) | none | MATCHED |
| A7 | `MAX_HOP_CHUNKS = 2` → 3 | capped case | capped case | MATCHED |
| A8 | per-neighbour dedup removed | rule case (one neighbour pulled through two edges) | rule case | MATCHED |
| A9 | scored-hit reuse removed | scan-exclude case | scan-exclude case | MATCHED |
| A10 | reason refs zeroed | a-hopped + rule | a-hopped + rule | MATCHED |
| A11 | scan reads unstripped chunk text | none (designed survivor) | none | MATCHED |

Under-predictions chased, not smoothed: under A2 the unexcluded duplicate at `pressing-vireford` is also
marked `via: "graph"` (the mark keys on chunk id), so its first-pass ref `[2]` has no hop line and the rule
case reds — one defect, two tests, both correct. Under A5b the first-pass identity case distinguishes hop
entries by their digest mark, so unmarking the digest reds it too — the identity check reads the mark it
compares. Designed survivors, recorded rather than hidden: A6 (casefold) and A11 (header-stripping in the
scan) are currently unexercised by the label population — labels and bodies share their capitalisation, and
no stored label lives in a chunk header — and both are kept for body-authoring variance; a corpus that
lowercases a body, or a label in a heading, would make them load-bearing.

## Two pre-existing HEAD reds fixed in this landing (they sit in this unit's files)

* `tests/test_knowledge_rag.py::test_ask_citations_use_ref_for_the_marker_and_slug_for_the_link` had been red
  since `e00e87d` ("all five metrics now passing gates"), which stringified `Hit.citation()`'s
  `ordinal`/`score`/`similarity` **and** `assemble_context`'s `[n]` `ref` to satisfy `app/api/v1/agents.py`'s
  `list[dict[str, str]]` response model — against `apps/web/lib/types.ts` (which declares all four as numbers,
  and whose `fmt()` prints "—" for strings) and against the test that already read them as numbers. The fix
  restores the numbers and stringifies at the agents boundary, where the model actually demands it.
* The corpus contract (`test_every_corpus_document_has_required_frontmatter_and_parses_into_chunks`) had been
  red since `1dd375c`: `real-world-football-entities.md`'s lead section (an h1 plus intro before the first
  `##`) chunked without the `Title — Section` first line. The lead is now a `## Overview` section.
* Both measured red on a `git archive HEAD` plane before the fixes (2 failed, 34 passed), red on a `dab6b50`
  plane, fixed here; the joint file was 18/18 on both legs at the end.

## Named, not fixed: three agent-lane reds are pre-existing

`tests/test_agents.py::TestAgentOrchestrator::test_run_cached_answer`,
`tests/test_agents_benchmark.py::test_agent_benchmark_overall` and `::test_agent_benchmark_confidence` fail
identically on extracted planes at `e00e87d` (the benchmark commit itself), `dab6b50` and HEAD, none of which
contain any change of this unit — the benchmark's "standalone" green does not reproduce through these pytest
gates on a fresh per-run database. Owed a follow-up unit; named in this unit's commit message rather than
fixed from a feature branch.

## Reproduce

```
cd .scratch && python r87_land_probe.py      # golden-set probe through the shipped modules (SQLite default)
cd ../apps/api && python -m pytest tests/test_knowledge_joint.py tests/test_knowledge_rag.py -q
FOOTBALL_OS_TEST_DATABASE_URL=postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_test \
  python -m pytest tests/test_knowledge_joint.py tests/test_knowledge_rag.py -q
cd ../.. && python .scratch/r87_arms.py && python .scratch/r87_arms2.py   # 12 arms, restores sha256-verified
```
