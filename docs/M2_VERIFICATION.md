# M2 — Football Knowledge + RAG: verification record

Date: 2026-09-21/22 (host-local, overnight run). Milestone: spec §28–§29 (knowledge base, RAG pipeline),
§62 (AI labelling), §63–§64 (testing + agent evaluation), §88 Definition of Done.

Scope of this document: what was built, the commands that prove each claim, and the numbers those
commands printed. Anything not reproduced here is not claimed.

Host and ports: API `127.0.0.1:8731`, web `127.0.0.1:3210`, PostgreSQL + pgvector container
`football_os_db` on `127.0.0.1:54321` (`pgvector/pgvector:pg16`, extension version `0.8.6`).
Nothing else on this machine was touched.

---

## 1. What M2 delivers

| Piece | Where | What it does |
| --- | --- | --- |
| Corpus | `data/knowledge/**/*.md` (16 documents + `README.md`) | Editorial football knowledge written for this project: training, sports-science, tactics, rules, match-analysis, history. Frontmatter carries `id/title/category/tags/applies_to/difficulty/source/confidence/last_reviewed`. |
| Portable vector column | `app/core/vector_type.py` | `EmbeddingVector` TypeDecorator → `vector(256)` + HNSW on PostgreSQL, JSON array + in-process cosine on the SQLite fallback (ADR-002). One model, two engines. |
| Ingestion | `app/services/knowledge/{chunking,ingest}.py` | frontmatter parse → clean → section split → merge/split to 220–1300 chars → title-prefixed chunks → embeddings → rows. Idempotent by content hash; a file that disappears is deleted; a file that fails to parse is a hard error in the report. |
| Retrieval | `app/services/knowledge/retrieval.py` | semantic (pgvector `<=>` when the extension is live), keyword (BM25 computed here), and hybrid (reciprocal rank fusion) + deterministic feature rerank; metadata filters on category/position/difficulty/tag/slug; answerability gate; every score and reason returned. |
| Answers | `app/services/knowledge/answer.py` | context assembly under a character budget, extractive digest in demo mode, LLM path only when a key exists, verbatim citations, confidence with human-readable reasons, query audit row. |
| HTTP | `app/api/v1/knowledge.py` | `GET /knowledge/status`, `GET /knowledge/documents`, `GET /knowledge/documents/{slug}`, `POST /knowledge/search`, `POST /knowledge/ask`, `POST /knowledge/ingest` (staff only, audited). |
| Evaluation | `apps/api/evals/{golden_rag.json,run_rag_eval.py}` | 16 in-scope golden queries + 3 out-of-scope questions, five hard gates, CLI and importable `evaluate()`. |
| Migration | `migrations/versions/0002_knowledge_base.py` | three tables + indexes + conditional HNSW index + `CREATE EXTENSION vector` on PostgreSQL; full `downgrade()`. |

## 2. Backend evidence (all commands run on this host)

### 2.1 Corpus → database, both engines

```
$ python -m seed                                  # DATABASE_URL = postgresql+psycopg2://…:54321/football_os
knowledge base: {'documents_seen': 16, 'created': 16, 'chunks_written': 122,
                 'embedding_model': 'hash-local', 'embedding_dim': 256, 'elapsed_ms': 1389, 'errors': []}
```

Idempotency (second run, unchanged path):

```
documents_seen=16 created=0 updated=0 unchanged=16 chunks_written=0  (41–52 ms)
```

Forced re-embedding rewrites exactly the same number of rows — it replaces, it does not stack:

```
forced: chunks_written=122 created=0 updated=16 ; corpus_stats chunks still 122
```

This was a real defect caught by the new test: assigning a fresh chunk collection flushed the
INSERTs before the DELETEs, so `uq_chunk_document_ordinal` blew up on `force=True`. Fixed in
`ingest.py` by clearing and flushing the old rows first, and pinned by
`test_ingestion_is_idempotent_and_rewrites_only_changed_documents`.

pgvector is genuinely in play on PostgreSQL:

