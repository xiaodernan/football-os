# ROADMAP — FOOTBALL OS

Rule (spec §96): no milestone opens until the previous one is *running, tested and visually verified*. Current gate status is maintained in this file.

| Milestone | Scope | Gate | Status |
| --- | --- | --- | --- |
| **M0 Foundation** | monorepo, git, CI, docs+ADRs, design system, Next.js, FastAPI, Postgres/pgvector compose, auth foundation, provider abstraction, health checks | both apps build, tests green, login works | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M1 Player + AI Coach vertical slice** | Create user → create player → profile → training → completion → AI Coach → progress → history | closed loop usable in browser with real persistence | ✅ verified 2026-09-21 ([evidence](docs/M0_M1_VERIFICATION.md)) |
| **M2 Football Knowledge + RAG** | ingestion, chunking, embeddings, pgvector hybrid retrieval, rerank, citations, Football AI | answers carry resolvable source citations | ✅ verified 2026-09-21 ([evidence](docs/M2_VERIFICATION.md)) |
| **M3 Football World** | RealPlayer/Team/Competition/Match/Stats/News + unified search + SEO routes | 20 teams / 300 players / 130 matches / 500 articles synthetic world, public pages for all five entities | ✅ verified 2026-09-22 ([backend](docs/M3_VERIFICATION.md) · [web surface](docs/M3_WEB_VERIFICATION.md)) — world 3.2 (2026-09-23) added the sixth §65 gate item, 100 training sessions, browsed at `/world/training` |
| **M4 Tactical Lab** | interactive board, formations, in/out possession, roles, animation, AI tactical analysis | 50 tactical systems + drag/draw/save/share + analysis with evidence | ✅ verified 2026-09-22 ([backend](docs/M4_VERIFICATION.md) · [web](docs/M4_WEB_VERIFICATION.md)) — analysis cites the corpus for 6 of 6 topics on all 50 systems (2 were refused until the corpus gained the missing passages); 3D pitch and board sharing beyond one owner are open follow-ups |
| **M5 Video Analysis** | upload → storage → transcode job → frame extraction → vision provider → events → report | demo vision provider behind real interface | ✅ verified 2026-09-22 ([pipeline](docs/M5_VERIFICATION.md) · [web](docs/M5_WEB_VERIFICATION.md)) — upload, report, detection timeline and owner-only byte-range playback proven in the browser |
| **M6 Football Simulation** | simulation engine, Career Mode, manager challenges, squad/training/finance | results labelled fictional; engine deterministic-testable | 🟡 in progress — engine, `/simulate`, the §65 training log, **Career Mode including its page**, **manager live challenges including their page**, the **§22 transfer market including its page** and the **§20 squad carry-over including its panel**, the **stored timeline (`sim_events`, its rows re-read by the report page)** and the **season ledger summed from those rows across a career's fixtures** ([engine+career backend](docs/M6_VERIFICATION.md) §10–§11 · [market backend](docs/M6_VERIFICATION.md) §14 — the market · [simulator+log](docs/M6_WEB_VERIFICATION.md) · [career web](docs/M6_CAREER_WEB_VERIFICATION.md) · [challenge web](docs/M6_CHALLENGES_WEB_VERIFICATION.md) · [carry-over](docs/M6_CARRY_OVER_VERIFICATION.md) · [timeline rows](docs/M6_SIM_EVENTS_VERIFICATION.md) · [season ledger](docs/M6_SIM_LEDGER_VERIFICATION.md)); 226/226 walk checks on a production build 2026-09-24, 45/45 on the §20 carry walk, 29/29 on the `sim_events` timeline walk and 39/39 on the ledger walk the same day, 498 API tests on both engines — what is outstanding is the §23 AI Scout, which is M7's own subject |
| **M7 Scouting + Recruitment** | scout search, shortlists, comparison, AI scout reports, transfer market | structured reports with role/team fit + risk | ✅ complete — the **§23 AI Scout API tier** landed: a requirements vocabulary that refuses what it does not know, a sentence parser that leaves nothing unaccounted for, and a search that cuts the stored pool one stated phrase at a time and publishes every cut ([evidence](docs/M7_SCOUT_VERIFICATION.md)); `/api/v1/scout/{rules,parse,search}` with 100 test items on both engines. The §22 market also landed early inside M6, so `GET /api/v1/transfers/rules` and a career's need/fit/budget arithmetic are already the published numbers the scout reasons over. **§24's report** (thirteen fields, every figure recomputed from the row it reports on), **§27's player comparison** (ten dimensions, 47 measures, and no composite score by construction) and the **`/scout` page** that renders search, report and comparison alike are now landed too ([report evidence](docs/M7_SCOUT_REPORT_VERIFICATION.md) · [comparison evidence](docs/M7_PLAYER_COMPARISON_VERIFICATION.md) · [web walk](docs/M7_SCOUT_WEB_VERIFICATION.md)): **233 scout test items on both engines**, 68/68 walk checks on a production build 2026-09-25, and six defects planted one at a time over the report module — five caught by the suite as written, the sixth (`>= 4` raised to `>= 9` in a risk threshold) caught only after that boundary was swept rather than sampled. **§23's 建立 shortlist landed too**: migration `0015`, two tables that store membership and the manager's own words and *no figure about a player*, seven routes under `/api/v1/scout/shortlists`, a re-check of the stored sentence on every read, and the panel on `/scout` that walks 97/97 checks on a production build ([shortlist evidence](docs/M7_SHORTLIST_VERIFICATION.md)). M7's last verb landed with it: **the transfer simulation** — `POST /api/v1/scout/simulate-transfer` prices a signing against the career's balance *and* its standing wage bill, rebuilds the eleven with and without him through the selector the engine plays, and replays each future fixture **twice at the same seed**, writing no row of any kind ([evidence](docs/M7_TRANSFER_SIM_VERIFICATION.md)). **M7 is complete**: Scout, Search, Shortlist, Player comparison, AI Scout and Transfer simulation from the spec's list — 814 items green on both database legs, 124/124 walk checks on a production build, 12 defects planted across the report and simulation modules with every one now turned red by a test, and the contract regenerated at 91 paths / 106 operations |
| **M8 Club OS / Academy** | organisations, teams, coaches, IDP, curriculum, permissions, multi-tenant | B2B tenant isolation proven | ✅ verified 2026-09-28 — **§39's and §41's storage tier landed**: four tables, six roles over twelve permissions published as code rather than copied as rows, thirteen doors under `/api/v1/club`, and isolation proved at **every** door that names a tenant (fourteen, derived from the route table, knocked on by a stranger and by a director of another tenant in both address forms) — the walk that found and closed a live enumeration hole at `POST /club/{id}/accept` ([evidence](docs/M8_CLUB_OS_VERIFICATION.md)): **113 items in §39's own file on both database legs**, twelve planted defects with every one now turned red, and the contract at 104 paths / 124 operations *at that step* — 116 / 143 after §40 landed below. **§41's `Sessions` and `Reports` landed** (`club_reports`, migration `0018`/`0019`: the first with a derived load printed beside the two columns it comes from, the second storing a question and no answer at all — every figure re-summed at read time and scoped to whoever reads it; 29 tests across the two tiers, the club suite at **240 items green on both legs** and the whole API suite at **1063 passed + 1 skipped on each leg** (SQLite 408s, PostgreSQL 561s), the contract at **120 paths / 151 operations** and 16 academy paths, and the isolation walk over **41** doors that name a tenant (14 §39, 18 §40, 8 §41's session and report doors, 1 §42's tenant-meter door — counted from the route table by the suite itself, not by this row)) (`club_sessions`, migration `0018`, four doors, 16 tests: load derived from the row's own minutes and rpe, attendance bounded by the sheet, a child present needing §40's consent, a future date refused, a guardian scoped to their own child's log) — **§42's entitlement architecture landed as data:** `usage_events` (migration `0020`) records one row per act with the period in the key, the ceiling is read from `entitlements` rather than a constant, an exceeded ceiling is a 409 that prints plan/used/limit, and only `reports_saved` is enforced by a door today — the rest is published as `published_not_enforced` because a ceiling nothing refuses on is data, not a rule. No price, currency, provider or checkout field exists anywhere in the payload. **Only §42's payments remain: nothing in this tier takes money, and §39's `Matches` row is still a sentence in `limitations()` rather than a table** *(written at §42's step; `Matches` has since landed as migration `0021` and the notice board has since landed as a page, both described below, so the one clause of this sentence still standing is the payments one)*. **The club tier's web surface landed on top of it** — `/club`, `/club/rules`, `/club/{ident}` and `/club/{ident}/plans/{plan}`, walked end to end in a browser against a production build ([evidence](docs/M8_CLUB_WEB_VERIFICATION.md)): **194/194 checks**, §40's order witnessed as refusals rather than empty tables, the progress arithmetic re-derived from the review rows the page itself printed, and both database answers compared with the door's HTTP status. That run found two more live defects in code this milestone had already called finished, and closed them: `GET …/plans` answered a guardian with a different key set than it answers staff, which turned the tenant page into a **500** for the members §40 exists to serve (one door, one shape, held from both sides by a test), and the plan page printed a caller-relative withheld count under the words "withheld from the guardian", so a coach who had hidden a note from the family was told none were. **§40's academy tier landed on top of it the same day** ([evidence](docs/M8_ACADEMY_VERIFICATION.md)): twelve further paths / nineteen operations under `/club/academy` — the contract regenerated at **122 paths / 153 operations** *at that step* — §42's tenant-meter door is the path and operation it does not count, and the file now measures **123 paths / 154 operations**, 30 of them under `/api/v1/club` and 16 of those under `/club/academy`, six tables whose **published column list is the minimisation rule** (69 columns, asserted equal to the live schema), a guardian's consent row that is at once the gate, the scope ceiling, the record and the erasure anchor, thirty-six refusal codes with 403 still reserved for §39's single `insufficient_role`, and §39's isolation walk extended to all **36** doors that name a tenant (14 §39, 18 §40, 4 §41). The run found three live product defects and closed them: a role refusal that answered 500, a staff account able to mint a guardian's yes, and a cadence figure that could not report itself behind; the whole suite stands at **1010 items plus 1 skipped, green on both database legs** (SQLite 640s, PostgreSQL 668s, measured 2026-09-26) **at §42's step**; the suite now measures **1072 passed + 1 skipped, collected as 1073 items across 29 files, green on both legs again** (SQLite 1813.58s, PostgreSQL + pgvector 1562.41s, both `rc=0`), the club tier's five files standing at **258 items green in 558.98s** of it (§47's web tier, §42's meter and §41's reports being what those five files now knock on). **§51 then made one refusal code mean one HTTP answer at every club door**: `services/club/answers.py` assembles the single table from each tier's own four code sets and raises at import when two tiers register one code with two statuses, so a new tier appends its module to `TIERS` instead of editing a literal in a router, and the two codes that had been double-claimed were renamed payload-visibly (§41's `unknown_report_kind`, §42's `no_such_entitlement_plan`) with the contract unmoved at 123 paths / 154 operations. Measured on that commit 2026-09-27: **1159 items collected, 1157 passed + 2 skipped + 0 failed on both database legs** (per-run SQLite 2278.85s, PostgreSQL + pgvector 1198.56s, each `rc=0`), both skips named from `-rs` rather than counted, and the planted defect the pass exists to prevent was probed both ways — unregistering either renamed code turns 2 and 3 assertions red with a door's own HTTP answer among them, and the same slice run unmutated is green ([evidence](docs/M8_CLUB_OS_VERIFICATION.md) §9 and §10) **§39's last noun, `Matches`, landed on top of it** (`club_fixtures` + `club_match_appearances`, migration `0021`, five doors, three new permissions — the matrix is 20 over six roles, and §7's table had been stale at twelve): a fixture is arranged against a club in the generated world and played through the same engine every other match row uses, with the tenant's own sheet applied as a squad overlay over the world club its team is bound to, so the eleven that played is this tenant's eleven and appearance rows exist only while the eleven rebuilt from its rows is the eleven the stored report names — the scoreline, the timeline and every counted figure staying in `sim_matches`/`sim_events`, with a pointer, a slug and a digest here. The contract moved from 123 paths / 154 operations to **126 / 159**, the isolation walk now knocks on **46** doors that name a tenant, and `0021` was checked against a fresh database by `alembic check` (no new operations) and `schema_drift.py` (442 fixed-width columns, 0 narrower, 0 wider, 0 absent). Whole suite over `06de944`, both `rc=0`: **1192 passed + 1 skipped in 3229.89s** on per-run SQLite and **1192 passed + 1 skipped in 2626.82s** on PostgreSQL + pgvector, the one skip named from the printed line and the fall from two skips to one explained rather than celebrated. §48's planted-defect probe then caught what reading could not: five of eight arms red over that commit, and two of the three survivors were coverage wearing a different hat — a fielding gate that had never been knocked at its own boundary (the only small-side case names five of eleven), and an attribution rule no case reached at all. Both closed in `99a94ee` with a seam and four cases; re-measured over that commit as eleven arms behind an unmutated control (`rc=0`, 0 red), **10 of 11 turned the suite red**, the sole survivor being the 200-fixture cap that is held from the other side by the count the listing prints. The six club files over `99a94ee`: **368 passed in 1568.02s**. The two whole-suite legs are printed over the docs commit `5e01714` and both are `rc=0` — **1196 passed + 1 skipped in 1958.79s** on per-run SQLite, **1196 passed + 1 skipped in 1531.97s** on PostgreSQL + pgvector, 1196 being 1192 plus §48's four new cases — §39's fixtures panel then landed on the web tier — `/club/{ident}` arranges, plays and erases through its own controls, and the walk that proves it is **215/215 checks, exit 0** against a production build ([evidence](docs/M8_CLUB_WEB_VERIFICATION.md)): the side list, the ceiling, the block lengths and the eleven-and-a-keeper counts are each compared with what `fixture_caps` publishes rather than with a number typed in TSX, the date field opens on the day the door calls `today`, three refusals are held to be *not writes* (an absent club 404, a future day 422, an unplaced side `no_world_side`), the appearances column is summed in the browser before it is believed, and the erase repaints the table to its own empty sentence. What the walk does not claim is a successful play — that needs an eleven of adults placed in the ladder and is held by §48's suite, and the page says so in one line. **§49 and §50 then closed the two figures the session tier kept twice**: the attendance ceiling is now one constant that publishes the cap, applies the guard and refuses with the same number, held at its own boundary by four new cases, and the web form's five invented fallbacks are gone — `limits` is a required prop, both forms are gated on the rulebook door answering, and the page prints the door's own sentence for `load_units` rather than paraphrasing it. Measured over `22374b4`: whole suite **1200 passed + 1 skipped on both legs** (per-run SQLite 770.91s, PostgreSQL + pgvector 1066.11s, each `rc=0`), the planted-drift probe run as three arms behind an unmutated control with **every arm reddening the assertion named for it**, and the recorder panel's walk re-run at **217/217 checks, exit 0**. That probe's first pass printed inflated catch counts, and §11 of the evidence document withdraws those figures and names the two harness flaws that produced them. §57 wrote that noun as a board rather than a message: a notice is posted to an audience and no row stores a recipient, so `recipients`, `read_by` and `unread` are counted from the tenant's active memberships on every read (`docs/M8_CLUB_OS_VERIFICATION.md` §12). Measured over `cdd15b3`: nineteen new cases, the club group 372 + 1 red whose single failure was this run's own three-rights pin, `mypy` clean over 98 source files, the contract 126/159 → 129/164 additive, `alembic` at 0022 with `check` silent, and the SQLite leg 1229 passed + 1 skipped in 2051.13s — which is 1200 + 19 + 10 with both addends named. The PostgreSQL leg over the same commit printed **1229 passed + 1 skipped in 4818.22s, `rc=0`**, the same total and the same single named skip as the SQLite leg, so both legs agree on the same arithmetic. §39's four nouns now each have a storage tier, and the last of them has a page: `NoticeBoard` mounted on `/club/{ident}` over `b81e42d` as that tenant page's fourth write panel, walked at **252/252 checks, exit 0** on a production build the run attributed to itself by the `BUILD_ID` in the HTML it served, on ports it verified had no listening socket and against a database `scripts/qa_db.py` created for the run ([evidence](docs/M8_CLUB_WEB_VERIFICATION.md) §39's section) — the audience list, the two length ceilings and the pin ceiling all come from `announcement_caps`, `unread` is re-subtracted in the browser from the two figures printed on the same row, a second read is proved to be the same one receipt row by the door's own `already recorded`/`recorded_now: false` rather than by the page's note, no recipient-shaped key appears anywhere in the payload, and the guardian's rights pin moved to **four** and names `announce.read` — the re-count §57 had already made in the API suite. That run's first pass was 244/250, and all six reds were the walk's assumptions: three controls pressed inside rows the page had not repainted, two demanding that a repeat write change a note it cannot repaint, and one reversed-window case that had never knocked on its own boundary because navigating the filter remounts the form and only one of its two dates was being typed. §57's own probe then deleted each of its three load-bearing decisions in turn, over the two classes that answer them and behind an unmutated control that was green first (**170 passed in 272.45s, `rc=0`**): **three arms, none survived** — the ceiling guard 1 case red, the readership denominator 1, the staff audience predicate 3, each named from the runner's own line, with the target returned byte-identical (`sha256 72d95e87…`, `git status` clean). Its one defect was its own: the population line printed `170403` because the parser took every digit on pytest's `170 tests collected in 40.32s`, so the fraction above counts out of the control's measured 170 and §12 names the flaw instead of quietly re-running for a prettier number ([evidence](docs/M8_CLUB_OS_VERIFICATION.md) §12). **What is left of this milestone is §42's payments** — nothing in this tier takes money, and no currency, provider or checkout field exists anywhere in the project (the prices that do exist — §22's `transfer_listings.current_price` and the meter's USD-per-token rates — are a valuation and a cost measure, not a payment). |
| **M9 Community** | feed, posts, comments, likes, follows, shared boards/plans | creator→content→feedback loop | 🟡 in progress — **§35 landed as a tier, its doors and its page**: five `community_*` tables (migration `0023`) whose one rule is that **a post stores a kind, a pointer and the author's words, and no figure about the thing it shares** — `likes`, `comments`, `reposts`, `followers`, `following` and `feed_total` are `count(*)` over the reaction, comment, repost and follow rows at the moment of the read, each printed beside its own formula, and reach is a predicate over follows so an unfollow withdraws it at once and deletes nothing ([evidence](docs/M9_COMMUNITY_VERIFICATION.md)). A reaction, a repost and a follow are one row per pair **by unique constraint**, which the suite violates on purpose through the model rather than trusting the door to have checked. Twelve doors over eight paths, eleven of them private, and **no 403 anywhere in the tier**: what a caller may not reach is answered as absence with the same shape a row never written earns. Registered in the project's one answer table by appending the tier to `TIERS` — which is what surfaced a real collision the collision check cannot see: the first draft published `no_such_member`, already §39's sentence for "no standing in this tenant", and both answer 404, so it is now `no_such_account` and a case holds this tier's thirteen codes against every other registered tier's published set. Measured 2026-09-28: `tests/test_community.py` **45 passed in 10.31s**, `tests/test_club_answers.py` **86 passed in 2.37s**, `mypy` clean over **101 source files**, `ruff check .` clean, `alembic upgrade head` at `0023` with `check` silent on a scratch database, the contract **129 paths / 164 operations → 137 / 176** with the diff **653 insertions / 0 deletions** (exported from this tree on its own port, never the shared dev API), `tsc --noEmit` and `next build` both rc=0, and `/community` walked in Chrome at **38 of 38 checks, exit 0** on that production build, attributed by the `BUILD_ID` its own HTML carries, with both accounts in separate browser contexts. The walk found two defects in the page rather than the tier and both were closed here: the panel called `browserFetch` without naming a verb and that helper defaults to GET — a GET with a body is a fetch the browser refuses, so **every write the page pressed failed inside the client while the API suite stayed green** (first walk 20/37) — and a row-scoped note cannot survive the unfollow or erase that unmounts its row, so the note now carries the facts the door answered with and the wall keeps its own copy. The whole-suite SQLite leg, read out of its own `--junitxml` report: **1275 tests, 0 failures, 0 errors, 1 skipped, `rc=0`, junit 633.98s / wrapper wall 638.44s** — 45 of them `tests/test_community.py` and 1230 in the other 163 files, where §57 had recorded 1229, so **one case in the rest of the suite is unattributed and named as such** (task #65; two hypotheses measured and rejected). An earlier leg over the same commit printed `rc=0` and no summary line — the third time a bash redirect swallowed pytest's last line, which is why every leg now carries `--junitxml` — and the prediction written before it (1229 + 45 = 1274) missed by one and is recorded as a wrong prediction, not a figure — **closed 2026-09-29 by task #65**:
`pytest --collect-only -q` run in a detached worktree at `cdd15b3` (after asserting `app.__file__` resolves inside
that worktree) collects **1230 cases over 32 modules**, and §35's own leg report counts the same **1230 over the same
32**, module for module, the only difference in the whole comparison being `test_community.py` **0 → 45**. So §57's
**1229** was that 1230 minus its one named skip and no enumeration ever gained a case; the prediction's real error was
comparing a *passed* count with a *collected* one. The PostgreSQL leg over the same code printed the identical figures — **1275 / 0 failures / 0 errors / 1 skipped, `rc=0`, junit 1323.95s** (wrapper wall 1326.76s) — so both engines agree on 45 + 1230. §35's mutation probe then ran **four arms over its four load-bearing decisions, behind an unmutated control (`rc=0`, 0 red): 0 survived**, each arm turning exactly the case its written-down prediction named (A 1, B 2, C 2, D 1 red), with the target returned byte-identical (`restored=True`) and arm C's two untouched branches reported as partial coverage rather than as catches. Outstanding: §35's remaining product verbs, and §35's remaining product verbs — moderation, reporting and blocking are not in this build. |
| **M10 Creator Economy** | creator profiles, programs, guides, entitlement/pricing architecture | no payment vendor required to demo | 🟡 in progress — **§36's creator system landed 2026-09-28**: three tables behind migration `0024` (`creator_profiles`, `creator_guides`, `guide_citations`), and **its first four content objects landed 2026-10-21** — `creator_programs` and `creator_program_steps` behind migration `0030`, five doors under the same prefix (a schedule, a dose and a progression, runnable because every step names a catalogue drill), `creator_tactical_guides` behind migration `0031`, four doors (an address into the tactics catalogue, with every measurement recomputed on the read and `moved` when the board has changed), `creator_player_analyses` behind migration `0032`, four doors (an address into the generated world, its five rates computed from the player row's own columns on the read, and `moved` when the player has been refreshed), and `creator_match_analyses` behind migration `0033`, four doors (an address into the generated fixture list, its five measurements computed from the fixture row's own score and stats on the read, `moved` when the fixture has been revised, and an unplayed fixture refused at publication rather than read as a blank result), and no 403 anywhere in the tier; the tier's present census is the one §36's row in `docs/SPEC_COVERAGE_AUDIT.md` publishes and `tests/test_spec_audit_currency.py` recomputes against the committed contract, and `/creator` is the page that publishes a profile, writes a guide and cites the corpus by address ([evidence](docs/M10_CREATOR_VERIFICATION.md)). A guide stores a title, a frame and *addresses*: `citations`, `moved`, `tokens`, `guides` and `subscribers` are recomputed on every read from the rows their formulas name, a citation keys on `(document, ordinal)` plus the hash that sat there, and reach is §35's own follow predicate — so an unfollow withdraws a guide at once and deletes nothing. `creator_publish` and `creator_guide` joined §42's table as rows the data holds and **no door refuses on** yet (`ENFORCED` is still exactly `['reports_saved']`). Measured 2026-09-28: `tests/test_creator.py` + `tests/test_entitlements.py` **50 passed / 0 failures / 0 errors / 0 skipped in 23.84s** (junit), `mypy app` clean over **104 source files**, `ruff` clean, `alembic upgrade head` at `0024` with `check` silent on a scratch database, the contract at **144 paths / 187 operations** (7 paths / 11 operations this tier's), and `tsc --noEmit` with `NEXT_DIST_DIR=.next-ci next build` both rc=0. Also corrected here: `/community` and `/creator` were missing from `robots.ts`'s disallow list while every other session-gated prefix was in it (`3df6496`). **Corrected 2026-09-29 while §38's page was being measured**, because two clauses of this row were already false: `ab2d4c8` had landed `scripts/qa-creator.mjs` at **56 of 56 checks, exit 0** (so `/creator` does have a walk), and `471da30` had landed §38's CV assembler, its two doors and **14** cases (so §38 was not "not started"). **§38's browser half has now landed on top of that** — `/portfolio` ([evidence](docs/M10_PORTFOLIO_VERIFICATION.md)) paints the ten sections in §38's own order, holds every painted figure cell against the value the same door answered with (**0 disagreements over both reads**), prints `Matches` and `Stats` with the reason and the tables they would need and **not one figure cell**, and re-reads from the rows, so the filled count moves **0 → 3** when §7's door mints a player row. Measured 2026-09-29: `tsc --noEmit` rc=0 over an output file of **0 lines**, `next build` rc=0, `npm run lint` rc=0, `pytest tests/test_portfolio.py tests/test_community.py tests/test_creator.py` **96 tests / 0 failures / 0 errors / 0 skipped in 23.153s** (the three files that walk `apps/web/app/**/page.tsx`, so a new route is a change they can refuse), and `QA_BASE=http://127.0.0.1:3218 node scripts/qa-portfolio.mjs` at **37 of 37 checks, exit 0** — 0 console errors, 6 recorded knocks answering only 200/201/401/404, `scrollWidth - innerWidth = 0px` at 375, 95 payload keys walked with **0** money-shaped ones. **Now recorded**: both whole-suite legs ran over `031a3c1` and each wrote its own result line into
`.scratch/leg_p38_summary.txt` — **sqlite rc=0, 1326 tests / 0 failures / 0 errors / 1 skip, 1067.045s junit over
1069.88s wall**, and **postgres rc=0, the same 1326 / 0 / 0 / 1, 3005.326s junit over 3072.96s wall**. The runner's
docstring holds the population predicted before the run (§36's 1293 + 19 creator-door cases + §38's 14 CV cases =
1326), and both engines measured exactly that; the addends were then re-read from the runs' junit reports, not from
the arithmetic. **§38's share output then landed, at the API tier** (measured 2026-09-29): one table `cv_shares` behind
migration `0025`, `services/portfolio/sharing.py`, and four doors so `/portfolio` declares **6** (five private, one
that answers with no session). The sharing tier joined `answers.TIERS`, which is what gives its four codes a status
instead of a 400 fall-through — `no_such_share` 404, `section_unknown` 422, `minor_section_blocked` 422,
`share_already_revoked` 409, and no 403. **All three of §38's permitted public outputs now name a door** — the public
player profile and the share link are the same read, `GET /portfolio/share/{token}`, a subtraction of the private CV
rather than a second assembler, while `GET /portfolio/cv.pdf` renders that same live read as an owner-authenticated
download. Measured over the bytes this row describes:
`pytest tests/test_portfolio_share.py tests/test_portfolio.py` **38 tests / 0 failures / 0 errors / 0 skipped, rc=0**
(24 new + §38's 14 re-run, because one of their claims went stale the moment the tier grew a second door);
`alembic upgrade head` rc=0 through `0024 -> 0025` and `alembic check` rc=0 saying `No new upgrade operations detected`
on a scratch database; `mypy app` clean over **108** source files; `ruff check app tests` rc=0 — its first pass found
**1** error, an unsorted import block of mine, fixed and then re-measured rather than quoted forward; the contract at
**149 paths / 193 operations / 63 schemas** with a **169 added / 1 deleted** diff whose single deletion is the reworded
rules-door sentence; and a **6-arm planted-defect probe at SURVIVORS=0**, control 24/0 before and after every restore,
each arm's red set equal to the set written into the script beforehand. The slice's first run turned up one production
defect — `section_unknown` was unreachable because the ordering helper cleaned the name before the validator saw it,
so asking for `wallet` minted a link instead of refusing — and five reds that were the test file's own fault, recorded
in `docs/M10_PORTFOLIO_VERIFICATION.md` with the two probe notes (an arm that crashes the runner reports reds that
prove nothing; a census reading the constant under test goes vacuous when that constant is emptied). **§38's browser
share surface then landed** (measured 2026-09-29): `/portfolio` now has a section selector and open/copy/close
controls, and `/portfolio/shared/{token}` renders only the published sections from the same live read. A browser with
no session opened the link, the payload carried **no** `user_id`, `email`, `display_name`, `account`, `id` or
`visibility` key, an unpublished section was named only as withheld, and revoking the token made both the JSON door
and the HTML page answer **404**. Measured on the production plane: `tsc --noEmit` rc=0, `npm run lint` rc=0,
`next build` rc=0 (`BUILD_ID` `EgWRUtYWNBIJkxIShsf8X`), and `QA_BASE=http://127.0.0.1:3219 node
scripts/qa-portfolio.mjs` at **51/51 checks, exit 0**, **4** screenshots, **10** recorded knocks and **0** console
errors. **§38's PDF output then landed** (measured 2026-09-29, **and re-read 2026-10-04 over `862359e`: the sentence
below describes a working copy, not this repository — `git log -- apps/api/app/services/portfolio/pdf.py` answers no
commit, the committed contract has no PDF door, HEAD's `apps/api/requirements.txt` names no renderer, and
`PUBLIC_OUTPUTS["pdf"]` still starts "not in this build"; every figure in this paragraph therefore stands as a
measurement of bytes that are not committed here**): `services/portfolio/pdf.py` renders the live
`build_cv` result in memory with ReportLab, `GET /portfolio/cv.pdf` is owner-authenticated and rate-limited, and the
Next proxy forwards `content-disposition`/`cache-control`, so the `/portfolio` download control returns a real
non-cached document. `/portfolio` now declares **7 doors**; the focused portfolio pair collected **40 cases** and
exited **0**, `ruff` and `mypy` were clean, the contract is **150 paths / 194 operations / 63 schemas**, and the
production walk passed **53/53 checks, exit 0** with **4** screenshots, **11** door knocks, **0** console errors and
a **38,769-byte** PDF carrying **10/10** section titles (`BUILD_ID` `qFs0RdZcehJ5lv9ZjqWXr`). The PDF route adds no
table and opens no share row; public PDF delivery through a share token is deliberately not enabled. **Still not
claimed**: the whole-suite legs over these bytes; the prediction written before that run is §38's recorded **1326**
plus the share slice's **24** = **1350**, and that figure is now measured on the collection plane — `pytest
--collect-only -q` in a detached worktree at `e008ac3` (with `app.__file__` asserted inside the worktree first)
collects **1350 cases over 36 test modules** — while pass/fail, the skip count and each leg's `rc` are still owed to
the two legs. |
| **M11 Multi-Agent Football AI** | orchestrator + research/data/tactical/training/scout/video/simulation/coach agents, agent memory | spec §33 and §87 composite tasks succeed on benchmark | ✅ verified 2026-10-20 — **§34 agent memory landed 2026-10-06**: `AgentMemory` model with UUID IDs via `new_public_id("am")`, migration `0026`, service layer (`set_memory`/`get_memory`/`list_memories`/`delete_memory`/`prune_expired`), API tier (**4 paths / 4 operations** under `/api/v1/agents/memory`: set/get/list/delete), TTL-based expiration with timezone-aware datetime comparison for SQLite compatibility, **8 passing tests** covering CRUD + TTL behavior. **§31-§33 agent orchestrator landed 2026-10-06**: BaseAgent abstract class with remember/recall/list_context helpers; **ResearchAgent** queries RAG pipeline and caches answers (24h TTL); **CoachAgent** analyzes player profile + goals and recommends training sessions (7-day goal memory); **TacticalAgent** queries tactical_systems table for formation analysis, pressing/width/depth comparisons, and tactical concept explanations (7-day cache); **ScoutAgent** parses natural language scouting requirements and searches RealPlayer database via waterfall filter pipeline, returning ranked candidates with market valuations (7-day cache); **SimulationAgent** explains the deterministic possession-block-v1 match engine, xG modeling, pressing mechanics, card/injury rates, and what the engine deliberately does NOT model using published coefficients from simulation.engine module (7-day cache); **VideoAgent** explains the video analysis pipeline (upload validation → probe → frame sampling → detection → event extraction → report), documents demo vision provider limitations, and guides users on interpreting computer vision results (7-day cache). Factory function instantiates agents by type from registry. Orchestrator API: **4 paths / 4 operations** under `/api/v1/agents` (list/run/context/**composite**), all auth-gated via current_user, memories persisted via db.commit() after agent.run(), **27 passing tests**. **§33 composite tasks landed**: POST `/api/v1/agents/composite` automatically routes complex multi-domain queries to relevant agents based on keyword detection, executes them sequentially, aggregates results with step-by-step traceability, and computes overall confidence. **§64's benchmark landed 2026-10-07** (27 golden cases, 5 metrics plus the `trace_integrity` this row's last landing added, 9 gating cases) and **§33's stored trace landed 2026-10-20**: `services/agents/traces.py` stores every composite run on §34's own tier (`agent_memories`, agent type `orchestrator`, `trace:` prefix, 30-day TTL), the answer carries `trace_id`, and **2 new paths** (`GET /agents/traces`, `GET /agents/traces/{trace_id}`) read it back — a foreign or never-issued id answers the same 404, and a run where every step failed is still traced; `trace_integrity` (the share of composite runs whose stored trace replays the steps the answer named) measures **1.0** against a gate of 1.0. OpenAPI contract regenerated at **187 paths / 236 operations / 83 schemas** ([evidence](docs/M11_AGENT_TRACE_VERIFICATION.md)) |
| **M12 Production hardening** | security, performance, observability, cost, caching, rate limits, governance, backup/DR | load + pen test report clean; **account-level erasure implemented** (today only player data is deletable — `DATA_POLICY.md` §3) | ⬜ |

## M0 exit criteria (verified)

- [x] `git init`, `.gitignore`, no secrets tracked
- [x] `PROJECT_AUDIT.md`, `ARCHITECTURE.md`, `ROADMAP.md`, `ADR/*`, `SECURITY.md`, `DATA_POLICY.md`, `AI_POLICY.md`, `CONTRIBUTING.md`
- [x] FastAPI boots, `/healthz`, `/api/v1/*` OpenAPI available, migrations run
- [x] Next.js builds, design system tokens present, dark premium shell renders
- [x] Auth foundation: register, login, JWT, RBAC guard
- [x] Provider abstraction with DEMO MODE fallback that self-labels
- [x] CI workflow (install → lint → test → build)
- [x] Docker Postgres + pgvector verified on this host: compose healthy, `alembic upgrade head` + `alembic check` (no drift), 21 tables, `vector` extension, and the full pytest suite green against it — see `docs/M0_M1_VERIFICATION.md` §1.3–1.5

## M1 exit criteria (the first real FOOTBALL OS loop)

1. register → 2. create UserPlayer (position, age, level, foot, goal) → 3. derive archetype + attributes (explainable) → 4. player card renders → 5. ask Coach "What should I train today?" → 6. session created from training catalogue with objective/setup/coaching points/mistakes/progression/test → 7. complete session with self-rated execution → 8. XP awarded with reason + attribute delta with reason → 9. progress page shows level/streak/skill curves → 10. history page lists every session with its evidence → 11. coach follow-up message reflects the new state → 12. API + engine tests green → 13. screenshots captured on desktop + mobile viewport.

All 13 are verified: `docs/M0_M1_VERIFICATION.md` §2 maps each one to a passing check in
`apps/web/scripts/visual-qa.mjs` (34/34 browser assertions, 19 PNGs captured to `docs/screenshots/`) plus the
23-test API/engine suite on SQLite and PostgreSQL.

## Now → next session

**M3 Football World — done.** Backend evidence in [`docs/M3_VERIFICATION.md`](docs/M3_VERIFICATION.md), web-surface
evidence in [`docs/M3_WEB_VERIFICATION.md`](docs/M3_WEB_VERIFICATION.md).

Backend (verified 2026-09-21):

1. [x] seven tables + `0003_football_world` migration, `alembic upgrade head` and `alembic check` clean on pgvector
2. [x] seeded deterministic generator (`WorldRng` → `plan_world(seed)` → identical `fingerprint()`), fictional name tables, no scraped or licensed material
3. [x] idempotent sync: upsert by natural key, schema-fit validation before insert, second pass reports `changed=0`, deletions cascade with 0 orphan links
4. [x] 500-article newsroom that only quotes numbers present in the stat tables, `claim_class` separating fact / analysis / speculation, desk bylines and `source_name='synthetic-world'`
5. [x] one unified search over all five entity types, explainable ranking, per-hit path + provenance
6. [x] 12 public `/api/v1/world/*` routes registered and live, `GET /capabilities` reporting `m3_football_world` from the data rather than the code
7. [x] 41 world tests, 89 total, green on SQLite **and** PostgreSQL+pgvector; ruff + mypy clean; `docs/api/openapi.json` regenerated (40 paths / 44 operations)

Web surface (verified 2026-09-22):

1. [x] `/team/{slug}`, `/player/{slug}`, `/match/{slug}`, `/competition/{slug}`, `/news/{slug}` mounted at the exact §80 paths the API hands out — pages link through `path` fields, never by rebuilding a URL
2. [x] a world index (counted contents + §65 gate state) and the unified search page, both public and JS-free
3. [x] `sitemap.ts` gained those entries in the same commit: 983 `<loc>` values, asserted to match the API's own per-table counts, each answering 200
4. [x] `DEMO DATA` badging driven by each row's own `data_origin`/`is_demo_data` + the API disclaimer, and an explicit "no score yet" state for scheduled fixtures
5. [x] `visual-qa.mjs` extended with 42 world assertions and screenshots at 1440px and 375px against a production build (110/110)
6. [x] structured data per entity: `Dataset`, `SportsOrganization`, `SportsTeam`, `Athlete`, `SportsEvent`, `NewsArticle`, plus `SearchAction`; `/world/search` is `noindex, follow`

**M4 Tactical Lab — closed 2026-09-22.** The gate (50 systems + drag/draw/save/share + analysis with evidence) is met;
the items still open below it are follow-ups, not gate gaps. **M5 Video Analysis — closed the same day**, pipeline and
browser both. **M6 Football Simulation — first slice verified 2026-09-23**: the deterministic possession-block engine,
its `/simulate` surface, and the last outstanding §65 gate item (100 world training sessions, browsable at
`/world/training`). **Next inside M6:** Career Mode (§20) as the container a season is played in, then manager live
challenges (§21) and the transfer market (§22), with every result labelled fictional rather than observed.

Verified 2026-09-22 (the pure layer + storage + reads, 99 tests):

1. [x] `pitch.py` — one metre coordinate system (origin at the team's own goal, Law 1 dimensions), clamping, thirds/lanes/zones, nearest-neighbour and centroid maths; a non-finite coordinate is rejected at construction
2. [x] `roles.py` — 14 roles, each with separate in- and out-of-possession duties, instructions, a stated risk, and the tactical attributes it demands (the same six the player model stores, so fit can be computed)
3. [x] `shapes.py` — ten authored base shapes × five temperaments; every shape validated to eleven slots, one keeper, on the grass
4. [x] `analysis.py` — in-possession shift and out-of-possession rescale (the block's span is exactly the authored `block_depth`, its top exactly `press_line_y`), eight metrics that each carry their own formula, and six named counterfactuals that move only the slots they name
5. [x] `plan.py` — 50 systems whose strengths/risks are **decided from their own measurements against the catalogue quartiles**, each sentence quoting the number and the percentile; deterministic fingerprint; `tactical_problems()` empty
6. [x] stored: `tactical_systems` + `0004` migration, `alembic upgrade head`/`check` clean, idempotent sync by slug (second pass `created=0 updated=0 unchanged=50`), a poisoned plan rolls back and writes nothing
7. [x] served: 5 public `/api/v1/tactics/*` routes (status, list with formation/temperament/search filters, detail, counterfactual, compare); metrics are recomputed from the stored coordinates, and every response repeats its provenance and disclaimer; `m4_tactical_lab` is derived from the row count
8. [x] 188 tests green on SQLite **and** PostgreSQL+pgvector; ruff + mypy clean (53 files); `docs/api/openapi.json` regenerated (45 paths / 49 operations)

Web surface (verified 2026-09-22):

9. [x] `/tactics` index — counted store, the eight measures with their formulas, one real board, filters by shape and temperament, JS-free pagination and search
10. [x] `/tactics/{slug}` — the last §80 route shape the site did not serve: both phases drawn from the stored metres by `components/pitch.tsx` (server-rendered SVG, Law 1 markings, band colours, no client JS), the transform stated with its own numbers, the roles in the field, and the graded verdicts quoted character for character from the API
11. [x] `/tactics/{slug}?change=…` — a counterfactual is a URL: before-positions hollow, each moved player drawn as an arrow, the delta table beside it, and clamps reported rather than hidden
12. [x] `/tactics/compare?a=&b=&phase=` — plain GET form, `noindex, follow`, both boards measured side by side
13. [x] `sitemap.ts` gained the 50 system URLs in the same commit (1034 `<loc>` entries, each answering 200); `PROJECT AUTHORED` labelling is single-sourced in `OriginBadge` and asserted absent-of-`DEMO DATA` in the walk
14. [x] 136/136 browser assertions at 1440px and 375px against a production build, 54 PNGs, zero console errors — `docs/M4_WEB_VERIFICATION.md`

Still open in M4:

1. [x] AI tactical analysis with citations: `GET /tactics/{slug}/feedback` puts six coaching questions to the M2 corpus
   through the same hybrid retrieval and answerability gates as `/knowledge`, and renders only the statements whose
   passage resolves — first measured as 4 cited and 2 refused for every system, because the library held no passage on
   using width to stretch a block or on how high a team sits. The refusals went on the page with the gate that produced
   them; rewording the queries to score `answerable` would have bought citations to off-topic passages, which is worse
   than none. The gap was then closed by **writing the two missing passages** (`width-in-attack`, `squad-height-and-territory`),
   not by moving a threshold: 6 cited and 0 refused across all 50 systems, with `run_rag_eval` still at recall 1.0 /
   citation integrity 1.0 / refusal accuracy 1.0 on 18 documents and 138 chunks
2. [x] `GET /tactics/{slug}/fit` — the session's player against the shape's six tactical demands, with published
   thresholds (`short ≤ -12`, `exceeds ≥ +4`), 409 `no_player` when there is no profile
3. [x] user boards, stored and served: `tactic_boards` + migration `0005`, 8 routes under `/api/v1/boards`
   (create/edit/delete, share by 32-hex token, revoke, public read-only view, ceiling of 24 per account).
   Coordinates are validated before they are written, metrics are recomputed on every read, a second account
   gets 404 rather than 403, and the shared payload exposes no owner identity — 17 tests on both engines plus
   a live HTTP pass (`docs/M4_VERIFICATION.md` §8)
4. [x] the drag interface: pointer-move the eleven dots on the same metre-scaled board, snap to 0.5 m, save — the walk
   proves the dragged position reaches the database (a midfielder measured 55 → 64.5 m) — then share a token link,
   revoke it, delete the board
5. [x] animation: `PhasePlayer` interpolates the two stored phases with the transform sentence beside it, badged
   `SIMULATION` and carrying AI_POLICY §2's exact stamp, which the walk asserts is present
6. [ ] 3D pitch (spec §13 lists 2D/3D; 2D is what ships)
7. [ ] boards are single-owner by design: no co-editors, comments or public gallery — that needs M9's permission and
   consent story, not just a listing
8. [x] corpus follow-up so the two refused topics can be cited: `data/knowledge/tactics/width-in-attack.md` and
   `squad-height-and-territory.md` authored to the corpus's own shape rules, `python -m evals.run_rag_eval` re-measured
   rather than loosened — recall@5 1.0, MRR 0.9167, citation integrity 1.0, refusal accuracy 1.0 on 18 documents /
   138 chunks, with two new golden questions both ranking first

**M5 Video Analysis — verified.** Evidence: [`docs/M5_VERIFICATION.md`](docs/M5_VERIFICATION.md) (pipeline) ·
[`docs/M5_WEB_VERIFICATION.md`](docs/M5_WEB_VERIFICATION.md) (browser).

Verified 2026-09-22 (29 video tests on both engines + a live HTTP pass + a browser walk):

1. [x] media layer: `ffprobe` container facts, `ffmpeg` frame sampling to PPM at an even interval, a
   PNG display copy, all as subprocesses with fixed argument lists; missing tools raise
   `MediaToolMissing` and the API answers 503 rather than inventing frames
2. [x] demo vision provider `demo-pixel-stats` behind the `VisionProvider` protocol that had been pinned
   since M0: pitch-green fraction, brightest-cell and **centroid of the non-pitch pixels**, movement
   events with shift, speed and confidence — every threshold in the payload, plus a `limitations`
   sentence saying it detects no players, ball or football events
3. [x] upload contract: container decided by **magic bytes** (a `MZ` file named `.mp4` → 415), size ceiling
   in one place (`UploadTooLarge` → 413), sha256 + byte count stored, 20 clips per account, storage keys
   that cannot escape the root, `var/` gitignored
4. [x] `video_assets` / `video_detections` + migration `0006`; `LocalStorageProvider` implemented at last
   (it said "Lands with M5"); 7 routes; `Job` and `ModelCall` rows written for real, including a failed
   ledger row when the media tools are absent — and the jobs endpoint states there is no queue
5. [x] ownership: every video read needs a session, another account gets 404 on all five doors, and the
   report omits `storage_key`; deletion removes the row, the detections and the bytes on disk
6. [x] the web surface: `/video` holds the upload form and `/video/{id}` the report — detection timeline, the
   sampled frames shown as the PNGs `ffmpeg` wrote, and a `<video>` whose source is the owner-only file route.
   That route answers byte ranges, and the cookie proxy now carries `Range` out and `Content-Range` back, so the
   browser seeks instead of downloading: `206 bytes 0-99/58056`, suffix ranges, `416 bytes */58056`. No §80 route
   and no sitemap entry — the report is `noindex` and robots keeps `/video` out of the crawl. 12 checks in that
   block, **164/164** in the walk, 58 screenshots (`docs/M5_WEB_VERIFICATION.md`)

Still open in M5:

1. [x] frame overlay: draw the measured centroids on the displayed frame, so a viewer can see which
   pixels the numbers describe — verified 2026-09-29, walk check added to `visual-qa.mjs` (check 234),
   ring drawn at each detection's (x, y) on the sampled frame it belongs to, title carries the
   measurement sentence, 234/234 green.
2. [ ] event semantics (a real vision model or hand-labelled data) — mapping pixel movement to passes,
   shots or presses would be a claim this build cannot support
3. [x] linking a clip to a user's player or an M6 match, and short shareable clips — verified 2026-09-30:
   - POST /video/{id}/link-player — link to caller's football identity (UserPlayer)
   - POST /video/{id}/link-match — link to caller's M6 simulation match
   - POST /video/{id}/share + DELETE /video/{id}/share + GET /video/shared/{token} — revocable share
     token (§17 pattern), public read without session or owner identity
   - VideoAsset model gains player_id, match_id, share_token, shared_at, visibility
   - tests/test_video.py: TestM5Item3LinksAndSharing (4 cases) all pass
   - walk still 234/234, exit 0

Verification harness to extend: `pytest` on both databases, `python -m evals.run_rag_eval`,
`scripts/export_openapi.py`, `apps/web/scripts/visual-qa.mjs`. `docs/api/openapi.json` remains the
contract the web tier codes against.

**M6 Football Simulation (first slice) — verified 2026-09-23.** Evidence:
[`docs/M6_VERIFICATION.md`](docs/M6_VERIFICATION.md) (engine + storage + reads) ·
[`docs/M6_WEB_VERIFICATION.md`](docs/M6_WEB_VERIFICATION.md) (browser).

**Manager live challenges (§21) — backend and page verified, 2026-09-24**
(`docs/M6_VERIFICATION.md` §11 · [`docs/M6_CHALLENGES_WEB_VERIFICATION.md`](docs/M6_CHALLENGES_WEB_VERIFICATION.md)).
Six authored scenarios, each time-limited by a window the engine
enforces, goal-based on objectives the caller cannot lower, and reward-based on a verdict recomputed
from the run's own rows. 32 tests, a live pass on a seeded database, and every constraint publishing
whether it binds — so "no transfers" and "academy players only" read as stated intent rather than as
rules something applied. `/challenges` and `/challenges/runs/{slug}` put it on screen, and the browser walk
holds it to the arithmetic: 17 checks over the measured club, the four-field form, the summed verdict and the
`409 window_closed` the route answers for a seventh round.

**The transfer market (§22) — API tier and page verified 2026-09-24** (`docs/M6_VERIFICATION.md` §14 — the
market, [`docs/M6_MARKET_WEB_VERIFICATION.md`](docs/M6_MARKET_WEB_VERIFICATION.md) — the browser). A budget
became a sum of rows: `transfer_listings` priced by a formula the response prints, `career_squad_moves`
as the only thing that moves money, a club's need read as its weakest engine band, a fit that reuses that
same band measurement, a seller that answers an offer by a published ladder, and a release clause that is
the only way into a rival. A deal changes the eleven through a round-scoped overlay composed at read time,
so the generated world's player rows are never rewritten and a later signing cannot rewrite an older
match — `replay_is_identical` rebuilds the squad *as of* the round and refuses rather than blaming the
engine for an input change. 8 routes, 49 tests, both engines, and the match report now carries
`squad_label` so an unfamiliar name in a club's eleven explains itself. That paragraph above about
"no transfers" being stated intent is superseded: since this landed, the rule binds.
`/career/{slug}/market` is the page: 86 checks against a production build, the clause and wage arithmetic
re-derived from the DOM, the ladder driven by clicking a row, and a signing sold straight back on so that
the ledger's two fees and the squad's net counts are reconciled against each other in the same walk.

Verified 2026-09-23 → 2026-09-24 (377 API tests on both engines + a browser walk at 226/226):

1. [x] `possession-block-v1@1.0.0`: a 90-minute match as fifteen six-minute blocks, each side measured from ten
   factor rows through nine named rates, every rate shipping with the expression that produced it
2. [x] determinism a stranger can check: `sha256` digest over the inputs, stored beside the report in `sim_matches`
   (migration `0007`), and `POST /api/v1/simulate/{ident}/replay` re-playing from the stored seed + minutes + two
   systems so the page prints `stored · replayed · Identical.` rather than asking to be believed
3. [x] every result labelled fictional: `data_origin='simulation'`, `is_demo_data=true`, the simulation disclaimer on
   the row and on `/simulate`, and no claim that any of it was observed
4. [x] ownership: `/simulate` is behind the session wall, another account gets 404 on every door, and deleting a
   match removes it for its owner (the walk re-reads both rows and gets 404)
5. [x] the last §65 gate item: `real_training_sessions` (migration `0008`), 100 rows drawn in proportion to the
   minutes the generated players played, each quoting a catalogue drill and copying its duration and difficulty,
   `load_units = duration_min × rpe` computed on request — served by `GET /api/v1/world/training`, browsed at
   `/world/training`, and printed as `MEETS` by `/world`'s own counts table
6. [x] a session-rotation defect the walk found rather than a test: parallel proxied calls signed the user out of
   their own account. Fixed with `REFRESH_REUSE_GRACE_SECONDS` (ADR-003 amended), destroy-on-stale-reuse, logout that
   deletes the credential, a single-flight refresh in the cookie proxy, and four tests that age `revoked_at` instead
   of sleeping
7. [x] the console gate now attributes a failed request by its **own URL** (`message.location().url`), not by the
   page the reader was on — which is what let it name the walk's own doubled path
9. [x] **Career Mode's page** (same day, §20): `/career` and `/career/[slug]` — the form that states a manager, club, philosophy, tactical system, budget and objectives, and the season page whose record, objective verdicts, fixture list and table of clubs met are all read back from the API's sums. Behind the session wall like the simulator, disallowed in robots, absent from the sitemap, reachable from a panel action on `/simulate`. 17 checks in the walk, quoted in [`docs/M6_CAREER_WEB_VERIFICATION.md`](docs/M6_CAREER_WEB_VERIFICATION.md)
10. [x] **Career Mode's backend** (same day, §20): `careers` + `career_fixtures` (migration `0009`), a fixture
   list that is a *rotation* anyone can reproduce, rounds decided by `run_simulation` so there is still only one
   match model, a record and a mini-table summed from the career's own rows with their formulas printed,
   objectives that must be stated before a career can open, and 6 `/api/v1/careers/*` routes — 28 tests on both
   engines (`docs/M6_VERIFICATION.md` §10). **No page for it yet**, and the budget is stated intent nothing spends.

Still open in M6:

1. [x] **a page for the challenges** (2026-09-24, §21): `/challenges` holds the six-scenario catalogue, the start
   form and this account's runs; `/challenges/runs/[slug]` shows the verdict above the rounds it is summed from. The
   walk proves the three §21 adjectives where they can actually break — the form has four fields and none of them is
   a knob, the club handed back is the arithmetic minimum of the ranking the same response printed, and the round
   past the window is refused by the *route* with `409 window_closed` and the final verdict beside it. 17 checks,
   quoted in [`docs/M6_CHALLENGES_WEB_VERIFICATION.md`](docs/M6_CHALLENGES_WEB_VERIFICATION.md)
2. [x] **the transfer market's API tier** (2026-09-24, §22): `transfer_listings` + `career_squad_moves`
   (migration `0011`), a valuation whose every figure is the printed formula recomputed from a stored
   player row, a need that is the club's own weakest engine band, a budget that is a sum of move rows and
   nothing else, a seller that answers an offer by a published ladder, a release clause that is the only
   way into a rival, and a round-scoped squad overlay that reaches the eleven without editing the world.
   Eight routes, 49 tests, and the engine now prints `squad_label` in a match report so a player who is
   not on the club's page is explained by the report itself (`docs/M6_VERIFICATION.md` §14 — the market).
   **The page landed the same day**: `/career/{slug}/market` — the dozen offers with their clause and wage
   arithmetic re-derived in the browser, the negotiation ladder driven by clicking a row, the signing that
   joins the eleven, the loan with its end round, the sale whose proceeds arrive, and the ledger the balance
   is summed from, all behind the `/career` session wall. 86 checks, quoted in
   [`docs/M6_MARKET_WEB_VERIFICATION.md`](docs/M6_MARKET_WEB_VERIFICATION.md). It also caught a published
   formula the code does not run: §22's own rule text said `weekly_wage = asking ÷ 500` and
   `release_clause = asking × 1.5` while both are rounded to the 5-credit step — the 49 backend tests asserted
   the rounded values, so only the sentence shown to a manager was false. The wage bill is still not
   deducted (item 8) and `no_transfers` is still advertised as merely stated (item 7).
3. [x] **squad and training carry-over between matches** (2026-09-24, §20 backend **and its panel on the
   season page**): `career_appearances`
   (migration `0013`) records one row per player the engine selected per round, at the fixture's full
   length; the round after it reads a decayed three-round window off those rows — `load = Σ minutes ×
   0.5^rounds-since`, over a window that holds 157.5 units — plus a training reserve of at most 0.15
   given back by the player's own rows in `real_training_sessions`, and the resulting `condition`
   weights each selected player's stored form before the eleven's mean is taken. That last step is why
   no digest moved: `form` is an index the fatigue term already reads, an empty condition map is
   bit-for-bit the old number, and the two new Metrics appear only on a side that actually carries load.
   `replay_is_identical` grew a second refusal for exactly this reason — a deleted trace would otherwise
   print as the engine disagreeing with itself — and `play_round` refuses to attribute a round whose
   rebuilt eleven does not match its own report. 17 new tests in `tests/test_carry_over.py`, **450 API
   tests green on both engines**, quoted with the four published formulas in
   [`docs/M6_CARRY_OVER_VERIFICATION.md`](docs/M6_CARRY_OVER_VERIFICATION.md). The page side is
   **45/45 walk checks** on a production build (§8 of the same document): two rounds played through the
   season page's own button, every printed condition re-derived from the constants the page itself
   publishes, and the report page checked against the season page for the same two expressions. Player
   growth, resting a tired player and substitutions are still not implemented and the module says so.
4. [x] **`sim_events`: the timeline as rows** (2026-09-24, migration `0014`) — and the premise the line
   itself carried is wrong, so the module's first section says so: nothing was being regenerated.
   `simulate_match` builds the event list once, `run_simulation` stores the whole report — events included
   — in `sim_matches.report`, and the detail route reads that JSON back without asking the engine anything;
   only `/replay` re-derives, deliberately. What the rows add is **addressability**: "who scored most in
   this career", "how many sendings-off in this competition" and "who took the most attempts, and at what
quality"
   stop meaning unrolling every report in the world, and the two composite indexes are the shapes those
   questions take. Two rules, both tested rather than asserted in prose: *the rows are a copy, not a second
   opinion* (written in the report's own transaction, never fed back to the engine, and a disagreement is
   reported field-by-field **in the report's favour** — `test_a_moved_minute_is_caught_even_though_the_length_is_unchanged`
   is why the check is per field and not per count); and *a name is not an identity* (`lineup` is inside
   every stored match's digest, so it cannot gain ids — identity is the name looked back up in the same
   eleven, and a shared name yields `ambiguous` and claims no player rather than writing one man's record
   under another's name). The writer's own docstring promised idempotence the code did not have: with
   `SessionLocal(autoflush=False)` a `SELECT` cannot see rows queued earlier in the same transaction, so
   the second call deleted nothing and hit `UNIQUE constraint failed: sim_events.match_id, sim_events.ordinal`
   — two load-bearing flushes, one test. `GET /simulate/{ident}` and a fresh play now carry a `timeline`
   whose `source` a page **has** to print, because "read from sim_events rows" and "this match predates the
   table" are different claims; nothing was backfilled, and the fallback says so in its own sentence.
   26 tests in `tests/test_sim_events.py` — **476 API tests green on both engines** — measured against the
   code with a one-line mutation (5 of 26 red), and the panel is **29/29 walk checks** on a production build
   ([`docs/M6_SIM_EVENTS_VERIFICATION.md`](docs/M6_SIM_EVENTS_VERIFICATION.md)).
   Item 10 has since read them across matches — the career page carries a season ledger
   ([`docs/M6_SIM_LEDGER_VERIFICATION.md`](docs/M6_SIM_LEDGER_VERIFICATION.md)).
5. [x] **the player page prints the `training_log` its route already returns** (2026-09-25, `f4c0bec`): the
   sessions newest first with the drill linked into the Training Academy, the totals above them, and a
   consistency notice that re-adds the printed minutes and load and sets them against those totals, so a reader
   can see the two figures are the arithmetic of the rows under them rather than trusting either. A player the
   generator never picked is told so, and prints an em-dash where a mean RPE would be, because `mean of nothing =
   0` rendered as a measured average is a number this build does not have. Held by the walk's own check inside
   the **233/233** production run of 2026-09-28.
6. [x] **a per-run test database** — `conftest.py` pointed every run at one fixed `football_os_pytest`
   and its session fixture began with `drop_all()`, so two overlapping runs made the other's tables
   vanish. Caught while re-running §21: one spurious `relation "training_drills" does not exist` in a
   test that never queries that table, green on rerun. Fixed by creating, provisioning (`vector`) and
   dropping a uuid-suffixed database per server-backed run — proved by **two full 376-test suites
   running concurrently, both green, nothing left behind** (`docs/M6_VERIFICATION.md` §13).
   The default SQLite leg had the same defect in three lines (`_DB_PATH` was fixed while the guard read
   `DATABASE_URL`, and the unlink ran at import, so `--collect-only` deleted a database) and now names
   its own file and cleans only that up: **two full 377-test suites concurrent, both green, the shared
   default's mtime unchanged, nothing left in `%TEMP%`** (§15)
7. [x] **§11's constraint metadata under-stated `no_transfers`** (fixed 2026-09-25, `f4c0bec`): the catalogue
   published `enforced=False` with `how="there is no transfer market yet (spec §22), so no signing is possible
   with or without this rule"` while §22's `market.transferable()` had been refusing every move for a career
   carrying the rule and saying `enforced: true` about it from the other side of the codebase. Three places move
   together and none of them is a backend-only edit: that row, `tests/test_challenges.py` (which holds the
   catalogue's flag to the market's own, for every scenario that carries the rule), and the walk's needle on the
   run page. The direction of the error was an under-claim — a binding rule advertised as merely stated — so
   nothing the product promised became false meanwhile. Measured on a production build **2026-09-28: 233/233,
   exit 0**, with the run page reading *3 APPLIED / 1 STATED ONLY*.
8. [x] **a wage bill** (2026-09-24, §22 continued): each round the engine plays now costs the career the
   weekly wage of every deal it holds at the start of that round, written as one `career_wage_charges` row
   (migration `0012`) with the players it was raised on named in `detail` and the balance it left in
   `budget_after`. A wage is money that moves with no player, so it is its own table rather than a fifth
   `career_squad_moves` kind whose `player_id` is a non-null foreign key the eleven is composed from — and
   the ledger the page and the walk read is both tables in round order, which is the property a *derived*
   charge could never satisfy. `BUDGET_FORMULA` gained its fourth term, `limitations()["wages"]` says what
   still is not charged (the club's own stored squad; any consequence of a negative balance), and the
   market walk grew from 86 checks to 103 with the rate read before the round and the charge read after it
   (`docs/M6_MARKET_WEB_VERIFICATION.md` §5)
9. [x] **one needle in `visual-qa.mjs` asserted a sentence this project no longer tells** (re-pointed
   2026-09-25, `f4c0bec`): the career form used to print "Nothing spends this budget yet — there is no transfer
   market in this build", which became false when §22's page and wage bill landed. `components/CareerForm.tsx`
   says what the budget does now, and the check holds the page to both halves of the claim — what the budget
   buys *and* what it still cannot do. It passed in the same **233/233** run of 2026-09-28.
10. [x] **a season ledger over those rows** (2026-09-25, §20+ continued): `app/services/simulation/ledger.py`
   runs the query item 4 left unwritten — every goal, attempt, booking and injury of a career's own
   fixtures, grouped by `player_id` *and* filtered to the career's `team_id`, because a fixture's home side
   is not always that club and an event belongs to the side that printed it. Nothing is backfilled or
   cached: the figures are summed from `sim_events` on the request, and a read writes nothing back (one
   test asserts it). The panel `/career/{slug}` prints keeps the company that makes a count checkable —
   `scope` says whose side was counted, `source` says whether any traced fixture existed at all,
   `truncated` says when the 40-name cap bit, the `ambiguous` and `unnamed` shares are printed with the
   repeated names beside them rather than quietly folded into somebody's row, and `consistency` sets the
   rows' goal figure against `career_fixtures.club_goals` over the same matches, naming both numbers when
   they disagree instead of preferring either. A goalkeeper gets no credit for a save, and the limitation
   says why: a chance event names the player who took the shot. Measured: 22 tests in
   `tests/test_sim_ledger.py` and **498 API tests green on both engines**, four API gates, `tsc` clean, and
   a **39/39** browser walk (`scripts/qa-ledger.mjs`) that re-counts each fixture's stored report twice more
   — by type for the club, and per name against the row it prints — on a production build. Three mutations
   came back red, and one of them (a cap cut to 4 names) caught a check that was over-claiming, since an
   honestly-labelled cut is the design working rather than failing ([`docs/M6_SIM_LEDGER_VERIFICATION.md`](docs/M6_SIM_LEDGER_VERIFICATION.md)).
Still open: a season's ledger is only as complete as the rounds whose reports are still stored.

4. [x] **cross-career and league-wide aggregates** (2026-10-02): `GET /simulation/aggregates/league/{competition_slug}` and `GET /simulation/aggregates/player/{player_slug}` plus `GET /careers/{ident}/ledger`, all summing from `sim_events` at request time. `TestSimulationAggregates` (4 cases at landing; **7 as `pytest --collect-only -q` counts `tests/test_simulation_aggregates.py` at `2285100`**, where the player door stopped refusing world players who had played no manager's season) and `TestSimulationAggregates` (league/player) pass. Migration `2e197f085070` adds `player_id`, `match_id`, `share_token`, `shared_at`, `visibility` to `VideoAsset` for clip linking/sharing (M5 item 3, landed same day). `GET /careers/{ident}/ledger` and `GET /simulation/aggregates/*` endpoints verify green on both engines.

**M8 Club OS — §39 and §41's storage tier landed 2026-09-26** ([evidence](docs/M8_CLUB_OS_VERIFICATION.md)):

1. [x] migration `0016_club_organisations`: `organizations` (globally unique slug, `kind` ∈ academy / club / school / scout_desk, two-letter country, `visibility_default`), `organization_members` (`UNIQUE(organization_id, user_id)`, both FKs cascade, `status` ∈ active / invited / revoked), `club_teams` (`UNIQUE(organization_id, name)` — two tenants may name a team the same words — and `world_team_id` on `SET NULL`), `club_team_members` (`UNIQUE(team_id, player_id)`, **no figure column**)
2. [x] `app/services/club/access.py`: six roles and twelve permissions as **code that is published**, not rows that are copied — default-deny, unknown role grants nothing and is reported until its row goes. `parent`'s row was empty when this tier landed and stated that §40 had not filled it; §40 filled it with the three rights a guardian holds, each scoped by a consent row rather than by the tenant, and the sentence that used to call it empty now reads as §39's published limitation: `a parent's row in the matrix holds three rights and every one of them is scoped by a consent row, not by the tenant`
3. [x] thirteen doors / eighteen operations under `/api/v1/club`, a tenant addressed by slug **or** id and a team by id **or** name; `GET /club/capabilities` answers without a session, because §41's buyer asks what the roles mean before anybody signs in (contract regenerated at **104 paths / 124 operations**)
4. [x] twenty refusal codes, each carrying the figures behind its sentence, with the set asserted closed and every code given exactly one HTTP answer — **403 exists for one code only** (`insufficient_role`), so a foreign tenant is a 404 and the tier never confirms what exists
5. [x] isolation proved at every door that names a tenant: fourteen of them derived from `app.routes`, knocked on by a stranger and by a real director of a *different* tenant, in both address forms, with the refusal checked for the tenant's name, its slug, its team and both accounts' emails. **This is where the milestone's one live defect surfaced** — `POST /club/{id}/accept` built its 404 from the row it had just resolved, so a signed-in account with no invitation anywhere could have walked an id range and printed every academy on the platform; it now echoes the address the caller typed, and mutating any of the three sites back to the resolved row turns the door test red
6. [x] `users.organization_id` watched and never trusted: filled by the first membership, ignored by the second, cleared by a departure and by a tenant deletion, and a privilege planted into it still answers 404 while `access_problems()` names the divergence
7. [x] the tier's own gate: table presence (not a try-block) so an un-migrated database reports an empty working surface instead of a 500, counts that move with the work, and `routes` published as structured data with a two-way test against the route table — prose no test reads is not a contract
8. [x] **§41's own nouns arrived**: `Sessions` (migration `0018`), `Reports` (`0019`) and the tenant's own ceiling over `entitlements`/`usage_events` (`0020`), each read through a door that prints the standing it read with. At that step, §39's Training / Matches / Tactics / Video / Communication rows were still limitations; Matches and Communication have since landed, while the remaining rows stay explicitly out of this build rather than being presented as complete.
9. [x] **the web surface and its walk**: `/club`, `/club/rules`, `/club/{ident}` and `/club/{ident}/plans/{plan}`, plus §41's session and report panels and §42's ceiling meter — **194/194 checks, exit 0** against a production build on a database `scripts/qa_db.py` created for the run ([evidence](docs/M8_CLUB_WEB_VERIFICATION.md)). Three more live defects fell out of it, and two of the three are one sentence read two ways: a session recorded from the page stored *the address the caller typed* while every reader resolved it, so a guardian was told their own child had attended nothing (#3); the sheet's capacity guard ran over that same untyped-free list, so `attendees=[slug, id]` for one child was refused as naming two (#4, found by the test that holds #3); and the rulebook page described the `ready` flag as "whether their tables exist" when the rule has a second condition, so a freshly provisioned database was called a fault (#5 — the rule is now one published constant both doors print). Nothing in the API tier above claimed a page until this row landed.

**M8 §40 Youth Academy — the minors' tier landed 2026-09-26** ([evidence](docs/M8_ACADEMY_VERIFICATION.md)):

1. [x] migration `0017_academy_development`: `academy_curricula`, `development_plans`, `plan_assessments`, `coach_feedback`, `plan_video_evidence`, `guardian_consents` — and `STORED_FIELDS` publishing all **69** of their columns, which is what makes data minimisation a testable sentence rather than an intention
2. [x] **one row does four jobs**: `guardian_consents` gates every write about a child, ceilings which kinds of row may exist at all (`plan` / `assessment` / `feedback` / `video`), records whose account claimed the child, and anchors erasure. Guardianship is self-declared and the answers say so, because a platform that cannot verify a claim should not pretend its gate does
3. [x] twelve door-guide lines / nineteen doors, printed beside §39's own by `GET /club/capabilities` so a page is handed one complete list rather than two halves it has to discover; one line per path, because the guide that double-books a path is the guide a page renders twice
4. [x] progress is arithmetic with its formula printed beside every figure: `reviews_due_by_cadence` = `floor(plan_days_open / (review_weeks × 7))`, `axis_change` first review to last, `one_review_is_not_a_direction` when the history is one row — and `not_a_column`, because a stored progress figure is a stale progress figure
5. [x] thirty-six own codes (6→404, 26→422, 4→409, **0→403**) plus four shared with §39, one code meaning exactly one thing: an over-long field is `text_too_long` with `field`/`length`/`max`, not a per-field code that would send a caller off to delete the wrong row. Every cap measured from both sides — 12 curricula, 8 phases, 0–1200 minutes, 100 plans, 1–52 weeks, 6 focus areas, 8 goals, 52 reviews, 200 notes, 20 citations, 10 claims per guardian
6. [x] a 422 never echoes the value that was submitted, and a foreign or ungranted child answers `no_such_player`/`no_such_plan` — §39's own rule, applied to rows §39 never had. The isolation walk now counts **32** tenant-naming doors from the route table (14 + 18), and a stranger's answer is byte-identical to a director-of-elsewhere's
7. [x] three product defects found by the suite rather than by a probe: `insufficient_role` built with a duplicate `role=` keyword so a scout reading a plan got a 500; `grant_consent`/`withdraw_consent` asking only the matrix for `consent.grant_own`, which every staff role passes, so a director could mint the yes that gates a tenant's own children — the published scoped rule is now enforced at the door with `required_role`; and a cadence figure computed between the reviews that exist, which cannot be behind by construction
8. [x] erasure is a dry run before it is a delete: `GET …/players/{player}/data` prints the counts per table with the column list beside them, `DELETE` without `confirm` returns those same counts, and the walk proves the world's player row, §39's sheet row and the uploader's clip file all survive it

**M8 §39 Matches — the tier's last noun landed 2026-09-27** (code `06de944`, the probe's two holes closed in
`99a94ee`; [evidence](docs/M8_CLUB_OS_VERIFICATION.md) §9 and §10):

1. [x] `club_fixtures` + `club_match_appearances` (migration `0021`), five doors under `/club/{ident}/fixtures`,
   three permissions added to the matrix (`match.read`/`match.write`/`match.erase`), `answers.TIERS` gained a member.
2. [x] **an arrangement, not a result**: the tier stores a pointer, a slug and a digest; the scoreline, the timeline
   and every counted figure are read from `sim_matches`/`sim_events` at request time.
3. [x] **the tenant's own eleven**: the sheet is applied as a `SquadOverlay` over the world club the team is bound to
   (the base squad removed, the named players added), and appearance rows are written only while the eleven rebuilt
   from the tenant's rows is the eleven the stored report names — the disagreement leaves the match standing and
   records nothing, and says which of the two shapes it hit.
4. [x] the isolation walk extended from 41 to **46** doors that name a tenant; a DOORS entry for a body-reading POST
   now carries a real payload, because an empty dict never reaches `require()` and the walk proves nothing.
5. [x] eleven planted defects over the tier, behind an unmutated control: **10 turned the suite red**. The two that
   survived the first eight-arm run were the suite's blind spots — a gate tested only far from its boundary, and a
   rule no case reached — and both are named, with their catchers, in §9's table.
6. [x] the whole suite's two database legs over the fixed tier, `rc=0` on each: **1196 passed + 1 skipped in
   1958.79s** on per-run SQLite and **1196 passed + 1 skipped in 1531.97s** on PostgreSQL + pgvector, measured over
   `5e01714`, with the single remaining skip named from each leg's own `-rs` line.
7. [x] the fixtures panel on the web tier: `/club/{ident}` now arranges, plays and erases through its own controls,
   walked at **215/215 checks** against a production build ([evidence](docs/M8_CLUB_WEB_VERIFICATION.md)).
8. [x] §39's `Communication` noun landed as migration `0022` plus `services/club/announcements.py`: a notice carries
   words and an audience predicate, receipts are one row per account, and `recipients`/`read_by`/`unread` are
   recomputed from the current roster rather than stored counts. The API file measures **19 cases** and a three-arm
   planted-defect probe with **0 survivors**; `/club/{ident}` mounts the board and its receipt action, walked at
   **252/252 checks, exit 0** against a production build ([API evidence](docs/M8_CLUB_OS_VERIFICATION.md) §12 ·
   [browser evidence](docs/M8_CLUB_WEB_VERIFICATION.md)).

## Spec modules no milestone owns (audit 2026-09-27)

`[docs/SPEC_COVERAGE_AUDIT.md](docs/SPEC_COVERAGE_AUDIT.md)` maps all 30 product modules to measured evidence (197 contract paths, 61 page
routes, 34 migrations). Everything in §4–�?2 has a door except none, and the row below is what it still lacks; `apps/api/tests/test_spec_audit_currency.py` recomputes the three figures, every `�?N file(s)` count any
committed markdown publishes �?here, in the audit and in a verification record alike, every path the audit's §A table
cites, every door-and-page census that table publishes and every
`/api/v1/…` route citation in the ledger:

- [x] **§30 Knowledge Graph — the joint half (closed 2026-10-07).** The projection, its three `/api/v1/graph/*`
    doors and the `/graph` pages landed (mounted at `3651587`; 6 node kinds, 13 edges over stored foreign keys,
    walked by `visual-qa.mjs` §12i), so the audit's older "no table, no route, no service" sentence is retired — a
    `graph_edges` table is deliberately *not* what this build ships. Both halves then closed: the anchoring half
    (`apps/api/app/services/knowledge/graph_join.py`, `e61ff07`) answers *which stored nodes does this sentence
    name* and prints them in the answer's `reasons`; and after `1dd375c` built the corpus-world naming substrate,
    the **recall hop** landed with §87 (`apps/api/app/services/knowledge/recall.py`).
    Re-taken: `git grep -li knowledge_graph -- apps/api/app/services/knowledge` → 2 files, one per half. The hop may not lower `retrieval.py`'s
    measurement-derived floors — it runs only after they answer — and it is measured against the joint golden set
    M11 wrote (8 cases, every one naming a committed node), so the clause this item tracked is closed on its own
    terms (2026-10-07).
- [x] **§38 Football Career Portfolio — all three permitted outputs landed under M10:** the CV (ten live sections), its public projection (`/portfolio/share/{token}`), the revocable share link (`POST/DELETE /portfolio/share`), and the owner-authenticated PDF (`GET /portfolio/cv.pdf`). The CV, share link, and PDF all render from the same live read (`build_cv` / `build_cv_pdf`); the PDF endpoint (`/api/v1/portfolio/cv.pdf`) was added in `services/portfolio/pdf.py` (reportlab-based, CID-font for CJK), wired at `api/v1/portfolio.py` line 102, and tested in `test_portfolio.py` (22 tests, 0 failures). The minors' `videos` guard uses §40's threshold and §17's revocable-token precedent.

The audit's condition is now satisfied and §38's CV-and-link half is complete: §35's community permission layer landed
2026-09-28 (`docs/M9_COMMUNITY_VERIFICATION.md`), so the public CV projection does not bypass the tier that decides
who may read a record, and the minors' `videos` guard uses §40's threshold. Broader minor-publication policy remains
a follow-up rather than a claim of this slice. §30's joint clause closed with §87 — the hop runs only after the
retrieval floors answer and is measured against the joint golden set — so the §38 item above is this section's only
unchecked one.

## Cross-cutting gates (spec §80 SEO, §81 i18n)

Milestones do not own these; every public route must satisfy them as it lands.

- [x] §80 metadata layer: `metadataBase` from `SITE_URL`, per-route canonical + OpenGraph (`pageMetadata()`), site-level
  and document-level JSON-LD — verified in `docs/SEO_VERIFICATION.md` against a **production build**, not a dev server
- [x] §80 `sitemap.xml` and `robots.txt` generated from live API reads; every advertised `<loc>` is asserted to answer
  200, and session-gated routes are excluded from the sitemap and disallowed in robots rather than published as redirect chains
- [x] `visual-qa.mjs` carries the SEO assertions, the `/settings` locale and milestone rows, and 42 Football World
  assertions (**110/110**, run `202609212343` against a production build, 46 PNGs, zero console errors). It tags browser
  console errors with the route they occurred on, probes every sitemap `<loc>` through a bounded pool, and records an
  unhandled abort as a failed check plus a screenshot instead of one log line — `docs/M3_WEB_VERIFICATION.md` §5
- [x] §80 SEO routes for the world entities (`/player|team|match|competition|news/{slug}`) — mounted at the paths
  `SEO_ROUTES`/`web_path()` in `app/services/world/plan.py` emits, with the same `pageMetadata()` helper, and
  `sitemap.ts` lists all 983 of them from the API's own `path` fields (`docs/M3_WEB_VERIFICATION.md` §3)
- [x] §81 messages: `messages/{en,zh,zh-TW}.json` are landed and `GET /capabilities` reports
  `locales: ["en", "zh", "zh-TW"]` — all three shipped since **2026-10-06** when both Chinese catalogues
  carried the full key set translated (`zh-TW` 288/288; `zh` 287/288, the search example sentence being Chinese
  in the English file already, so its falling back is the honest state). The history: until 2026-10-01 the files
  were byte-copies of the English one and `meta.py` correctly reported `["en"]`; `9ba8178` flipped it early, the walk
  caught it 2026-09-29 as a settings row claiming three shipped languages over one translated file, and it was put
  back to `["en"]`. Then on 2026-10-06 the translations actually arrived and the flag was flipped for real.
  `middleware.ts` now decides the locale from the `fo_locale` cookie, the caller's `Accept-Language` and the account's
  own column, passing it as the `x-next-intl-locale` header the layout reads, so `<html lang>` follows the reader and
  every existing URL stands. `test_locale_claims.py` gates the API's claim against the actual catalogues in both
  directions (over-claiming and under-claiming), plus duplicate-key detection and catalogue-length checks.

- [x] §74's other half (`2d3673e`): the four error handlers answer at `detail.code` like every door, so the
  product's one reader (`normalizeError`) gets a code, a message and the field list instead of its fallback
  string. `10` cases + a 7-arm probe (0 survivors, one arm's mismatch is prediction-side) and both
  whole-suite legs at 1373 tests / 1 known portfolio FK red on each engine —
  `docs/SECURITY_AUTHORIZATION_VERIFICATION.md` §9

  A concurrent run owns `docs/SECURITY_AUTHORIZATION_VERIFICATION.md`, and its in-flight §7 text already
  points at a §9 it has not landed yet — so the two sections collide by number. Nothing here renumbers or
  rewrites that file: if `## 9.` ever disappears from it, the record is not lost, it is `7aa6e91`'s,
  readable with `git show 7aa6e91:docs/SECURITY_AUTHORIZATION_VERIFICATION.md`, and the repair is to append
  it back after whichever section landed beside it. Both are meant to survive; number them by order.

- [x] §2.3d of the M2 record: the pgvector leg's `leg_limit`, which §2.3b owed because its six arms all ran on a
  SQLite plane, probed on a PostgreSQL plane (`git archive 674df64` → `.scratch/plane_pgarm_041638`). Two arms:
  control 26 collected / 0 red, and `leg_limit = 10_000` → **1 red**, `test_rag_eval_gates_pass_on_this_database`,
  with `recall_at_k=0.9444` / `hybrid_delta=-0.0556` and the same five documents §2.2 printed when the *fallback*
  leg was unwindowed. My written-ahead prediction was a survivor and is falsified — §2.3b had already published the
  mechanism (the tail competes for the same five slots) and I predicted from "widening only adds rows" instead. The
  finding is that the window is load-bearing on **both** planes, so the width is now pinned by one case name on
  each engine. No production line changed; `docs/M2_VERIFICATION.md` §2.3d.
- [x] §74's web half is gated (`docs/ERROR_SHAPE_WEB_VERIFICATION.md`): `apps/web/scripts/qa-error-shape.mjs`
  loads the shipped `apps/web/lib/api.ts` through this repo's TypeScript and feeds it
  `apps/web/fixtures/refusals.json` — 10 bodies, the 6 producer ones held against the backend's own
  bytes by `apps/api/tests/test_error_answer_shape.py` (+3 cases, 13 in the file). 54 of 54 checks
  green, 6 arms + control on a plane with every red count predicted (0 survivors), exit-code probe 0/1,
  both whole-suite legs on `50efc5e`+unit at 1430 tests / 27 reds, of which 26 are `50efc5e`'s own and 1
  is the known portfolio FK pin / 0 errors / 2 skipped, i.e. +3 cases and +0 red over the same plane
  without this unit. Wired into `scripts/check.sh` and CI's `web` job, because `apps/web` has no unit
  runner and nothing reads a `.mjs`. Finding re-measured, not inherited: the archive-that-did-not-
  collect hole this unit hit between `a7cf9c6` and `e07fcfb` was closed by `30e9d37`, so both whole-
  suite legs here run over the current head `50efc5e` rather than an older baseline.
- [x] §75's web-script census (`docs/WEB_SCRIPT_INVENTORY_VERIFICATION.md`): `apps/web/scripts/qa-gate-inventory.mjs`
  accounts for every invocable file in that directory — 14 of them, 12 `.mjs` plus `verify-production.sh` plus the
  census itself — and each is either invoked by a runner it reads or exempt for a reason re-proved from its own bytes
  (`live-tier` needs a browser *and* a base URL, inherited through a delegation edge when the file is a wrapper;
  `report-only` needs an exit status it never sets). 39 checks, all green; 16 runs (12 arms + a `.sh`-reach pair +
  control) with the red *labels* predicted first came back 16/16 MATCHED, no survivors, exit code tracking `failed`
  in every one. Two of its own draft defects were found and fixed before landing: a comment naming a script counted
  as gating it (arm `A12` proves the call-anchored form does not), and a reason reading a fact key the row does not
  carry silenced nothing — it reddened 22 named checks, and arm `A11` reinstates it to keep that loud. Two
  predictions were wrong in the same run and are recorded rather than smoothed: `A5`'s and `A9`'s denominators, both
  arithmetic, both landing on the clause each arm is about. No whole-suite leg is claimed: the changeset holds no
  `.py` path, which is what that sentence is allowed to mean.
- [x] §79's contract-currency gate (`docs/OPENAPI_CONTRACT_VERIFICATION.md`): `docs/api/openapi.json` is the artifact
  `ROADMAP.md:215` says the web tier codes against, and until this unit **nothing in `apps/api/tests` read it**.
  Measured at `3651587`: the committed file listed 149 paths / 193 operations while the same commit's own
  `app.openapi()` answered **160 / 205 / 63 schemas** — 12 operations added, 0 removed, schema-name sets identical, so
  the drift was invisible to anything counting components. The 11 missing paths are `graph` ×3, `simulation/aggregates`
  ×3, `video` ×4 (5 operations), `careers/{ident}/ledger` ×1 — six of them the tiers that commit itself wired up.
  Cause: `scripts/export_openapi.py` fetched `{base}/api/v1/openapi.json` from a *running* service whose default port
  (8731) is shared on this machine, which makes a committed contract a property of whoever holds a socket. It now
  builds the spec in-process, proves the imported `app` package lives in this repository before trusting it, pins LF on
  write, and takes `--out`. `apps/api/tests/test_openapi_contract_currency.py` gates four shapes separately — path set,
  (path, verb) pairs, component schema names, and byte equality between the shipped exporter and the committed file —
  so the first red names the kind of drift; `check.sh:20` and both CI pytest steps invoke it, 4 passed / 0 failed /
  0 errors on the landing plane. Witness: `7` runs (control + 6 arms: stale contract, deleted verb, renamed schema,
  restored scraper, dropped `newline`, unmounted router) against case-name predictions written first,
  7/7 MATCHED, 0 survivors, with the artifact-side and app-side halves each carrying their own arm. The regenerated
  contract is derived from the landing HEAD and staged index-only; another lane's uncommitted copy of that file is
  untouched. No whole-suite leg is claimed for the +4 cases — the leg figure in `.scratch/r78_leg_summary.txt` is
  measured over the commit before this test file exists.
- [x] §81's path-currency gate (`docs/SPEC_AUDIT_PATH_CURRENCY_VERIFICATION.md`): C6 was written because the §38 row
  this project shipped at `862359e` was false — it named `services/portfolio/pdf.py` and "an owner-authenticated PDF
  built from the same read", while that ref's `git ls-tree` holds `__init__.py`/`cv.py`/`sharing.py`, `git log` for
  `pdf.py` answers no commit, the committed contract holds 5 portfolio paths / 6 operations and no PDF door, HEAD's
  requirements name no renderer, `cv.py`'s own `PUBLIC_OUTPUTS["pdf"]` opens "not in this build", and the evidence
  document the row cites states the same absence. The case resolves every repository path the two *verdict* ledgers
  cite (the audit's §A table, ROADMAP's unowned-modules section) against the committed tree — population derived from
  the claim rather than from an exemption table, brace groups expanded one member list at a time, two groups in one
  token refused, and two floors from the same scan (the walk must contain the audit, the token list must be non-empty)
  so "nothing unresolved" can never mean "nothing read". Reverse control measured before the arms: HEAD's own bytes
  give 23 tokens → 33 candidates → **1 survivor, `services/portfolio/pdf.py`**; the corrected ledgers give 26 → 35 →
  **0**. Witness: 8 runs (control + 6 red arms + 1 designed-green) `runs=8 matched=8 not-matched=0`, and because five
  arms redden the same single case each also predicted the *message fragment* the gate prints — the survivor token —
  which is what keeps A1..A5 from being one arm five times. Two prediction-side defects recorded, not smoothed: A4's
  first patch target hit twice (I had written the same phrase into two of my own inserts) and its guessed carrier
  `apps/api/requirements-dev.txt` turned out to be committed, so its green was a true measurement and the wrong
  prediction. The milestone narrative is deliberately **not** gated: measured whole-file, 11 of 73 candidates do not
  resolve and 10 of those legitimately (`.scratch` witness artifacts, a mid-pattern glob, prose fragments), so a gate
  there would need a hiding place. Door/route citations are gated by §83's C9
  (`docs/SPEC_AUDIT_ROUTE_CURRENCY_VERIFICATION.md`).
- [x] §82's census-currency gate (`docs/SPEC_AUDIT_CENSUS_VERIFICATION.md`): the §A table attached seven counts to
  route families without saying whether each counted paths or operations, printed `33 paths under `/api/v1/club*``
  beside a `/club*` page family of 4, and kept two whole-contract totals from past commits in a table whose heading is
  present tense. C7 recomputes every `N paths / M operations under `/api/v1/…`` census and every page-family count
  against the committed contract and committed `apps/web/app/**/page.tsx`; C8 refuses `(N doors)`, a bare `(N)` after a
  route token, and a per-row `contract N/M`, because none of the three has a reader that could keep it honest. Both
  floors come from the same scan (10 dual censuses, 3 page censuses, counted by the gate's own `published_censuses()` —
  the hand-pinned 10 that measured 9 is what revealed §38's census was spelled outside the grammar, so that row was
  canonicalized rather than the grammar widened). Reverse control over a plane holding `8b68b0f`'s unedited ledgers:
  collected 8, red 2, with C7 naming its own floor and C8 naming `['6', '11']`. Witness 9 runs / 9 MATCHED / 0
  mismatches, A8 moving the *producer* (one added operation, path count pinned at 160) so the ledger is shown to follow
  the contract rather than merely quote it. Spelled numerals — row 30's "Three committed doors" — are outside this
  grammar, and the designed-green A7 says so while staying green.
- [x] §83's route-citation gate (`docs/SPEC_AUDIT_ROUTE_CURRENCY_VERIFICATION.md`): the audit cited API doors in
  three spellings no reader could recompute — one brace group mixing door literals with a path parameter
  (`/api/v1/video/{upload,{id},analyse,file,frames/{i},jobs}`), a group whose member carried a second brace
  (`/api/v1/coach/{ask,plan,today,history,drills/{slug}/knowledge}`), and doors written as web routes
  (`/progress/export`). C9 resolves every `/api/v1/…` citation in the ledger against the committed contract — exact
  door, family for a `*` suffix, path-shape match for a parameterized door whose *parameter names* must be the
  contract's own, and equal-or-under for a citation the prose introduces as absent — while a token that is the
  referent of a C7/C8 census is skipped because there it is a prefix, not a path. Measured first: HEAD's ledger
  answers 31 of its citations with 3 defects; the corrected ledger answers 49 with 0, which is where the four
  floors come from (49 citations, 12 parameterized, 1 negated, 10 census referents
  excluded — all read by the gate's own scan). Reverse control over `ad9b841`'s unedited ledger: collected 9, red 1,
  C9 naming both `CONFLATED` groups and `PARAMETER-NAME /api/v1/video/{{id}}/jobs`. Witness 10 runs /
  10 MATCHED, including an arm that moves the *producer* (the contract renames a path parameter) and one
  designed-green arm that cites a committed door no row cited before. Two limits are recorded rather than smoothed:
  a `CONFLATED` refusal retires a token before its inner misspelling is read, and a citation with no `/api/v1` prefix
  is outside this population — which is why §9–12's `/trainings/…` row was rewritten into the grammar instead of
  being left to a case that cannot see it. No whole-suite leg is claimed by this unit.
- [x] §84's joint-retrieval anchoring half (`docs/M11_JOINT_RETRIEVAL_VERIFICATION.md`). `retrieval.py` itself never
    reads the graph (the hop landed later in `apps/api/app/services/knowledge/recall.py`, §87) — but
    `apps/api/app/services/knowledge/graph_join.py` answers the other half of §30's sentence, *which stored nodes
    does this sentence name*, and `apps/api/app/services/knowledge/answer.py` prints
    those relations in `reasons`: the channel `/api/v1/knowledge/ask` already publishes and
    `apps/web/app/knowledge/KnowledgeAsk.tsx` already renders, so no response key and no contract regeneration was
    needed while `docs/api/openapi.json` is held dirty by another lane. Anchoring requires a node's whole label in
    the question, so a football word or half a label anchors nothing; `apps/api/evals/golden_joint.json` (8 cases,
    3 near misses, 1 refusal control) retires the audit's "0 files / 0 of 18 queries" measurement, re-taken on the
    plane as `git grep -li knowledge_graph -- apps/api/app` → 7 files and
    `git grep -li knowledge_graph -- apps/api/app/services/knowledge` → 2 files (both re-read after §87 added
    `recall.py`). Nine cases green; three arms, each
    red at exactly the predicted case: A1 partial-overlap anchoring, A2 the hop wired into the refusal branch, A3 a
    demo fact printed without its disclosure. The refusal control is what makes A2 decisive — every ordinary
    out-of-scope question anchors nothing, so only a question that names a stored club and still misses the corpus
    can tell "not asked" from "asked and agreed". Plane baseline joint 9/0 red, regression over
    `apps/api/tests/test_knowledge_rag.py`, `apps/api/tests/test_knowledge_graph_census.py`,
    `apps/api/tests/test_world.py` 90/0 red (SQLite; the PostgreSQL engine on this machine is still dead).
- [x] §85's file-count reader for every ledger that publishes one (`docs/SPEC_FILE_CITATION_CURRENCY_VERIFICATION.md`).
    C3 had read a single document; its population now comes from the walk — every committed markdown file carrying a
    `→ N file(s)` citation is a carrier and must be registered with a floor — beside two new clauses: a refusal (a
    file count printed next to a grep command in a shape the grammar cannot read) and a void-directory belt (a
    citation naming a directory that holds no committed file is not a measurement of absence). The two claims this
    unit retired were stale *and* unreadable: the §30 bullet above still said the knowledge-package scan answered no
    file at all, and the joint record published the same zero in bold, where `e61ff07` answers one file,
    `graph_join.py`. Nine cases; floors 3 / 3 / 4 read out of the gate's own scan over the landed bytes; six arms
    plus a reverse control and a restored control — nine plane runs, nine MATCHED, no mismatches — each judged on the
    case name and the failure message, because four of them predict which sentence of the one case fires: count,
    refusal, belt, floor. One prediction missed on its own arithmetic and the record says so: stranding the singular
    spelling strands five counts, not the three I had written down — the scan's population was right, my mental count
    was not. No whole-suite leg is claimed by this unit.
- [x] §86 M11 §30 recall hop substrate measured, falsified, and gated (`docs/SPEC_30_RECALL_HOP_SUBSTRATE_VERIFICATION.md`).
    The recall hop — an edge widening the answer's context beyond what BM25/cosine retrieved — is blocked on corpus-world
    naming substrate, not on the retriever's floors. Measured at `ba947e0` by the new gate case
    `TestHopSubstrate::test_no_committed_passage_carries_a_stored_entity_label`: **330** player/team/competition labels,
    **138** chunk bodies (heading stripped), **0** whole-label containment hits, and only **2** labels sharing even one
    word with any body ("Braehaven Elite League", "Ravhull FC" — both generic terms like "league"/"fc"). A draft hop
    (kept in `.scratch/r86_graph_recall_draft.py`, never shipped) produced 4 pulls over the 8 joint questions; every one
    was attributed to the neighbour `match "Matchday 1 game 1 · not played"`, whose label is composed of generic words.
    With deterministic sorted neighbour ordering, the population is **0 of 8**. Six-run witness **6/6 MATCHED**: BASE
    (10 collected, 0 red), REV (HEAD's pristine file, `-k TestHopSubstrate`, 0 collected), A1 any-word predicate
    (`terms <= in_body` → `bool(terms & in_body)`) → exactly one red with message `now carry a stored entity label`
    (42 false hits under any-word), A2 kinds narrowed to `("team",)` → `floor 330`, A3 chunk scan `.limit(1)` →
    `passage scan read 1 chunk(s)`, A4 delete the shared-word belt branch → `do not overlap at all`. The feature was
    reverted rather than landed with an over-claiming disclosure. Building the hop requires either a corpus ingestion
    pipeline that tags passages with entity IDs (a new column on `KnowledgeChunk` populated by a named-entity linker),
    or a separate index mapping entity labels to chunk IDs. Until such a substrate exists, the anchoring half (#84) is
    the full extent of §30's joint clause: the graph adds facts to an answer the retriever already cleared, and adds
    nothing to a refusal. Plane group regression over `test_knowledge_joint.py` + `test_knowledge_rag.py` +
    `test_knowledge_graph_census.py` + `test_world.py`: **109 collected / 0 red** (SQLite; the PostgreSQL engine on this
    machine is still dead). Superseded within the day: `1dd375c` created the substrate this row measured absent, and
    §87 (below) landed the hop that pulls on it.
- [x] §87's recall hop (`docs/SPEC_30_HOP_VERIFICATION.md`). The half §84 left open — a stored edge pulling a
    passage into an answered context — now ships as `apps/api/app/services/knowledge/recall.py` plus a two-phase
    `answer.assemble_context(hits, main=…, extra_budget=…)`: first-pass hits render under the unchanged 4-chunk /
    3200-char budget (bit-identical to the single-phase render on every measured query, asserted by a test that
    compares the two renders), and hop pulls render in a second segment whose budget is that budget plus the summed
    pull body length, so the reserve can never evict the pull it was granted. A neighbour is hoppable only when the
    passage carries the full label string (the looser content-word rule measured degenerate — match labels collapse
    to generic words and attribute any passage that says "final"); pulls exclude exactly what the first pass
    renders, are capped at 2, dedup per neighbour per anchor, and order by (document slug, ordinal) because chunk
    ids rotate per ingestion (asserted by a re-ingestion case). The hop runs only on the branch the retriever
    already answered — the refusal side stays witnessed by `TestFloorsUntouched`. Measured on both engine legs:
    **44 knowledge tests green** (18 joint + 26 rag; PostgreSQL took these legs for the first time on this machine —
    61.3s vs SQLite 46.6s); the golden-set probe shows **10 hops across 7 of 8 answers**, every hop rendered, first
    pass bit-identical everywhere. Substrate re-measured after this commit's corpus bridge section: 330 labels,
    **155 chunks**, **46 whole-label hits across 24 labels** (20 demo teams + their 4 leagues). Twelve witness arms
    (mutations of the shipped scan and the answer integration, predictions written before the run): ten red exactly
    the predicted cases; two under-predictions chased rather than smoothed — A2's unexcluded duplicate also reds the
    rule case (the duplicate carries the via mark, so its first-pass ref has no hop line), and A5b's digest unmark
    also reds the first-pass identity case, which reads digest marks; two designed survivors confirmed — the
    casefold and the header-strip in the scan are currently unexercised by the label population and are kept for
    body-authoring variance. Two pre-existing HEAD reds were fixed in this landing because they sit in its files:
    `e00e87d` had stringified the citation `ordinal`/`score`/`similarity` and the `[n]` `ref` to satisfy the agents'
    response model — against `apps/web/lib/types.ts` and the test that already read them as numbers — so the numbers
    are restored and `app/api/v1/agents.py` stringifies at its own boundary; and `real-world-football-entities.md`'s
    lead section chunked without a ` — ` heading line, reddening the corpus contract since `1dd375c`, fixed by making
    the lead an `## Overview` section. Three agent-lane reds are pre-existing and NOT fixed here, measured on planes
    at `e00e87d`, `dab6b50` and HEAD without any of this work: `test_run_cached_answer`, the benchmark overall and
    confidence gates — named in the commit, owed a follow-up unit. No whole-suite leg is claimed.
