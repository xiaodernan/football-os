import type { MetadataRoute } from "next";

import { absolute } from "@/lib/site";

/** Rendered per request so `SITE_URL` at runtime wins over whatever the build saw. */
export const dynamic = "force-dynamic";

/**
 * Everything below is either session-gated (it redirects anonymous visitors to /login) or a
 * JSON proxy. The crawlable surface is the knowledge library — and, from M3, the world pages.
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
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", disallow: DISALLOWED }],
    sitemap: absolute("/sitemap.xml"),
    host: absolute("/"),
  };
}
