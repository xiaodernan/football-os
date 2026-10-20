# Share preview: what a reader sees before they click

Measured on plane `cc0ad34` + this worktree (Next.js 15.5.25, node v24.18.0), 2026-10-21. Four claims, each carried
by an artifact named below rather than by this prose:

1. a link to somebody's CV, board or clip previewed **the site**, not the page — "FOOTBALL OS" over the tagline —
   because a page with no `openGraph` of its own inherits the root layout's site-level block;
2. every indexed page promised a large picture (`card: "summary_large_image"`) that **did not exist**: `docs/SEO_VERIFICATION.md`
   §3 published that absence as a deliberate exclusion while the tag that needs it shipped anyway;
3. both are now refused by a static gate, `apps/web/scripts/qa-share-preview.mjs` (**25 checks, files only**), and
   that gate is proven decisive by a 17-arm battery in which **17/17 matched a prediction written before the run**;
4. and the live half — a built server serving `/og.png`, and a share page's `<head>` carrying the card — is a
   `next build` + `next start` leg recorded in §4 below, not a claim the gate makes.

## 1. The two defects, as measured

`app/layout.tsx` declared a site-level `openGraph`; the three `/…/shared/<token>` pages declared `title`,
`description` and `robots` and nothing else. Next merges a child's metadata over the layout's, so an absent
`openGraph` is not an absent card — it is the **site's** card, served for a page whose entire purpose is one
person's CV, board or clip.

Separately, `pageMetadata` had printed `card: "summary_large_image"` on every indexed page since it landed. That is
a promise of an image. `public/og.png` did not exist. So the site declared a picture it had not got on 10 of the 14
routes a signed-out reader reaches — while §3 of the SEO doc told the reader, truthfully at the time, that the tag
was absent *because* no licensed or project-authored asset existed.

The fix is one helper a page cannot misuse and one asset the project authored:

- `sharedMetadata()` in `lib/site.ts` decides `robots: {index:false, follow:false}` and the **parent** canonical
  itself, so a caller cannot forget either; the caller supplies only the page's title, its description and its own
  share path. `og:url` keeps the token — that is where the reader lands, and the token is already what the page's
  JSON-LD publishes.
- `scripts/make_og_image.mjs` renders `public/og.png` (1200×630, 62,647 bytes) from `app/icon.svg`, the two strings
  in `lib/site.ts` and the tokens in `styles/globals.css`. Nothing was copied in, so §89's ban on scraped or stock
  imagery still holds; the SEO doc's exclusion is retired in place rather than deleted.

## 2. §109b — the defect found while verifying: HEAD did not build

While preparing this document the plane itself was type-checked, and **`cc0ad34` is red**. On a clean
`git archive HEAD` plane, `npx tsc --noEmit` answers exactly one error:

```
app/portfolio/shared/[token]/page.tsx(10,10): error TS2305:
  Module '"@/lib/site"' has no exported member 'sharedMetadata'.
```

`cc0ad34` wired the shared CV page to `sharedMetadata` and committed **the page only**. The helper lived in the
working tree, so the type gate the commit message cites ("the type gate said so") was genuinely run — against a tree
that was not the one being committed. `scripts/check.sh:110` arms exactly this control, and it is not the control
that failed but the ordering: the gate read a dirty tree, the commit took a subset.

This unit retires it, because `lib/site.ts` — `sharedMetadata`, `ogImages()`, `SITE_DESCRIPTION`, the `OG_IMAGE_*`
constants — lands here. Verified both ways on the two planes:

| plane | `npx tsc --noEmit` |
| --- | --- |
| clean `git archive HEAD` (`cc0ad34`) | **1 error** — TS2305, quoted above |
| this worktree (HEAD + the unit) | **0 errors** |

The lesson is recorded in §5 rather than left as an anecdote: a landing that spans a helper and its callers must
type-check *the staged subset*, not the tree it was written in.

## 3. The gate and its witness battery

`apps/web/scripts/qa-share-preview.mjs` — **25 checks, all refusing independently**, wired into `scripts/check.sh`.
It *transpiles and calls* `lib/site.ts`, so clauses 3–6 are about the bytes a page receives rather than about
whether a string appears in the source:

| # | what it refuses |
| --- | --- |
| 1, 1b | the walk finds ≥ 3 `shared/` pages and every one parses — a blind walk would grade an empty set and print "0 problems" |
| 2 | each share page builds metadata through `sharedMetadata` **imported from `lib/site.ts`** (by binding, so a local function of the same name cannot satisfy it) and hand-writes no `openGraph` |
| 3, 3b, 3c | the card names the page; `og:url` is the share URL while the canonical is the parent, and the two are never the same bytes; the site still appears, as `siteName`, never as the title |
| 4 | `noindex`/`nofollow` is the helper's decision — a share token *is* the credential |
| 5, 5b | both readers carry the picture: `openGraph.images` **and** `twitter.images`, one entry each at the declared size |
| 6 | no `summary_large_image` anywhere in `app/**` without an image behind it — the two helpers graded by calling them, every hand-written `twitter` block graded structurally, and the graded count printed so a rule that found nothing cannot read as a rule that passed |
| 7, 7b, 7c | the asset answers: `public/og.png` exists, is a PNG by its signature, its **IHDR** says the size `lib/site.ts` declares, and it is ≥ 10,000 bytes so a flat placeholder fails |
| 8, 8b, 8c | the generator sizes, words and colours itself only from `${OG_IMAGE_*}`, `${SITE_NAME}`, `${SITE_TAGLINE}` and `${tokens.*}` — the card's own markup slice is graded, so a comment may name the brand but the picture may not copy it |
| 9, 9b, 9c | every declared canonical is a static page the app answers; each share path sits under its own route with the token half interpolated; and no share prefix appears in `sitemap.ts` in any of the three spellings a hand-edited entry takes |

