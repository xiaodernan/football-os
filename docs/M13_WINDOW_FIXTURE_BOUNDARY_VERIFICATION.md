# M13 verification — a signing window that straddles a stored fixture

M13 Phase 2 item 5 shipped the window as a range of round numbers and refused a deal in a closed
round. The half it left open is the question a career with a generated calendar raises: the window
is a slice of the career's own season, while every round it covers replays a fixture the world has
already stored (usually with a score). Nothing said how many of those rounds the window had already
covered, how many signing rounds it still held, or whether a signing could reach back into the
stored fixture. This unit answers all three on the read; it writes nothing.

Date: 2026-11-02.

## 1. What the window publishes now

`transfer_window` in `apps/api/app/services/simulation/market.py` gains four fields on both of its
return branches:

| Field | Meaning |
| --- | --- |
| `window_from_round` | the open window's first round within the season, or `null` when closed |
| `window_to_round` | the open window's last round within the season, or `null` when closed |
| `played_in_window` | how many of that window's rounds the career has already stored a fixture for |
| `signing_rounds_left` | how many rounds the career can still sign in, counting the next one |

The arithmetic is a slice of the rounds the block already computed, not a second calendar:

```
season_index      = (rounds_played) // season_rounds + 1
round_in_season   = (rounds_played) % season_rounds + 1
window_first      = (season_index − 1) × season_rounds + window_from_round
played_in_window  = clamp(rounds_played − window_first + 1, 0, window_to_round − window_from_round + 1)
signing_rounds_left = window_to_round − round_in_season + 1        # open window only
```

A closed window publishes `null` bounds and zero for both counts: a range a deal cannot be made in
buys no signing rounds rather than an implied one. A career with no horizon keeps its stated
"open" reading and publishes the same zero/`null` values, because there is no window to count.

`WINDOW_FORMULA` now ends with the boundary the fields measure: a window judges only the career's
own next round, the generated fixture that round replays is read from the world and **never
rewritten**, so a signing covers the round's eleven without touching the stored world score. The
same block reaches `market_view["window"]` and `career_view["window"]`, so both doors answer with
one reading.

## 2. The stored fixture is an input, not a target

The claim is pinned on a career whose next round really came from `next_fixture_plan`, not from a
hand-written fixture:

- the generated `RealMatch` row is read before the signing (`status`, both scores, both club ids);
- a listed outsider is signed through `market.buy`;
- the world row is re-read and every one of the five values is unchanged;
- the move's `round_index` is `rounds_played + 1`, the round it covers — the same rule
  `moves_as_of` already reads for the eleven.

A later signing therefore cannot rewrite a stored world score, and cannot rewrite a stored career
report either: `career_fixtures` keeps its own `match_id`, and the replay path reads the move only
for rounds at or after the round it was made before.

## 3. Tests

`apps/api/tests/test_transfers.py::TestTransferWindow` grows three cases (nine in the class):

| Test | Claim |
| --- | --- |
| `test_the_window_counts_the_rounds_it_covers_and_the_signing_rounds_left` | open round 1 → 0 played / the window's length left; after three rounds → 3 played / the remainder; the round after the window → closed with null bounds and zero |
| `test_a_career_with_no_horizon_counts_no_signing_rounds` | a career with no competition keeps `state=open` and publishes `null`/0 rather than a guessed range |
| `test_a_signing_before_a_stored_world_fixture_leaves_that_fixture_untouched` | the world row's status, score and clubs are byte-for-byte the values read before the signing; the move is stored for the next round |

Targeted run: `python -m pytest tests/test_transfers.py::TestTransferWindow -q` → **9 passed**.
The adjacent suites — `test_transfers.py`, `test_transfers_api.py`, `test_career.py`,
`test_career_api.py` — are **162 passed**. `ruff check app tests` and `mypy app` (161 files) are
clean.

## 4. Disclosures

- **No web panel in this unit.** The market page's `data-testid="market-window"` panel is being
  edited by the concurrent M6 lane, and the career page does not render the window block at all.
  The four fields travel on both JSON doors so that panel can print them; this record does not
  claim a page walk.
- **The window is counted in the career's rounds, not in `real_matches` statuses.** A generated
  fixture may be `scheduled` or `completed` before the career plays it; both are the same input to
  a replay, so the block does not treat one status as a different boundary.
- **No migration.** The fields are recomputed on the read from `career.rounds_played` and the
  published constants; there is no stored counter to drift.

## 5. Reproduce

```
cd apps/api
python -m pytest tests/test_transfers.py::TestTransferWindow -q
python -m pytest tests/test_transfers.py tests/test_transfers_api.py tests/test_career.py tests/test_career_api.py -q
python -m ruff check app tests
python -m mypy app
```
