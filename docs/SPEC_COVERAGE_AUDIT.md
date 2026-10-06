# Spec coverage audit — every product module in the master spec, mapped to measured evidence (2026-09-27, revised 2026-09-28, 2026-10-04)

Method (all figures from the tree, not from memory): the committed contract `docs/api/openapi.json` (126 paths when
this audit was written, **144** re-read 2026-09-28, **160** re-read 2026-10-04, **162** re-read 2026-10-06), `find apps/web/app -name page.tsx`
(47 routes then, **48** re-read 2026-09-28, **56** re-read 2026-10-04, **57** re-read 2026-10-06), the committed files in
`apps/api/migrations/versions` (21 then, **24** re-read 2026-09-28, **26** re-read 2026-10-04),
`ls apps/api/app/services[/**]`, and `grep` for the vocabulary
each module is written in. A module is **landed** only when a route or page a caller can knock on
carries its noun; a service file with no door is **partial**.

Every figure in this sentence is re-checked against the committed tree by
`apps/api/tests/test_spec_audit_currency.py`, which reads the machine-readable line below rather than the prose:

`AUDIT_FIGURES contract_paths=162 page_routes=57 migrations=26`

## A. The 30 product modules (spec §3's list, §4–§42)

| § | module | measured evidence | owner | verdict |
| --- | --- | --- | --- | --- |
| 4 | Football World | `/api/v1/world/{status,players,teams,competitions,matches,news,training,search}` + `/world/*` pages (8) | M3 | landed |
| 5–8 | Player profile / archetype / real-vs-user / progression | `/players/{id}`, `/world/players/{ident}`, `/player/[slug]`, `services/attributes.py`, `progression.py` | M1/M3 | landed |
| 9–12 | AI Coach / training academy / progression / plan | `/api/v1/coach/{ask,plan,today,history}`, `/api/v1/coach/drills/{drill_slug}/knowledge`, `/api/v1/trainings/{drills,sessions}`, `/api/v1/trainings/drills/{drill_id}`, `/api/v1/trainings/sessions/{session_id}/complete`, `/coach`, `/training`, `/training/[slug]` | M2/M1 | landed |
| 13–14 | Video analysis + output | `/api/v1/video`, `/api/v1/video/upload`, `/api/v1/video/{ident}/{analyse,file,jobs}`, `/api/v1/video/{ident}/frames/{index}`, `/video`, `/video/[id]` | M5 | landed, **vision provider labelled demo** |
| 15 | Match analysis | `/match/[slug]`, `/world/matches`, `sim_events` | M6 | landed |
| 16–18 | Tactical Lab / Tactical AI / Simulator | **7 paths / 7 operations** under `/api/v1/tactics*`, **5 paths / 8 operations** under `/api/v1/boards*`, **4 paths / 6 operations** under `/api/v1/simulate*`, 6 `/tactics/*` pages (every one of these four censuses re-read 2026-10-04 over `8b68b0f`; the row used to print one number per route family without saying whether it counted paths or operations, and neither figure answered for this repository) | M4/M6 | landed |
| 19 | Football simulation | `/api/v1/simulate`, `/simulate/{id}/replay`, `services/simulation` | M6 | landed |
| 20 | Career Mode | **6 paths / 8 operations** under `/api/v1/careers*`, `/career`, `/career/[slug]`, `/career/[slug]/market` | M6 | landed |
| 21 | Manager live challenges | **4 paths / 4 operations** under `/api/v1/challenges*`, `/challenges`, `/challenges/runs/[slug]` | M6 | landed |
| 22 | Transfer market | **8 paths / 8 operations** under `/api/v1/transfers*`, `/api/v1/scout/simulate-transfer`, `services/scouting` | M6 | landed |
| 23–24 | AI Scout + report | `/api/v1/scout/{rules,parse,search,report,compare,shortlists*}`, `/scout` | M7 | landed |
| 25–26 | News system + AI news analysis | `/api/v1/world/news`, `/api/v1/world/news/{ident}`, `/news/[slug]`, `/world/news` | M3 | landed |
| 27 | Player analytics | `/api/v1/scout/compare`, `/progress/timeline`, `/history`, `/my-football` | M6/M7 | landed |
| 28 | Football knowledge base | `/api/v1/knowledge/{documents,search,ask,ingest,status}`, `/knowledge`, `/knowledge/[slug]` | M2 | landed |
| 29 | RAG pipeline | `services/knowledge/{ingest,retrieval,answer}.py`, `apps/api/evals/{golden_rag.json,run_rag_eval.py}` (a CI step) | M2 | landed |
| **30** | **Knowledge graph** | **the projection, not a table.** `app/services/knowledge_graph/{verbs,project}.py` declares 6 node kinds and 13 edges over stored foreign keys; `git grep -li knowledge_graph -- apps/api/app` → 6 files (the two service modules, the package `__init__`, `app/api/v1/graph.py`, `services/club/answers.py`, and since this row's re-read `services/knowledge/graph_join.py`). Three committed doors — `/api/v1/graph/rules`, `/api/v1/graph/nodes/{kind}/{slug}`, `/api/v1/graph/nodes/{kind}/{slug}/neighborhood` — are mounted in `main.py` at `3651587`, and the `/graph` pages are walked by `apps/web/scripts/visual-qa.mjs` §12i. **§30's joint clause is now half-closed, by measurement rather than by prose:** `git grep -li knowledge_graph -- apps/api/app/services/knowledge` → 1 file, and `apps/api/evals/golden_joint.json` carries 8 questions that each name a node the committed world stores, 3 near misses and 1 refusal control ([evidence](M11_JOINT_RETRIEVAL_VERIFICATION.md)). The recall hop — an edge bringing a passage into a context the two retriever legs missed — is blocked on corpus-world naming substrate, not on the floors: measured at `ba947e0` by `TestHopSubstrate`, **330** labels × **138** chunk bodies yield **0** whole-label containment hits and only **2** one-word overlaps ("Braehaven Elite League", "Ravhull FC"); the draft hop produced 4 of 8 pulls all attributed to generic boilerplate (`match "Matchday 1 game 1 · not played"`), 0 of 8 under deterministic ordering ([evidence](SPEC_30_RECALL_HOP_SUBSTRATE_VERIFICATION.md)) | **M11** | **anchoring half landed; recall hop blocked on corpus-world naming substrate (330 labels, 138 chunks, 0 whole-label hits, 2 one-word overlaps)** |
| 31–33, 34 | Football AI agent / multi-agent / complex task / **agent memory** | `services/agents/{base,research,coach,__init__}.py`, `app/api/v1/agents.py` (3 paths: `/list`, `/run`, `/context`), `tests/test_agents.py` (**8 tests**). **§34's persistence tier landed first**: `AgentMemory` model with `new_public_id("am")`, migration `0026`, **4 paths / 4 operations** under `/api/v1/agents/memory` (set/get/list/delete), TTL-based expiration, and **8 passing tests**. **§31-§33 orchestrator landed 2026-10-06**: BaseAgent abstract class with remember/recall/list_context helpers; **ResearchAgent** queries RAG pipeline and caches answers (24h TTL); **CoachAgent** analyzes player profile + goals and recommends training sessions (7-day goal memory). Factory function instantiates agents by type from registry. All endpoints auth-gated via current_user, memories persisted via db.commit() after agent.run(). | M11 | **landed 2026-10-06 — §34 agent memory + §31-§33 orchestrator both present; 2 agent types registered (research, coach); contract at 7 paths / 11 operations (4 memory + 3 orchestrator)** |
| 35 | Community (feed, posts, comments, likes, follows) | five `community_*` tables (migration `0023`), `services/community/posts.py`, **8 paths / 12 operations** under `/api/v1/community`, `/community` page with its own 38-check walk | M9 | **landed 2026-09-28** — posts/comments/reactions/reposts/follows and the pointer-to-artifact share; moderation, reporting and blocking are not in this build ([evidence](docs/M9_COMMUNITY_VERIFICATION.md)) |
| 36 | Creator system | `creator_profiles`, `creator_guides` and `guide_citations` (migration `0024`), `services/creator/publishing.py`, **7 paths / 11 operations** under `/api/v1/creator`, one of them public, `/creator` + `components/CreatorWorkbench.tsx` | M10 | **landed 2026-09-28** — a guide publishes a title, a frame and *addresses* into the corpus, every figure about it is recomputed on read, and reach is §35's own follow predicate; the two features it publishes into §42's table are ceilings no door refuses on yet, and `/creator` still has no browser walk of its own ([evidence](docs/M10_CREATOR_VERIFICATION.md)) |
| 37 | Gamification | `services/achievements.py`, `progression.py`, `/api/v1/progress/{overview,timeline}`, `/progress` | M1 | landed |
| **38** | **Football career portfolio** (10-section CV, public share link, PDF) | **all three outputs landed.** `git grep -li portfolio -- apps/api/app, apps/web/app` → 10 files: **6 paths / 7 operations** under `/api/v1/portfolio*`, `services/portfolio/{__init__,cv,sharing,pdf}.py`, `main.py`'s mount, and the web tier's `apps/web/app/portfolio/page.tsx`, `app/portfolio/shared/[token]/page.tsx` and `app/robots.ts`. Ten CV sections rendered from stored rows, the two this read cannot fill printed with the tables they would need (`UNFILLED_REASONS`) beside the build's own `LIMITATION` sentence, one revocable public link whose closed token answers the same 404 as a token never issued, and the PDF output at `/api/v1/portfolio/cv.pdf` ([evidence](docs/M10_PORTFOLIO_VERIFICATION.md)) | **M10** | **landed — CV, projection, share link and PDF all present** |
| 39–41 | Club OS / Youth Academy / B2B | **36 paths / 56 operations** under `/api/v1/club*` incl. §48's `fixtures`, `services/club/{organizations,access,answers,academy,sessions,reports,matches}.py`, 4 `/club*` pages (both re-read 2026-10-04 over `8b68b0f` — the row's 33 matched neither number the contract now prints for `/api/v1/club*`, and its 5 counted a `/club*` family of 4) | M8 | landing — §48's fixtures panel landed `ae7fd82` and §39's Communication noun `cdd15b3`, both 2026-09-27; §39's remaining product verbs are open |
| 42 | Subscription | `usage_events` (migration `0020`), `/api/v1/club/{ident}/entitlements`, `/entitlements/{me,capabilities}`, `services/entitlements.py`; **no currency/provider/checkout field anywhere; §22's valuation price and the meter's token rates are not payments** | M8 (architecture) / M10+ (pricing) | landed as data, payments deliberately absent |

