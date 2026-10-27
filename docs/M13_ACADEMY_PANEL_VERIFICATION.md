# M13 verification — the youth academy's outcomes, rendered and walked through every verdict

`career_view["academy"]` landed in the API tier on 2026-10-28 (`academy_view` in
`apps/api/app/services/simulation/academy.py`, recorded in
[M13_ACADEMY_OUTCOMES_VERIFICATION.md](M13_ACADEMY_OUTCOMES_VERIFICATION.md)). This increment is the
web half: `lib/types.ts` types the block, `components/CareerAcademy.tsx` renders it on
`/career/{slug}` between the season's development curve and the board projection, and the shipped
build is walked through all three verdicts the wire's own closed set names.

Date: 2026-10-28.

## 1. What the panel prints

Every figure is the wire's; the page does no arithmetic and decides nothing.

| Panel part | Wire field(s) |
| --- | --- |
| eyebrow "a class of {count} at or under {ceiling}…" | `class_size`, `youth_age_max` |
| key/value grid (6 rows) | `class_size`, `selected_count`, `next_in_line_count`, `squad_size`, `formation`, `youth_age_max` |
| table columns player / position / age / minutes | `player_name`, `position`, `age`, `minutes` (en-GB grouped) |
| stored → projected | `stored_overall`, `projected_overall` (one decimal, the wire's own rounding) |
| headroom | `potential_headroom` |
| band standing | `band_rank`, `band_size`, `seats_in_band`, and ` · ` + `gap_to_last_seat` when it is not null |
| verdict badge | `verdict` — `selected` → `badge badge--live`, `off_the_pace` → `badge badge--demo`, `next_in_line` → the neutral `badge` |
| note, formula, the six derivations | `note`, `academy_formula`, `formulas` (each key printed spaced, each sentence as the API wrote it) |
| warning notice | `limitations.projections` |

The empty branch (`available` false, or no trainee rows) prints the eyebrow with a zero class, the
panel's own "No youth class to judge", the API's `reason`, and the limitation notice — and pins by
absence that no key/value grid, no table and no formulas heading appear, the deal-book precedent.

`potential_headroom` got a column because it is one of the six figures whose derivation the panel
prints: a formula sentence for a number the reader could not see is the same class of defect this
project keeps landing against ("published on every career read and no page could read it").

## 2. Catalogue

20 new keys under `careerDetail` in `en.json`, `zh.json` and `zh-TW.json` — the 17 the panel was
drafted with, plus `academyThAge`, `academyThHeadroom` and `academyThVerdict` for the three column
headers the draft borrowed from other namespaces. `careerDetail` now holds 285 keys; the catalogue
population is **3811 keys, 3766 translated** in each Chinese file (the same 45 named fallback
tokens), and `apps/web/messages/README.md`'s table moved to those figures, which
`qa-locale-tokens.mjs` recomputes from the catalogues rather than trusting.

The header values reuse the wording the tier already uses for the same sense — "Age" (as in
`scout.thAge`), "Headroom" (as in `scout.thHeadroom`) and "Verdict" (as in `scout.thVerdict`), with
the Chinese 年龄 / 上升空间 / 判定 and 年齡 / 上升空間 / 判定 — but under `academy`-prefixed names,
because the page's translator is bound to `careerDetail` and cannot reach another namespace.
`qa-shared-keys.mjs` keys its rows on the key **name** held by two or more namespaces
(`byKey`/`valueShared` in the script), so differently-named single-namespace keys add no binding: the
ceiling held at exactly **234 bindings across 98 rows**. Diffing `git show HEAD:apps/web/messages/en.json`
against the file on disk measures the claim rather than asserting it — 20 added names, every one
`academy`-prefixed, and zero of them held by a second namespace.

## 3. The defect the walk found before anything landed

The first walk run died in its own lookup: `KeyError: 'thAge'`. The component asked `careerDetail`
for `thAge` and `thVerdict`, and neither exists there — measured over
`git show HEAD:apps/web/messages/en.json`, `thAge` lives in `scout`, `world`, `club`, `worldTeam` and
`academy`, `thVerdict` in `scout`. A page renders what its bound namespace holds, so those two
headers had no value to print.

No shipped gate could see it, and that was probed rather than assumed. With the draft spelling
put back into `components/CareerAcademy.tsx`, `qa-i18n-literals.mjs` answered **8/8 PASS at 3661 key
calls**; with a key that exists in *no* namespace (`zzzNoSuchKeyProbe`) planted in the same file, it
answered **8/8 PASS at the same 3661 calls**. The number never moved, which names the mechanism: the
gate records a bare key call qualified by the namespaces it can bind to that translator name in the
file itself (`apps/web/scripts/qa-i18n-literals.mjs:804`-`:824`), and a shared component receives its
translator as a prop and binds no namespace at all — so `candidates` is empty and none of its keys
enter the population the existence check reads.

**The control that makes the probe mean something.** The identical planted line — a module-level
`(t) => t("h27gategapplantedkey")` — was appended to `app/career/[slug]/page.tsx`, which does bind
`careerDetail`. There the gate answered **7/8, `FAIL every key the source asks for is in the catalogue
— 1 key(s) the catalogue does not hold`, at 3662 calls**: one call counted, one key charged. Against
`components/CareerNextOpponent.tsx` the same plant answered **8/8 at 3661** — nothing counted, nothing
charged. So the gate is not broken; it is blind on one side of the seam, and both probes restored the
file byte-identically (sha256 compared before and after).

**The measured population of the blind side:** 7 files under `apps/web/components/` make **167 bare
`t("…")` calls** that never enter the gate's recorded set — `CareerNextOpponent` 34,
`CareerContracts` 29, `CareerBoard` 25, `CareerFinance` 24, `CareerAcademy` 23, `CareerHighlights` 18,
`CareerDevelopment` 14. This panel is one of them; only its walk covers it this time. **The gap is a
gate gap, not a catalogue gap**: the question "does this key belong to the namespace the rendering page
bound" is only answerable at the seam between page and component. Opened as item 22 in
[ROADMAP_NEXT.md](ROADMAP_NEXT.md).

## 4. The live walk — verdicts reached by surgery, not by luck

The academy block is recomputed from the stored rows on every read, so a walk that reads one stored
state can only ever see the verdicts that state happens to produce. `.scratch/walk-academy.py` is
driven phase by phase by `.scratch/phase-driver.sh`: set the walked player's stored `overall` in the
walk database, **restart the private API** (the response cache would otherwise replay the previous
phase's answer), fetch the career view, then fetch the shipped page in all three locales and compose
every expected string from that view and the committed catalogues. Nothing is typed by hand.

The walked career is `highlights-walk-played-braa-R58n` (three under-21s, 720 minutes each, a 4-4-2
squad of 15). Janek Tober's band holds 4 players and the shape gives it 2 seats, so his stored
overall moves him through all three verdicts:

| Phase | stored overall | rank / seats | gap to last seat | verdict | badge class | checks |
| --- | --- | --- | --- | --- | --- | --- |
| `as_is` | 49 | 2 of 4 | — | `selected` | `badge badge--live` | 171, 0 red |
| `next_in_line` | 48 | 3 of 4 | 1 | `next_in_line` | `badge` | 172, 0 red |
| `off_the_pace` | 44 | 4 of 4 | 5 | `off_the_pace` | `badge badge--demo` | 172, 0 red |
| `as_is` (restored) | 49 | 2 of 4 | — | `selected` | `badge badge--live` | 171, 0 red |

Each phase run carries 24 checks for the empty branch (`board-walk-cort`: the walk database's copy
of Cordale Town had its under-21s aged past the ceiling, so the career legitimately answers
`no squad player is at or under the age ceiling of 21`), and the two surgery phases carry one
anti-vacuity check the `as_is` runs cannot: a trainee row must actually carry that phase's verdict on
the wire, so a phase that silently did not happen is red rather than green-and-empty. **686 checks
over the four runs (171 + 172 + 172 + 171), 0 red** — 49 per locale on the available branch (eyebrow,
six key/value needles, eight column headers, eight cells per trainee row, note, formula, six formula
list items, limitation notice, plus the single check that the panel title appears exactly once) and 8
per locale on the empty branch.

Three build-and-walk iterations were needed and each red was the check's or the component's own
composition, not the wire:

* **run 1** raised `KeyError: 'thAge'` — §3's defect; fixed by authoring the three header keys.
* **run 2** (33 red): the server was the previous build — `kill` in bash had killed the `npx`
  wrapper, not the Node listener (the port's real owner, found with `netstat -ano` and stopped with
  `taskkill //PID … //F`) — and, on the fresh build, three cells were composed from **adjacent JSX
  expressions**, which React separates with `<!---->` comment nodes. The stored→projected cell, the
  standing+gap cell and the formula list item now build one template literal each (`storedCell`,
  `standingCell`, `{` — ${sentence}`}`), so the row is one text node.
* **run 3** (20 red): every remaining red was a string carrying an apostrophe — the eyebrow, `note`,
  `academy_formula`, the limitation notice, two formula sentences. React escapes `'` in text as
  `&#x27;`; the walk's escaper had been switched to `quote=False`. `html.escape(text, quote=True)`
  reproduces React's text escaping and the 20 went green with no change to the panel.

## 5. Gates

| Gate | Result |
| --- | --- |
| `tsc --noEmit` | 0 errors |
| `next build` | clean, served by `next start -p 3217` over the private API on 8732 |
| rendered walk | 686 checks over four phase runs (171/172/172/171), 0 red (both branches × three locales) |
| `qa-i18n-literals.mjs` | 8/8 at 3661 key calls — and it stays 8/8 at the same count against both planted spellings (§3) |
| `qa-shared-keys.mjs` | ceiling held at exactly 234 bindings / 98 rows |
| `qa-locale-tokens.mjs` | re-derived 3811 keys / 3766 translated from the catalogues |
| `qa-locale-completeness.mjs` | 3811 / 3811 / 3811 |
| `qa-unused-keys.mjs` | 0 keys asked for by nothing, floor 0 |
| `qa-key-drift.mjs` | 4/4, the reviewed ledger current |
| `qa-population-floor.mjs` | 3/3 on the **committed** tree (it reads `git show HEAD:`): every namespace at or above baseline, 3811 × 3 |
| `qa-translation-freshness.mjs` | 2/2 on the committed tree: no stale `zh`/`zh-TW` row left behind by the 20 new English sentences |
| `apps/api/tests/test_locale_claims.py` | 7 passed (it pins this README's figures against `en.json`) |

## 6. Disclosures

* **The api CI job's red is foreign, not cured here.** The `market.py` mypy errors that the
  highlights and development records named are that lane's own batch; this unit touches no API file.
* `system_slug`, `stored_potential`, `training_units`, `effective_minutes`, `band`, `player_slug`,
  `tau` and `rate` are on the wire and are **not** printed by this panel. `tau`/`rate` belong to the
  development panel beside the curve they govern; the rest are the row's identity or the inputs the
  printed figures were computed from. `formulas` explains each of them in the API's own words, which
  is what the panel prints instead.
* The empty branch is reached by aging one club's youths in a **copy** of the walk database
  (`.scratch/walk-academy.db`, derived from `walk-board.db`); the shipped demo world seeds no career
  whose squad is entirely over 21, so the branch is real but only reachable with that surgery. The
  record states it rather than pretending the world produced it.
* The walk's phase surgeries mutate only `real_players.overall` for one player and are restored
  (`as_is` re-walked green at 49 after the last phase). The API restart between phases is the cache
  contract's own read-your-writes behaviour (`docs/M13_READ_YOUR_WRITES_VERIFICATION.md`): a plain
  GET after a non-2xx-writing restart replays whatever the fresh process computes.
* `apps/web/messages/README.md`'s committed bytes end every line with `\r\r\n` (95 lines, 190 CRs —
  the 5d55d41 bulk rewrite's artifact). This unit's edit is 2 lines and re-encodes to the file's own
  spelling, so `git diff --numstat` stays `2 2` instead of churning all 95; the doubled CR is left
  for a record of its own.
* **The roadmap prose entered HEAD inside another lane's commit.** `docs/ROADMAP_NEXT.md` was on disk
  with this unit's two edits (item 7's landing note, the new item 22) when the signing-window lane
  committed `51c3b93` at 07:09:31, and that commit took the file's whole working-tree state — 33 of its
  40 added lines are this unit's words, under a commit message about the transfer window. The content
  is in HEAD and verified byte-equal to disk; only the attribution is wrong, and it is stated here
  rather than re-landed (a second commit of the same file would fight the shared tree). Nothing else
  from this unit was swept: `51c3b93` carried `career.py`, `test_career.py` and the roadmap only.
* Three verdict labels, both badge classes and the gap interpolation now have readers, but the walk
  saw only one squad shape (a 4-4-2, 15 squad members, three under-21s, two seats in the attack
  band). A wider class, a band with no seats, or a trainee whose `band_rank` is null are the API's
  own branches and are pinned by `apps/api/tests/test_academy_outcomes.py`, not by this walk.

## 7. Reproduce

```bash
# the private API over the walk database (the driver restarts it after every surgery)
cd apps/api && DATABASE_URL="sqlite:///D:/足球项目/.scratch/walk-academy.db" \
  uvicorn app.main:app --host 127.0.0.1 --port 8732

# the shipped site, on a port no other walk is holding
cd apps/web && npm run build
API_INTERNAL_URL=http://127.0.0.1:8732 npx next start -p 3217

# one phase: stored overall, phase name
bash .scratch/phase-driver.sh 48 next_in_line
bash .scratch/phase-driver.sh 44 off_the_pace
bash .scratch/phase-driver.sh 49 as_is

# the walk alone, against the current stored state
python .scratch/walk-academy.py as_is          # 171 checks, 0 red
```