```
$ docker exec football_os_db psql -U football -d football_os -tAc "SELECT extversion FROM pg_extension WHERE extname='vector'"
0.8.6
$ … -tAc "SELECT indexdef FROM pg_indexes WHERE indexname='ix_chunk_embedding_hnsw'"
CREATE INDEX ix_chunk_embedding_hnsw ON public.knowledge_chunks USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')
$ … embedding column data_type → USER-DEFINED (vector(256))

$ python -c "…search(db,'how do I defend a 1v1 …')"
backend= hybrid-pgvector top= 1v1-defending-posture 0.61 answerable= True
answered= True backend= hybrid-pgvector citations= 4 conf= 0.822      # /ask over pgvector
```

Schema drift:

```
$ python -m alembic upgrade head && python -m alembic check
No new upgrade operations detected.
```

`migrations/env.py` excludes `ix_chunk_embedding_hnsw` from autogenerate: the HNSW shape
(`USING hnsw … WITH (m, ef_construction)`) is pgvector-specific and cannot be declared on the
portable column, so autogenerate would only ever propose dropping it. The index is migration-owned.

### 2.2 RAG evaluation gates (spec §64)

`python -m evals.run_rag_eval` on **both** engines, over the corpus as it ships today (18 documents /
138 chunks; 18 golden questions + 3 out-of-scope). PostgreSQL leg — one throwaway database created for
the run on the project's own container, dropped afterwards — rc=0:

```
corpus: 18 documents / 138 chunks / backend=hybrid-pgvector
  recall_at_k        1.0      gate >= 0.85
  mrr_at_k           0.9167   gate >= 0.6
  citation_integrity 1.0      gate >= 1.0
  refusal_accuracy   1.0      gate >= 1.0
  hybrid_delta       0.0      gate >= 0.0
  keyword recall@5  1.000    semantic recall@5  0.889
  citations checked: 72
all gates passed
```

SQLite leg, fresh database file, **rc=1**. This is a 2026-09-30 correction: the version of this section
claimed "the SQLite fallback prints the same five gate values", and that sentence is measured false.
Three of the five move, and the report refuses itself:

```
corpus: 18 documents / 138 chunks / backend=hybrid-vector-python
  recall_at_k        0.9444   gate >= 0.85
  mrr_at_k           0.9028   gate >= 0.6
  citation_integrity 1.0      gate >= 1.0
  refusal_accuracy   1.0      gate >= 1.0
  hybrid_delta       -0.0556  gate >= 0.0
  keyword recall@5  1.000    semantic recall@5  0.889
  citations checked: 72
FAILURES:
  - when-to-press: no acceptable document in top 5 — got ['squad-height-and-territory', 'pressing-evolution-notes', 'squad-height-and-territory', 'squad-height-and-territory', 'squad-height-and-territory']
  - metric hybrid_delta=-0.0556 is below the 0.0 gate
```

Two independent fresh SQLite files produced these identical numbers, so it is not a flake, and no
threshold was loosened to accommodate the reading. What the two engines share is each individual leg:
keyword recall@5 is 1.000 on both, semantic recall@5 is 0.889 on both — meaning the expected document is
outside the *semantic* top 5 for `when-to-press` on either engine. What diverges is the **fusion**. With
pgvector, the fused list recovers `when-to-press` to rank 4; with the in-process cosine fallback the same
two legs leave it past slot 5, which makes `hybrid_delta` (hybrid recall minus keyword-only recall)
negative. So ADR-002's promise that the ranking is reproducible without the extension is true of the two
scored legs and **not** of the hybrid order, and the payload's `backend=` field is what tells a reader
which of the two they are looking at. That difference was a production defect rather than a gate-tuning
question — the answer a `/knowledge` visitor got for `when-to-press` depended on which database the
deployment used — and it is repaired in §2.3b, the same day. Both readings above are the **before**
numbers of that repair; no threshold moved for either of them.

Rank detail: 16 of 18 golden questions put the expected document at rank 1 on **both** engines; `read-game`
lands at rank 4 on both (its answer is genuinely spread over several documents), and `when-to-press` at
rank 4 on PostgreSQL while the SQLite fallback drops it out of the five.

