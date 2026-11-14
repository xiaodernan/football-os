## Item 41 — the featured duel: the world picks its own argument, and it ships with a card

The other half of Item 40's "visible platform" work, and the first arc where the product **starts the conversation** instead of answering it.

**The door** (`GET /api/v1/world/duel/featured`). The world generates two distinct footballers on
every seed but has never once argued with itself in public; this is the loudest possible form of
that self-argument: the door picks the sharpest scorer (`goals` desc, `assists` desc, `overall` desc,
`minutes` desc) and the most creative hand (`assists` desc, `goals` desc, `overall` desc,
`minutes` desc), and answers with the **exact** `compare()` envelope the duel page argues over —
same seven columns, same verdict shape. A client reads it without knowing the route exists. The
empty-world case refuses with the world tier's shared `NOT_FOUND` code, never an invented pair;
`test_world_duel.py` gained two cases (a stable pair across two calls; the pair never meets itself).
Contract re-exported at **231 paths / 298 operations**; `AUDIT_FIGURES` and the ROADMAP quote moved
with it in the same commit.

Not editorial, not random, and never cached-stock: the door is arithmetic over the world's own columns,
and the home card refreshes with every world sync.

**The surfaces.**

* Home page gains **one panel**, server-rendered: the corner pair in the duel page's own ember style
  (position eyebrow, name, OVR figure), the verdict line (`{name} takes the ledger.` or the levelled
  sentence), the CTA into the canonical duel URL. When the door refuses, the panel answers with the
  same copy it would give — a refusal with a next step — rather than a broken section on a marketing page.
* **Two share cards** (`opengraph-image.tsx` on both duel routes), generated at request time from the
  door — the ledger's palette, the two corners, seven cells tinted by the winning side, gold `v`
  between them. They render even when the API refuses: the card degrades to the slugs the URL asked
  for, never to a 500 in the share window. `pageMetadata()` gained an `images` override — the two
  duel pages and the picker now previews with the card it serves, instead of the site's flat card.
* A latent defect fell out of the sweep: `qa-share-preview` had been red on this tree since Item 36/37's
  route-group moves (its static-page check could not see `app/<path>/(index)/page.tsx`) — the gate
  answered for "the canonical target is a page" that was a page, and it explained it to nobody. The
  gate now resolves route groups the way Next does; 31/31 again.

**Local evidence.** tsc 0; `qa-i18n-literals` 9/9 (4,515 key calls), `qa-unused-keys` 3/3,
`qa-icu-messages` 2/2 (26,736 messages), `qa-locale-completeness` (4,456 × 6), `qa-key-drift` 4/4,
`qa-locale-tokens` 7/7, `qa-population-floor` 3/3, `qa-metadata-title` 197/197, `qa-crawl-policy` 9/9,
`qa-share-preview` 31/31; 15 duel tests green; the four contract gates pass at the featured commit
(41 passed in the batch). **Not claimed.** The OG image path has not been rendered on this host
(Next 15 is build-heavy here); the CI build leg is the proof on the card — and the image copy stayed
strictly in proof tokens, with zero English sentences, because the renderer carries only the latin
face. The home panel's visual verification is CI-time too.

---

## How to work an item