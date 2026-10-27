# M13 verification — the season's story, rendered

`career_view["highlights"]` landed in the career-view depth batch (M13 Phase 2): the biggest win, the
worst loss, the longest winning and unbeaten runs, clean sheets kept, rounds without a goal, and the
same played rounds split by venue. The API computes it off the fixture rows it already holds — no
extra query, nothing written back — and `apps/web/app/career/[slug]/page.tsx` never read it, and
`apps/web/lib/types.ts` had no type for it. This increment renders the block: the meeting lines, the
runs, and the home/away table, in all three locales, with an explicit empty branch for the career that
has not kicked off yet.

Date: 2026-10-28.

## 1. What the block publishes

Everything is a retrospective over the career's own played rounds; the API's `note` says so and the
page prints that note verbatim.

| Field | Meaning |
| --- | --- |
| `available`, `reason` | false until the first round is played; the reason is the API's own string |
| `played` | how many rounds the story is retold from |
| `biggest_win`, `worst_loss` | the largest positive / negative margin, ties broken by more goals scored; round index, side, opponent, score, outcome |
| `longest_winning_run`, `longest_unbeaten_run` | consecutive-round runs read oldest first |
| `clean_sheets`, `failed_to_score` | rounds with 0 conceded / 0 scored |
| `home`, `away` | the same rounds split by side: played, won, drawn, lost, goals for/against, points |
| `formula`, `note` | the selection rules and what the block does not promise |

## 2. What the page prints

`components/CareerHighlights.tsx` is a server component wired into the career page between the deal
book and the board projection. It prints the wire figures and the API's own strings; the page does no
arithmetic of its own, so the story cannot drift from the fixtures it is told from.

* A key/value grid: biggest win and worst loss as meeting lines ("Round 2 · Home · 1–0 against
  Durgard Metropolitan", or the muted "none yet this season"), the two runs, clean sheets, and
  rounds without a goal.
* The venue split as a three-column table — measurement, home, away — one row per figure, with an
  em-dash when a side's split is absent (a split that exists but is all zeroes prints its zeroes).
* The API's `formula` (mono) and `note`.
* The unavailable branch: "Nothing to retell yet" plus the API's own reason.
* `limitations.projections` as a warning notice, as the sibling panels do.

17 new keys under `careerDetail` in `en.json`, `zh.json` and `zh-TW.json`. Four sentences reuse the
namespace's existing keys — `thPlayed`, `rowPoints`, `rowUnbeaten`, and the venue names
`opponentH2hVenueHome`/`opponentH2hVenueAway` — rather than minting duplicates, so the
`qa-shared-keys` ceiling stays at exactly **234 bindings / 98 rows** (it may only fall).

`apps/web/messages/README.md`'s population table moved with the catalogues: **3781 keys, 3736
translated** in each Chinese file, the same 45 named fallback tokens — and `qa-locale-tokens.mjs`
checks the table against the catalogues, so the figures are derived, not typed.

## 3. The live walk — one three-round career, one untouched career

Built with `next build` (clean, `tsc --noEmit` 0 errors) and served by `next start -p 3214` with
`API_INTERNAL_URL=http://127.0.0.1:8732`, against a private API on 8732 (the same walk database the
previous M13 panel units used).

`.scratch/walk-highlights.py` registered a fresh walk account, opened two careers, and played three
rounds at Braeford Athletic; Dunmoor Town stayed untouched. The expected figures below were read from
the API response first, written to `.scratch/highlights-expect.json`, and asserted against the
rendered HTML by `.scratch/check-highlights-page.py` — never typed into the check by hand, and every
sentence interpolated from the committed catalogues:

| Figure | The API's answer the page had to print |
| --- | --- |
| biggest win | Round 2, home, 1–0 vs Durgard Metropolitan |
| worst loss | Round 1, home, 0–2 vs Dunmoor Town |
| longest winning run / unbeaten run | 1 / 2 |
| clean sheets / failed to score | 1 / 1 |
| home split | 3 played, 1-1-1, 2 for, 3 against, 4 points |
| away split | all zeroes (the side exists, so zeroes print, not dashes) |

The round indices are the API's own `round_index` — the same raw index the next-opponent panel
prints, so the two panels cannot disagree about which round a meeting was.

`.scratch/check-highlights-page.py`: **78 checks, 0 red** over `en`, `zh`, `zh-TW` × the played and
the untouched career — figures, meeting lines, split rows, headers, the empty state and its reason,
and the panel's own words in both Chinese catalogues. A first run was 75/78: the three reds were the
check's own needle (it un-escaped the apostrophe the document correctly carries as `&#x27;`), fixed
in the check, not the panel.

## 4. Gates

| Gate | Result |
| --- | --- |
| `tsc --noEmit` | 0 errors |
| `eslint` on the three touched files | clean |
| `next build` | clean |
| `qa-shared-keys.mjs` | 4/4 — ceiling held at exactly 234 bindings / 98 rows |
| `qa-key-drift.mjs` | 4/4 — 13 drifting sites of 117 groups, all named |
| `qa-key-drift-witness.mjs` | 10/10 |
| `qa-locale-tokens.mjs` | 5/5 — re-derived 3781 keys / 3736 translated from the catalogues |
| `qa-icu-coverage.mjs` / `qa-unused-keys.mjs` / `qa-namespace-ownership.mjs` / `qa-translation-quality.mjs` | all green |

## 5. Disclosures

* **The momentum batch staled two i18n gates on master, cured in `b59544b` before this unit landed.**
  The concurrent Phase 1 commits (`b05804e`..`08199bb`) added `substitutionsLabel`/`ariaSubstitutions`
  sharing the English "Substitutions" whose Simplified and Traditional strings deliberately diverge
  (label 换人, accessible name 换人次数, mirrored in zh-TW) — an unreviewed same-context drift that
  turned `qa-key-drift` red, and the same batch's fourteen keys staled `qa-locale-tokens` (README said
  3750, the catalogue held 3764). The cure reviewed the pair into the ledger and recounted the README
  census for the tree as it stood; this unit's own keys move the census again, and the same two gates
  are green at this commit. Their CI run at `08199bb` (40545813008) caught both reds — the gates
  worked; the cure just arrived from a second lane.
* `highlightsNoMeeting` ("none yet this season") has no live row in this walk — both walked careers
  either have both meetings or neither. The spelling is one `t()` away from the tested paths and no
  arithmetic of the page's own depends on it.
* The away split's all-zero row prints zeroes rather than dashes by design: the split exists; the
  side simply has not been played. The dash is reserved for an absent split object.

## 6. Reproduce

```bash
# the private API (already running on 8732 with .scratch/walk-board.db,
# a copy of the QA SQLite database advanced to head)
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-board.db" \
  uvicorn app.main:app --host 127.0.0.1 --port 8732

# the shipped site
cd apps/web && npm run build
API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3214

# the walk
python .scratch/walk-highlights.py         # registers, opens two careers, plays three rounds
python .scratch/check-highlights-page.py   # 78 checks against the rendered HTML
```