The battery is `.scratch/share109-arms.mjs`: 17 arms, each mutating **one** shipped input on a frozen copy of the
landing plane outside the repo root, each with its expected red-check ids written into the row before the run.

```
arms=17 matched=17 mismatched=0
```

- **R0 is the reverse control** — the same gate against the two share pages as `cc0ad34` wrote them. It answers
  `2, 2, 9, 9, 9b, 9b`: the helper clause for both pages plus the route clause for both. A gate that graded HEAD
  green would gate nothing.
- **A13** deletes the helper and the gate answers `FATAL` (exit 2), not a quiet pass over an empty population.
- **A8/A8b** replace the asset with an honest-size 1×1 PNG and with a non-PNG: 7b, 7c and 7 go red respectively, so
  the size claim is read off the file's own IHDR rather than off the declaration it is checking.
- **A12** advertises a share route in the sitemap; the crawl-policy gate goes red in lockstep (`1`), which is what
  makes the two gates one decision rather than two opinions.
- **A15** hand-writes a large card with no picture on a non-share page — clause 6's population is not limited to the
  three pages this unit was about.

The three gates this unit touched are green on the worktree: share-preview **25/25**, crawl-policy **9/9**
(61 pages, 34 gated, 31 noindex, 25 disallowed), metadata-title **160/160**, i18n-literals **2/2**.

## 4. The live leg

`next build` (exit 0) then `SITE_URL=http://127.0.0.1:3213 next start -p 3213` — a new port, so the reading is this
build's and not a dev server left running. `.scratch/r109-heads.mjs`
fetches each route as a **signed-out reader**, which is every link-preview bot there is, and parses `<head>` with a
tag-by-tag attribute scan rather than a byte search:

| route | status | og:title | og:image | tw:card | robots | canonical |
| --- | --- | --- | --- | --- | --- | --- |
| `/tactics/shared/{token}` | 200 | Shared tactical board | `/og.png` | summary_large_image | noindex, nofollow | `/tactics` |
| `/video/shared/{token}` | 200 | Shared clip | `/og.png` | summary_large_image | noindex, nofollow | `/video` |
| `/portfolio/shared/{token}` | 200 | Shared Football CV | `/og.png` | summary_large_image | noindex, nofollow | `/portfolio` |
| `/knowledge` | 200 | Football Knowledge | `/og.png` | summary_large_image | — | `/knowledge` |
| `/world` | 200 | Football World | `/og.png` | summary_large_image | — | `/world` |
| `/club/rules` | 200 | Club and academy rulebook | **ABSENT** | **summary** | — | `/club/rules` |
| `/login`, `/register`, `/` | 200 | FOOTBALL OS (site card) | `/og.png` | summary_large_image | — | ABSENT |
| `/world/search`, `/tactics/compare` | 200 | FOOTBALL OS | `/og.png` | summary_large_image | noindex, follow | own route |
| `/my-football`, `/scout`, `/portfolio` | 307 | — | — | — | — | redirect → `/login?next=…` |

The three figures that carry the unit:

- `og:image present: 10 of 14`, `twitter:image present: 10 of 14`, and **`summary_large_image declared: 10, of
  those carrying an image: 10`** — the promise is paid on every page that makes it. The four without an image are
  the three session-gated redirects (no card is served; they answer 307) and `/club/rules`, which declares the
  smaller `summary` card and therefore owes no picture. That is the distinction clause 6 grades: a card type that
  needs no image is a choice, a `summary_large_image` with nothing behind it is a lie.
- Each share page's `og:url` carries the **full token** (`…/tactics/shared/0000…`) while its canonical is the parent
  (`…/tactics`) — the two-halves decision the helper owns, observed as served bytes rather than as source.
- `GET /og.png` → **200, `image/png`, 62,647 bytes**, matching the IHDR the gate read; and
  `GET /sitemap.xml | grep -c shared` → **0**, so a token URL is never advertised to a crawler.

## 5. Boundaries — what this does not claim

- **The card is the site's, not the page's picture.** Every share page renders the same `og.png`; the *text* of the
  card is per-page. A per-surface image would be a second asset generator, and §89 still forbids sourcing one from
  anywhere but this repo.
- **A token in `og:url` is a disclosure to whoever the link is forwarded to**, which is the same exposure the page
  body already has. `noindex`/`nofollow` keeps it out of search; it does not keep it out of a crawlable chat log.
  it does not keep it out of a crawlable chat log. Revocation stays the owner's own route, and this unit neither
  adds nor tests one — though the three surfaces spell it three ways (`POST /boards/{id}/revoke`,
  `DELETE /video/{id}/share`, `DELETE /portfolio/share/{token}`), which is a census worth having elsewhere.
- **Locale.** The share card's title and description come from `getTranslations`, so they follow the reader's
  locale; the routes are not locale-prefixed (`/zh/…` answers 404), so this leg read the default. Nothing here
  claims the zh card was fetched — `qa-metadata-title.mjs` (160 checks) owns the catalogue side.
- **The gate is files-only.** It never opens a port, and it does not claim what a *specific* bot renders; the
  served-`<head>` evidence is §4, and it is a `next start` reading of this build.
- **§109b's control already existed.** `check.sh:110` runs `npm run typecheck`, so nothing new is armed for this
  class of failure. What was missing was ordering — the gate read a dirty tree while the commit took a subset — and
  the remedy is the one in §5's last paragraph: type-check the staged set before it becomes HEAD.
