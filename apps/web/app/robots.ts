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
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", disallow: DISALLOWED }],
    sitemap: absolute("/sitemap.xml"),
    host: absolute("/"),
  };
}