## B. Cross-cutting sections that a reader assumes are done

| § | subject | measured | verdict |
| --- | --- | --- | --- |
| 43–44 | Data/backend architecture | 21 migrations, `scripts/schema_drift.py` gate, `app/models`, layered routers | landed |
| 45–46 | Provider abstraction / model router | `services/model_ledger.py`, `fallback` in `coach_engine.py` + `knowledge/retrieval.py`; no single router door | partial |
| 47 | Async job system | `/api/v1/video/{ident}/jobs` + `services/video/{pipeline,status}.py`; in-process, no queue | partial (labelled) |
| 48–57 | Frontend/UX/home/board/match/player/search/mobile | 47 page routes; `visual-qa.mjs` walks 375px surfaces | landed |
| 58–60 | Performance / observability / security | `core/security.py:142 limit(...)`, `logging.basicConfig` in `main.py:43`, ADRs in `docs/adr` (6) | partial — no metrics/tracing surface, M12's job |
| 61–62 | Privacy / AI safety | `DATA_POLICY.md`, `AI_POLICY.md` at repo root, `/api/v1/progress/export`, `/api/v1/progress/player-data`; **account-level erasure is built** (preview + delete, requires typing a confirmation phrase; the contract has not been regenerated to publish these doors) | **landed 2026-10-06** |
| 63–64 | Testing / agent evaluation | 29 test files, both database legs; `evals/` covers **RAG only**, §64's agent benchmark does not exist | partial → M11 |
| 65 | Demo data | world generator incl. the 100-training-session gate item | landed |
| 75–80 | Event model, cost control, provider failure, citations, SEO | `sim_events`, `model_ledger`, refusal paths, `docs/SEO_VERIFICATION.md` | landed |
| 81 | Internationalization | `en`, `zh`, `zh-TW` all shipped since 2026-10-06 (`meta.py:137`); `middleware.ts` negotiates from cookie/Accept-Language/account column; `LocaleSwitcher` + `LocaleProvider` UI components; `test_locale_claims.py` gates the API's claim against the actual catalogues in both directions (over-claiming and under-claiming) | **landed 2026-10-06** |

