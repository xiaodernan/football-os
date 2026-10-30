# M13 verification — the season boundary moves a club, and both pages say which way

ROADMAP Phase 3 item 9 landed as commit `49acf41` (2026-10-30) on top of item 11's two-tier
pyramid. The generated world now ends its completed season with a final table per league, swaps
the bottom club of each league with the top club of the league below it, draws 2027 from the new
membership, and publishes the move on the competition page — in the direction tier 1 actually
means.

Date: 2026-10-30.

## 1. The table decides, and it is the stored table

`builder._league_table` aggregates one league's completed fixtures into a final table. The order is
**points, then goal difference, then goals scored, then slug** — the same order the public standings
read, so a club is never relegated by a table nobody can see. The rows come from the fixture scores
the seed generated, not from a stored league position, and a fixture that is not completed or not in
that league is skipped rather than guessed at.

`builder._apply_promotion_relegation` then walks tier pairs in ascending tier order. Tier numbers
are levels: **tier 1 is the top flight**, a cup sits outside the pyramid at tier 0, and a gap in the
tier sequence is not a boundary. For each adjacent pair it takes

```
slots = min(movement_slots, len(upper_table) // 2, len(lower_table) // 2)
```

so a field is never emptied wholesale, and with the default `WorldSizes.movement_slots = 1` exactly
one club crosses each boundary: the bottom of the upper league goes down, the top of the lower
league comes up. A zero switches the movement off and leaves the pyramid frozen.

