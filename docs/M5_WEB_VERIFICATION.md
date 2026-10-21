# M5 verification — the video surface in a browser

M5's backend half is documented in [`M5_VERIFICATION.md`](M5_VERIFICATION.md): the container sniffing, the
`ffprobe`/`ffmpeg` calls, the pixel-measuring demo provider, the `Job`/`ModelCall` rows, the owner-only storage.
That document said, in its §7, that nothing in the browser could upload or read a clip. This document is the
increment that made the sentence false, and the evidence for the sentence that replaces it.

Date: 2026-09-22. Build: `NEXT_DIST_DIR=.next-ci SITE_URL=http://127.0.0.1:3211 npx next build`, served by
`next start` on the throwaway port, driven by `scripts/visual-qa.mjs` (system Chrome, puppeteer-core) against the
running API on 8731. Nothing below is asserted by reading source: each line is a value the browser reported.

The walk is one program for every milestone, so its total is the platform's: **164/164 checks**, 58 screenshots,
exit 0. Of those, 12 belong to video and 4 to the tactics analysis this increment touched (§4 item 7).

## 1. Two surfaces, both private

| Route | What it is | Why it is not public |
| --- | --- | --- |
| `/video` | the account's clip list and the upload control | `robots: { index: false, follow: false }` and `Disallow: /video` in `robots.ts`; no sitemap entry; §80 has no video route |
| `/video/{id}` | one clip's report: player, measured summary, detection timeline, sampled frames | same, and the page redirects to `/login?next=…` without a session |

A clip is the most identifying file the platform can hold, so the surfaces repeat the fact rather than trusting the
reader to infer it: the index head reads *"<name> · private to this account"*, each card carries
`data_origin: user`, the report's lede is the API's own `privacy` string, and `Provenance` states the split the page
depends on — *the clips are yours; the detections are a demo provider's pixel statistics*.

Components: `VideoUpload` (multipart POST through the cookie proxy, with the per-account ceiling shown before the
file is chosen), `VideoTools` (run the analysis, delete the clip) and the report page's own panels.

## 2. The proxy learned to carry bytes, not just JSON

`app/api/v1/[...path]/route.ts` is the only path a browser has to FastAPI, and it used to force
`Accept: application/json` and drop everything except a content type. That is correct for a report and fatal for a
video element, which asks for byte ranges and needs `Content-Range` back. So:

* `Range` is forwarded when the request has one, and `Accept` becomes `*/*` for those requests only;
* `Accept-Ranges`, `Content-Range` and `Content-Length` are copied back to the browser;
* the 401-refresh-and-replay path carries the same header, so a session that expires mid-watch still gets its bytes.

Measured on the same clip both ways (direct API, then through the proxy on the built site):

```text
bytes=0-99          → 206 Content-Range: bytes 0-99/58056
bytes=57032-        → 206 Content-Range: bytes 57032-58055/58056
bytes=-1024         → 206 Content-Range: bytes 57032-58055/58056
bytes=99999-        → 416 Content-Range: bytes */58056, code range_not_satisfiable
no Range            → 200 with all 58056 bytes
two ranges          → whole file, 200 (RFC 9110 lets a server ignore Range; it never half-serves)
```

`apps/api/tests/test_video.py` covers the same six cases server-side, and the walk proves the browser's own
`<video>` element reads metadata through the owner-only route: **duration 2.00 s, media error code none**.

## 3. What the walk asserts about video

Twelve checks (block 12e), each against the rendered page or the browser's own media element:

| Check | Reported value |
| --- | --- |
| the clip under test is generated, not third-party | `ffmpeg` testsrc2, 58 056 bytes, in the OS temp dir |
| the index offers an upload control and states the privacy rule | present |
| an uploaded clip lands on its own report, labelled as user content | `/video/vid_…` · `data_origin: user` |
| the report is noindexed and robots keeps `/video` out of the crawl | `noindex, nofollow` · `disallow /video: true` |
| analysis names its provider, model and limitations | provider `demo-pixel-stats` · model `ffmpeg ppm + pure-python statistics` · 1 detection |
| the frames strip shows exactly the samples the numbers came from | 8 shown / 8 sampled / 8 decoded by the browser |
| playback and frames come from owner-only API routes, not a public path | `/api/v1/video/{id}/file` |
| the browser really plays it | duration 2.00 s · media error code none |
| the proxy answers a byte range with the slice and the headers describing it | `206 bytes 0-99/58056` · suffix `bytes 57032-58055/58056` · past-end `416 bytes */58056` · no range `200` 58 056 bytes |
| a signed-out visitor is bounced and the routes answer 401 | page 307 → `/login?next=…` · clip 401 · frame 307 |
| mobile 375 px holds | 0 px horizontal overflow |
| deleting empties the list and kills the old URL | back to `/video` · report now 307 |

