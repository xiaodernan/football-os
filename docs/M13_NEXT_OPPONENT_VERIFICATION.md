# M13 verification — the next opponent, rendered

ROADMAP Phase 2 item 8's second read-only half landed on 2026-10-27: `career_view["head_to_head"]`
(this career's own record against the next opponent, summed from its fixtures and nothing else) and
`career_view["next_fixture_brief"]` (the engine's own band measurements of the next fixture's two
sides, side by side with the delta) have been published and pinned by `TestHeadToHead` /
`TestNextFixtureBrief` in `test_career.py` — and `/career/{slug}` never read either. This increment
types both blocks on the web wire and renders them on the career page in all three locales, in one
panel. Date: 2026-10-27.

## 1. What the panel prints

`components/CareerNextOpponent.tsx` is a server component. Its only arithmetic is formatting a
number to three decimals and prefixing a positive delta with `+`; every figure, sentence, formula
and note is the API's, so the page's comparison cannot drift from the measurement the engine will
play.

* The eyebrow names the round and the opponent, and the title says the opponent is measured two ways.
* **Head-to-head**: before the two have met, the empty state and the block's note; afterwards, a
  key/value grid (meetings, won/drawn/lost, goals, difference, points) plus one table row per
  meeting (number, home or away, score, outcome badge), the note and the formula beside its label.
* **Band measurement**: a key/value grid (venue, formations, systems — `the club's stored eleven`
  when no system is set — overall and form), then one table row per engine band with the career's
  index, the opponent's index and the signed delta; the stronger sentence, the weaker sentence, or
  the level sentence when neither list has a band; the note and the formula.
* `limitations["projections"]` closes the panel as a warning notice.

## 2. The live walk — four careers, four branches

Built with `next build` in a detached worktree (`D:/football-os-plane`, hardlinked `node_modules`)
and served by `next start -p 3212` with `API_INTERNAL_URL=http://127.0.0.1:8732`, against the same
private API on 8732 the board walk used. Every read carries `Cache-Control: no-cache` and every
play is followed by a read that waits for `record.played` to move: the API caches 2xx GET responses
for 60 seconds (`cached_response_for`), so an un-mitigated read taken just after a play returns the
pre-play body. Each page's expected strings were composed from the saved payload and the shipped
catalogue — no figure was typed into the check.

| Career | Played | Next | Head-to-head | Bands (career − opponent) | Sentences printed |
| --- | --- | --- | --- | --- | --- |
| `opponent-walk-fresh-braa-M06X` | 0 | Dunmoor (R1) | never met | all five negative | weaker only, empty h2h |
| `opponent-walk-strong-dunt-YWz8` | 0 | Braeford (R1) | never met | all five positive | stronger only |
| `opponent-walk-strong-dunt` | 7 | Haldwick (R8, away) | 1 win (2–1, home, R4) | +0.023 / +0.020 / −0.026 / +0.027, attack 0.000 | stronger and weaker, one level band |
| `opponent-walk-cycle-braa-05Qm` | 9 | Durgard (R10) | 2 meetings (R4 W 2–1, R6 D 0–0) | all five negative | both sentences, meeting table |

**23/23** checks passed, in `en` for all four careers and `zh` for the mixed one: the panel and its
translated title, the eyebrow, both sub-titles, every grid row and table cell read off the payload,
both sentence lists, the level-band delta rendered as `0.000`, the meeting rows' scores/venues/
outcomes, both formulas beside their labels, both notes, the limitation, and the structural
absences (no meeting table before a meeting, no stronger sentence on an all-weaker pairing, no
weaker sentence on an all-stronger pairing, no level sentence on a one-sided pairing).

Two lessons from the first run: React separates adjacent text expressions with `<!-- -->`, so the
checker strips comments with **no** space (a space turns `0–2` into `0 – 2` and false-reds every
scoreline); and a payload snapshot goes stale the moment the walk plays the career forward, so each
view is re-read after the collection loop finishes. A reverse control ran the same page against the
pre-change build on 3211: none of the five panel strings is present there, all five on 3212.

## 3. Catalogue and gates

Thirty-six keys were authored in each catalogue under `careerDetail` (five `bandLabel*`, seventeen
`opponentBrief*`, two `opponentEyebrow*`, eleven `opponentH2h*`, `opponentTitle`). The planned
`bandMidfield` collided with `tactics.bandMidfield` and would have tripped cross-namespace key
drift, so the labels are spelled `bandLabel*`. English values were chosen unique catalogue-wide;
where an English value already existed (`opponentH2hThOutcome` first read "Outcome", held by
`creator.thOutcome`) the value was re-worded. Population is now **3,712** keys; **3,667** are
translated in each Chinese catalogue, and `messages/README.md` carries the same figures.

Green at this commit: `qa-shared-keys` 4/4 at **234 bindings / 98 rows** (ceiling 234 — the new
English values added none), `qa-key-drift` 4/4 (98 issues / ceiling 119, 42 / 107), `qa-unused-keys`
3/3, `qa-icu-messages` 2/2 (11,136 messages), `qa-locale-tokens` 5/5, `qa-i18n-literals` 8/8,
`qa-metadata-title` 168/168, and `qa-gate-inventory` **167 of 169** — the two reds are the
concurrent session's untracked `qa-translation-quality.mjs`, which no gate names yet and which this
increment does not touch. `tsc` is clean for every file this unit changed; `next build` succeeds on
the detached plane.

## 4. Reproduce

```bash
# API already running on 8732 (see M13_BOARD_PROJECTION_VERIFICATION.md §4)
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .scratch/collect-opponent-views.py
PYTHONIOENCODING=utf-8 .venv/Scripts/python.exe .scratch/collect-opponent-views-2.py
# build the detached plane with the unit's files, then
API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3212
.venv/Scripts/python.exe .scratch/check-opponent-page.py --port 3212
```

## 5. Not claimed by this increment

* **The brief is a comparison, not a forecast.** No scoreline is predicted; the deltas are the same
  band indices the engine plays, and they change as rounds and signings change the rows.
* **The level-in-every-band branch is unreachable in the current world.** The in-process scan
  measured all 190 pairings of the 20 clubs: none is level across every band, and only 6 of the 40
  same-competition pairings are mixed at all. The sentence ships for an equal-measurement pairing
  the generated world has not produced; the walk's `0.000` delta row is the closest reachable
  witness.
* **`head_to_head` is this career's fixtures against this opponent and nothing else** — not the
  opponent's record against everyone, and never another competition's meetings.
* **The challenge run page does not render these blocks.** `ChallengeRunView` inherits
  `head_to_head` and `next_fixture_brief`; `/challenges/runs/{slug}` still prints only the record
  and objectives, as the board unit recorded.
* **The 60-second API response cache is left as found.** `serverFetch` sends `cache: "no-store"` to
  Next only; it does not send `Cache-Control: no-cache` upstream, so a page can render up to a
  minute of pre-play data. The walk bypassed it per request; the product defect is queued as its
  own unit.