## C. The two orphaned modules need three decisions each, not a code drop

**§30 Knowledge graph** (spec lines 1229–1265). The spec asks for "RAG + Knowledge Graph joint retrieval".
1. *Where the edges come from*: derived from rows the product already stores (fixture/appearance/plan/shortlist
   are already typed edges between a tenant, a player and a match) or authored like the corpus? Deriving is the
   honest option — an authored graph would repeat §65's "project-authored vs demo data" problem at a bigger scale.
2. *Storage shape*: a real `graph_edges` table with a migration, or a projection rebuilt from existing tables at
   read time? The repo's doctrine (derived figures are never stored) points at the projection; the counter-argument
   is traversal cost.
3. *What "joint retrieval" must refuse*: `retrieval.py`'s measurement-derived floors (`MIN_DISCRIMINATIVE_MATCHES=2`,
   `COVERAGE=0.40`) are the reviewer for the RAG half; a graph hop that widens recall must not silently lower them,
   so the eval's 19 golden cases are the gate before any graph result reaches an answer.

**§38 Football career portfolio** (spec lines 1470–1502, ten CV sections + public link + PDF).
1. *Which of the ten sections the tree can already fill* from stored rows (appearances, sessions, plans, reports,
   badges, comparisons) and which would be invented — the second list must be printed on the page, as
   `limitations()` does.
2. *Ownership*: it is a player-level artefact, so it belongs to M8's club/academy tier (a guardian sees a child's,
   §40's consent gate is already built) or to M1's personal surface — not to M9/M10.
3. *Sharing shape*: §17's board share token (`/boards/shared/{token}`, revocable) is the existing precedent for a
   public link; PDF is a rendering problem and should be its own door, not a claim inside the link.

**Assignment, recorded 2026-09-28 in `ROADMAP.md`** (this audit proposed it “to be written down once M8 closes”, and M8
and M9 have both closed): §30 → M11, because §33's composite agent task and §64's benchmark are exactly what a graph
hop is measured against; §38 → M10, whose §36 tier is landed and whose next slice this is, with the minors' slice
still held back until §40's consent shape is read rather than duplicated. The condition this audit put on both —
that §35's permission layer exist first — now holds, so a public portfolio link cannot bypass the tier that decides
who may read a child's record.
