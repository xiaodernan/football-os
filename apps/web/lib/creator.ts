/**
 * M10 §36 — the creator tier, as `GET /api/v1/creator/rules` and its private doors answer it.
 *
 * Every field below was read off a live response from the running API rather than from the service module's
 * return statement — a page typed against a shape the route never sends is how a user-visible lie survives a
 * green test file. A field appears because the API sends it; the sentences that explain a figure (`rule`,
 * `formula`, `note`, `source`) are part of the payload, so the page quotes them instead of paraphrasing the
 * arithmetic in the browser.
 */

export type CreatorRulesView = {
  caps: {
    guide_max: number;
    guide_title_max: number;
    guide_slug_max: number;
    guide_summary_max: number;
    citation_max: number;
    citation_note_max: number;
    profile_headline_max: number;
    profile_bio_max: number;
    sections: string[];
    visibilities: string[];
    visibility_rule: string;
  };
  counts: { profiles: number; guides: number; citations: number };
  formulas: Record<string, string>;
  refusals: string[];
  limitation: string;
  routes: { method: string; path: string; door: string }[];
  refusal_answers: Record<string, number>;
  entitlement_features: string[];
};

export type CreatorProfileView = {
  id: string;
  slug: string;
  account: { id: string; display_name: string };
  headline: string;
  bio: string;
  since: string;
  guides: number;
  subscribers: number;
  formulas: Record<string, string>;
  rule: string;
  created?: boolean;
};

export type GuideSection = "plan" | "drill" | "match" | "tactic" | "scout" | "video";
export type GuideVisibility = "public" | "unlisted" | "followers";

export type GuideView = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  section: GuideSection;
  visibility: GuideVisibility;
  published_on: string;
  author: { id: string; display_name: string };
  citations: number;
  moved: number;
  tokens: number;
  formulas: Record<string, string>;
  passages?: GuideCitationView[];
};

export type GuideShelfView = {
  items: GuideView[];
  total: number;
  limit: number;
  creator: string | null;
  section: string | null;
  formulas: Record<string, string>;
  rule: string;
};

export type GuideDetailView = GuideView & {
  passages: GuideCitationView[];
};

export type GuideCitationView = {
  id: string;
  document: string;
  ordinal: number;
  note: string;
  heading: string | null;
  moved: boolean;
};

export type CitationRecordedView = {
  citation: GuideCitationView;
  recorded_now: boolean;
  citations: number;
  moved: number;
  tokens: number;
  formulas: Record<string, string>;
};

export type ProfileIn = {
  slug?: string;
  headline?: string;
  bio?: string;
};

export type GuideIn = {
  section: GuideSection;
  title: string;
  summary?: string;
  visibility?: GuideVisibility;
};

export type CitationIn = {
  document: string;
  ordinal: number;
  note?: string;
};

/**
 * The figures a refusal answered with, in the order the door sent them.
 *
 * §36's refusals carry the number that decided them — a cap and what is held against it, a length and the limit —
 * so a page that printed the sentence and dropped the figures would be showing half of the answer. Each tier keeps
 * its own copy of this, as §35's does, so a creator surface never depends on the club tier's module.
 */
export function refusalFigures(details: unknown): string[] {
  if (!details || typeof details !== "object" || Array.isArray(details)) return [];
  return Object.entries(details as Record<string, unknown>)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key} ${Array.isArray(value) ? value.join(", ") || "none" : String(value)}`);
}


/** POST /creator/programs — one program with its steps and the figures counted now. */
export type ProgramView = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  visibility: string;
  published_on: string;
  steps: { position: number; drill: string; minutes: number; note: string }[];
  figures: { steps: number; minutes: number; sessions: number };
};

/** GET /creator/programs — the shelf. */
export type ProgramShelfView = {
  programs: {
    id: string;
    slug: string;
    title: string;
    summary: string;
    author: string;
    published_on: string;
    steps: number;
  }[];
  total: number;
};

/** POST /creator/programs — what a program asks for. */
export type ProgramIn = {
  title: string;
  summary?: string;
  visibility: string;
  steps: { drill: string; minutes: number; note?: string }[];
};
