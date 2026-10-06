# PLAN — the work that is left, in the order it should be done

`ROADMAP.md` says which milestone is open and what has been proven. This file says what to build **next**, in
order, with the evidence each item has to produce before it counts as done. It is written to be picked up cold:
every item names the files it touches, the gate it must pass, and the thing that would make it a lie.

Rule inherited from spec §96 and this project's own practice: **an item is done when its claim is measured, not
when its code exists.** A number in a document that no command reproduces is not evidence.

Last updated 2026-10-06.

---

## Done, and what it cost

| Item | Landed | Evidence |
| --- | --- | --- |
| **0. one gate, not three** | ✅ 2026-09-30 | `scripts/check.sh` and CI both run `python -m ruff check` with no path arguments. Proven by planting an unused import in `evals/`: invisible to the old target, caught by the new one, and the script exits 1. |
| **1. §13's 3D pitch** | ✅ 2026-09-30 | `components/pitch.tsx` projects the board's own metres isometrically; `237/237` walk checks on a production build, with a check that recomputes every dot from its metres and another that holds the projected lawn inside its `viewBox`. `docs/M4_WEB_VERIFICATION.md` §8. |
| **2a. §81's `locales` claim** | ✅ 2026-10-01 | `tests/test_locale_claims.py` binds `locales` to the catalogues in both directions. Found that `zh.json`/`zh-TW.json` are 278/278 copies of English, so the field stays `["en"]` — and now cannot be moved without a translation or left unmoved with one. |
| **2b. §81's translations + the switcher** | ✅ 2026-10-06 | `LocaleSwitcher` writes the `fo_locale` cookie middleware has always read; `locales` moved to `["en","zh","zh-TW"]`; both Chinese catalogues carry the full key set (`zh` 287/288, `zh-TW` 288/288 written as Traditional, not converted). `test_locale_claims.py` 4/4 on the new catalogues; the locale walk drives the real switcher and reads the repainted shell. Remaining half: wiring page bodies to the catalogues (only `Nav` and the switcher read them today). |
| **4. §61 account erasure end to end** | ✅ 2026-10-06 | `GET/DELETE /auth/account`: preview inventories every row and byte, one confirmed transaction, media containment refused before any write, last-owner blocking (409), §60's third 403 code (`invalid_password`) registered. 4 tests including the escaping-storage-key case a planted-defect probe demanded. |
| **§38/§60 portfolio share + PDF** | ✅ 2026-10-06 | `POST/GET/DELETE /portfolio/share[/{token}]`, `/portfolio/cv.pdf` (reportlab), robots keeps both off crawlers. Committed with the two above because all three share one contract file. |
| **— migration `2e197f085070`** | ✅ 2026-09-30 | Not on the plan; found by trying to run the SQLite leg it broke. Unadjusted autogenerate, PostgreSQL-only DDL, a `downgrade()` that could not run anywhere, and each new column indexed twice. |
| **— the OpenAPI contract and autocrlf** | ✅ 2026-10-06 | Not on the plan. The working copy of `docs/api/openapi.json` had been checked out CRLF while `scripts/export_openapi.py` writes LF, so the byte gate failed with *equal byte counts* — a host newline policy, not an artifact defect. Regenerated from the tree (162 paths / 208 operations, LF). Windows checkouts of this repo will do this again; the remedy is the exporter, never hand-editing. |

**The pattern worth naming.** Three of the four items above were *claims that had drifted from their evidence*,
not missing features: a gate three targets wide, a `locales` field nobody checked, a migration that had never
been run on the engine the docs tell you to use. The features in this project are in good shape. The documents
and the fields are where the work is.

---

## What is actually open

| Area | State | Where the truth is |
| --- | --- | --- |
| M0–M7 | ✅ verified | `ROADMAP.md` gate table |
| M8 Club OS | ✅ verified 2026-09-28 — only §42's **payments** open, and spec §42 says not to rush them | `docs/M8_CLUB_OS_VERIFICATION.md` |
| M9 Community | 🟡 §35 (posts, reactions, follows, feed) landed 2026-09-28; §36/§37 verbs still absent | `docs/M9_COMMUNITY_VERIFICATION.md` |
| M10 Creator Economy | 🟡 §38 portfolio landed, share links + CV PDF landed 2026-10-06 | `docs/M10_PORTFOLIO_VERIFICATION.md` |
| M11 Multi-Agent | ⬜ not started — and §30 Knowledge Graph waits on it by decision | `docs/SPEC_COVERAGE_AUDIT.md` |
| M12 Hardening | 🟡 §61 account erasure landed 2026-10-06; the rest of M12 (load, ops) untouched | `docs/SECURITY_AUTHORIZATION_VERIFICATION.md` |
| §81 i18n | 🟡 catalogues full, switcher works, shell switches — page bodies are still English literals | the grep that counts `useTranslations` callers |

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