`citation_integrity = 1.0` means all 72 emitted citation quotes are byte-for-byte substrings of the
stored chunk text — an answer cannot cite a sentence the corpus does not contain.

### 2.3 The refusal gate, measured rather than guessed

Refusal accuracy was 0.333 when the first version of this gate shipped: out-of-scope questions such
as *"what is the best expected goals model for the 2019 champions league"* were answered confidently
from `set-piece-zonal-marking` at score 0.414. The fix is an **answerability** computation in
retrieval: take the question's rare terms (document frequency ≤ 30 % of the corpus, bare numbers
excluded because `"10"` recurs in unrelated prose) and require the top passage to actually contain
them.

Thresholds were set from measurement over all 19 cases, not by intuition:

| case group | rare terms matched in the top passage | coverage |
| --- | --- | --- |
| 16 in-scope golden questions | min **2**, typical 3–5 | min **0.43**, typical 0.67–1.00 |
| 3 out-of-scope questions | max **1** (two of them 0) | max **0.33** |

→ `MIN_DISCRIMINATIVE_MATCHES = 2`, `MIN_DISCRIMINATIVE_COVERAGE = 0.40`, recorded as such in
`retrieval.py`. A question that shares **no** rare term with the corpus is now refused too — the
earlier logic treated an empty discriminative set as "nothing to check" and answered confidently,
which is the opposite of the intended behaviour.

Measured refusal examples (hybrid, SQLite engine):

```
xg-model      top 0.414  rare ['best','expected','goals']    matched ['best']        → refuse
boot-brand    top 0.406  rare ['brand','number']             matched []              → refuse
cleat-sensor  top 0.059  rare []                             matched []              → refuse (score floor)
handball      top 0.660  rare ['arm','handball','hits']      matched all 3, cov 1.00 → answer
```

Every refusal carries the reason (`0/2 rare terms matched … coverage 0.33 …`), so a user or a
reviewer can see *why* the system stayed silent instead of having to trust it.

### 2.3a The two floors re-measured, and turned into a case (2026-09-30)

The table above is a snapshot of a corpus that kept growing. Re-measured on the SQLite fixture database at
`7581dad` (18 documents, 138 chunks, `knowledge.search` in hybrid mode over the top 5), the golden set is
**18 in-scope + 3 out-of-scope = 21** questions, not 19, and the out-of-scope coverage peak is **0.20**, not
0.33. The two figures the table and the `retrieval.py` comment both carried had both drifted; the constants
themselves did not move (`MIN_DISCRIMINATIVE_MATCHES = 2`, `MIN_DISCRIMINATIVE_COVERAGE = 0.40`).

| population | rare terms matched in the top passage | coverage |
| --- | --- | --- |
| 18 in-scope questions | min **2** (`read-game`, exactly at the floor), max 7 | min **0.4286** (`offside`, 3 of 7), max 1.0 |
| 3 out-of-scope questions | max **1** (`xg-model`, 1 of 5; `boot-brand` 0 of 2; `cleat-sensor` carries no rare term) | max **0.20** (`xg-model`) |

All three out-of-scope questions still retrieve five candidate passages, so their refusal is the floors' doing
and not an empty result set. `tests/test_knowledge_rag.py::test_the_answerability_floors_sit_inside_the_measured_gap`
now recomputes that separation from `evals/golden_rag.json` on every run and asserts, for each axis,
`max(out) < floor <= min(in)`. The case exists because §2.3's other gate only proves *obedience*: with this
population every in-scope question clears **both** floors and every out-of-scope one fails **both**, so lowering
either constant alone changes no verdict at the door and moves no threshold — `recall_at_k` counts ranked
passages, not answerability.

Witness: six runs (a control plus five arms) on a plane built with `git archive HEAD` at `7581dad` and these
two files overlaid byte-identically, each arm re-based to the pristine bytes before it is applied, the whole
suite of the pair run per arm (`collected=2`, both case names asserted from the junit report).

