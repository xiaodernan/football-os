# M4 Tactical Lab — backend verification (spec §11–§13, §62, §65)

Date: 2026-09-22 · Tier: `apps/api` · Scope: the geometry, the 50-system catalogue, its storage and
`/api/v1/tactics/*`. The pages that consume it — `/tactics`, `/tactics/{slug}`, `/tactics/compare` — are verified in
[`M4_WEB_VERIFICATION.md`](M4_WEB_VERIFICATION.md); what M4 still does not claim (user-saved boards, animation, AI
commentary) is listed in §7.

## 1. Why this milestone starts with a coordinate system

The Tactical Lab's failure mode is decoration: eleven dots on a graphic with adjectives beside them.
So the first deliverable is measurement. Every number a tactics page will show is computed by
`app/services/tactics/analysis.py` from stored metres, and each metric carries the sentence that
explains how it was obtained — which is what lets the web tier print a formula instead of asking a
reader to trust a figure (spec §62).

| Layer | File | Owns | Test coverage |
| --- | --- | --- | --- |
| geometry | `pitch.py` | 105 × 68 m, origin at the team's own goal; clamp, thirds, five lanes, zones, nearest-neighbour, centroid | 12 tests incl. non-finite rejection |
| vocabulary | `roles.py` | 14 roles with separate in/out duties, instructions, stated risk, attribute demands | parametrised over every role and every shape |
| authored data | `shapes.py` | 10 formations × 5 temperaments — the only hand-written coordinates | 10 per-shape tests + 3 constructor rejections |
| measurement | `analysis.py` | both phase transforms, 8 metrics with formulas, 6 named counterfactuals | 22 tests incl. per-slot arithmetic |
| catalogue | `plan.py` | the 50 systems, graded against the catalogue's own quartiles | determinism, URL-safety, verdict-cites-number |
| storage | `sync.py` | upsert by slug, forced provenance, refuse-on-invalid, delete-what-the-plan-dropped | idempotence + a poisoned-plan rollback |
| reads | `app/api/v1/tactics.py` | 6 public routes + 1 authenticated, recomputed on request | 31 tests over HTTP |

## 2. What is in the catalogue, counted rather than described

```text
tactical systems        50   = 10 shapes × 5 temperaments, matching spec §65
metrics per board        8   width · depth · coverage · balance · spacing · isolation · line_separation · space_behind
counterfactuals          6   each names the slots it moves, and only those
roles                   14   every one is fielded by at least one shape (a test enforces it)
temperaments             5   press-high · control-possession · direct-transition · low-block · wide-overload
catalogue fingerprint   38a6757a9395…   stable across a cache clear, i.e. across processes
```

## 3. Invariants the tests prove, not assert in prose

- **The block is the same eleven players.** `out_of_possession` is a linear rescale: its vertical span
  equals the authored `block_depth` to 0.01 m, its top equals `press_line_y`, the keeper stays within
  4 m of its own line, and the role set is unchanged. A page can animate between the two without
  inventing a second drawing.
- **Nothing walks off the pitch.** Every change is clamped, and the clamp is *reported*: the
  counterfactual response lists each slot whose asked-for coordinate differs from where it was
  placed. Silently moving a player 3 m less than requested would make every downstream number a lie.
- **A change cannot move what it does not name.** A test compares every slot against
  `Change.desired()` arithmetic, and `widen-front` (x-only) is proven to leave every `y` untouched.
- **Every verdict quotes its own evidence.** Each computed strength/risk sentence contains the
  measurement and its percentile band, so the claim can be checked against the metric list in the
  same payload. Systems with no quartile extreme say so instead of being handed a compliment.
- **An invalid plan stores nothing.** Feeding `sync_tactics` a system with a nine-player board
  returns `ok=False` with the named defect and writes zero rows — a partial catalogue would otherwise
  be browsable as if it were the complete 50 the gate promises.
- **`m4_tactical_lab` is data-derived.** `/capabilities` reports it from `tactics_ready(db)`
  (count ≥ 50 and the table present), so the flag cannot advertise a route with nothing behind it.

## 4. The API surface

| Route | Purpose | Notes |
| --- | --- | --- |
| `GET /api/v1/tactics/status` | counts, gate, fingerprint, formulas, offered changes | `ready` is measured, not configured |
| `GET /api/v1/tactics` | browse with `formation`, `temperament`, `search`, `page`, `page_size` | each row carries its §80 `path` + headline metrics for both phases |
| `GET /api/v1/tactics/{slug\|id}` | one system: both boards, 8+8 metrics, verdicts, roles, transform note | metrics recomputed from the stored coordinates |
| `GET /api/v1/tactics/{slug\|id}/counterfactual?change=&phase=` | "what happens if", per-metric before/after/delta + clamps | unknown change → 422 `unknown_change` listing the six |
| `GET /api/v1/tactics/compare?a=&b=&phase=` | the eight metrics side by side with deltas | every row repeats its formula |
| `GET /api/v1/tactics/{slug\|id}/feedback` | six coaching questions put to the M2 corpus; cited statements and explicit refusals | any statement whose passage does not resolve (§7) |
| `GET /api/v1/tactics/{slug\|id}/fit` | this account's player against the shape's tactical demands | a player-less account: 409 `no_player`, never a zero-filled comparison |

Live proof on the dev database (pgvector, 2026-09-22): comparing `4-3-3 · High press` with
`4-3-3 · Compact low block` out of possession gives `space_behind` **44.0 m vs 10.0 m** — the
difference between the two ideas, measured rather than described. `raise-back-line` on the low block
moves `space_behind` 18 → 26 m and shortens the team's span by the same 8 m.

## 5. Defects found and fixed during this increment

