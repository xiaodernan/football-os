/** DTO types mirroring apps/api (schemas + the JSON envelopes the routes return). */

export const POSITIONS = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST", "CF"] as const;
export const LEVELS = ["beginner", "intermediate", "advanced", "elite"] as const;
export const FEET = ["left", "right", "both"] as const;
export const GOALS = [
  "improve_first_touch",
  "improve_passing",
  "improve_dribbling",
  "improve_finishing",
  "improve_defending",
  "improve_pressing",
  "improve_weak_foot",
  "improve_fitness",
  "improve_vision",
  "become_box_to_box",
  "become_playmaker",
  "become_inverted_winger",
] as const;
export const ROLES = ["fan", "player", "coach", "manager", "scout", "academy"] as const;

/** Retrieval filter enums the /knowledge search + ask endpoints accept. */
export const KNOWLEDGE_MODES = ["semantic", "keyword", "hybrid"] as const;
export const KNOWLEDGE_POSITIONS = ["goalkeeper", "defender", "midfielder", "forward", "all"] as const;
export const KNOWLEDGE_DIFFICULTIES = ["beginner", "intermediate", "advanced"] as const;

export type Position = (typeof POSITIONS)[number];
export type PlayingLevel = (typeof LEVELS)[number];
export type Foot = (typeof FEET)[number];
export type Goal = (typeof GOALS)[number];
export type UserRole = (typeof ROLES)[number];
export type AttributeGroup = "technical" | "physical" | "mental" | "tactical";

export type ApiError = { code: string; message: string; details?: unknown };

export type TokenPair = {
  access_token: string;
  token_type: string;
  expires_in_seconds: number;
  demo_mode: boolean;
};

export type UserOut = {
  id: string;
  email: string;
  display_name: string;
  role: string;
  plan: string;
  locale: string;
  streak_days: number;
};

export type PlayerOut = {
  id: string;
  name: string;
  position: string;
  age: number;
  level: string;
  preferred_foot: string;
  goal: string;
  height_cm: number | null;
  overall: number;
  potential: number;
  form: number;
  archetype: string;
  archetype_match: number;
  xp: number;
  level_number: number;
  attributes: Record<string, number>;
  visibility: string;
  is_demo_data: boolean;
  derivation_reasons: string[];
};

export type Drill = {
  id: string;
  slug: string;
  title: string;
  category: string;
  objective: string;
  difficulty: number;
  duration_min: number;
  equipment: string[];
  setup: string;
  instructions: string[];
  coaching_points: string[];
  common_mistakes: string[];
  progressions: string[];
  regression: string;
  test_prompt: string;
  test_target: string;
  target_attributes: Record<string, number>;
  positions: string[];
  xp_base: number;
  /** The coach projection carries these safety fields; the drill list route does not. */
  needs_pitch?: boolean;
  min_age_safe?: number;
  is_demo_data: boolean;
};

export type PlanSession = {
  drill_id: string;
  slug: string;
  title: string;
  category: string;
  duration_min: number;
  objective: string;
  why: string;
};

export type PlanDay = {
  day: number;
  date: string;
  type: "training" | "test" | "recovery" | "rest";
  sessions: PlanSession[];
  note: string;
};

/** Every AI/coach payload is this envelope plus the fields of the answering route. */
export type AiEnvelope = {
  demo_mode: boolean;
  provider: string;
  model: string;
  confidence: number;
  reasons: string[];
  sources: { type: string; ref: string; label: string }[];
  generated_at: string;
  disclaimer: string;
};

/** GET /coach/today — always carries a full recommendation set. */
export type TodayRecommendation = AiEnvelope & {
  message: string;
  recommendation: Drill;
  alternatives: Drill[];
  focus_attributes: string[];
  context: Record<string, unknown>;
  player: { overall: number; archetype: string; goal: string; streak_days: number };
};

/** POST /coach/ask — which fields accompany `message` depends on the detected intent. */
export type CoachAnswer = AiEnvelope & {
  intent: string;
  question: string;
  message: string;
  recommendation?: Drill;
  alternatives?: Drill[];
  plan?: { horizon_days: number; days: PlanDay[] };
};

/** POST /coach/plan */
export type GeneratedPlan = AiEnvelope & {
  horizon_days: number;
  goal: string;
  days: PlanDay[];
};

