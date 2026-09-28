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
  refusal_answers: Record<string, { status: number; sentence: string }>;
  entitlement_features: string[];
  data_origin: string;
  is_demo_data: boolean;
  disclaimer: string;
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