1. **A counterfactual whose label lied.** `push-full-backs` was implemented against the whole
   *defensive band*, so it moved the centre-backs too and its "+8 m space behind" was the accident of
   which role happened to be deepest. Replaced by role/band-targeted changes with a `target` string,
   and a test that recomputes each slot's expected coordinate.
2. **A payload key reached the ORM constructor.** `plan.PROVENANCE` grew a `disclaimer` field, and the
   sync passed it straight to `TacticalSystem(...)` → `TypeError` on the first real write. Columns are
   now selected from `TacticalSystem.__table__.columns`, and `_payload_column_gaps` fails the sync if
   a column exists that no payload key fills — the drift that bit once cannot recur silently.
3. **`alembic check` caught an index the migration invented** (`ix_tactical_systems_slug`, duplicating
   the unique constraint and declared by no model). Dropped from the revision and from the dev database.
4. **Percentile grammar.** "82th percentile" — the labels now go through an ordinal helper, and the
   test asserts the `\d+(st|nd|rd|th)` shape.
5. **Templates that claimed intent.** "…which is the point" was attached to a width measurement on a
   low block, where it was the wing-backs' coordinates rather than any intention. Rewritten as
   consequence ("…so their wide players must cover the whole flank").
6. **A dead catalogue entry.** `IWB` (inverted full-back) was fielded by no formation, so no system
   could ever be graded against it. Deleted; the inverted full-back remains where it actually is —
   as a documented delta of the possession temperament.

## 6. Reproduce

```bash
cd apps/api
python -m ruff check app tests                 # All checks passed
python -m mypy app                             # 54 source files, no issues
python -m alembic upgrade head && python -m alembic check
python -m pytest -q                            # 200 passed (SQLite)   · 111 of them are M4
FOOTBALL_OS_TEST_DATABASE_URL="postgresql+psycopg2://football:football@127.0.0.1:54321/football_os_pytest" \
  python -m pytest -q                          # 200 passed (pgvector)
python -m uvicorn app.main:app --host 127.0.0.1 --port 8731 &
python ../../scripts/export_openapi.py         # 47 paths / 51 operations, incl. the 7 /tactics routes
curl -s "localhost:8731/api/v1/tactics/compare?a=4-3-3-press-high&b=4-3-3-low-block&phase=out"
```

## 7. The cited analysis — and the two questions it refuses

`feedback.py` asks six questions of the knowledge corpus through the same `retrieval.search` that `/knowledge`
uses, with the same gates (`MIN_DISCRIMINATIVE_MATCHES = 2`, `MIN_DISCRIMINATIVE_COVERAGE = 0.40`, rare-term
`df ≤ 30%`, `MIN_USEFUL_SCORE = 0.045`). Measured on the running server with the corpus ingested (732 passages,
`hybrid-pgvector`):

| Topic | Outcome | Citation |
| --- | --- | --- |
| Pressing line (block depth) | cited | `/knowledge/buildup-vs-high-press#0` |
| Block compactness (spacing) | cited | `/knowledge/pressing-evolution-notes#2` |
| Build-up under pressure (isolation) | cited | `/knowledge/transition-defence-five-seconds#4` |
| Distance between the lines | cited | `/knowledge/how-to-read-a-game#1` |
| Width in attack | **refused** | “2/6 of the question's rare terms … → refuse” |
| How high the team sits | **refused** | “1/4 of the question's rare terms … → refuse” |

The refusals are the interesting result. Both topics *can* be made to answer `answerable=True` by rewording the
question — tried and rejected: the passages those rewordings retrieve are about reading a game and protecting the
middle on a counter, not about width or territory. Rewording to clear a gate would buy a citation that does not
support its sentence, which `AI_POLICY.md` §6 forbids and which a reader with the link open would catch. So the
payload carries the refusal, the gate that fired, the measured number, and the page says plainly that the library
has no passage for it. That gap is recorded as corpus follow-up work in `ROADMAP.md`, with the RAG eval to be
re-run after — not the gates loosened.

Every cited statement also keeps its own measurement trail: `metric.formula` is the same string the metrics table
prints, and `citation.ref` is an in-app anchor (`/knowledge/{slug}#{ordinal}`) which the browser walk fetches, so a
citation that resolved to nothing would fail the run rather than quietly mislead.

`fit` is arithmetic on the same six attributes the player model stores: `gap = attribute − demand`, `short` at
≤ −12, `exceeds` at ≥ +4, mean gap as the summary. Nothing in either endpoint writes to a stored row.

## 8. Not claimed by this milestone

* **The web surface is verified separately.** `/tactics`, `/tactics/{slug}` and `/tactics/compare` are live, and the
  50 system URLs are in `sitemap.ts` — the browser evidence is in [`M4_WEB_VERIFICATION.md`](M4_WEB_VERIFICATION.md).
* **No animation.** The two phases are stored as one transform pair so animation is a rendering job,
  but nothing renders them yet. The counterfactual view draws the displacement as arrows, which is the
  same data a tween would interpolate.
* **No user-saved or shared boards.** §65's M4 gate includes drag/draw/save/share: that needs an
  owned `tactic_boards` table plus a share token, which is §21 (community) plumbing, not a
  read endpoint. Not started.
* **No model writes anything.** `/feedback` is extractive assembly over the corpus and the measured rows and labels
  itself that way (`model: "extractive assembly …"`, `provider: "none (no AI key configured)"`); `/fit` is arithmetic
  on published thresholds. Neither mutates a player, a rating or a stored row. Two of the six topics stay ungrounded
  until the corpus gains the passages named in §7.
* The 50 systems are authored structures with measured consequences. They are not a claim about how
  any real team plays, and every response says so in its `disclaimer`.