| arm | change | `…floors_sit_inside_the_measured_gap` | `test_rag_eval_gates_pass_on_this_database` |
| --- | --- | --- | --- |
| control | none | green (predicted green) | green (predicted green) |
| W1 | matches 2 → 1 | **red** — `1 < 1` fails | green (predicted green) |
| W2 | coverage 0.40 → 0.0 | **red** — `0.2 < 0.0` fails | green (predicted green) |
| W3 | matches 2 → 3 | **red** — `3 <= 2` fails | green — **predicted red** |
| W4 | coverage 0.40 → 0.5 | **red** — `0.5 <= 0.4286` fails | green — **predicted red** |
| W5 | `answerable` stops consulting the coverage floor | green (predicted survivor, recorded as owed) | green (predicted green) |

Restored byte-identical after the run (`6f886463e549`). The two misses were chased rather than accepted, and
they are not a weakness of the new case — they are a defect in the existing one:
`tests/test_knowledge_rag.py:214` reads `assert report.passed`, while `EvalReport.passed` is a plain method
(`evals/run_rag_eval.py:68`; the class's only `@property` is `hybrid_delta` at :55). A bound method is always
truthy, so the suite never reads `report.failures`. Called properly, `evaluate()` on this database reports
`passed=False` at the **shipped** floors with two live entries — `when-to-press: no acceptable document in
top 5` (recall 17/18 = 0.9444) and `metric hybrid_delta=-0.0556 is below the 0.0 gate`, i.e. hybrid fusion
ranked worse than keyword-only on the SQLite semantic fallback. The same probe on a PostgreSQL corpus with the
same 18 documents and 138 chunks reported 0 failures, so the defect is engine-specific; both engines were then
run through the shipped CLI end to end (2026-09-30, rc=1 on SQLite / rc=0 on PostgreSQL, full reports in §2.2),
which pins the divergence to the fused leg: each single leg scores the same on both engines. The repair is owed
with both legs measured (tracked as "RAG eval gate: assert reads a bound method"). A sweep of the five floor
configurations through the repaired call, printed per arm, showed that a *lowered* floor adds no failure entry
at all while a *raised* one adds exactly `… golden query was refused` — which is the line between what only the
new case can see (W1, W2, W5) and what the repaired eval will also see (W3, W4).

The owed follow-up on the floors themselves: put an out-of-scope golden question in each single-floor shape —
2 rare terms of which the top passage matches 1 (coverage 0.50 clears 0.40, matches 1 fails 2), and ≥ 6 rare
terms of which it matches 2 (matches 2 clears 2, coverage 0.33 fails 0.40) — so that deleting either condition
from `answerable` makes the door answer something it must refuse. Today W5 survives because no such question
exists.

Reproduce:

```
cd apps/api
python -m pytest tests/test_knowledge_rag.py -k floors_sit_inside -q --junitxml=…
```

That case *is* the measurement: it reads `evals/golden_rag.json`, calls `knowledge.search(db, query,
mode="hybrid", top_k=5)` once per question, and derives both extremes from the rows it just retrieved — so a
corpus change moves the numbers the case checks instead of moving only the prose above it.

### 2.3b The two semantic legs were not the same population (2026-09-30)

§2.2 left off with an unexplained fact: keyword recall@5 and semantic recall@5 are identical on both
engines (1.000 and 0.889), yet the hybrid order differed, and only on SQLite. The cause is in
`retrieval._semantic_ranking`. The pgvector leg asks the index for a window —
`LIMIT :leg_limit` with `leg_limit = max(top_k * 4, 20)` = **40 chunk ids** — while the in-process fallback
built its `semantic_ranking` from **every** candidate above `MIN_SIMILARITY = 0.02`, which on this corpus is
all 138. Both lists then go into `reciprocal_rank_fusion`, which is rank-based: a chunk ranked 137th still
contributes a small positive amount, so the fallback leg's long tail of near-nothing matches was not merely
extra information, it was competition for the same slots. For `when-to-press` that tail put four
`squad-height-and-territory` chunks and one `pressing-evolution-notes` chunk ahead of the expected document,
knocking recall to 0.9444 and `hybrid_delta` to −0.0556 — fusion scoring *worse* than keyword-only, which the
`>= 0.0` gate exists to catch. The module docstring's promise that the fallback "computes the same ranking
in-process" was therefore true of the metric and false of the population.

The repair is one slice, applied where the fallback builds its ranking, so both legs hand the fusion the
same-sized window:

```
semantic_ranking = [ … if similarities[cid] > MIN_SIMILARITY ][: max(top_k * 4, 20)]
```

Measured, `python -m evals.run_rag_eval` on two `git archive HEAD` planes, each with its own fresh SQLite
file, prediction written before either ran:

| plane | semantic leg | rc | recall_at_k | mrr_at_k | hybrid_delta | `when-to-press` |
| --- | --- | --- | --- | --- | --- | --- |
| control (HEAD) | every candidate above 0.02 — 138 ids | 1 | 0.9444 | 0.9028 | −0.0556 | MISS, outside the top 5 |
| repaired | the same 40-id window the SQL leg asks for | **0** | **1.0** | 0.9213 | **0.0** | rank 3 |

PostgreSQL is untouched by this and did not need to be: the slice sits in the branch that only runs when the
extension is absent, and its leg was already windowed. Its five gate values stay as §2.2 prints them (recall
1.0, mrr 0.9167, delta 0.0, rc=0); the repaired SQLite plane now prints the same five, with mrr 0.9213
against 0.9167 — the residual gap is HNSW's approximate top-40 (migration 0002 builds
`ix_chunk_embedding_hnsw … vector_cosine_ops`) against exact in-process cosine, and it moves no gate.

