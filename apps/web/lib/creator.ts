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
  /** The career challenge's own vocabulary, published beside the other objects' (2026-10-22). */
  career_challenge_caps: {
    career_challenge_max: number;
    career_challenge_title_max: number;
    career_challenge_slug_max: number;
    career_challenge_summary_max: number;
    career_challenge_target_min: number;
    career_challenge_target_max: number;
    career_challenge_window_min: number;
    career_challenge_window_max: number;
  };
  /** Each objective kind is a published formula; the panel quotes the formula rather than paraphrasing it. */
  career_challenge_objective_kinds: Record<string, string>;
  career_challenge_formulas: Record<string, string>;
  career_challenge_counts: { career_challenges: number; career_attempts: number };
  career_challenge_rule: string;
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

/** POST /creator/challenges — the author's rule: an objective, a target and a window of rounds. */
export type CareerChallengeIn = {
  title: string;
  summary?: string;
  visibility: string;
  objective: string;
  target: number;
  window_rounds: number;
};

/** One entrant's run, judged on the read from their own career's fixture rows. */
export type CareerAttemptView = {
  id: string;
  career: {
    slug: string;
    manager_name: string | null;
    club_name: string | null;
    status: string | null;
    path: string | null;
    stored: boolean;
  };
  start_round: number;
  window: {
    start_round: number;
    end_round: number;
    rounds: number;
    played: number | null;
    remaining: number | null;
    closed: boolean;
  };
  status: string;
  actual: number | null;
  target: number;
  target_met: boolean | null;
  earned: boolean;
  formula: string;
  rounds: { round_index: number; outcome: string; club_goals: number; opponent_goals: number; points: number }[];
  reason: string;
};

/** GET /creator/challenges/{id} — the rule every viewer sees, and only the viewer's own run. */
export type CareerChallengeView = {
  id: string;
  slug: string;
  title: string;
  summary: string;
  visibility: string;
  published_on: string;
  author: { id: string; display_name: string };
  objective: { kind: string; target: number; formula: string };
  window_rounds: number;
  figures: { attempts: number };
  attempt: CareerAttemptView | null;
  formulas: Record<string, string>;
  rule: string;
};

/** GET /creator/challenges — the shelf, each row joined to the viewer's own entry flag. */
export type CareerChallengeShelfView = {
  items: {
    id: string;
    slug: string;
    title: string;
    summary: string;
    visibility: string;
    published_on: string;
    author: { id: string; display_name: string };
    objective: { kind: string; target: number; formula: string };
    window_rounds: number;
    attempts: number;
    entered: boolean;
  }[];
  total: number;
  limit: number;
  creator: string | null;
  formulas: Record<string, string>;
  rule: string;
};
