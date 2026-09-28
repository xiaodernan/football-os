# M9 verification — §35 Community

Every figure in this file was read out of a command this run executed and printed, with the plane it was measured
on named beside it. Where a figure could not be read, the row says so rather than carrying a number forward.

## What landed

Four commits, in the order they were made:

| commit | what it carries |
| --- | --- |
| `19e3077` | the five `community_*` tables, `services/community/posts.py`, migration `0023`, and the tier's own test file |
| `8cbde7e` | the twelve HTTP doors, the community tier's registration in the project's one answer table, and the doors' tests |
| `7d2ee6d` | the regenerated OpenAPI contract |
| `63161d2` | `/community`, its client panel, `lib/community.ts`, and `scripts/qa-community.mjs` |

The tier's shape is one sentence: **a post stores a kind, a pointer and the author's words, and no figure about the
thing it shares**. `likes`, `comments`, `reposts`, `followers`, `following` and `feed_total` are `count(*)` over the
reaction, comment, repost and follow rows at the moment of the read, each printed with its own formula. Reach is a
predicate over follows, so an unfollow withdraws it at once and deletes nothing, and a post the reader cannot reach
is answered as absence rather than as a refusal — which is how this tier stays free of a 403 (§51 reserves that
answer for the permission matrix, and a community door asks only whether the caller has a session).

## The figures, with the plane each was measured on

* `mypy app` — clean over **101 source files** (100 before the doors, plus `api/v1/community.py`); `ruff check .`
  clean over the whole API package, and `ruff format` left all five owned files unchanged.
