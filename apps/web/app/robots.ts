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
  "/tactics/shared",
  // Uploaded clips and everything derived from them. A clip is the most identifying file a user can
  // hand the platform, so it is disallowed rather than noindexed alone: no frame URL, no report.
  "/video",
  // Which fixtures an account chooses to play, and the reports of them. The clubs are public fiction
  // already; the account's own simulation history is not content, and a model scoreline must not be
  // crawlable as if it were a result.
  "/simulate",
  "/career",
  // A challenge run is a career: which scenario an account took on, and the verdict its own rounds
  // produced. Nothing here is a real competition, so nothing here should be crawlable as one.
  "/challenges",
  // The scouting screen reads the whole stored player table on an account, and a report or a comparison is
  // one manager's opinion-shaped cut of generated rows. `/scout/rules` is public JSON, but the page itself is
  // session-gated, so it is disallowed rather than noindexed alone.
  "/scout",
  // A tenant's members, sheets and children's plans. `/club/rules` is excepted below on purpose: the
  // permission matrix, the caps and the refusal table are the terms of the service, and §39 publishes them
  // at a door that needs no account — a rule an account holder cannot read until they have agreed to it is
  // not a rule.
  "/club",
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
