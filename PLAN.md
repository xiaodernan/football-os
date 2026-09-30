# PLAN — the work that is left, in the order it should be done

`ROADMAP.md` says which milestone is open and what has been proven. This file says what to build **next**, in
order, with the evidence each item has to produce before it counts as done. It is written to be picked up cold:
every item names the files it touches, the gate it must pass, and the thing that would make it a lie.

Rule inherited from spec §96 and this project's own practice: **an item is done when its claim is measured, not
when its code exists.** A number in a document that no command reproduces is not evidence.

Last updated 2026-09-30.

---

## What is actually open

| Area | State | Where the truth is |
| --- | --- | --- |
| M0–M7 | ✅ verified | `ROADMAP.md` gate table |
| M8 Club OS | ✅ verified 2026-09-28 — only §42's **payments** open, and spec §42 says not to rush them | `docs/M8_CLUB_OS_VERIFICATION.md` |
| M9 Community | 🟡 §35 (posts, reactions, follows, feed) landed 2026-09-28 | `docs/M9_COMMUNITY_VERIFICATION.md` |
| M10 Creator Economy | 🟡 §38 portfolio landed; §60 authorization census landed | `docs/M10_PORTFOLIO_VERIFICATION.md` |
| M11 Multi-Agent | ⬜ not started — and §30 Knowledge Graph waits on it by decision | `docs/SPEC_COVERAGE_AUDIT.md` |
| M12 Hardening | ⬜ not started | `ROADMAP.md` |
| §81 i18n | 🟡 the UI is English-only and `/capabilities` says so | `ROADMAP.md` cross-cutting gates |

