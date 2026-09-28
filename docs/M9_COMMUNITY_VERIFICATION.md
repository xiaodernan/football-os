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
* Whole-suite SQLite leg over `7d2ee6d`: **rc=0**, which is the runner's own statement that nothing failed. Its
  final summary line was **not recorded** — the same lost-last-line behaviour of a bash file redirect that ate the
  summary for the single-file run earlier in this session, three times now. So this milestone publishes no pass
  count for that leg, and the next leg must be run with `--junitxml` rather than trusting a redirect's tail. The
  arithmetic prediction made before it started (1229 + 45 = 1274) is not evidence and is not recorded as one.

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
* Both legs of the test matrix are not yet closed for this milestone: the PostgreSQL leg has not been run over
  `8cbde7e`..`63161d2`, and the SQLite leg's count is unrecorded as described above. §42's payments remain the one
  spec item the whole project has never implemented: no price, provider or checkout field exists anywhere.