The second half of the landing is the assertion that §2.3a had to leave as owed work: with
`assert report.passed` (a bound method, always truthy) repaired to `assert report.passed()`, the suite reads
`report.failures` for the first time. The two repairs are one mechanism — the ranking repair makes the gate
passable, the assertion repair makes it observed — and the witness proves the pair rather than either half:

| arm | change | eval gate case | floors-gap case |
| --- | --- | --- | --- |
| control | none | green | green |
| X1 | delete the window slice | **red** — recall 0.9444 / delta −0.0556 enter `report.failures` | green |
| X2 | X1 **and** the vacuous `assert report.passed` back | green — **expected**, this is the blindness the landing exists for | green |
| X3 | `MIN_DISCRIMINATIVE_MATCHES` 2 → 3 | **red** — §2.3a's W3 re-judged: `read-game` refused | red |
| X4 | `MIN_DISCRIMINATIVE_COVERAGE` 0.40 → 0.5 | **red** — §2.3a's W4 re-judged: `offside` refused | red |
| X5 | `MIN_DISCRIMINATIVE_MATCHES` 2 → 1 | green — a lowered floor changes no verdict at the door | red |

Six arms on a `git archive HEAD` plane with the two edited files overlaid, each arm re-based to pristine
bytes, `collected=2` and both case names asserted from junit every arm, plane restored byte-identical
(`b881c3195055`, `39d796c2e3e7`). **0 survivors, 0 prediction mismatches.** §2.3a's two missed predictions
(W3, W4) are now exactly the predicted reds, which is what "recorded as owed work" was for.

Module run on this landing: `tests/test_knowledge_rag.py` = **26 collected / 0 failures / 0 errors /
0 skipped** on per-run SQLite in 36.831 s and the same 26/0/0/0 on the PostgreSQL plane in 98.647 s, rc=0 on
both; `ruff check` clean. Still owed, and named so it does not quietly close: this witness ran on the SQLite
plane only, so the pgvector leg's own `leg_limit` is unprobed — an arm that widens it must be judged on a
PostgreSQL plane; and the two whole-suite legs over this commit (prediction unchanged at 1363 / 0 / 0 / 1
skip, since the landing adds no case) are what §4 of this document requires before the number is called a
baseline.

### 2.4 Unit / integration / API tests, dual database