Three cross-cutting defects have now been found and fixed **three separate times** (M4's `tactics/sync.py`, M7's
scouting modules, M8's academy tier): *the committed tree does not pass the gate its own documents quote.* The
cause is always the same — `ruff` is run against a narrower target than CI uses. Item 0 exists so this stops
recurring instead of being rediscovered.

---

## Item 0 — make the local gate the same gate as CI

**Why first.** `scripts/check.sh` runs `ruff check app tests seed.py migrations`. CI runs
`ruff check app tests evals seed.py migrations`. The documents quote `ruff check app tests`. Three targets, one
of them enforced. A green local run is therefore not evidence that the commit is green, and the difference has
already cost three repair passes.

**Do.** Give `scripts/check.sh` and CI one shared target — a single line both read, so they cannot drift again.
Update every document that quotes a narrower command to quote the shared one. Add the missing `evals` leg to
`check.sh`'s local run.

**Evidence.** `bash scripts/check.sh` exits non-zero on a tree that CI would reject — demonstrated by planting a
lint error in `evals/` (a file neither the old script nor the old docs covered) and showing the script catch it.

**Files.** `scripts/check.sh`, `.github/workflows/ci.yml`, `CONTRIBUTING.md`, the verification documents that
quote the command.

---

## Item 1 — §13's 3D pitch, as an isometric projection of the same metres

**Why.** Spec §13 asks for 2D **and** 3D. M4 shipped the 2D pitch, drawn as SVG from the metres the
measurements come from, and the ROADMAP has carried "3D pitch" as an open item since. It is the only M4 item that
is neither blocked on another milestone nor a policy question.

**Do.** Add a third view to `/tactics/{slug}` — alongside the existing 2D and the drag-to-arrange board — that
projects each of the eleven from the same `x_metres`/`y_metres` the 2D view reads, through a stated isometric
transform, and draws it as SVG. No new dependency: a 3D view that renders from the same numbers is a *projection*,
and a projection is arithmetic, not a renderer. Print the projection formula on the page beside the view, the way
every other figure on this project prints its own.

**The claim that has to hold.** A point at a known metre coordinate lands at the projected pixel the printed
formula gives for it. That is checkable without a screenshot and is the difference between a 3D view and a picture
that looks 3D.

**Evidence.** A walk check that reads one player's projected coordinates out of the DOM and compares them with the
formula recomputed in the browser from that player's own printed metres — plus the toggle asserted to leave the
underlying metres unchanged, so the 3D view cannot quietly become a second source of truth.

**Files.** `apps/web/app/tactics/[slug]/page.tsx`, `apps/web/components/**` (a new pitch component),
`apps/web/scripts/visual-qa.mjs`.

---

## Item 2 — §81 i18n: land the catalogues, then switch the field

**Why.** The cross-cutting gate says the UI is English-only and `GET /capabilities` reports
`locales: ["en"]` with `locales_planned` beside it. That is honest, and it is also unfinished work the spec asks
for.

**Do.** Land `messages/{en,zh,zh-TW}.json` covering the shell — navigation, page titles, buttons, the empty and
error sentences — and a loader that resolves the active locale from the same place `/settings` already stores
preferences. Switch `locales` in `/capabilities` **only** for the locales that are actually complete, and keep
`locales_planned` for the rest. A half-translated page is worse than an English one.

**Evidence.** `/capabilities`' `locales` equals the set of catalogues whose keys are complete, asserted against
the catalogues themselves rather than a hand-written list; the walk switches locale and re-reads a page, checking
that the switched strings are the catalogue's, not the fallback's.

**Files.** `apps/web/messages/*.json`, `apps/web/lib/i18n.ts`, `apps/web/app/settings/**`,
`apps/api/app/api/v1/meta.py`.

---

## Item 3 — §36/§37's remaining community verbs

**Why.** §35 landed the wall. Spec §36 and §37 ask for more than a flat feed.

**Do.** Read `docs/SPEC_COVERAGE_AUDIT.md` for which §36/§37 verbs are still absent, then land them the way §35
was landed: one table per noun, counts recomputed at read rather than stored, no 403 anywhere in the tier (what a
caller may not reach is answered as absence), and the tier appended to `answers.TIERS` so a new refusal code
cannot silently mean two things.

**Evidence.** The tier's own test file green on both database legs, a planted-defect probe with no survivors, and
the answer-table collision check extended to the new codes.

---

## Item 4 — M12's first slice: account-level erasure end to end

**Why.** `ROADMAP.md`'s M12 gate names it as the thing that is missing: *today only player data is deletable*.
`DATA_POLICY.md` §3 says so, and a product that can create an account but not erase it is a promise it cannot
keep. It is also the one M12 item that needs no load test to verify.

**Do.** Implement the erasure `DATA_POLICY.md` already describes, against the tables that exist now, and make the
page say what it removed and what it kept, with reasons — the pattern §40's child-data view already uses.

**Evidence.** A test that creates an account with rows in every table that names a user, erases it, and asserts
each table's state afterwards against a written expectation — including the rows that must *survive* because
another account's record refers to them.

---

## Item 5 — M11's first composite task

**Why.** It is the last unopened milestone that is not hardening, and §30 Knowledge Graph is blocked behind it by
an explicit decision.

**Do.** Do not start with eight agents. Start with §33's smallest composite task end to end — an orchestrator, one
specialist, one tool call and a stored trace — and measure it against §64's benchmark before adding a second
agent. A multi-agent system with no benchmark is a diagram.

**Evidence.** The benchmark run, its score, and the trace of the run that produced it.

---

## How to work an item

1. Read the milestone's existing verification document first. It will name the trap that was already hit.
2. Write the check before the feature when the check is expressible — several of this project's best findings
   came from a check that existed before the thing it checked.
3. Run `bash scripts/check.sh`. If it fails on files you did not touch, that is a finding, not an obstacle:
   record it and fix it in its own commit, the way the last three passes did.
4. Verify in a browser when the change is visible. `scripts/verify-production.sh` builds, serves on a throwaway
   port, proves the port is serving *that* build, then walks. Do not quote a walk figure you did not run.
5. Write the evidence into the milestone's verification document with the command that reproduces it.
6. If a claim turns out to be false, correct the claim in the same commit that corrects the code. Several of this
   project's documents currently say what was true at the step they were written, and say so.
