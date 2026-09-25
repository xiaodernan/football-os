# M7 — §23's shortlist: a list that stores membership, not figures

Spec line: §23 asks the scout for **建立 shortlist** next to the search and the report. This document certifies
the tier that answers it: migration `0015`, `app/services/scouting/shortlist.py`, seven routes under
`/api/v1/scout/shortlists`, and the panel on `/scout` that renders them.

## 1. The decision, and the table that carries it

A shortlist could have been a table of players with the numbers that recommended them pasted in. This one is
not, and the reason is a comparison with the table in this project that *does* store numbers:

| | `transfer_listings` (§22) | `scout_shortlists` / `scout_shortlist_items` (§23) |
| --- | --- | --- |
| what it is | the record of an act — an offer was made at this price and a seller answered it | a live question — *who am I watching* |
| figures | **snapshotted**: asking fee, current price, release clause, wage, fit, at listing time | **none**: every number is read from `real_players` again on the request that shows it |
| why it may not move | rewriting it would falsify a negotiation that already happened | a copied rating keeps answering after the row behind it has been regenerated, scored, or repriced |

So `scout_shortlists` holds `owner_id`, `name`, `query` (the sentence the list came out of), `role`, an optional
`career_id`, and the two provenance columns; `scout_shortlist_items` holds `shortlist_id`, `player_id`, `note`
and `position`. That is the whole storage. `position` is insertion order — the only number about a player in the
schema, and a number about the list rather than about him.

Two constraints the schema, not the code, enforces:

* `UniqueConstraint(shortlist_id, player_id)` — one player cannot be on one list twice, so the list's own count
  cannot lie about how many players it holds;
* `ForeignKey(real_players.id, ondelete="CASCADE")` — a membership row cannot outlive the player it names, so a
  list cannot accumulate ghosts. `uq_shortlist_owner_name` also keeps two lists of one account from sharing a
  name, while leaving two accounts free to choose the same words.

`career_id` is `SET NULL`: **a deleted career must not delete the list that was reading it** — it may only stop
the list being able to say whose need it answers.

## 2. The routes

| Door | Session | Answers |
| --- | --- | --- |
| `GET /scout/shortlists` | required | this account's lists, each with its sentence, role, career slug, `players_listed`, `room_left`, and the integrity gate over its own rows |
| `POST /scout/shortlists` | required | open a list from a name plus an optional sentence, role and career |
| `GET /scout/shortlists/{ident}` | required | the read: every member with §23's own candidate projection, the career's current need and fit, and the stored sentence re-applied member by member |
| `PATCH /scout/shortlists/{ident}` | required | change the words — name, sentence, role, career link |
| `DELETE /scout/shortlists/{ident}` | required | delete the list; the cascade takes the membership rows |
| `POST /scout/shortlists/{ident}/items` | required | put a stored player on it, with an optional note |
| `DELETE /scout/shortlists/{ident}/items/{player}` | required | take him off; the rows that stay keep the positions they had |

Twelve scout doors in all; the contract carries **90 paths and 105 operations**, regenerated from this tree and
committed as `docs/api/openapi.json`.

## 3. Refusals, each with the figures behind its sentence

Twelve codes, published by `/scout/rules` (all twelve as a list, eight of them written out as sentences a client
can branch on), and classified in exactly one of three answer shapes:

| Shape | Codes | Measured answer |
| --- | --- | --- |
| 404 — a thing that is not there | `no_such_shortlist`, `no_such_player`, `no_such_career` | `no_such_shortlist` on another account's id: `{'code': 'no_such_shortlist', 'ident': 'ssl_dawJtdNklbnwV7mL', 'lists_held': 0}` — a foreign id is answered exactly like one never issued |
| 422 — words that cannot be stored | `name_required`, `name_too_long`, `query_too_long`, `note_too_long` | 90-character name: `'nnnn…' is 90 characters and this column holds 80`, with `length: 90, max: 80` |
| 409 — a state the request would break | `name_taken`, `too_many_shortlists`, `shortlist_full`, `already_listed`, `not_listed` | same player twice: `409 already_listed`, `"Toriel Veitoux is already on 'Shape list bf78d5'…"`, with the shortlist id and the player slug beside it |

The caps are the service's, not pydantic's, on purpose: a transport-level 422 names a field and a rule, while
the service's refusal names **the length it was handed and the length allowed**, which is the version a reader
can check their own request against. The limits are `20` lists per account and `30` players per list, and a
route refuses at the twenty-first and the thirty-first with `held` and `limit` printed.

The length caps also apply to fields that would otherwise be silently truncated by the database: a 241-character
note is refused, and the test suite checks that no half-written note was stored either.

## 4. The read, measured against the live dev world

One list, two members, the stored sentence `找一个 22 岁以下的球员`:

```text
item 1  toriel-veitoux  overall 70  potential 77  headroom 7  asking 1,372,500  answers [22 岁以下]  lost []
item 2  faryn-caleith   overall 69  potential 70  headroom 1  asking   997,500  answers []         lost [22 岁以下]
counts  membership_rows 2 · printed 2 · answered_everything 1 · answered_nothing 1 · no_sentence_to_answer 0
```

The second row is 31 years old: it is on the list because somebody put it there, and the list says in its own
output that it no longer answers the question the list was built from. Nothing about that is stored, so nothing
can go quietly out of date.

`PATCH` the same list to `找一个 30 岁以上的球员` and the two members swap verdicts while the membership rows do not
move: still `answered_everything: 1, answered_nothing: 1`, now held by the other player. The order, the notes and
the ids are untouched — the sentence is what was stored, and the sentence is what was re-asked.

