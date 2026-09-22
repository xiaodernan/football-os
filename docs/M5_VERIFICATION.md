# M5 Video Analysis — pipeline verification (spec §14, §47, §61, §62, §77)

Date: 2026-09-22 · Tier: `apps/api` · Scope: upload contract, ffmpeg media layer, the demo vision
provider, detections, jobs and ledger. **The web surface is not claimed here** — there is no upload
form or report page yet; §7 says what is therefore still missing.

## 1. Why the vision part is statistics and not a model

The spec's rule (§45, §77, `AI_POLICY.md`) is that an absent credential is *stated*, never hidden
behind plausible output. So the vision provider here does something a reader can check by hand: it
decodes the frames ffmpeg produced, measures how much of the picture is pitch-green, finds the
centre of the pixels that are not, and calls a movement an event when that centre shifts by at least
0.02 frame widths between samples. Every threshold ships inside the response, next to a `limitations`
sentence saying it does not detect players, a ball, a formation or a football event.

That makes the demo honest **and** makes the tests able to say something strong: a clip that does not
move must produce zero detections, and one where a square travels a known distance must report a
shift of that distance.

| Layer | File | Owns |
| --- | --- | --- |
| media | `app/services/video/media.py` | ffprobe facts, frame sampling to PPM, a PNG display copy; subprocess calls with fixed argument lists |
| vision | `app/services/video/vision.py` | PPM decode, green/bright/luma stats, centroid motion, the `demo-pixel-stats` provider |
| pipeline | `app/services/video/pipeline.py` | upload validation and hashing, stage recording, detections, `Job` + `ModelCall` rows, the report |
| contracts | `app/providers/__init__.py` | `LocalStorageProvider` implemented at last (it said "Lands with M5"), `get_vision_provider`, provider status |
| routes | `app/api/v1/video.py` | 7 endpoints: upload, list, report, analyse, file, frame, jobs, delete |
| tables | `video_assets`, `video_detections` (migration `0006`) | container facts and measured events; the bytes stay on disk, keyed by owner |

## 2. The upload contract

* The **bytes** decide the container: `ftyp`/`MOVI`/EBML magic for mp4/MOV/webm. A file named
  `x.mp4` whose content starts `MZ` is refused `415 unsupported_container`, and the refusal happens
  before anything is written or stored (test asserts no row exists afterwards).
* Size: one place checks it (`pipeline.store_upload`), raising `UploadTooLarge` → 413. `Settings` is
  frozen deliberately, so the ceiling is a parameter of the seam rather than something a test pokes
  into a shared object.
* `sha256` and `size_bytes` are stored, and the ceiling is 20 clips per account (`409 video_limit`)
  and 64 MiB per clip (`VIDEO_MAX_BYTES`).
* Storage keys are built from the owner and a generated id; `LocalStorageProvider._path` refuses a
  key that resolves outside the root, so a filename can never become a directory climb.

## 3. What a test run measures end to end

`tests/test_video.py` generates its own clips with ffmpeg (`testsrc2`, and a green field with a
static square) — no third-party video enters the repository, and `var/` is gitignored so uploads
never can either.

```text
moving clip (testsrc2, 2 s)   → 8 samples, 1 movement detection, provider demo-pixel-stats, demo_mode True
still clip (green + box)      → 8 samples, 0 detections, green_fraction_mean > 0.9
centroid arithmetic (hand-built PPMs) → a square from x=6 to x=30 on a 96 px field measures 0.25 frame widths
malformed pixmaps             → four variants, all refused
foreign account               → 404 on report/file/frames/analyse/delete, empty list, 401 for anonymous
deletion                      → row gone, detections gone, the file is gone from disk
```

Live against the running server (pgvector, 2026-09-22): upload → 201 `uploaded` `2.0s 320x180 h264`;
a renamed `MZ` file → 415; analyse → stages `probe, extract_frames, analyse`, 8 frames, 1 detection
at `t=1.0s (0.399, 0.484)` conf 0.666; frame 0 → 3,729-byte PNG; anonymous read → 401;
jobs → 1 row with `Recorded during the request that asked for the work`; delete → 204 and no file left.

## 4. Jobs, ledger, and the absence of a queue

The spec's §47 job table and §46 model ledger existed as schema only. The video pipeline is their
first real writer: one `Job` (`video.analyse`) per run with per-stage progress and timings, and one
`ModelCall` per vision pass — including a `success=False` row when the media tools are missing. The
`jobs` endpoint's own note says it plainly: there is no queue and no worker behind these rows, and
the work happens during the request that asked for it. That is a deliberate PRINCIPLE 1 choice, not
an oversight; a real queue would be added against a measured need.

## 5. Defects found and fixed while building this

1. **A test that "proved" anonymity while signed in.** `auth_client` is built on the same `client`
   fixture instance, so it carries the Authorization header: `client.get(f"{API}/{id}")` returned 200
   and the assertion was about to be written as a pass. Fixed by opening a genuinely separate
   `TestClient`; the endpoint was never broken, the test was.
2. **A duplicate size check.** The route re-implemented the ceiling next to the pipeline's own. The
   route now defers to the single check, so the two cannot disagree about what the limit is.
3. **A frozen `Settings` and a monkeypatch that could not touch it** (`FrozenInstanceError`) — the
   seam takes `max_bytes` instead.
4. **A cell-mean detector that saw nothing.** The first measurement split the frame into a 4 × 4 grid
   and called a change an event when cells moved ≥ 12 luma. On a real clip with a small bright
   target it produced zero events — correct for that instrument, useless as a claim. Replaced by the
   bright-pixel centroid, which measures the thing that moved; the cell counts stay in the payload as
   context, not as the trigger.
5. **Dead weight in the response.** The report exposed `storage_key`; it is an internal path, and a
   test now asserts it is absent.

## 6. Reproduce

```bash
cd apps/api
python -m ruff check app tests                 # All checks passed
python -m mypy app                             # 61 source files, no issues
python -m alembic upgrade head && python -m alembic check
python -m pytest -q                            # 244 passed (SQLite)   · 26 of them are M5
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest -q                          # 244 passed (pgvector)
python ../../scripts/export_openapi.py         # 59 paths / 67 operations, incl. the 7 /video routes
```

Requires `ffmpeg` and `ffprobe` on PATH; without them the media and pipeline tests skip with a reason
and the API answers `503 media_tools_missing` rather than inventing frames (`DATA_POLICY.md` §2).

## 7. Not claimed by this milestone

* **No upload UI, no report page.** Nothing in the browser sends a clip or shows a timeline of
  detections yet, so the §65 "upload → … → report" chain is verified at the API only. The web
  increment needs the privacy rules respected: an account's clips are never public, so no §80 route
  and no sitemap entry for them.
* **No event semantics.** Detections are movement of a brightness centroid. Mapping them to passes,
  shots or presses would need a real model or hand-labelled data, and neither exists here.
* **No linking a clip to a match or a player**, no clipping/share links, no frame-level drawing on the
  pitch overlay — all of those belong with the report page and M6's match data.
* **No background processing or storage service.** Local disk and synchronous jobs today; the
  `StorageProvider` interface is what a real object store would slot behind.
