import type { MetadataRoute } from "next";

import { absolute } from "@/lib/site";

/** Rendered per request so `SITE_URL` at runtime wins over whatever the build saw. */
export const dynamic = "force-dynamic";

/**
 * Everything below is either session-gated (it redirects anonymous visitors to /login) or a
 * JSON proxy. The crawlable surface is the knowledge library, the Football World pages (M3) and
 * the Tactical Lab (M4) — none of which require an account, which is exactly why they may be advertised.
 */
const DISALLOWED = [
  "/api/",
  "/login",
  "/register",
  "/onboarding",
  "/my-football",
  "/training",
  "/coach",
  "/progress",
  "/history",
  "/settings",
  // A person's own boards, and links they handed out on purpose. `/tactics` and the 50 authored
  // system pages stay crawlable; these two prefixes are user content, not publication.
  "/tactics/boards",
  // The gallery is public but it is user content: the same rule the clip report holds.
  "/tactics/gallery",
  // A tray is the account's own correspondence.
  "/notifications",
  "/tactics/shared",
  // Uploaded clips and everything derived from them. A clip is the most identifying file a user can
  // hand the platform, so it is disallowed rather than noindexed alone: no frame URL, no report.
  "/video",
  // Which fixtures an account chooses to play, and the reports of them. The clubs are public fiction
  // already; the account's own simulation history is not content, and a model scoreline must not be
  // crawlable as if it were a result.
  "/simulate",
  // The cross-career ledgers. Same rule as the row above and the same rows behind it: a league table or a
  // player aggregate is the sum of what an account's own rounds produced, so it is not content even though
  // the world's fixtures are. `scripts/qa-crawl-policy.mjs` found these three prefixes missing when the list
  // was written by hand — the pages declare `noindex`, but a signed-out fetch answers 307 and a redirect has
  // no `<head>`, so the declaration was never readable by the one crawler that would have honoured it.
  "/simulation",
  "/career",
  // A challenge run is a career: which scenario an account took on, and the verdict its own rounds
  // produced. Nothing here is a real competition, so nothing here should be crawlable as one.
  "/challenges",
  // The scouting screen reads the whole stored player table on an account, and a report or a comparison is
  // one manager's opinion-shaped cut of generated rows. `/scout/rules` is public JSON, but the page itself is
  // session-gated, so it is disallowed rather than noindexed alone.
  "/scout",
  // The agent console: which agents an account has run, and what each one answered. The roster itself is public
  // JSON at `/api/v1/agents/list` — which the `/api/` row above closes — while this page is the account's run log.
  "/agents",
  // §30's graph browser. Its nodes are the generated world's own rows, so the *entities* it links to are
  // crawlable through the sitemap; the browser is a session-gated view over them, and the four pages under it
  // (`/graph`, `/graph/nodes/<kind>`, `<slug>`, `<slug>/neighborhood`) all redirect a signed-out reader.
  "/graph",
  // A tenant's members, sheets and children's plans. `/club/rules` is excepted below on purpose: the
  // permission matrix, the caps and the refusal table are the terms of the service, and §39 publishes them
  // at a door that needs no account — a rule an account holder cannot read until they have agreed to it is
  // not a rule.
  "/club",
  // A person's own feed (§35) and the guides an account writes (§36). Both pages redirect
  // a signed-out visitor to `/login`, and this file's rule is that a session-gated route is
  // disallowed rather than offered to the crawl as a redirect chain. Both carry their own
  // `noindex` as well, and neither is in the sitemap; the tier behind them has no public page
  // to except, the way `/club/rules` is.
  "/community",
  "/creator",
  // §38's CV and its shared links. The private page redirects a signed-out visitor and every figure in it is one
  // account's own rows. A shared link is public to the person holding it, but it is still user content and is not
  // offered to crawlers, on the same rule as §17's shared tactical boards.
  "/portfolio",
];

/** The one `/club` path that is not a person's data. */
const ALLOWED = ["/club/rules"];

export default function robots(): MetadataRoute.Robots {
  return {
    // A longer `Allow` match wins over a `Disallow` prefix in the standard, which is what makes the
    // rulebook indexable while everything under `/club` that names a real tenant is not.
    rules: [{ userAgent: "*", allow: ALLOWED, disallow: DISALLOWED }],
    sitemap: absolute("/sitemap.xml"),
    host: absolute("/"),
  };
}
