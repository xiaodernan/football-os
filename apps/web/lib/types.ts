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

/* ---------------------------------------------------------------------------
 * M3 Football World — GET /api/v1/world/* (spec §54 match centre, §55 player page,
 * §56 unified search, §65 generated data, §80 public routes).
 *
 * Nullability mirrors the SQLAlchemy columns exactly: a `Mapped[int | None]`
 * column must be `number | null` here, so a page cannot print an absent figure
 * as `0`. Every payload extends `WorldEnvelope`, which is why no world page has
 * to remember to add its own provenance note.
 * ------------------------------------------------------------------------- */

export type WorldEnvelope = {
  data_origin: string;
  is_demo_data: boolean;
  demo_data: boolean;
  disclaimer: string;
};

/** GET /world/status — what the tables actually hold, measured not asserted. */
export type WorldStatus = WorldEnvelope & {
  version: string;
  seed: number;
  auto_sync: boolean;
  counts: Record<string, number>;
  seasons: string[];
  news_categories: string[];
  positions: string[];
  stat_method: Record<string, string>;
  gate: Record<string, number>;
};

/** The shared shell of the five list routes. */
export type WorldPage<T> = WorldEnvelope & {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
};

export type TeamBrief = { id: string; slug: string; name: string; short_name: string; path: string };
export type PlayerBrief = { id: string; slug: string; name: string; position: string; path: string };
export type CompetitionBrief = { id: string; slug: string; name: string; kind: string; path: string };

/** A fixture as the list/aggregate routes report it. `score` is text on purpose. */
export type MatchBrief = WorldEnvelope & {
  id: string;
  slug: string;
  path: string;
  season: string;
  round_label: string;
  kickoff_at: string | null;
  venue: { name: string; city: string };
  status: string;
  home: TeamBrief | null;
  away: TeamBrief | null;
  home_goals: number | null;
  away_goals: number | null;
  score: string;
  summary: string;
};

export type PlayerRow = WorldEnvelope & {
  id: string;
  slug: string;
  path: string;
  name: string;
  position: string;
  secondary_positions: string[];
  age: number;
  nation: string;
  preferred_foot: string;
  height_cm: number | null;
  season: string;
  overall: number;
  potential: number;
  archetype: string;
  archetype_match: number;
  goals: number;
  assists: number;
  appearances: number;
  starts: number;
  minutes: number;
  rating: number;
  form: number;
  team_id: string | null;
  club?: TeamBrief | null;
};

/** Team statistics as stored: two sides per metric, plus scalars like attendance. */
export type StatPair = { home: number; away: number };
export type MatchStats = Record<string, number | StatPair | Record<string, string>>;

/** One per-player line inside a played match — the atom every aggregate is checked against. */
export type StatLine = WorldEnvelope & {
  id: string;
  natural_key: string;
  match_id: string;
  match_slug: string | null;
  match_path: string | null;
  kickoff_at: string | null;
  competition: CompetitionBrief | null;
  player: PlayerBrief | null;
  team_id: string;
  role: string;
  position: string;
  minutes: number;
  goals: number;
  assists: number;
  shots: number;
  shots_on_target: number;
  passes: number;
  passes_accurate: number;
  key_passes: number;
  tackles: number;
  interceptions: number;
  duels_won: number;
  saves: number;
  fouls: number;
  yellow_cards: number;
  red_cards: number;
  rating: number;
};

export type TeamRow = WorldEnvelope & {
  id: string;
  slug: string;
  path: string;
  name: string;
  short_name: string;
  city: string;
  stadium: string;
  capacity: number;
  manager_name: string;
  formation: string;
  brand_color: string;
  nation: string;
  season: string;
  squad_size: number;
  overall: number;
  competition: CompetitionBrief | null;
};

export type CompetitionRow = WorldEnvelope & {
  id: string;
  slug: string;
  path: string;
  name: string;
  country: string;
  kind: string;
  tier: number;
  region: string;
  season: string;
  summary: string;
  team_count: number;
};

export type NewsRow = WorldEnvelope & {
  id: string;
  slug: string;
  path: string;
  title: string;
  summary: string;
  category: string;
  claim_class: string;
  season: string;
  source_name: string;
  author: string | null;
  url: string | null;
  published_at: string | null;
  topics: string[];
  entities: Record<string, string[]>;
  entity_links: EntityRef[];
};

/** A typed pointer into the world; `path` is the §80 route the API itself publishes. */
export type EntityRef = { type: string; slug: string; id: string | null; path: string };

export type CompetitionList = WorldPage<CompetitionRow> & { kinds: string[] };
export type TeamList = WorldPage<TeamRow> & { seasons: string[]; nations: string[] };
export type PlayerList = WorldPage<PlayerRow> & { sorts: string[]; positions: string[] };
export type MatchList = WorldPage<MatchBrief> & { statuses: string[] };
export type NewsList = WorldPage<NewsRow> & { categories: string[]; claim_classes: string[] };

export type StandingRow = {
  position: number;
  team_id: string;
  team: TeamBrief | null;
  name: string;
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
};

export type CompetitionDetail = WorldEnvelope & {
  competition: CompetitionRow;
  season: string;
  standings: StandingRow[];
  teams: (TeamBrief | null)[];
  fixtures: MatchBrief[];
  completed: number;
  scheduled: number;
  format_note: string;
};

export type TeamDetail = WorldEnvelope & {
  team: TeamRow & { summary: string };
  squad: PlayerRow[];
  fixtures: MatchBrief[];
  recent_stat_lines: StatLine[];
  squad_notes: string[];
};