export type Overview = {
  player: {
    id: string;
    name: string;
    position: string;
    age: number;
    goal: string;
    overall: number;
    potential: number;
    form: number;
    archetype: string;
    archetype_match: number;
    preferred_foot: string;
  };
  attributes: Record<string, number>;
  attribute_groups: Record<string, Record<string, number>>;
  xp: { total: number; level: number; next_level_at: number; progress_in_level: number };
  training: {
    sessions_completed: number;
    sessions_this_week: number;
    streak_days: number;
    last_session_at: string | null;
  };
  achievements: { slug: string; title: string; description: string; awarded_at: string }[];
  empty_state: boolean;
  demo_data: boolean;
};

export type Timeline = {
  sessions: { date: string; status: string; xp: number | null; execution: number | null; drill: string; category: string }[];
  attribute_series: Record<string, { at: string; after: number; delta: number; reason: string }[]>;
  xp_events: { at: string; amount: number; reason: string; formula: string }[];
  level_estimate: number;
  demo_data: boolean;
};

export type SessionItem = {
  id: string;
  status: "planned" | "in_progress" | "completed" | "skipped";
  planned_date: string;
  completed_at: string | null;
  xp_awarded: number | null;
  execution_rating: number | null;
  focus_quality: number | null;
  self_notes: string | null;
  recommendation_reasons: string[];
  drill: {
    id: string;
    slug: string | null;
    title: string;
    category: string;
    duration_min: number;
    difficulty: number;
    test_prompt: string;
    test_target: string;
  };
};

export type SessionList = { items: SessionItem[]; page: number; page_size: number; total: number; demo_data: boolean };

export type PlannedSession = { session_id: string; status: string; drill: Drill; reasons: string[] };

export type CompletionResult = {
  session_id: string;
  status: string;
  xp_awarded: number;
  xp_formula: string;
  attribute_changes: { attribute: string; delta: number; before: number; after: number; reason: string }[];
  /** Per-target-attribute skill point banking; explains a session that moved nothing yet. */
  skill_progress: { attribute: string; earned: number; banked: number; needed: number; value: number; ceiling: string }[];
  player_level: number;
  level_changed: boolean;
  streak_days: number;
  new_achievements: string[];
  form: number;
  player: { id: string; overall: number; potential: number; archetype: string; archetype_match: number; xp: number };
  coach_feedback: { content: string; reasons: string[]; confidence: number };
  reasons: string[];
  demo_mode: boolean;
};

export type CoachHistory = {
  items: {
    id: string;
    role: string;
    kind: string;
    content: string;
    reasons: string[] | null;
    confidence: number | null;
    demo_mode: boolean;
    provider: string | null;
    model: string | null;
    created_at: string;
  }[];
  memory: {
    sessions_total: number;
    xp_total: number;
    level: number;
    recent_categories: string[];
    attribute_trend: { attribute: string; reason: string }[];
  };
  disclaimer: string;
};

export type HealthResponse = {
  status: string;
  environment: string;
  database_dialect: string;
  pgvector: boolean;
  providers: Record<string, unknown>;
  notes: string[];
};

/**
 * GET /capabilities — the single wire definition. Routes read milestones from this instead
 * of guessing (spec §88), so a flag that flips in the API cannot be shadowed by a stale copy.
 */
export type CapabilitiesResponse = {
  m0_foundation: boolean;
  m1_player_ai_coach: boolean;
  m2_rag: boolean;
  m3_football_world: boolean;
  m4_tactical_lab: boolean;
  m5_video_analysis: boolean;
  m6_simulation: boolean;
  m7_scouting: boolean;
  m8_club_os: boolean;
  m9_community: boolean;
  /** What the world tables actually hold, so a half-written world cannot render as if it were real. */
  m3_world?: { tables_present: boolean; counts: Record<string, number>; auto_sync: boolean; seed: number };
  /** Languages the interface actually renders. The API reports only shipped ones (spec §81), so
   * this is `["en"]` until `messages/` exists. */
  locales: string[];
  locales_planned?: string[];
  demo_mode: boolean;
};

/* Aliases: the routes were authored against both naming schemes. */
export type Account = UserOut;
export type Player = PlayerOut;
export type ProgressOverview = Overview;
export type ProgressTimeline = Timeline;
export type SessionListItem = SessionItem;
export type SessionListPage = SessionList;

/* ---------------------------------------------------------------------------
   Football Knowledge (RAG) — mirrors apps/api/app/api/v1/knowledge.py envelopes.
   AI-shaped responses (search/ask) reuse the AiEnvelope fields below but carry
   richer `sources` (provenance + section), so they are declared independently.
--------------------------------------------------------------------------- */