Every figure in those rows came out of `search.pool()`, the same projection `POST /scout/search` sorts and cuts,
so a list cannot print a number its own search disagrees with; `figures_from` says as much in the payload, and
`account_content` keeps the two kinds of data apart: *the name, the sentence, the order and the notes are this
account's own words; the players, clubs and figures beside them are generated fiction*.

## 5. The gate that ships with the tier

`shortlist_problems(session, user)` runs on the account's own rows inside `GET /scout/shortlists`, and checks:

* every membership row either names a player in the pool or is reported under `gone_from_the_world`, never
  printed as a blank;
* positions are exactly `1..n` with no repeat and no gap — the assertion that a duplicate would break;
* a name that does not fit its column, and a list holding the same player twice;
* and, for every member, that the printed `overall`, `age` and `headroom` equal the stored row's own columns —
  the copy-detection check, run against the same read a page gets.

`/capabilities` carries `m7_shortlist` with `ready` (is there a pool to list from), the counts of both tables,
the caps, and `stores_no_figures: true`. `/scout/rules` carries the whole `shortlists` block.

## 6. Where this tier stops

* **It is not a ranking.** No figure is computed across a list's members; `position` is the order rows were
  added. Ranking two players against each other is §27's comparison, dimension by dimension, with the same
  refusal of a single score.
* **Membership is not observation.** Putting a player on a list changes nothing about him — no form, no
  contract, no interest from a club, no wallet moved.
* **The re-check covers the stored sentence only.** Filters stated field by field on the search route are not
  stored on a list, so they are not re-applied either; a list that wants a question checked again has to keep the
  words it asked in.
* **No transfer happens here.** §22's market routes are the only doors that move a player or money; the
  remaining M7 item — a transfer simulation involving a scouted candidate — still has to be built.
* A list is private to its account: not published, not indexed, not shareable, disallowed for crawlers with the
  rest of `/scout`, and every figure on it is generated fiction about a generated player.

## 7. The panel, walked in a browser

`/scout` now carries `ScoutShortlistPanel` under the search: open a list (optionally carrying the sentence that
was just typed), add a player the search returned with a note of one's own, read the list back, refuse to add him
twice, take him off, delete the list. It is driven by the same production-build walk as the rest of the screen —
`apps/web/scripts/qa-scout.mjs`, now **97/97 checks** (the 29 added ones are all shortlist), on uvicorn `8734`
against the development PostgreSQL world and `next start -p 3213`, 2026-09-25 at 02:57 local.

What the added checks assert, with the numbers they printed:

* **the page publishes the API's caps, not its own** — `cap 20 lists · 30 players each` on the panel's eyebrow;
* **a list starts empty and says so** — `0 PLAYERS ON IT · 0 MEMBERSHIP ROWS STORED · 30 ROOM LEFT`;
* **the sentence typed into the search box is the sentence stored on the list** — read out of the list row, not
  from a request the walk made behind the page's back;
* **the list's numbers are the search's numbers** — `2:21/21 5:68/68 6:77/77 7:9/9 8:1336500/1336500`, cell by
  cell, comparing the two tables the reader has both on screen; the foot is compared as the word `left`, because
  a foot is not a number and the first version of this check read a matching pair as a mismatch;
* **the note survives, and so does the position** — `1`, and `walk note: kept from the first search`;
* **a stored sentence is re-applied to the member it found**, printed as answer chips beside the words the
  vocabulary never understood: `22 岁以下左脚预算 2000 万中场 · not understood: 擅长推进`;
* **the second add of one player is refused on the page**, and the refusal keeps its arithmetic: `already_listed —
  Fariel Toban is already on 'QA list 250255'; a second row for one player would make the list's own count lie…`;
* **the refusal survives the refresh that follows it** — and this is the one place the walk caught a real defect
  rather than a wrong assertion. `openList()` used to clear the fault on success, so the re-read that proves the
  row was *not* added also wiped the sentence explaining why. A refusal is now cleared only by the next write the
  reader attempts;
* the row the walk is about to remove is waited on by its own button (`disabled` is a state, not a failure), two
  rows sit at `1,2` with `28 ROOM LEFT` printed, removing one leaves the other where it was, and after the
  delete the account holds no list of that name — the walk cleans up its own lists;
* one browser console error appeared in the whole run and it is the walk's own 409, named in its allowance list.

## 8. Measured

* **Migration round trip.** `alembic upgrade head` from `0014` on a throwaway SQLite file, then `alembic check`:
  *No new upgrade operations detected* — the schema and the models agree, which is the gate that has caught an
  invented index here before. The same migration ran at the head of both full test legs below, on PostgreSQL too.
* **Tests.** `apps/api/tests/test_scout_shortlist.py` — **50 items**, green on the SQLite leg in 194 s.
* **PostgreSQL full leg, this tree:** **779 passed, 1 skipped in 983.99 s** (730 items before the tier, 780 with it).
* **SQLite full leg, this tree:** **779 passed, 1 skipped in 718.04 s** — the same 780 items, both engines green.
* **A route-level shape probe** (`/scout/shortlists` against the running dev API, list created and deleted again)
  produced the figures quoted in §4: `already_listed` beside `shortlist`+`player`, `name_too_long` beside
  `length: 90, max: 80`, a foreign id answering `no_such_shortlist` with `lists_held: 0`, and `401 unauthenticated`
  for an anonymous caller at every door.
