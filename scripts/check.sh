#!/usr/bin/env bash
# Every gate the project recognises, in one command (spec §88 Definition of Done).
# Run before committing. Exits non-zero on the first failure.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "── Lint: the project's one target ─────────────────────"
# One file, `scripts/lint.sh`, and CI runs that same file. It lints the whole of `apps/api` plus every committed
# `.py` outside that tree, the extra population derived from `git ls-files` on every run rather than typed here —
# the typed lists are what let three targets disagree while only one was enforced, and what kept four committed
# files in `scripts/` invisible to a command whose comment claimed the whole project was in scope.
bash "$ROOT/scripts/lint.sh"

echo "── API: types ────────────────────────────────────────"
(cd apps/api && python -m mypy app)

echo "── API: tests ────────────────────────────────────────"
(cd apps/api && python -m pytest)

echo "── API: migrations (drift check on SQLite + PostgreSQL) ─"
(cd apps/api && rm -f _check.db \
  && DATABASE_URL="sqlite:///./_check.db" python -m alembic upgrade head >/dev/null \
  && DATABASE_URL="sqlite:///./_check.db" python -m alembic check \
  && rm -f _check.db)
if [[ -n "${DATABASE_URL:-}" && "${DATABASE_URL:-}" != sqlite* ]]; then
  (cd apps/api && python -m alembic upgrade head && python -m alembic check)
else
  echo "skipped PostgreSQL leg (export DATABASE_URL to a PostgreSQL URL to run it)"
fi
# The two legs below are CI's PostgreSQL job, and one variable decides both: the suite above switches engines on
# FOOTBALL_OS_TEST_DATABASE_URL (`tests/conftest.py`), so the seed and the RAG benchmark take the same switch rather
# than a second one to drift from the first. CI runs the suite twice — once per engine — because SQLite accepts
# over-length strings and lax types; a local run is one engine per invocation, chosen by this variable.
if [[ -n "${FOOTBALL_OS_TEST_DATABASE_URL:-}" && "${FOOTBALL_OS_TEST_DATABASE_URL:-}" != sqlite* ]]; then
  echo "── API: seed on the PostgreSQL engine ───────────────"
  (cd apps/api && python -m seed --with-demo-user)
  echo "── API: RAG evaluation gates (pgvector leg) ─────────"
  # Spec §64's benchmark is the reviewer for any change to retrieval, chunking or the corpus. The suite gate
  # (`tests/test_knowledge_rag.py`) already holds the same thresholds on whichever engine the suite is on;
  # this leg is CI's report shape on the engine CI runs it on, so a quiet corpus change cannot merge.
  (cd apps/api && python -m evals.run_rag_eval)
else
  echo "skipped the seed and RAG-benchmark PostgreSQL legs (export FOOTBALL_OS_TEST_DATABASE_URL to a throwaway PostgreSQL URL; the suite's own gate tests/test_knowledge_rag.py ran above)"
fi

echo "── Web: refusal-shape gate ───────────────────────────"
# Not a browser walk: this one loads apps/web/lib/api.ts through the repo's own TypeScript and feeds it the
# answer bodies pinned in apps/web/fixtures/refusals.json, every one of which apps/api/tests/test_error_answer_shape.py
# holds against the backend's bytes. It needs no server and no port, so it belongs with the other gates and not in
# a scheduled walk — and neither tsc (tsconfig excludes `scripts`) nor next lint (its dirs do not include `scripts`)
# reads a .mjs, so a runner has to name it or nothing does.
(cd apps/web && node scripts/qa-error-shape.mjs)

echo "── Web: script-inventory gate ────────────────────────"
# Who checks the checkers. Every invocable file in apps/web/scripts is either named by a runner this gate reads
# (check.sh, ci.yml, the package manifest) or exempt for a reason re-proved from its own bytes on every run — so
# "the browser walks are verified" cannot quietly become a claim carried by files nothing invokes. It reads files
# only: no server, no browser, no port, which is why it runs here rather than joining the live-tier walks.
(cd apps/web && node scripts/qa-gate-inventory.mjs)

