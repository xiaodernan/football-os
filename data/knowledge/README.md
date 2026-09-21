# Football knowledge corpus

Plain-text markdown that the API ingests into the knowledge base at boot
(`apps/api/app/services/knowledge/ingest.py`). This is the corpus the RAG answers cite, so
the file format *is* an interface:

```text
---
id: kebab-case-slug          # unique across the whole corpus; also the document's public slug
title: "Displayed title"
category: training           # training | tactics | rules | coaching | sports-science |
                             # match-analysis | player-profile | team-profile | history
tags: [lowercase, keywords]
applies_to: [midfielder]     # goalkeeper | defender | midfielder | forward | all
difficulty: intermediate     # beginner | intermediate | advanced
source: "who wrote this and under what right"
confidence: high             # high | medium — the author's own editorial confidence
last_reviewed: 2026-09-18
---

## Section heading
Prose. `## ` headings are the chunk boundaries.
```

Ingestion rejects a file that is missing `id`/`title`/`category`/`source`, uses an unknown
category/difficulty/position, or produces no chunks — the error appears in the boot log and
in `POST /api/v1/knowledge/ingest`, never silently.

## Provenance and licence

Every document here is `data_origin="project-authored"`: written for this project, from
general football coaching knowledge, with no text reproduced from books, federation
rulebooks, media articles or video games. That is a distinct class from `synthetic`
(generated demo world data, always labelled **DEMO DATA** in the UI) and from `licensed`
or `open` feeds, which arrive through `FootballDataProvider`/`NewsProvider` with a provider
id and licence reference. See `DATA_POLICY.md` §1.

Because the corpus is real editorial content rather than demo data, the documents carry
`is_demo_data = false` and the library surfaces label each answer with its `source:` line
instead of a DEMO DATA badge.

## Writing rules (why they exist)

- 650–950 words, 5–8 `##` sections. Chunks are cut on those headings, so each section must
  read alone: no "as above", no cross-references.
- Never invent a statistic, a study, an author or a citation. Illustrative quantities are
  phrased as typical ranges. `## Evidence and its limits` / `## When this does not apply`
  sections say out loud where guidance is general practice rather than a finding.
- Rule summaries describe the logic of the law in original wording and point at IFAB as the
  maintainer rather than quoting numbered clause text.
- Use the wording a real player would type ("how do I stop getting beaten in 1v1") in the
  first line of a section — that phrasing is what the retrieval golden set measures.

## Changing this directory

The eval gate is the reviewer:

```bash
cd apps/api
python -m evals.run_rag_eval          # recall@5, MRR, citation integrity, refusal accuracy
```

Adding or rewriting a document that makes an answer better is welcome; a change that drops
recall below 0.85, breaks verbatim citation integrity, or lets an out-of-scope question be
answered fails the gate and the test suite.