* `apps/api/tests/test_community.py` alone, on the committed tree: **45 passed in 10.31s** (rc=0, read from the
  runner's own summary line). Twenty-seven cases came with the service and eighteen with the doors: the route guide
  held against the live `/api/v1/community` route table in both directions, all eleven private doors answering a
  caller with no session **401 before any row is looked up** (parametrized from the guide, so a door added later
  cannot arrive unguarded), ten codes refused through a real request each carrying the status the shipped table
  publishes, and the erase door answering somebody else's post as absence while taking its reaction, comment and
  repost rows down with it.
* `tests/test_club_answers.py` — **86 passed in 2.37s**. This is the file that guards the table `8cbde7e` widened,
  and its `TIERS`-derived assertions are what made appending the community tier the honest way to register it.
* `alembic upgrade head` reaches `0023_community` and `alembic check` answers *No new upgrade operations detected*
  — both against a scratch SQLite file under `.scratch/`, never the shared dev database.
* `docs/api/openapi.json` — **129 paths / 164 operations → 137 / 176**, and the diff is **653 insertions,
  0 deletions**: eight paths, twelve operations, all `/api/v1/community/…`, nothing else moved. The same tree
  measured 137 / 176 in-process through `app.openapi()` before the server was started, and the export was taken
  from that server on `127.0.0.1:8739` — `scripts/export_openapi.py` scrapes a *running* service and its default
  base is the shared dev API on 8731, which is an older build with neither club nor community tier.
* Web tier: `tsc --noEmit` rc=0 and `next build` rc=0 (both measured again after the two repairs below).
* `scripts/qa-community.mjs` — **38 of 38 walk checks passed, exit 0**, on `http://127.0.0.1:3217` against a
  production build, attributed to its own tree by the `BUILD_ID` the served HTML carries, with the API this run
  started on `127.0.0.1:8740` over `.scratch/m9_qa_api.db`. Screenshots landed in `docs/screenshots/` (untracked,
  as every other milestone's are).
* Whole-suite SQLite leg, per-run database: **`tests=1275 failures=0 errors=0 skipped=1`, runner `rc=0`, junit
  `time=633.98s` against the wrapper's own wall of 638.44s** — every one of those figures read out of
  `.scratch/leg_m9_sqlite2.xml`, which is why this leg has a number and the leg before it did not. The tree at launch
  was `7d2ee6d`; the only working-tree changes during the run were the docs commits `ff575a2` and `cfb6672`, and no
  test reads `docs/` (grep over `apps/api/tests` and `apps/web/scripts` returned no reader), so the code measured is
  `7d2ee6d`'s code. The one skip is
  `tests/test_scout_search.py::TestPublishedArithmetic::test_each_sorting_orders_the_survivors_by_its_published_key[need_fit]`,
  named from the XML's own `skipped` element rather than counted.
* The composition of that 1275, counted per test class from the same report: **45** cases in
  `tests/test_community.py` and **1230** across the other 163 files. §57 recorded **1229** for that second population
  (both `.scratch/leg57_sqlite.log` and `.scratch/leg57_pg.log` print `1229 passed, 1 skipped`), and
  `git log --name-only cdd15b3..HEAD -- apps/api/tests` shows no commit touching the test tree except my two community
  commits. So **one case appeared in the rest of the suite and this record does not claim to know where**: two
  hypotheses were measured and rejected — nothing outside `test_community.py` mentions `answers.TIERS`, and the corpus
  check at `tests/test_knowledge_rag.py:38` is a single case with a `>= 12` floor while
  `git log cdd15b3..HEAD -- data/knowledge` is empty. Task #65 carries the remaining method. An enumeration that
  silently gains a case is the same kind of enumeration that can silently lose one, which is why this stays a named
  gap rather than becoming a rounding.
* An earlier SQLite leg over the same commit is superseded: it printed **rc=0 and no summary line**, the third
  occurrence of a bash file redirect swallowing pytest's last line, and it is the reason the legs now run with
  `--junitxml`. The arithmetic prediction written down before either leg started (1229 + 45 = 1274) missed by one and
  is recorded as a prediction that was wrong, not as a figure.

## The two defects the walk found, both in the page rather than the tier

1. The panel called `browserFetch` without naming a verb, and that helper defaults to **GET** — a GET with a body
   is a fetch the browser refuses outright, so every write pressed on the page failed inside the client while the
   API suite stayed green. `useCommunityCall` now names its method the way §39's `useClubCall` does. The first walk
   over the page was 20/37 and this was the cause of most of its reds; the 38/38 figure above was measured on the
   repaired tree, which also corrects the sentence in `63161d2` that said the re-run was still outstanding.
2. A note that said only `publish: posted` is the same sentence for every post, so the walk could not tell two
   presses apart; and a note kept in the row could not survive an unfollow or an erase, because the refresh the verb
   triggers unmounts the row that owned it. The note now carries the facts the door answered with (the new id,
   `recorded_now`, `removed`) and the wall keeps a copy of its own under `data-note="wall"`. Two walk iterations
   (28/37 then 35/38) were spent finding out that the harness, not the tier, was the one lying.

## What M9 does not claim

* **No entitlement gate.** The meter has no community feature, so publishing costs nothing and the ceilings are row
  counts, not prices — said in the tier's own `LIMITATION` sentence and printed on the page.
* **No reader list, and no private channel.** Nothing in the schema can name a recipient; the doors publish counts
  and vocabulary, and the panel's follow state is derived from the authors the feed itself listed. A followed
  account that has published nothing reachable is therefore not shown as followed, which the page says out loud
  rather than guessing at.
* **No moderation, reporting, blocking or DMs** — §35's community is a publication tier in this build.
* PostgreSQL leg over the same code, its own throwaway database on the pgvector container: **`tests=1275
  failures=0 errors=0 skipped=1`, runner `rc=0`, junit `time=1323.95s` inside a wrapper wall of 1326.76s**. The two
  legs therefore agree on the same three figures — 1275, zero failures, the one named skip — and on the same
  arithmetic (45 community + 1230 rest), so the count is not an engine's accident. §42's payments remain the one
  spec item the whole project has never implemented: no currency column, payment provider or checkout field exists anywhere. The prices that *do* exist — §22's `transfer_listings.current_price` and the USD-per-token rates in `app/providers/__init__.py:129-130` — are a valuation and a cost measure, not a payment, and this milestone corrected the three sentences in this project's own records that said otherwise, in the section below.

## A claim this milestone corrected

A pre-flight census over 206 source files (`price`, `currency`, `checkout`, `vendor`, `payout`, `creator`, `program`,
`guide`, `entitlement` — run 2026-09-28 to plan M10) falsified a sentence this project had written three times:
*"no price, provider or checkout field exists anywhere in the project."* `TransferListing`
(`apps/api/app/models/__init__.py:1034`) carries a `current_price: Mapped[int]` column, and
`apps/api/app/providers/__init__.py:129-130` holds `_PRICE_IN` / `_PRICE_OUT` USD-per-token rates the cost meter
multiplies. What is genuinely absent — and what `services/entitlements.py:77 NO_PAYMENT` has been saying correctly,
scoped to its own tier — is a **payment**: no currency column, no provider, no checkout field. Four records were
rewritten to say the narrow true thing: this file, `docs/M8_CLUB_OS_VERIFICATION.md` (§57's "does not claim"),
`docs/M8_CLUB_WEB_VERIFICATION.md` (§42's bullet) and the §42 row of `docs/SPEC_COVERAGE_AUDIT.md`, plus the ROADMAP
M8 cell. No test or script reads `docs/` (grep over `apps/api/tests` and `apps/web/scripts` returned no reader), so
the correction moves no measured plane. The method is the point: a claim about *the whole project* has to be measured
over the whole project, not inferred from the tier that wrote it.

## The probe over §35's four load-bearing decisions

`scripts/probe_m9.py`'s discipline was carried over from §57: an unmutated control has to be green before any arm
counts, an arm has to change a *value or predicate* rather than break the syntax (a mutant that will not import
produces zero reds and zero evidence), every red has to be named from the runner's own report, and the target is
restored from a byte-exact copy with a hash check. Four arms, one per decision:

| arm | what it deletes | predicted red | observed red | named case(s) |
| --- | --- | --- | --- | --- |
| A | the post-ceiling guard (`if held >= MAX_POSTS_PER_USER` → `if False and …`) | 1 | **1** | `test_the_post_ceiling_accepted_at_its_edge_is_refused_one_past_it_with_its_own_figures` |
| B | the followers reach predicate in `read_post` | 2 | **2** | `test_a_followers_post_reaches_a_follower_and_answers_absence_to_everybody_else`, `test_following_through_a_door_is_what_opens_a_followers_post_to_that_reader` |
| C | the pointer-prefix branch in `_pointer` | 2 | **2** | `test_a_post_that_is_not_a_note_must_point_at_its_own_kind`, `test_every_code_a_door_can_refuse_with_is_answered_with_the_status_the_table_publishes` |
| D | the `note`-carries-no-pointer branch (a silent drop instead of a refusal) | 1 | **1** | `test_a_note_carries_words_and_refuses_a_pointer_it_could_not_explain` |

`control rc=0 reds=0` first, then **`SUMMARY arms=4 survived=0 restored=True`**, and `git status --porcelain` for the
target came back empty afterwards. Each arm was pre-checked in memory before it ran: anchor matched exactly once, the
mutant still compiled, and exactly one `raise` ended up behind a constant-False guard — so a survivor would have
meant a real hole rather than a broken edit. The predictions were written into the script before the first run, and
every one of them landed: **six reds across four arms, each the predicted case, none extra**.

Arm C is the one worth reading twice. It kills only the *prefix* branch, so the two cases that exercise `_pointer`'s
other branches — a `note` carrying a pointer, and a pointer shaped wrong (`?`, `#`, trailing space, trailing slash) —
stay green, and that is reported as **partial coverage** rather than counted as a catch. Arm D exists because of that
reading: it aims at the note branch specifically, and it did turn exactly the case its prediction named.

What the probe does not claim: it says nothing about the HTTP layer (the twelve doors are held by their own cases,
including the eleven 401-before-any-row checks), and it does not touch `answers.ANSWERS`, whose collision blindness —
two tiers, one code, the same status — is what `no_such_account` was renamed for and is now held by a test instead.