export type PlayerDetail = WorldEnvelope & {
  player: PlayerRow & {
    club: TeamBrief | null;
    competition: CompetitionBrief | null;
    attributes: Record<string, number>;
    derivation_reasons: string[];
    clean_sheets: number;
    yellow_cards: number;
    red_cards: number;
    summary: string;
  };
  season_stats: {
    season: string;
    appearances: number;
    starts: number;
    minutes: number;
    goals: number;
    assists: number;
    clean_sheets: number;
    yellow_cards: number;
    red_cards: number;
    rating: number;
    stored_from: string;
    matches_stored: number;
    consistency_check: string;
  };
  recent_form: {
    match_id: string;
    match_slug: string;
    match_path: string;
    kickoff_at: string | null;
    role: string;
    position: string;
    minutes: number;
    goals: number;
    assists: number;
    rating: number;
  }[];
  stat_lines: StatLine[];
  method: Record<string, string>;
};

export type MatchDetail = WorldEnvelope & {
  match: MatchBrief & { stats: MatchStats; competition: CompetitionBrief | null };
  line_ups: Record<"home" | "away", { team: TeamBrief | null; starters: StatLine[]; substitutes: StatLine[] }>;
  stat_lines: StatLine[];
  available: boolean;
  note: string | null;
  method: Record<string, string>;
  goals_check: { match_goals: number; line_up_goals: number };
};

export type NewsDetail = WorldEnvelope & {
  article: NewsRow & { body?: string };
  body: string;
  related: EntityRef[];
  editorial_note: string;
};

/** One ranked result of GET /world/search (spec §56). */
export type WorldSearchHit = WorldEnvelope & {
  type: string;
  slug: string;
  id: string;
  title: string;
  subtitle: string;
  score: number;
  path: string;
  reasons: string[];
};

export type WorldSearchResponse = WorldEnvelope & {
  query: string;
  results: WorldSearchHit[];
  total: number;
  types: string[];
  note: string;
};

/* ---------------------------------------------------------------------------
 * M4 Tactical Lab — GET /api/v1/tactics/* (spec §11–§13, §62, §65, §80).
 *
 * These rows are `project-authored`, not synthetic: the coordinates are a design
 * artefact of this repository and every figure is measured from them, which is why
 * `is_demo_data` is false here and the disclaimer talks about measurement instead of
 * invention. The board is stored as data, so the shapes below mirror `Role.to_dict`
 * and `Metric.to_dict` from the API rather than restating them.
 * ------------------------------------------------------------------------- */

export type BoardSlot = { role: string; label: string; band: string; x: number; y: number; zone: string };

export type BoardMetric = { key: string; label: string; value: number; unit: string; formula: string };

export type RoleCard = {
  key: string;
  label: string;
  band: string;
  in_possession: string;
  out_of_possession: string;
  instructions: string[];
  demands: Record<string, number>;
  risk: string;
};

export type ChangeCard = { key: string; label: string; note: string; phase: string; target: string[] };

export type TacticsStatus = TacticsProvenance & {
  ready: boolean;
  counts: Record<string, number>;
  gate: Record<string, number>;
  stored: number;
  catalogue_fingerprint: string;
  formations: string[];
  temperaments: string[];
  metrics: BoardMetric[];
  metric_keys: string[];
  changes: ChangeCard[];
  auto_sync: boolean;
  units: Record<string, string>;
  note: string;
};

/** The API's provenance trio for this dataset — authored content, so `is_demo_data` is false. */
export type TacticsProvenance = { data_origin: string; is_demo_data: boolean; disclaimer: string };

export type SystemBrief = TacticsProvenance & {
  id: string;
  slug: string;
  path: string;
  name: string;
  formation: string;
  temperament_key: string;
  temperament_label: string;
  idea: string;
  press_line_y: number;
  block_depth: number;
  content_hash: string;
  in_possession: Record<string, number>;
  out_of_possession: Record<string, number>;
  strengths: string[];
  risks: string[];
};

export type SystemList = TacticsProvenance & {
  items: SystemBrief[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
  formations: string[];
  temperaments: string[];
};

export type SystemDetail = TacticsProvenance & {
  id: string;
  slug: string;
  path: string;
  name: string;
  formation: string;
  temperament_key: string;
  temperament_label: string;
  idea: string;
  press_line_y: number;
  block_depth: number;
  defensive_narrowing: number;
  content_hash: string;
  build_up: string;
  tempo: string;
  pressing_trigger: string;
  width_note: string;
  instructions: string[];
  demands: Record<string, number>;
  strengths: string[];
  risks: string[];
  phase_in: BoardSlot[];
  phase_out: BoardSlot[];
  metrics_in: BoardMetric[];
  metrics_out: BoardMetric[];
  roles: RoleCard[];
  counterfactuals: ChangeCard[];
  changes: ChangeCard[];
  transform_note: string;
};

export type CounterfactualMetric = {
  key: string;
  label: string;
  unit: string;
  formula: string;
  before: number;
  after: number;
  delta: number;
  moved: boolean;
};

export type CounterfactualResponse = TacticsProvenance & {
  system: SystemBrief;
  change: ChangeCard;
  phase: string;
  board_before: BoardSlot[];
  board_after: BoardSlot[];
  metrics: CounterfactualMetric[];
  moved_count: number;
  clamped: { role: string; asked: { x: number; y: number }; placed: { x: number; y: number } }[];
  recomputed: boolean;
  note: string;
};

export type CompareMetricRow = {
  key: string;
  label: string;
  unit: string;
  formula: string;
  a: number;
  b: number;
  delta: number;
};

export type CompareResponse = TacticsProvenance & {
  a: SystemBrief;
  b: SystemBrief;
  phase: string;
  metrics: CompareMetricRow[];
  note: string;
};