The rewrite happens in place on `_Club.league` — but `_Club.season_league` is never touched. That
second field is what the newsroom reads for every 2026 fact (league name in a spotlight, the
competitions an entity belongs to, the two sides of a transfer note, a competition's member list),
so a July 2026 report still names the league the match was played in after the club has moved. The
2027 fixtures and the team rows are drawn after the swap, so they carry the new membership.

`plan_world`'s ordering is the whole trick:

```python
fixtures = [*_league_fixtures(...), *_cup_fixtures(...)]
_apply_promotion_relegation(dims, leagues, fixtures)
fixtures.extend(_upcoming_fixtures(...))
```

completed season → table → swap → next season's calendar.

## 2. The page derives the boundary from membership, not from a stored event

`GET /api/v1/world/competitions/{slug}` builds the league table from the fixtures of the requested
season, so a relegated club still has a 2026 row on the page of the league it left. Membership and
the fixtures' entrants differ exactly at the boundary, and `_movement` reads the difference:

* `entrants` — the clubs the season's fixtures name, via `_team_map`.
* `registered` — the clubs whose `competition_id` is this competition today.

A club in one set and not the other moved. Each moved club is classified by the tiers of the two
leagues it belonged to: a new tier **smaller** than the old one is a promotion (tier 1 is the top
flight), a larger one is a relegation. Without both league rows there is no direction to state, and
the club is left off the movement list rather than labelled by guesswork.

The response carries

```json
"movement": {
  "season": 2026,
  "promoted":  [{"team": {...}, "from": {...}, "to": {...}}],
  "relegated": [{"team": {...}, "from": {...}, "to": {...}}]
}
```

and the rules for the three page states:

| Page | `teams` | `movement` |
| --- | --- | --- |
| stored season, league | the clubs the fixtures name | the boundary, or `null` when nothing moved |
| future season, league | the clubs registered for it | `null` — the season has not been played |
| cup | registered ∪ fixture entrants | `null` — a cup is not a tier |

The future-season rule was a live-walk correction, not the first design: deriving `teams` from the
fixtures alone left the 2027 page showing the four clubs named by its two scheduled fixtures. A
season with no results has membership as its truth, so `entrants` is used only when the requested
season equals `competition.season`.

## 3. The web panel, and the direction defect it surfaced twice

`apps/web/app/competition/[slug]/page.tsx` renders a `Panel` between the table and the entrant
chips, hidden when `movement` is null or holds no rows: the eyebrow names the boundary
("Season boundary · 2026"), the rule sentence says the membership changed and the stored table
decided it, and each row prints the direction ("Promoted" / "Relegated"), an `EntityLink` to the
club and the path `from → to`. Six keys carry the copy in `en`, `zh` and `zh-TW`:

| Key | en | zh | zh-TW |
| --- | --- | --- | --- |
| `movementEyebrow` | Season boundary · {season} | 赛季边界 · {season} | 賽季邊界 · {season} |
| `movementTitle` | Promotion & relegation | 升级与降级 | 升級與降級 |
| `movementPromoted` | Promoted | 升级 | 升級 |
| `movementRelegated` | Relegated | 降级 | 降級 |
| `movementPath` | {from} → {to} | 从 {from} 到 {to} | 從 {from} 到 {to} |

The same commit fixed a fallback the future-season page exposed: a league with no stored fixtures
used to borrow the cup's note ("progression is the bracket of N drawn fixtures"), which is false
of a league. `tablePending` now says the season has no played fixture and points at the entrants.

**The direction got itself wrong twice, and the live walks caught both.** The first implementation
labelled by membership difference (a club that left this league was called "relegated" *on this
page* whatever its new tier), so the tier-2 page called the club that went up "relegated". The
rework classified by tiers but compared them as `new.tier > old.tier → promoted`, still backwards
because tier 1 is the top. A second walk printed "promoted: Ostmont Albion: Lyndera → Braehaven"
on the tier-2 page and made the inversion obvious. The fix is `promoted if new.tier < old.tier`,
and the API test now asserts **direction** by fetching each named competition's tier:

```python
if tier(entry["to"]["slug"]) <= tier(entry["from"]["slug"]):
    errors.append(("relegated", entry["from"]["name"], entry["to"]["name"]))
# ... and the promoted loop refuses tier(to) >= tier(from)
assert not errors, f"tier 1 is the top flight, so these directions are inverted: {errors}"
```

A mutation run flipping the comparison back to `>` failed with exactly that message
(`[('relegated', 'Braehaven Elite League', 'Lyndera Superleague'), ...]`); the source was restored
byte-identically.

## 4. Evidence

| Check | Result |
| --- | --- |
| `pytest tests/test_world.py` | **57 passed** (9 of them new: 3 plan-level, 3 DB-level, 3 API-level) |
| `pytest tests/test_world.py tests/test_openapi_contract_currency.py tests/test_locale_claims.py` | **exit 0** — the contract still reproduces its committed bytes; the catalogue README is recomputed |
| `scripts/lint.sh` | **All checks passed!** |
| `mypy app` | **Success: no issues found in 161 source files** |
| `tsc --noEmit` (web worktree) | clean |
| 16 catalogue gates (`qa-key-drift`, `qa-icu-messages`, `qa-unused-keys`, `qa-locale-*`, `qa-population-floor`, `qa-shared-keys`, `qa-namespace-ownership`, `qa-translation-*`, `qa-plural-select`, `qa-icu-coverage`, `qa-i18n-literals`, …) | **16/16 exit 0** |

Item 9 added six movement keys and one fallback key: **3,964 -> 3,971 keys**, with **3,926
translated** in each Chinese catalogue and the same **45** identical tokens (placeholders, machine tokens and acronyms); the
README's table is the recomputed figure, not a typed one. The new keys were written as bytes with
the locale's own punctuation — `“”` in zh, `「」` in zh-TW, `。` endings — and verified by codepoint,
not by eye on a GBK console.

### The live walk — API on `:3299`, seed 3, SQLite

* Every league page: **8 standings rows, 8 clubs, 56/56 fixtures** with both sides named.
* `lyndera-superleague` (tier 1) and `braehaven-elite-league` (tier 2) published the same two
  moves, in opposite directions: **Ostmont Albion** (bottom of tier 1, 15 pts) relegated to
  Braehaven; **Elnwick Athletic** (top of Braehaven, 27 pts) promoted to Lyndera.
* The second pairing moved **Corgard Town** down and **Haldhaven Albion** up.
* `?season=2027`: 8 clubs (Elnwick absent, Ostmont present), 2 scheduled fixtures, `movement` null.
* A cup page: 7 completed fixtures, `movement` null.

### The browser pass — API `:3299`, `next dev` `:3211`, in-app browser

The in-app browser had no visible surface, so this pass is DOM-level (snapshots and script
evaluation), not screenshots:

* `zh`: «赛季边界 · 2026» / «升级与降级» / «降级 Ostmont Albion 从 Lyndera Superleague 到
  Braehaven Elite League» / «升级 Elnwick Athletic 从 Braehaven Elite League 到 Lyndera Superleague».
* `en` (`fo_locale=en`): «SEASON BOUNDARY · 2026» / «Promotion & relegation» / «RELEGATED Ostmont
  Albion Lyndera Superleague → Braehaven Elite League» / «PROMOTED Elnwick Athletic Braehaven Elite
  League → Lyndera Superleague».
* `zh-TW`: «賽季邊界 · 2026» / «升級與降級» / «降級 … 從 Lyndera Superleague 到 Braehaven Elite
  League» / «升級 …».
* 2027 league page in all three locales: no movement panel, 8 entrant chips with the new member and
  without the promoted one, and the new `tablePending` sentence («这个赛季还没有已踢的比赛…» /
  «No fixture in this season has been played yet…» / «這個賽季還沒有已踢的比賽…»).
* The cup page: no movement panel, the cup note unchanged.

## 5. What this does not claim

* **One club per boundary by default.** `movement_slots` can move more and is tested at 0, but the
  generated world ships 1; nothing claims a play-off, head-to-head tie-break or an away-goals rule.
  The tie-break is points, goal difference, goals scored, slug — published, and no more.
* **The move happens at world generation, not inside a career.** A career's fixture rows are the
  world's results; the membership rewrite changes the 2027 calendar and the team rows. A career
  opened after the boundary plays its club's new league; the 2026 tables on the public pages still
  name the clubs that played them.
* **No movement row is stored.** The block is derived on read from `real_matches` and
  `teams.competition_id`, so regenerating the world with the same seed reproduces the same moves,
  and a hand-edited team row would move the page with it. There is no event table to drift.
* **Future seasons beyond what the world scheduled.** The 2027 page shows the two fixtures the
  generator schedules ahead; it is membership plus that calendar, not a full 2027 season table.
* **Cups never move.** A cup has no tier, so a cup page publishes no movement even though its
  entrants change from season to season.

## 6. Reproduce

```bash
# the tests
cd apps/api && python -m pytest tests/test_world.py -q
cd apps/api && python -m pytest tests/test_world.py tests/test_openapi_contract_currency.py tests/test_locale_claims.py -q

# the live walk (fresh SQLite, seed 3)
cd apps/api && DATABASE_URL="sqlite:///$TEMP/movement-walk.db" WORLD_SEED=3 KNOWLEDGE_AUTO_INGEST=0 \
  python -m uvicorn app.main:app --host 127.0.0.1 --port 3299

curl -s "http://127.0.0.1:3299/api/v1/world/competitions/braehaven-elite-league"   # movement.promoted
curl -s "http://127.0.0.1:3299/api/v1/world/competitions/lyndera-superleague"      # movement.relegated
curl -s "http://127.0.0.1:3299/api/v1/world/competitions/braehaven-elite-league?season=2027"  # movement null, 8 clubs

# the page (the API above, a dev server pointed at it)
cd apps/web && API_INTERNAL_URL=http://127.0.0.1:3299 npx next dev -p 3211
# open /competition/braehaven-elite-league and ?season=2027
```