echo "── Web: middleware gating gate ───────────────────────"
# Which routes a signed-out reader may reach is one function's decision, and a prefix list that reaches down into
# `/video/shared/<token>` made two share-link pages answer 307 to /login — a link handed to a person with no
# account. This gate loads `isProtected` out of middleware.ts itself (transpiled, called), and asks it of all 59
# page routes, so a change to the matching logic moves the verdict and not only the lists. Files only: no server,
# no browser, which is why it runs here rather than in the live-tier walks that would need a token-free plane.
(cd apps/web && node scripts/qa-middleware-gating.mjs)

echo "── Web: crawl-policy reconciliation gate ─────────────"
# middleware.ts, app/robots.ts and app/sitemap.ts each decide part of what a crawler may see, and each only
# *described* the others in a comment. This gate loads all three decisions (transpiled, called) and reconciles them
# against every page's own `robots:` declaration: a session-gated route must be disallowed, an advertised route must
# be neither gated nor self-declared noindex, and an `Allow` exception must still cover a reachable page under a
# disallowed prefix. It found 8 gated pages in no disallowed prefix at all — `/agents`, the four `/graph` pages and
# the three `/simulation/aggregates` pages — whose `noindex` was inert because a 307 has no `<head>` to read.
# Files only: no server, no browser.
(cd apps/web && node scripts/qa-crawl-policy.mjs)

echo "── Web: metadata-title i18n gate ─────────────────────"
# §81 2c's permanent rule over the whole page population: a page may still write its <title> as a load-time
# literal, but only while its own heading is a literal that says the same thing — a literal tab over a keyed
# heading repaints differently per locale, which is the bug the arc is closing. The gate walks every app/**/page.tsx
# through the repo's own TypeScript, so the population, the literal ceiling (24 today) and the two ledger rows are
# all re-derived from the bytes on every run: a scan that narrows itself, an exemption that goes stale and a page
# that drifts from its own heading each go red. Files only: no server, no browser, which is why it runs here.
(cd apps/web && node scripts/qa-metadata-title.mjs)

echo "── Web: share-preview card gate ──────────────────────"
# §109: a share link is handed to a person, and the card they see before clicking said "FOOTBALL OS" instead of
# naming the CV, board or clip it carried, because a page with no `openGraph` of its own inherits the root layout's
# site-level block. This gate loads `sharedMetadata` and `pageMetadata` out of lib/site.ts (transpiled, called),
# then asks each of the three app/**/shared/[token] pages whether it builds its metadata through that helper rather
# than hand-writing one: the card must name the page, point at the share URL while the canonical stays on the parent,
# keep the helper's noindex, and pay for every `summary_large_image` promise with an image whose declared size matches
# the IHDR of public/og.png — the file whose absence docs/SEO_VERIFICATION.md §3 used to publish as a deliberate
# exclusion. It also grades the generator's own card markup, which may size, word and colour itself only from the
# module's constants and the stylesheet's tokens. Files only: no server, no browser.
(cd apps/web && node scripts/qa-share-preview.mjs)

echo "── Web: English-literal i18n gate ────────────────────"
# The other half of §81: the copy a page writes in English in the source, counted over every app/**/*.tsx through
# the repo's own TypeScript — JSX text, label-ish attributes and label-ish object properties, which are three
# shapes and not one. The count is a ceiling that may only fall: wiring a page to its catalogue lowers it, and a
# page that adds copy in English raises it, which is what this gate says. Files only: no server, no browser.
(cd apps/web && node scripts/qa-i18n-literals.mjs)

echo "── Web: catalogue-ICU gate ───────────────────────────"
# A catalogue message is a program, not a string: next-intl parses it when the page renders it, and a message
# that does not parse throws instead of printing. Nothing in the build reads a catalogue — next-intl resolves a
# key in the browser — so a malformed message compiles, typechecks, lints and then 500s the page that reads it.
# This gate parses every message in all three catalogues with the app's own ICU parser, refuses a plural or a
# select with no "other" branch, and holds the same key to the same placeholders in all three files. It found
# five messages written with mustache placeholders ({{count}}), which ICU reads as an argument that never began.
# Files only: no server, no browser.
(cd apps/web && node scripts/qa-icu-messages.mjs)

