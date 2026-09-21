# SEO + crawlability — verification record (spec §80, §81)

Date: 2026-09-21 · Tier: `apps/web` · Evidence run: `202609212143` (66/66 browser assertions, 29 PNGs in `docs/screenshots/`)

A later run (2026-09-21 22:40 UTC) extended the harness to 68/68 by asserting two `/settings` rows: that M3 Football World
reads Live from the data-derived API flag, and that the locale row ships only `en` with `zh`/`zh-TW` labelled planned.

Spec §80 requires public pages to carry Metadata, OpenGraph, Structured Data, Sitemap and Canonical, with
`/{entity}/{slug}` routes. §81 asks for en / zh / zh-TW. This record states what is true now and names what is not.

## 1. What was missing before this increment

`app/layout.tsx` set only `title` + `description`. There was no `metadataBase`, so every relative URL in metadata
resolved against nothing; no `app/sitemap.ts`, no `app/robots.ts`, no `alternates.canonical` on any route, no
OpenGraph or `application/ld+json` anywhere, and `og:*` tags did not exist. `README.md` and `ARCHITECTURE.md` also
claimed `i18n(en/zh/zh-TW)`, which was never true (see §5).

## 2. What exists now

| Piece | File | Verified by |
| --- | --- | --- |
| Single public origin knob | `lib/site.ts` → `siteOrigin()` from `SITE_URL`, default `http://127.0.0.1:3210` | every assertion below; documented in `apps/web/.env.example` |
| `metadataBase` + site-level OpenGraph defaults | `app/layout.tsx` | render of `<head>` on all routes |
| Per-route canonical + OG (never at layout level, or every child self-canonicalises to home) | `pageMetadata()` in `lib/site.ts`, used by `/knowledge` and `/knowledge/{slug}` | `knowledge index publishes canonical + matching OpenGraph URL` |
| Site graph (`WebSite`) | `app/layout.tsx` body | `a WebSite graph identifies the site by absolute URL` |
| Document graph (`Article`: headline, url, `mainEntityOfPage`, author, `dateModified`, keywords) | `app/knowledge/[slug]/page.tsx` | `document page carries Article structured data with its headline` |
| `sitemap.xml` generated from a live API read | `app/sitemap.ts` | 3 assertions: served, 17 `<loc>` entries, every entry answers 200 |
| `robots.txt` | `app/robots.ts` | 2 assertions: `text/plain`, all session-gated paths disallowed |

Rendered head of `/knowledge/warmup-structure` (production build, `SITE_URL=http://127.0.0.1:3211`):

```html
<link rel="canonical" href="http://127.0.0.1:3211/knowledge/warmup-structure"/>
<meta property="og:type" content="article"/>
<meta property="og:url" content="http://127.0.0.1:3211/knowledge/warmup-structure"/>
```
```json
{"@context":"https://schema.org","@type":"Article","headline":"Structuring a warm-up: ramp, activation, mobility, ball",
 "url":"http://127.0.0.1:3211/knowledge/warmup-structure","author":{"@type":"Organization","name":"FOOTBALL OS"},
 "publisher":{"@type":"Organization","name":"FOOTBALL OS"},"inLanguage":"en","isAccessibleForFree":true,
 "dateModified":"2026-09-18","keywords":"warm up, activation, mobility, ramping, session preparation"}
```

## 3. Deliberate exclusions (honesty, not omission)

- **`/` is not in the sitemap.** For a signed-out visitor it `redirect()`s to `/login` (or `/onboarding`), so
  advertising it would publish a redirect chain as a page. Same for `/training`, `/training/{slug}`, `/coach`,
  `/my-football`, `/progress`, `/history`, `/settings` — all session-gated, all in `robots.txt` `Disallow`.
- **No `og:image` / `twitter:image`.** There is no licensed or project-authored image asset to point at, and
  §89 forbids copied imagery. The tag is absent rather than filled with a stock or scraped picture.
- **`sitemap.xml` lastmod comes from `last_reviewed ?? ingested_at`** — the API's own fields, not a build timestamp.
- Filter links such as `/knowledge?category=tactics` are not listed; they are the same content under a query
  string, i.e. duplicate URLs a crawler would otherwise be told to treat as distinct pages.

## 4. One defect found and fixed during this increment

`app/robots.ts` was first emitted as **static** (`○ /robots.txt` in the build manifest), so its `Sitemap:` and
`Host:` lines froze whatever `SITE_URL` the *build* saw: fetched from a server running with
`SITE_URL=…:3211`, robots.txt still pointed at `…:3210` while sitemap `<loc>` values correctly said `:3211`.
Adding `export const dynamic = "force-dynamic"` moved it to `ƒ /robots.txt` and the mismatch disappeared
(re-verified: `Host: http://127.0.0.1:3211/`, `Sitemap: http://127.0.0.1:3211/sitemap.xml`).

Also changed in the harness: browser console errors are now tagged with the route they happened on
(`… @ /path`), because a minified React code alone is not actionable. The first production-build run printed one
React `#418` hydration error that has **not** reproduced in the clean run above or in a targeted walk of six public
routes; it is recorded here rather than dropped, and the new tagging will name the route if it returns.

## 5. i18n (spec §81) — not built

The UI is English-only: no `messages/*.json`, no locale routing, no translation layer. What existed was a
`locales: ["en","zh","zh-TW"]` field in `GET /capabilities`, which reads as a shipped feature. Corrected where it
was overstated: `README.md` architecture line now lists what the web tier actually does (SEO metadata, sitemap,
robots) and its honesty-guarantees section states the English-only reality; `ARCHITECTURE.md` §6 now marks i18n as
not built and describes the target shape. The `/capabilities` field itself is a backend change and is tracked in
`ROADMAP.md` under "Now → next session" so the claim and the code can be reconciled together.

## 6. Reproduce

```bash
# build beside the live dev server, then serve the production build on a spare port
cd apps/web
npx tsc --noEmit && npm run lint                       # clean
NEXT_DIST_DIR=.next-ci npx next build                  # ƒ /sitemap.xml, ƒ /robots.txt
SITE_URL=http://127.0.0.1:3211 NEXT_DIST_DIR=.next-ci npx next start -p 3211
curl -s http://127.0.0.1:3211/robots.txt | tail -2     # Host/Sitemap must name 3211
curl -s http://127.0.0.1:3211/sitemap.xml | grep -c "<loc>"   # 17
QA_BASE=http://127.0.0.1:3211 node scripts/visual-qa.mjs      # 66/66, exit 0
```

The QA walk exercises the whole M1+M2 loop against the **production build**, not a hot-reloaded dev server, so the
SEO assertions above are read from server-rendered HTML.
