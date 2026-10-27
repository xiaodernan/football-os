# M13 verification — the key-drift ceiling ratcheted to the figures the tree measures

`apps/web/scripts/qa-key-drift.mjs` holds its cross-namespace drift ceilings as constants that may
only fall. They were set on 2026-10-25 from that day's review (119 sentence issues, 107 key issues)
and had not moved since — while the tree's drift had. This unit measures the real figures, attributes
the fall, ratchets both ceilings onto it, and proves the ratchet bites with a three-plane arm battery.

Date: 2026-10-28.

## 1. The measurement, from the gate's own output

| Reading | sentence issues / shared sentences | key issues / shared keys | same-context sites / groups |
| --- | --- | --- | --- |
| `dce0734` (2026-10-26, the commit that set the ceilings) | **119 / 240** — exactly the ceiling | **107 / 260** — exactly the ceiling | 12 / 115 |
| `b59544b` (2026-10-28) | **99 / 241** | **42 / 260** | 13 / 117 |
| `43a2d6e`, `614d016`, `5d55d41` (HEAD) | 99 / 241 | 42 / 260 | 13 / 117 |

Each row is the gate itself run against that commit's catalogue bytes (extracted with
`git show <commit>:apps/web/messages/*.json` into `.scratch/kd-plane/<commit>/` and read through the
gate's own `QA_I18N_WEB` seam), so the numbers are the gate's, not a reimplementation's. The whole
fall happened inside `dce0734..b59544b`.

## 2. What dissolved the drift

Nine commits touched the catalogues in that window; eight of them only added keys (additive keys can
raise drift, never cure it). The value edits are the same-sense alignment batch: **16 changed values
in each CJK file** (`git diff dce0734 b59544b -- apps/web/messages/zh.json` lists exactly 16
deletions — `simulator`, `thManager`, `met`, `thAnswer`, `thOff`, `thSv`, the `*ing` progress verbs,
…, mirrored in zh-TW). Aligning a shared sentence's translations dissolves its sentence issue for
that locale; aligning a shared key name's value dissolves one issue per (namespace, locale) that held
the divergence, which is why 16 value edits resolved 20 sentence issues and 65 key issues. The same
window also added one same-context group and one reviewed ledger entry (the momentum batch's
`substitutionsLabel`/`ariaSubstitutions` pair, cured in `b59544b`) — 115→117 groups, 12→13 sites,
which is also why the gate's docstring said 115/12 and was stale until this unit re-read the census.

## 3. The ratchet

`SENTENCE_CEILING` 119 → **99**, `KEY_CEILING` 107 → **42** — both now exactly the figures this HEAD
measures, so any new divergence, however small, is red. The gate's prose follows the measurement:
the docstring's population figures are re-read from the census (117/13), and the ceiling comment
names the ratchet date, the measured figures, and the attribution above. No check's shape changed:
still four checks, the same counting the 2026-10-25 review measured.

## 4. The arm battery — the ratchet bites

`.scratch/kd-arm-battery.mjs` copies the committed catalogues into three `QA_I18N_WEB` planes and
runs the gate on each, reading the gate's own printed verdicts:

| Plane | Mutation (zh, on a copy) | Result |
| --- | --- | --- |
| control | none | 4/4 pass, exit 0 — 99/241 and 42/260 against ceilings 99/42 |
| sentence-arm | `nav.world` "足球世界" → `臂测世界` | sentence check **FAIL** — 100 > 99, exit 1; key check still 42/42 |
| key-arm | `common.aiGenerated` → `臂测生成` | sentence check **FAIL** (100 > 99 — the sentence is shared too) and key check **FAIL** — **44** > 42, exit 1 |

Both ceiling checks bite. The key arm's +2 is the gate's own accounting, not a surprise: a key-name
divergence is counted once per namespace holding it (`common` and `knowledge`), so one mutated value
raises the count by two. The sentence arm isolates check 3 with exactly +1. The real catalogues are
never touched (the arms run on copies; `git status apps/web/messages/` shows only the two foreign
untracked baselines before and after).

## 5. Disclosures

* The ceilings are constants a human re-ratchets after a fall; nothing ratchets them automatically.
  A fall without a re-ratchet leaves a stale (loose) ceiling that still gates new drift — it just
  tolerates up to 20 sentence / 65 key regressions before reding. This unit closes that gap at this
  measurement; the next fall should be followed by the next ratchet.
* The key-drift count double-counts one divergence (once per namespace holding the shared key name),
  inherited unchanged from the 2026-10-25 review so the ceiling means what that review measured. The
  ratchet preserves the shape deliberately; reshaping the count is a different unit.
* `sharedSentences` and `sharedKeys` (241 / 260) are printed but not pinned: additive keys with
  aligned translations are legitimate growth, and only drift is capped.

## 6. Reproduce

```bash
node apps/web/scripts/qa-key-drift.mjs                 # 4/4, ceilings 99/42 on the working tree
node .scratch/kd-arm-battery.mjs                       # control + two +1-drift arms on copied planes
# per-commit readings:
for c in dce0734 b59544b 5d55d41; do
  mkdir -p .scratch/kd-plane/$c/messages
  for f in en zh zh-TW; do git show $c:apps/web/messages/$f.json > .scratch/kd-plane/$c/messages/$f.json; done
  QA_I18N_WEB="$PWD/.scratch/kd-plane/$c" node apps/web/scripts/qa-key-drift.mjs
done
```