```
$ python -m pytest -q                                                 # SQLite fallback
46 passed
$ FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" python -m pytest -q
46 passed
$ python -m ruff check app tests evals seed.py && python -m mypy app
All checks passed!   /   Success: no issues found in 36 source files
```

`tests/test_knowledge_rag.py` (23 tests) covers: the corpus contract itself (every shipped file
parses, has provenance, chunks with the heading prefixed), ingestion idempotency and forced
replacement, embedding dimension, `project-authored` provenance, all three retrieval modes,
metadata filters confining every hit, verbatim citation quotes, refusal of three nonsense
questions, the extractive demo answer, the query audit row pointing at real chunks, the full eval
gate as a test, and the HTTP surface including the staff-only ingest route.

The session fixture now ingests the corpus, because the API ingests on boot — tests must see the
same universe the app serves.

### 2.5 Live API on PostgreSQL

```
boot log: knowledge base ready docs=16 chunks=122 written_now=0 backend=hash-local
          boot env=development dialect=postgresql+psycopg2 demo_mode=True
GET /api/v1/knowledge/status  → documents 16, chunks 122, embedding_dim 256, pgvector true,
                                 database_dialect postgresql, modes [semantic, keyword, hybrid],
                                 reranker feature-local
GET /api/v1/knowledge/documents → 16 items across
                                 history, match-analysis, rules, sports-science, tactics, training
```

`docs/api/openapi.json` was regenerated from the running API: 28 paths / 32 operations, including
all six `/api/v1/knowledge*` routes.

### 2.6 Explainability and anti-hallucination properties actually enforced

* Every search and answer response carries `demo_mode`, `provider`, `model`, `confidence`,
  `reasons[]`, `sources[]`, `generated_at`, `disclaimer`.
* With no `OPENAI_API_KEY` the answer is an extractive digest of the cited chunks and the payload
  says `model: "extractive-no-model"` — nothing pretends to be a language model (spec §45).
* Retrieval reports which engine ranked it (`pgvector`, `vector-python`, `bm25-python`,
  `hybrid-pgvector`, `hybrid-vector-python`) plus per-leg timings.
* Corpus provenance is `data_origin="project-authored"`, `is_demo_data=false`: this is content the
  project wrote, not third-party data and not placeholder data. The history note explicitly refuses
  to be treated as documented history, and the rules notes defer to IFAB wording.
* `POST /knowledge/ingest` is staff-only and writes a real `AuditLog` row; the rate-limit helper and
  `model_ledger.budget_exhausted` guard the AI routes (429 `ai_budget_exhausted`) so retrieval keeps
  working even when the daily spend cap is hit.

### 2.7 Live HTTP round-trip (not just in-process tests)

A throwaway `player` account against the running API on PostgreSQL:

```
login                        201
POST /knowledge/search       200  backend=hybrid-pgvector hits=3 confidence=0.95
                                 answerable=True matched=['receive','set']
                                 rank 1 = passing-under-pressure score 0.5025
                                 citation ref = /knowledge/passing-under-pressure#5   sources = 3
POST /knowledge/ask          200  answered=True model=extractive-no-model demo_mode=True
                                 confidence=0.757 citations=4 sources=4
POST /knowledge/ask          200  answered=False citations=0 confidence=0.0
   (nonsense question)       reason: "the top passage shares too little of the question's rare
                                 vocabulary to answer honestly: 0/2 rare term(s) matched (need >= 2)
                                 at coverage 0.00 (floor 0.4)"
POST /knowledge/ingest       403  {"code":"forbidden","message":"Staff role required"}   (player)
POST /knowledge/search       401  anonymous
```

The `ingest` line is a transcript of what that door answered when §29 landed, and §60 corrected it: `forbidden`
was a code no answer table registered, and the allow-list beside it named `staff` and `operator`, standings no
account can hold. A `player` caller is now refused `insufficient_role` with `held`/`required`/`roles` beside the
message, and `tests/test_authorization_census.py` is what keeps both spellings reachable.

The refusal is the interesting line: the system says *why* it stayed silent in terms a reviewer can
check, instead of returning a confident sentence.

## 3. Web surface — `/knowledge`, verified in the browser