The frames check waits for `img.complete && naturalWidth > 0` on every strip image rather than trusting the
response, so "8 shown" means eight decoded PNGs — the same bytes `ffmpeg` wrote, shown without `next/image`
re-encoding them (a deliberate `<img>` with the reason in a comment above it).

## 4. Defects this increment caught

1. **A reload made the report lie.** `POST /video/{id}/analyse` returned the measured summary; `GET /video/{id}`
   rebuilt its report from the `Job` row alone, and the job had stored only counters. Reload a measured clip and the
   page said *"No analysis stored for this clip yet"* about numbers it had printed a minute earlier. Found by
   clicking the browser's reload, not by any test. Fix: the run now stores its `stages` rows and its measured
   `analysis` summary on `job.result` (not the events — those are already rows), and `report_for` accepts either
   live `Stage` objects or the plain dicts a finished job kept, so the two shapes cannot disagree.
   `test_a_report_read_later_carries_the_same_measurements_as_the_run_that_produced_them` compares every field of the
   two responses, provider and thresholds included.
2. **Stage rows of two shapes crashed the report.** The same fix first raised `AttributeError: 'dict' object has no
   attribute 'name'` and aborted the walk at 110/111 — the normalisation above is what the report now uses for both.
3. **An upload that has never been analysed.** Asserted rather than assumed: `analysis is None`, `job is None`,
   `stages == []`, status `uploaded`. A report must not look thinner *or richer* than what was measured.
4. **The console-error list was a footnote.** The walk printed browser errors and still exited 0. It now fails a
   check unless every error is one the walk provoked on purpose. Four lines survive that gate, and they are two
   events each logged twice by Chromium: `bytes=99999999-` against a 58 056-byte clip answering 416, and deleting a
   clip whose file the browser was still reading — detaching the `<video>` element does not cancel a read already on
   the wire, so its follow-up range request answers 404.
5. **Two false alarms, both in the harness.** The strip read "0 decoded" because the assertion beat the images
   (fixed by waiting for decode), and `limitations` failed to match because `innerText` inserted the line breaks a
   narrow monospace cell wraps at (fixed by asserting `textContent` of a `data-testid` block).
6. **The walk's readiness probe measured the wrong thing.** `apps/web/scripts/verify-production.sh` waited for
   `/healthz` and *then* compared chunk hashes; `/healthz` is an app route that proxies the API, so twice the script
   aborted with `served chunk: none` while a server started by hand on the same port served the chunk the build
   names. The loop now polls the fact the walk depends on — this build's webpack hash inside a rendered page's HTML
   — for up to 60 seconds, and reports the HTTP status it saw, so a dead or stale port reads as a status instead of
   a shrug.
7. **A citation check that encoded an accident.** "one library link per analysis point" held only while two of the
   six topics were refused: 4 points, 4 passages. Once the corpus gained the missing passages all 6 topics were
   cited and two of them leaned on the same document, so the walk failed a page that had got *better*
   (`4 citation links · 200 statuses`). It now compares the DOM's links against the payload's distinct
   `citation.ref` values and asserts every one resolves — the claim was always "each passage cited exists", never
   "each point cites a different passage".

## 5. Still not claimed

* **No event semantics.** The timeline's marks are positions where non-pitch pixels moved; nothing on the page may
  call them passes, shots or runs, and the provider's own `limitations` sentence sits above the table.
* **No background worker.** Analysis runs inside the request that asks for it; the job row records that run, and
  the queue-shaped `Job` table is what a real worker would attach to later (PRINCIPLE 1).
* **No real detector.** With a vision key configured the same seam would carry a different provider; without one
  the page labels itself `demo_mode True`, which the walk reads back off the payload.

### A clip's delete left its own analysis job behind (2026-10-21)

`DELETE /api/v1/video/{ident}` removes the row, the stored original and the sampled frames — and the
**job row that described the analysis** outlived it. The `jobs` table has no foreign key to `video_assets`
(it is a queue row, and the queue is what a background worker would attach to later), so the clip's
analysis job was a row that outlived the thing it described: its payload still named an asset id that
answered 404.