echo "── Web: catalogue's dead keys gate ────────────────────"
# The copy gate above asks whether every key the source asks for IS in the catalogue. This asks the other
# half: whether every key the catalogue holds is ASKED FOR. The two are not the same check, and only one of
# them was ever written — so the catalogue could hold 3736 keys while the tree read 3510, and every gate in
# the suite would have said the catalogue was complete. A key nothing reads is a translation that ships to
# nobody, written three times and re-read whenever the message beside it changes. This resolves every read
# in the tree (a translator is identified by its binding, and a read whose argument cannot be resolved
# exempts its whole namespace rather than being guessed at) and refuses a count above the floor. Files only.
(cd apps/web && node scripts/qa-unused-keys.mjs)

echo "── Web: locale-token gate ─────────────────────────────"
# The locale's technical tokens: the values that are the same in every language, and only those. Two claims
# in this project were conventions rather than measurements. "The identical values are the ones that are
# supposed to be identical" was never checked, so an English *phrase* could sit in the Chinese catalogue
# untranslated — a Chinese reader saw "weekly minutes" as a cap's name — and the set of identical values is
# now named, key by key, with the reason each one is the same in every language. And "the English catalogue
# is English" was never checked either: en.json held a Chinese sentence, so an English reader saw Chinese,
# and the Chinese copy of it made the coverage figures call it translated. Files only.
(cd apps/web && node scripts/qa-locale-tokens.mjs)

echo "── Web: field-name i18n gate ─────────────────────────"
# The arc's third class of defect, which the copy gate above cannot see: a catalogue key used for the *wrong
# field*. The scout's shortlist and the scout's transfer panel once shared one accessible name, so a script that
# filled a field by name filled the wrong one, and the browser walk went red over a projection that never ran. This
# gate reads every page's own component graph and refuses two different components on one page declaring the same
# constant aria-label key. Files only: no server, no browser.
(cd apps/web && node scripts/qa-field-labels.mjs)

echo "── Web: cookie-proxy gate ─────────────────────────────"
# The web tier's session design is one sentence: the access token is httpOnly, so no script can read it, and every
# call a browser makes reaches the API through the cookie proxy. Nothing held that. This gate reads every fetch in
# the tree and refuses one that names a target outside /api/ — an absolute URL, or a base built from one — because
# a browser that reached the API directly would have to hold the token. Files only: no server, no browser.
(cd apps/web && node scripts/qa-proxy-gate.mjs)

echo "── Web: API-string gate ──────────────────────────────"
# The other half of the dead-key gate, asked of the other side of the wire: the API publishes sentences, the
# web tier reads them, and where else does the web tier hold a copy? A copy in the web tier's own code is a
# dead string — the API's sentence is the live one, so the API's wording could change and the page would
# not follow it, and there would be a second place to fix when it does. The API's refusal sentences reach
# the web tier through the catalogue (the `errors` namespace, one key per code, the English value being
# the API's own message, held by apps/api/tests/test_locale_claims.py), so the catalogue is the source of
# truth and this gate reads them from there rather than teaching a second census of the API's source. It
# also holds that the refusal boundary is wired on both paths a refusal arrives through, and that every
# refusal code's sentence is translated in both Chinese catalogues. Files only: no server, no browser.
(cd apps/web && node scripts/qa-api-strings.mjs)

echo "── Web: error-boundary gate ───────────────────────────"
# A page that throws is caught by the framework's own error screen unless the tree holds a boundary --
# and that screen is English in every language, on a page whose every other sentence comes from the
# catalogue. The tree had a not-found page in the reader's language and no boundary at all. This gate
# holds that the boundary is there, that it is a client component, and that its sentences are in the
# catalogue in all three languages. Files only: no server, no browser.
(cd apps/web && node scripts/qa-error-boundary.mjs)

echo "── Web: types ────────────────────────────────────────"
(cd apps/web && npm run typecheck)

echo "── Web: build ────────────────────────────────────────"
(cd apps/web && npm run build)

echo "── All gates passed ──────────────────────────────────"
