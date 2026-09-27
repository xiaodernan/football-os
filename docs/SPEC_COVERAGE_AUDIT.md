# Spec coverage audit — every product module in the master spec, mapped to measured evidence (2026-09-27)

Method (all figures from the tree, not from memory): the committed contract `docs/api/openapi.json` (126 paths,
listed), `find apps/web/app -name page.tsx` (47 routes), `ls apps/api/app/services[/**]`, and `grep` for the
vocabulary each module is written in. A module is **landed** only when a route or page a caller can knock on
carries its noun; a service file with no door is **partial**.

## A. The 30 product modules (spec §3's list, §4–§42)

| § | module | measured evidence | owner | verdict |
| --- | --- | --- | --- | --- |
| 4 | Football World | `/api/v1/world/{status,players,teams,competitions,matches,news,training,search}` + `/world/*` pages (8) | M3 | landed |
| 5–8 | Player profile / archetype / real-vs-user / progression | `/players/{id}`, `/world/players/{ident}`, `/player/[slug]`, `services/attributes.py`, `progression.py` | M1/M3 | landed |
| 9–12 | AI Coach / training academy / progression / plan | `/api/v1/coach/{ask,plan,today,history,drills/{slug}/knowledge}`, `/trainings/{drills,sessions/{id}/complete}`, `/coach`, `/training`, `/training/[slug]` | M2/M1 | landed |
| 13–14 | Video analysis + output | `/api/v1/video/{upload,{id},analyse,file,frames/{i},jobs}`, `/video`, `/video/[id]` | M5 | landed, **vision provider labelled demo** |
| 15 | Match analysis | `/match/[slug]`, `/world/matches`, `sim_events` | M6 | landed |
| 16–18 | Tactical Lab / Tactical AI / Simulator | `/api/v1/tactics*` (6 doors), `/boards*` (5), `/simulate*` (4), 6 `/tactics/*` pages | M4/M6 | landed |
| 19 | Football simulation | `/api/v1/simulate`, `/simulate/{id}/replay`, `services/simulation` | M6 | landed |
| 20 | Career Mode | `/api/v1/careers*` (5), `/career`, `/career/[slug]`, `/career/[slug]/market` | M6 | landed |
| 21 | Manager live challenges | `/api/v1/challenges*` (4), `/challenges`, `/challenges/runs/[slug]` | M6 | landed |
| 22 | Transfer market | `/api/v1/transfers*` (8), `/api/v1/scout/simulate-transfer`, `services/scouting` | M6 | landed |
| 23–24 | AI Scout + report | `/api/v1/scout/{rules,parse,search,report,compare,shortlists*}`, `/scout` | M7 | landed |
| 25–26 | News system + AI news analysis | `/api/v1/world/news`, `/api/v1/world/news/{ident}`, `/news/[slug]`, `/world/news` | M3 | landed |
| 27 | Player analytics | `/api/v1/scout/compare`, `/progress/timeline`, `/history`, `/my-football` | M6/M7 | landed |
| 28 | Football knowledge base | `/api/v1/knowledge/{documents,search,ask,ingest,status}`, `/knowledge`, `/knowledge/[slug]` | M2 | landed |
| 29 | RAG pipeline | `services/knowledge/{ingest,retrieval,answer}.py`, `apps/api/evals/{golden_rag.json,run_rag_eval.py}` (a CI step) | M2 | landed |
| **30** | **Knowledge graph** | **no route, no table, no service.** `grep -rliE 'knowledge_graph|graph_edge' apps/api/app` → 0 files. Only the corpus's *edge vocabulary* in `data/knowledge` prose | **nobody** | **MISSING — no milestone owns it** |
| 31–34 | Football AI agent / multi-agent / complex task / agent memory | `grep -rli agent apps/api/app` → `services/coach_engine.py` only. No `/api/v1/agents`, no orchestrator, no benchmark | M11 | owned, not started |
| 35 | Community (feed, posts, comments, likes, follows) | 0 of those nouns in the route table or the page tree | M9 | owned, not started |
| 36 | Creator system | same | M10 | owned, not started |
| 37 | Gamification | `services/achievements.py`, `progression.py`, `/api/v1/progress/{overview,timeline}`, `/progress` | M1 | landed |
| **38** | **Football career portfolio** (10-section CV, public share link, PDF) | **no route, no page, no service.** `grep -rli portfolio apps/api/app apps/web/app` → 0 files. The data it would summarise all exists (career, scout, club, training, video) | **nobody** | **MISSING — no milestone owns it** |
| 39–41 | Club OS / Youth Academy / B2B | 33 paths under `/api/v1/club*` incl. §48's `fixtures`, `services/club/{organizations,access,answers,academy,sessions,reports,matches}.py`, 5 `/club*` pages | M8 | landing now (§39's Communication noun + fixtures panel open) |
| 42 | Subscription | `usage_events` (migration `0020`), `/api/v1/club/{ident}/entitlements`, `/entitlements/{me,capabilities}`, `services/entitlements.py`; **no price/currency/provider/checkout field anywhere** | M8 (architecture) / M10+ (pricing) | landed as data, payments deliberately absent |

## B. Cross-cutting sections that a reader assumes are done

| § | subject | measured | verdict |
| --- | --- | --- | --- |
| 43–44 | Data/backend architecture | 21 migrations, `scripts/schema_drift.py` gate, `app/models`, layered routers | landed |
| 45–46 | Provider abstraction / model router | `services/model_ledger.py`, `fallback` in `coach_engine.py` + `knowledge/retrieval.py`; no single router door | partial |
| 47 | Async job system | `/api/v1/video/{id}/jobs` + `services/video/{pipeline,status}.py`; in-process, no queue | partial (labelled) |
| 48–57 | Frontend/UX/home/board/match/player/search/mobile | 47 page routes; `visual-qa.mjs` walks 375px surfaces | landed |
| 58–60 | Performance / observability / security | `core/security.py:142 limit(...)`, `logging.basicConfig` in `main.py:43`, ADRs in `docs/adr` (6) | partial — no metrics/tracing surface, M12's job |
| 61–62 | Privacy / AI safety | `DATA_POLICY.md`, `AI_POLICY.md` at repo root, `/progress/export`, `/progress/player-data`; **account-level erasure is not built** | open → M12 |
| 63–64 | Testing / agent evaluation | 29 test files, both database legs; `evals/` covers **RAG only**, §64's agent benchmark does not exist | partial → M11 |
| 65 | Demo data | world generator incl. the 100-training-session gate item | landed |
| 75–80 | Event model, cost control, provider failure, citations, SEO | `sim_events`, `model_ledger`, refusal paths, `docs/SEO_VERIFICATION.md` | landed |
| 81 | Internationalization | `en`-only copy; a `country="en"` argument in the club tier, no message catalogue | open |

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

**Proposed assignment** (to write into `ROADMAP.md` once M8 closes): §30 → M11, because §33's composite agent task
and §64's benchmark are exactly what a graph hop is measured against; §38 → M10 (creator/portfolio surface), with
the minors' slice held back until §40's consent shape is read rather than duplicated. Neither may be started while
M9 is open, since §35's permission layer is what a public portfolio link would otherwise bypass.