## Item 2a — §81 i18n: the claim, before the translation

**Why.** The cross-cutting gate says the UI is English-only and `GET /capabilities` reports `locales: ["en"]` with
`locales_planned` beside it. That is honest, and it is also the only field in the project that nothing checked.

**Done 2026-10-01.** The catalogues exist with the full key set; `tests/test_locale_claims.py` now binds `locales`
to them in both directions, so the field cannot be over-claimed or left stale. See the table above.

**What it found.** The catalogues are copies, so the honest answer stays `["en"]` and the switch is now a
mechanism rather than a note to a future reader. The translating itself is item 2b.

**Files.** `apps/web/messages/*.json`, `apps/web/lib/i18n.ts`, `apps/web/app/settings/**`,
`apps/api/app/api/v1/meta.py`.

---

## Item 2b — §81's actual translations

**Done 2026-10-06 (two commits: `2671102` mechanism, `56d524c` words).** The switcher writes the cookie,
middleware answers in it, and both Chinese catalogues carry the full key set — `zh` 287/288 (the search example
sentence is Chinese in the English file already, so its one fallback is the honest state), `zh-TW` 288/288
written as Traditional with Taiwan usage, not converted. `test_locale_claims.py` 4/4 on the new catalogues; the
full locale walk (`node scripts/visual-qa-locale.mjs`, production build at `56d524c`) passed **249/249**, including
driving the switcher, surviving a reload and reading the repainted shell. The claims in `meta.py`,
`messages/README.md`, `CONTRIBUTING.md`, `ARCHITECTURE.md` and `M3_WEB_VERIFICATION.md` were corrected in the same
commit as the words.

## Item 2c — §81's remaining half: wire the pages to the catalogues

**Why next.** A complete catalogue that two components read is a library, not an interface. `grep -r
"useTranslations\|getTranslations" apps/web --include=*.tsx` returns `Nav.tsx` and `LocaleSwitcher.tsx` and
nothing else — every page body still renders English literals, so the switcher repaints the nav bar above a
page that cannot change. The catalogue is now the *easy* part; this item is the long tail.

**Do.** One namespace at a time, in the order a reader meets them: `auth` (login/register forms), `settings`
(the page that also carries the delete-account panel), `common` (shared verbs), then the big feature pages
(`scout`, `career`, `validation`, `disclaimer`). Each page wired is a page the walk can read in Chinese —
extend `scripts/visual-qa-locale.mjs` to assert one translated string per wired page rather than trusting the
absence of literals.

**Evidence.** The locale walk's per-page assertions: switch to `zh`, read a string that used to be a literal,
assert it equals the catalogue's value. The `useTranslations` caller count moves with each landing.

**Watch for.** `middleware.ts` resolves the locale server-side; a client component reading `useTranslations`
needs the locale in its provider — `app/layout.tsx` already passes it, so the trap is only forgetting
`getTranslations` on server components (it is async; `Nav.tsx` is the client-side worked example).

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

**Done 2026-10-06 (`2671102`, found as a finished uncommitted tree from 10-03, verified then committed).**
`GET /auth/account` previews the full inventory; `DELETE /auth/account` takes the phrase and the password,
erases in one transaction, refuses an escaping storage key **before** any write (503 `private_media_not_erased`),
and blocks a last owner with other active members (409). Rows that must survive (`SET NULL` model calls) do; the
audit row names no erased identity. The census gained its third 403 code (`invalid_password`) and an erased
account answers 401 `unauthenticated` again rather than 403 describing somebody who is not there. Evidence:
`tests/test_account_deletion.py` (4 cases, including the escape probe), full suite green except the contract
byte gate this same landing fixed.

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
