# Visual QA screenshots

These PNGs are produced by the browser verification walk, not authored by hand:

```bash
cd apps/web
npm run qa:visual          # == node scripts/visual-qa.mjs
```

The script needs the API on `:8731` and the web tier on `:3210` running (see `README.md` for the boot commands
and `docs/M0_M1_VERIFICATION.md` §2.2 for the walk itself). It registers a throwaway account, walks the full
loop, asserts 34 checks, and writes one screenshot per surface named
`<run-stamp>-<index>-<surface>-<viewport>.png`.

## Why the images are not tracked

`docs/screenshots/*.png` is listed in `.gitignore`. Two reasons:

1. **9 MB of churn per run.** Every run stamps a new minute, so committing them doubles the repository on each
   verification pass while preserving nothing reproducible — the script regenerates them in about 90 seconds.
2. **The global pre-commit hook false-positives on them.** `codex-global` scans staged bytes for conflict
   markers and flags the compressed IDAT streams in some of these PNGs (`<<<<<<<`-length runs of `<`, `>`, `=`
   appearing as literal byte sequences inside deflate data). The files are valid images — every one starts with
   `\x89PNG\r\n\x1a\n` and is decoded by the browser — so the check is a scan artifact, not a defect. The
   correct fix is to not commit the binaries; `--no-verify` would hide a real gate.

So the tracked record of a verification pass is the **text** report pasted verbatim into
`docs/M0_M1_VERIFICATION.md` §2.2, and this manifest is the index of what the run captured.

## Latest run — `202609211947` (M1 exit criteria, 34/34 passed)

Desktop 1440x900:

| File | Surface | What it proves |
| --- | --- | --- |
| `202609211947-01-login-desktop.png` | `/login` | Sign-in form renders; new accounts land on onboarding |
| `202609211947-02-onboarding-desktop.png` | `/onboarding` | Position/foot/injury questions submit to a real player row |
| `202609211947-03-my-football-desktop.png` | `/my-football` | Archetype, level, attribute radar, `DEMO DATA` label |
| `202609211947-04-coach-today-desktop.png` | `/coach` | Rule-engine recommendation with per-reason citations |
| `202609211947-05-coach-ask-desktop.png` | `/coach` ask panel | Intent classification + reasons + disclaimer envelope |
| `202609211947-06-coach-plan-desktop.png` | `/coach` plan builder | 7-day plan whose sessions link into training content |
| `202609211947-07-training-index-desktop.png` | `/training` | Drill catalogue reachable from the plan |
| `202609211947-08-drill-detail-desktop.png` | `/training/<slug>` | Drill detail with "Add to my sessions" |
| `202609211947-09-session-logger-desktop.png` | session logger | Self-report inputs incl. the notes textarea |
| `202609211947-10-session-logged-desktop.png` | completion result | XP formula, skill-point banking, coach feedback |
| `202609211947-11-progress-desktop.png` | `/progress` | Level, streak, attribute history |
| `202609211947-12-history-desktop.png` | `/history` | Completed session listed with its evidence note |
| `202609211947-13-settings-desktop.png` | `/settings` | Account email, export, platform status |

Mobile 375x812 (screenshots are supplementary; the authoritative result is the overflow/nav assertions in the
report — zero horizontal overflow and 7/7 nav links visible on each surface):

| File | Surface |
| --- | --- |
| `202609211947-14-mobile-my-football.png` | `/my-football` |
| `202609211947-14-mobile-coach.png` | `/coach` |
| `202609211947-14-mobile-training.png` | `/training` |
| `202609211947-14-mobile-progress.png` | `/progress` |
| `202609211947-14-mobile-settings.png` | `/settings` |
| `202609211947-14-mobile-login-signed-out.png` | `/login` after logout |

Re-run and the stamps change. To keep a specific run as evidence for a milestone, force-add only those files
with `git add -f docs/screenshots/<stamp>-*.png` and say why in the commit message.
