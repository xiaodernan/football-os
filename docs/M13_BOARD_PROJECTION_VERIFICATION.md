# M13 verification — the season projection, rendered

ROADMAP Phase 2 item 8's read-only half landed on 2026-10-25: `board_view` (`career.py`) extends the
career's own record over the season's horizon and marks each additive objective on or off that pace. It
has been published on `career_view["board"]` on every read since, pinned by `TestBoard` in
`test_career.py` — and `apps/web/app/career/[slug]/page.tsx` never read it. This increment types the
block on the web wire and renders it on the career page in all three locales. Date: 2026-10-27.

## 1. What the block publishes

Everything is recomputed from the career's `career_fixtures` rows on the request; no counter is stored.

| Field | Meaning | When it is interesting |
| --- | --- | --- |
| `season_rounds`, `season_source` | the horizon and where it came from: the challenge's window, else `2 × clubs` | always |
| `played` | rounds with a stored fixture | always |
| `points_per_round`, `goals_for_per_round` | `round(sum ÷ played, 3)` | **`null`** until a round is played |
| `projected` | `{wins, points, goal_difference}` at `round(actual ÷ played × season_rounds)` | **`{}`** until a round is played, or with no horizon |
| `objectives[]` | each stored objective with `projected` and `on_pace` added | `projected` is **`null`** for a streak such as the unbeaten run |
| `on_track` | `all(on_pace)` over the trackable objectives | **`null`** when none is additive |
| `formula`, `note` | the arithmetic, and what the projection does not promise | always |

## 2. What the page prints

`components/CareerBoard.tsx` is a server component. It prints the wire figures and the API's own
`formula` and `note`; the page does no arithmetic, so the projection cannot drift from the record it was
derived from.

* The eyebrow names `played` of `season_rounds` rounds, and the title states the panel is about the board
  targets' direction.
* A key/value grid: the horizon and its source, both per-round paces, the projection (`wins · points ·
  goal difference`, or the sentence that nothing is projected yet), and the on-track verdict — every
  target on pace, the number off it, or the sentence that no target can be projected.
* One table row per objective: the label, what was asked for, what it stands at, the projection at this
  pace (a dash for a streak), and a badge — **on pace**, **off the pace**, or **as it stands**.
* The block's `note`, the formula beside its translated label, and `limitations.projections` as a warning
  notice.

## 3. The live walk — three careers, three branches

Built with `next build`, served by `next start -p 3211` with `API_INTERNAL_URL=http://127.0.0.1:8732`,
against a private API on 8732 backed by a copy of the QA SQLite database advanced to head with
`alembic upgrade head`. All expected figures were read from the API response first and then asserted
against the served HTML; none was typed into the check.

| Career | Rounds | Horizon | Paces | Projection | Verdict |
| --- | --- | --- | --- | --- | --- |
| `board-walk-braa-gXAm` | 3 of 8 | double round-robin | 1 / 0.667 | 3 wins · 8 points · −5 GD | **off the pace**, 1 target |
| `board-walk-cort-bL97` | 0 of 8 | double round-robin | — / — | nothing projected yet | no additive target |
| `board-walk-cort-OIPx` | 2 of 8 | double round-robin | 2 / 1 | 4 wins · 16 points · 8 GD | **every target on pace** |

The first career stores four objectives and exercises all three row verdicts:

| Objective | Asked for | Now | At this pace | Row verdict |
| --- | --- | --- | --- | --- |
| points | 3 | 3 | 8 | on pace |
| wins | 1 | 1 | 3 | on pace |
| goal difference | 2 | −2 | −5 | off the pace |
| unbeaten | 2 | 1 | — | as it stands |

The second career was opened and never played: the paces read —, the projection states that nothing is
projected yet, every row shows — and *as it stands*, and the target verdict is the unprojectable sentence.
The third was opened with a points target of 0 and played two rounds, so the all-on-pace branch is read
from a real response rather than left to a default.

**93/93** checks passed, in `en` and `zh`, covering: the panel and its translated title, the eyebrow, the
horizon value and source, both pace figures, the projected figures (or the empty sentence), the target
verdict, all five column headers as `<th scope="col">`, every objective's target/actual/projection and
badge, the formula beside its label, the note, the limitation, and cross-locale absence of the other
locale's title. Two rendering facts the first run had to learn: React writes ASCII apostrophes as
`&#x27;` and separates adjacent text expressions with `<!-- -->`, so the API's prose is compared in its
escaped form. A negative control swapped the projected wins for `wins + 1` and confirmed the mutated row is
absent from the same page that carries the real one.

## 4. Catalogue and gates

Twenty-five keys were authored in each catalogue under `careerDetail`; English values were chosen to be
unique catalogue-wide so the shared-key ceiling does not move. Population is now **3,657** keys;
**3,612** are translated in each Chinese catalogue, and `messages/README.md` carries the same figures.

Green at this commit: `qa-locale-completeness` 2/2, `qa-icu-coverage` 2/2, `qa-icu-messages` 2/2,
`qa-locale-content` 3/3, `qa-locale-formatting` 2/2, `qa-plural-select` 2/2,
`qa-namespace-ownership` 2/2, `qa-locale-tokens` 5/5, `qa-shared-keys` 4/4 at **234 bindings / 98 rows**
(ceiling 234), `qa-shared-keys-witness` 8/8, `qa-key-drift` 4/4, `qa-key-drift-witness` 10/10,
`qa-i18n-literals` 8/8, `qa-unused-keys` 3/3 (three dynamic lookups unresolved, unchanged),
`qa-token-drift` 2/2, `qa-population-floor` 3/3, `qa-baseline-gates` 16/16, and the API's
`tests/test_locale_claims.py` 7/7. `tsc --noEmit` and `next build` are clean.

## 5. Reproduce

```bash
cp apps/api/var/qa12.db .scratch/walk-board.db
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-board.db" \
  ../../.venv/Scripts/python.exe -m alembic upgrade head
DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-board.db" \
  ../../.venv/Scripts/python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8732
cd apps/web && npm run build && \
  API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3211
.venv/Scripts/python.exe .scratch/walk-board.py        # registers, opens three careers, plays rounds
.venv/Scripts/python.exe .scratch/check-board-page.py  # 93 checks against the served pages
```

## 6. Not claimed by this increment

* **No board acts on the projection.** Nothing is promoted, relegated, sacked or embargoed; the block is
  read-only, as item 8's API half already stated.
* **The zero-objective branch is not reached by any API-created career.** `POST /careers` refuses a career
  with no objective (`no_objectives`), so the panel's empty state is written for a stored career whose
  objective list was emptied outside this API, and the walk did not exercise it.
* **The projection is linear, not a forecast.** It is the current record extended over the horizon; it
  does not model fixtures, form, injuries or opponents, and it changes as soon as another round is played.
* **The page does no arithmetic.** Every figure, the formula and the note are the API's; a change to the
  derivation is a change to `career.py`, and the page follows without an edit.
* **The challenge run page does not render the block.** `ChallengeRunView` inherits `board`, but
  `/challenges/runs/{slug}` still prints only the record and objectives; the career page is the only
  reader so far.
