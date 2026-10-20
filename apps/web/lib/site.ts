/**
 * Public-origin helpers for SEO metadata. Canonicals, OpenGraph URLs and the sitemap must
 * carry the same host a visitor used, so `SITE_URL` is the single knob that sets it.
 */

import type { Metadata } from "next";

export const SITE_NAME = "FOOTBALL OS";

/**
 * The sentence the product opens with. It lives here because three readers want the same bytes — the layout's
 * `description`, its `WebSite` graph, and the `alt` text of the card below — and a card that disagrees with the
 * page it previews is two authors inside one tag.
 */
export const SITE_TAGLINE = "Watch. Understand. Train. Play. Manage. Become.";

/** The tagline plus the clause the root layout and the `WebSite` graph both print after it. */
export const SITE_DESCRIPTION = `${SITE_TAGLINE} — a football operating system for fans, players and coaches.`;

/**
 * The share card's picture, and the two numbers a reader checks it against.
 *
 * `twitter.card: "summary_large_image"` is a promise of an image, which this file used to make without having one.
 * The asset is now the project's own — `scripts/make_og_image.mjs` renders it from the mark in `app/icon.svg` and
 * the two strings above, so nothing was copied in — and `qa-share-preview.mjs` reads the PNG's own IHDR header and
 * refuses a card whose declared size, its path, or the module that points at it disagree with the bytes on disk.
 */
export const OG_IMAGE_PATH = "/og.png";
export const OG_IMAGE_WIDTH = 1200;
export const OG_IMAGE_HEIGHT = 630;

export function siteOrigin(): string {
  return (process.env.SITE_URL ?? "http://127.0.0.1:3210").replace(/\/+$/, "");
}

export function absolute(path: string): string {
  return `${siteOrigin()}${path.startsWith("/") ? path : `/${path}`}`;
}

/** The card image, sized and described. Both `openGraph.images` and `twitter.images` are set: a scraper reads one
 * or the other, and a card that loses its picture depending on which tag it reads is a coin toss. */
export function ogImages(): NonNullable<Metadata["openGraph"]>["images"] {
  return [{ url: absolute(OG_IMAGE_PATH), width: OG_IMAGE_WIDTH, height: OG_IMAGE_HEIGHT, alt: `${SITE_NAME} — ${SITE_TAGLINE}` }];
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
  /** The one declaration the helper never set on its own. User-content pages that are
   * public but never indexed — the gallery, the clip report — pass their robots here
   * instead of leaving the helper, which is what the metadata gate's forms check reads. */
  robots?: Metadata["robots"];
}): Metadata {
  const url = absolute(input.path);
  const images = ogImages();
  return {
    title: input.title,
    description: input.description,
    robots: input.robots,
    alternates: { canonical: url },
    openGraph: {
      type: input.type ?? "website",
      url,
      title: input.title,
      description: input.description,
      siteName: SITE_NAME,
      images,
    },
    twitter: { card: "summary_large_image", title: input.title, description: input.description, images },
  };
}

/**
 * OpenGraph for a page that is handed to a person by link and never advertised to a crawler: the three
 * `/…/shared/<token>` surfaces.
 *
 * A share page used to declare only `title`, `description` and `robots`, which means it inherited the root
 * layout's site-level `openGraph` — so a link to somebody's CV, board or clip previewed as "FOOTBALL OS" with the
 * site's description. The card is the whole of what a reader sees before clicking, and it named the product
 * instead of the thing they were sent to.
 *
 * Two decisions the caller does not get to make: `robots` is fixed to noindex/no-follow, because the token is the
 * credential and indexing it hands the link to everybody; and the canonical points at the *parent* surface, so the
 * share page never self-canonicalises a URL that is not in the sitemap. `sharePath` still carries the token: the
 * card's own `og:url` is where the reader lands, and the token is already what the page's JSON-LD publishes.
 */
export function sharedMetadata(input: {
  title: string;
  description: string;
  sharePath: string;
  canonicalPath: string;
  type?: "website" | "article";
}): Metadata {
  const images = ogImages();
  return {
    title: input.title,
    description: input.description,
    robots: { index: false, follow: false },
    alternates: { canonical: absolute(input.canonicalPath) },
    openGraph: {
      type: input.type ?? "website",
      url: absolute(input.sharePath),
      title: input.title,
      description: input.description,
      siteName: SITE_NAME,
      images,
    },
    twitter: { card: "summary_large_image", title: input.title, description: input.description, images },
  };
}
