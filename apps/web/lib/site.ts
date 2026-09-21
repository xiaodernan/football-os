/**
 * Public-origin helpers for SEO metadata. Canonicals, OpenGraph URLs and the sitemap must
 * carry the same host a visitor used, so `SITE_URL` is the single knob that sets it.
 */

import type { Metadata } from "next";

export const SITE_NAME = "FOOTBALL OS";

export function siteOrigin(): string {
  return (process.env.SITE_URL ?? "http://127.0.0.1:3210").replace(/\/+$/, "");
}

export function absolute(path: string): string {
  return `${siteOrigin()}${path.startsWith("/") ? path : `/${path}`}`;
}

/**
 * Canonical + OpenGraph for one indexable page. Set this per route, never in the root
 * layout: a layout-level `alternates.canonical` is inherited by every child page, which
 * would make the whole site point at the same URL.
 */
export function pageMetadata(input: {
  title: string;
  description: string;
  path: string;
  type?: "website" | "article";
}): Metadata {
  const url = absolute(input.path);
  return {
    title: input.title,
    description: input.description,
    alternates: { canonical: url },
    openGraph: {
      type: input.type ?? "website",
      url,
      title: input.title,
      description: input.description,
      siteName: SITE_NAME,
    },
    twitter: { card: "summary_large_image", title: input.title, description: input.description },
  };
}