export type KnowledgeCategoryCount = Record<string, number>;

/** GET /knowledge/status */
export type KnowledgeStatus = {
  documents: number;
  chunks: number;
  categories: KnowledgeCategoryCount;
  embedding_models: string[];
  characters: number;
  sources: string[];
  pgvector: boolean;
  database_dialect: string;
  embedding_dim: number;
  providers: Record<string, string | boolean>;
  modes: string[];
  answer_floor: number;
  source_root: string;
  demo_mode: boolean;
};

/** A row of GET /knowledge/documents and the shared header of the detail route. */
export type KnowledgeDocument = {
  slug: string;
  title: string;
  category: string;
  tags: string[];
  applies_to: string[];
  difficulty: string;
  source: string;
  editorial_confidence: string;
  last_reviewed: string | null;
  data_origin: string;
  is_demo_data: boolean;
  char_count: number;
  chunk_count: number;
  embedding_model: string;
  ingested_at: string | null;
};

export type KnowledgeDocumentList = {
  total: number;
  categories: string[];
  items: KnowledgeDocument[];
};

/** One chunk of a document; `ordinal` is the anchor a citation deep-links to. */
export type KnowledgeSection = {
  ordinal: number;
  heading: string;
  text: string;
  char_count: number;
  tags: string[];
};

export type KnowledgeDocumentDetail = KnowledgeDocument & {
  sections: KnowledgeSection[];
};

/** Reranker feature vector behind a result's score. */
export type RetrievalFeatures = {
  lexical?: number;
  semantic?: number;
  coverage?: number;
  heading?: number;
  [key: string]: number | undefined;
};

export type KnowledgeSearchResult = {
  chunk_id: string;
  document_slug: string;
  title: string;
  heading: string;
  ordinal: number;
  category: string;
  difficulty: string;
  applies_to: string[];
  tags: string[];
  score: number;
  similarity: number;
  lexical: number;
  features: RetrievalFeatures;
  rank: number;
  excerpt: string;
};

/** A passage the answer/ranking was built from; `ref` is an in-app deep link. */
export type KnowledgeCitation = {
  type: string;
  chunk_id: string;
  document_id: string;
  slug: string;
  title: string;
  section: string;
  ordinal: number;
  category: string;
  source: string;
  quote: string;
  score: number;
  similarity: number;
  /** The 1-based `[n]` marker this citation answers to in the answer text — not a URL. Deep-link with `slug` + `ordinal`. */
  ref: number;
};

export type KnowledgeSource = {
  type: string;
  ref: string;
  label: string;
  section?: string;
  provenance?: string;
};

/** Honest verdict on whether the corpus actually covers the query. */
export type Answerability = {
  answerable: boolean;
  discriminative_terms: string[];
  discriminative_matches: string[];
  discriminative_coverage: number;
  df_ratio_limit: number;
  coverage_floor: number;
  match_floor: number;
};

export type RetrievalTimings = Record<string, number>;

/** POST /knowledge/search */
export type KnowledgeSearchResponse = {
  query: string;
  mode: string;
  retrieval_backend: string;
  scanned_chunks: number;
  top_score: number;
  reasons: string[];
  timings_ms: RetrievalTimings;
  results: KnowledgeSearchResult[];
  citations: KnowledgeCitation[];
  answerability: Answerability;
  demo_mode: boolean;
  provider: string;
  model: string;
  confidence: number;
  sources: KnowledgeSource[];
  generated_at: string;
  disclaimer: string;
};

/** Ask answers are assembled extractively; `digest` maps each [n] ref to its sentences. */
export type KnowledgeDigest = {
  ref: number;
  title: string;
  section: string;
  sentences: string[];
};

/** POST /knowledge/ask — when `answered` is false, `answer` is the refusal and citations are empty. */
export type KnowledgeAskResponse = {
  question: string;
  answered: boolean;
  answer: string;
  digest: KnowledgeDigest[];
  citations: KnowledgeCitation[];
  demo_mode: boolean;
  provider: string;
  model: string;
  confidence: number;
  reasons: string[];
  retrieval_backend: string;
  mode: string;
  scanned_chunks: number;
  top_score: number;
  timings_ms: RetrievalTimings;
  sources: KnowledgeSource[];
  generated_at: string;
  disclaimer: string;
};