The delete now takes the clip's own jobs with it, and the case that says so is
`test_deleting_a_clip_takes_its_own_analysis_job_with_it` in `tests/test_video.py` — it writes the job
row the way the pipeline writes it (`payload: {"asset_id": …}`), deletes the clip, and asserts the job is
gone. **Measured 2026-10-21:** `tests/test_video.py` **34 passed**; the case was turned red on purpose
first (the delete matching no job type), and it failed with *"the clip's analysis job outlived the clip
it described"*; `ruff` clean, `mypy` clean over **153 source files**.

The policy's own sentence about this — that per-video deletion was *not implemented* — was **stale**: the
door has been there since M5 and the walk has pressed it in a browser ("deleting empties the list and makes
the old report URL unusable"). `DATA_POLICY.md` §3 says so now.


## 6. Frame overlay — detection rings on the sampled frames (verified 2026-09-29)

Each detection the demo provider measures now carries a ring on the frame its timestamp falls on.
The ring sits at the exact `(x, y)` the table prints, so the numbers point at the pixels they
describe. Hovering the ring prints the timestamp, the kind, the confidence and the sentence the
measurement was called with — the centre of the non-pitch pixels, not a player or a ball.

Walk check added (check 234 of 234):

- every detection is drawn on the frame it was measured from, at the x and y its row prints
- the ring's `data-x` / `data-y` match the table to the printed precision (three decimals)
- the frame whose caption time is the nearest sample to the detection's `t_s`
- the ring's `title` carries the full sentence: `t_s · kind · confidence% — why`

Screenshots: the `video-frames` panel now shows rings over the thumbnails. Exit 0, 234/234 checks.

## 7. Clip linking and shareable clips (M5 item 3, verified 2026-09-30)

Spec §14 asks for "linking a clip to a user's player or an M6 match, and short shareable clips".

### API endpoints

| Method | Path | Purpose |
|--------|------|---------|
| `POST /video/{id}/link-player` | Link clip to one of the caller's football identities (UserPlayer) |
| `POST /video/{id}/link-match` | Link clip to an M6 simulation match the caller owns |
| `POST /video/{id}/share` | Create a revocable share token for this clip |
| `DELETE /video/{id}/share` | Revoke the share token |
| `GET /video/shared/{token}` | Public read of a shared clip — no session, no owner identity |

The share token follows the §17 tactical board precedent: one token per clip, created on first share,
reused on subsequent shares, revoked by clearing the token (the row stays so the account knows when it was shut).

### Model changes

`VideoAsset` gains:
- `player_id` (FK to `user_players`, nullable, SET NULL on delete)
- `match_id` (FK to `sim_matches`, nullable, SET NULL on delete)
- `share_token` (unique, nullable)
- `shared_at` (timestamp of first share)
- `visibility` (`private` | `shared`)

Indexes on `player_id` and `match_id` for efficient lookups.

### Web surface

- `/video/{id}` page now has a "Linked to" panel with forms to link player/match
- "Share this clip" panel with Create share link / Revoke link buttons
- `/video/shared/{token}` renders the **record** the upload left behind — the ten fields `GET /video/shared/{token}`
  actually returns (id, title, filename, duration, frame size, status, `frame_count`, `data_origin`, `is_demo_data`),
  with no owner identity disclosed. It does **not** play the footage: `GET /video/{id}/file` and `/frames/{index}` are
  owner-session routes by design (video.py's own docstring: "to its owner only"), so a shared reader sees what was
  recorded, not the clip. The page previously typed this read as the owner's `VideoReport` and reached into
  `report.asset`, which the shared door has never returned — an anonymous reader got HTTP 500, and before that HTTP 307
  to `/login` from the middleware. Both halves are corrected and re-read live in
  `docs/MIDDLEWARE_GATING_VERIFICATION.md`; whether a share link *should* disclose the measurements and the bytes is
  an open design question recorded there, not settled here.

### Tests

`TestM5Item3LinksAndSharing` (4 cases in `tests/test_video.py`):
1. `test_link_player_and_match_and_share` — full flow: upload, link player, link match, share, public read, revoke
2. `test_link_player_rejects_wrong_owner` — cannot link another user's player
3. `test_link_match_rejects_wrong_owner` — cannot link another user's match
4. `test_share_link_is_revocable_and_not_guessable` — token is 32 hex chars, revoked link returns 404

All tests pass. Production walk 234/234, exit 0. Build, tsc, lint all green.