`apps/web/scripts/visual-qa.mjs` was extended with 14 knowledge assertions and four more mobile surfaces and run against the live
stack (Next.js on 3210 → FastAPI on 8731 → PostgreSQL + pgvector on 54321). **57/57 checks passed,
28 screenshots captured** (`docs/screenshots/202609212121-*`); the M1 suite still passes unchanged, so
the new surface did not regress the old one.

| Check (assertion, not eyeball) | Result |
| --- | --- |
| Library renders the authored corpus | 16 document cards, all read from `GET /knowledge/documents` |
| Every card carries provenance + its real chunk count | `{"total":16,"withProvenance":16,"withPassages":16}` |
| Page states the corpus size it was read from | "16 project-authored documents, 122 indexed passages" |
| Document detail renders passages with citation anchors | 8 passages, 8 anchorable (`#0…#7`) |
| Origin declared, demo flag honest | `data_origin=project-authored`, `is_demo_data=false` |
| Hybrid search runs over the live corpus | 5 hits · 122 chunks scanned · backend `hybrid-pgvector` |
| Top result shows its own numbers | `score 0.622 · cosine 0.290 · bm25 5.600 · lexical 5.600 · semantic 0.290 · coverage 1.000 · heading 0.000` |
| Search excerpt is verbatim in the stored passage | fetched `/knowledge/…#n`, whitespace-normalised substring match |
| Ask returns a grounded answer with citations | 4 citations, 2 342 chars of answer |
| Inline `[n]` markers resolve | `[1]…[4]` → `/knowledge/buildup-vs-high-press#0`, `/knowledge/pressing-evolution-notes#4`, `/knowledge/pressing-triggers#3`, `/knowledge/transition-defence-five-seconds#7` |
| A citation link resolves to the exact passage it quotes | `#0` — quote is verbatim |
| Answer generation self-labels | badge reads `DEMO MODE · EXTRACTIVE ANSWER`, never "AI-generated" |
| Out-of-scope question refused, nothing invented | `NO GROUNDED ANSWER … · 0 citation(s)` |
| Refusal names the measured gate | reasons carry the rare-term/coverage floors, not a shrug |
| 375 px pass | `/knowledge` and `/knowledge/{slug}` render with 0 px horizontal overflow, 8/8 nav links visible |
| 375 px pass (regression guard on M1) | `/history` and a drill detail page, plus the existing five surfaces, all clean |

Two honesty rules the browser pass enforces rather than trusts:

- **`PROJECT AUTHORED` and `DEMO MODE` are different badges.** The library, document pages and every
  citation use `PROJECT AUTHORED` (the corpus is written for this project — labelling it demo data
  would be false). `DEMO MODE` is rendered only where answer generation is extractive, and the notice
  at the top of the page names the reranker and embedding models behind it.
- **No number on the page is modelled.** Scores, cosine, bm25, chunk counts, scanned totals,
  confidence, timings and provenance strings all come from the API's own fields; the panel footers
  say which endpoint each block reads from.

### 3.1 A real defect the browser pass caught

The first run crashed the Ask panel with a client-side exception. Cause: `/knowledge/ask` overloads
`citations[].ref` as the **1-based `[n]` marker** (an integer, mirroring `sources[].ref`), while the
web component passed it straight into `<Link href>`. Next rejected the number and killed the route.

Fixed in the consumer, not by bending the API: the citation card now deep-links with
`slug` + `ordinal` (`/knowledge/{slug}#{ordinal}`), `lib/types.ts` documents `ref: number` as the
marker, and `tests/test_knowledge_rag.py::test_ask_citations_use_ref_for_the_marker_and_slug_for_the_link`
pins both meanings so the next consumer cannot guess wrong. 25 knowledge tests are green on SQLite and
PostgreSQL+pgvector after the change.

This is the argument for browser verification over reading the JSX: the payload was correct, the type
mirror was plausible, and only an executed page failed.

### 3.2 Reproduce

```bash
cd apps/web && npm run typecheck && npm run lint && npm run qa:visual
```

