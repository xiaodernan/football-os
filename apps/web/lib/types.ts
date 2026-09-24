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

/** One demo-world training session: `GET /world/training`, spec §65's 100 Training Sessions. */
export type WorldTrainingRow = {
  id: string;
  player_slug: string;
  player_name: string;
  player_path: string;
  position: string;
  season: string;
  date: string;
  drill_slug: string;
  drill_title: string;
  drill_path: string;
  category: string;
  difficulty: number;
  duration_min: number;
  rpe: number;
  load_units: number;
  status: string;
  summary: string;
};

/** Totals the API computes from the rows it is serving, never stores beside them. */
export type WorldTrainingTotals = {
  sessions: number;
  total_minutes: number;
  total_load: number;
  categories: string[];
  drills: string[];
  load_formula: string;
  mean_rpe: number;
};

export type WorldTrainingList = WorldPage<WorldTrainingRow> & {
  filters: { player: string | null; team: string | null; category: string | null; season: string | null };
  categories: string[];
  page_totals: WorldTrainingTotals;
  gate: Record<string, number>;
};

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

/* ---------------------------------------------------------------------------
 * M4 user boards — GET/POST/PATCH /api/v1/boards/* (spec §13, §21, §61).
 * Coordinates are the account's own (`data_origin: 'user'`), and the metrics are
 * recomputed by the API from whatever it has stored, which is why the editor
 * shows server numbers only and says when they are stale.
 * ------------------------------------------------------------------------- */

export type BoardPositions = { role: string; label?: string; band: string; x: number; y: number; zone?: string };

export type BoardMetrics = { key: string; label: string; value: number; unit: string; formula: string };

export type BoardDetail = TacticsProvenance & {
  id: string;
  slug: string;
  name: string;
  note: string;
  origin_system: string | null;
  visibility: string;
  path: string;
  phase_in: BoardPositions[];
  phase_out: BoardPositions[];
  metrics_in: BoardMetrics[];
  metrics_out: BoardMetrics[];
  roles: RoleCard[];
  updated_at: string | null;
  shared_at?: string | null;
  share_url?: string | null;
};

export type BoardList = TacticsProvenance & {
  items: BoardDetail[];
  total: number;
  limit_per_user: number;
};

/** `GET /boards/shared/{token}` — a public read that names no owner. */
export type SharedBoard = BoardDetail & { owner: { name: string; id: string | null } };

/* ---------------------------------------------------------------------------
 * M5 Video Analysis — /api/v1/video/* (spec §14, §47, §61, §62).
 *
 * An asset row is `data_origin: 'user'` and never public; its detections are
 * `demo_mode: true` measurements of pixels. The two labels are different and the
 * types keep them apart on purpose.
 * ------------------------------------------------------------------------- */

export type VideoAssetSummary = {
  id: string;
  title: string;
  filename: string;
  status: string;
  duration_s: number;
  width: number;
  height: number;
  size_bytes: number;
  content_type: string;
  frame_count: number;
  created_at: string | null;
  data_origin: string;
  is_demo_data: boolean;
};

export type VideoList = {
  items: VideoAssetSummary[];
  page: number;
  page_size: number;
  total: number;
  pages: number;
  limit_per_user: number;
  privacy: string;
};

export type VideoDetection = {
  id: string;
  kind: string;
  t_s: number;
  x: number;
  y: number;
  confidence: number;
  why: string;
  provider: string;
  model: string;
  demo_mode: boolean;
};

export type VideoStage = { name: string; status: string; progress: number; detail: Record<string, unknown>; ms: number };

export type VideoReport = {
  asset: VideoAssetSummary & {
    status: string;
    fps: number;
    codec: string;
    bitrate_kbps: number;
    frame_interval_s: number;
    sha256: string;
    error: string | null;
  };
  job: { id: string; type: string; status: string; progress: number; error: string | null; result: Record<string, unknown> | null } | null;
  stages: VideoStage[];
  detections: VideoDetection[];
  analysis: {
    provider: string;
    model: string;
    demo_mode: boolean;
    task: string;
    frames_seen: number;
    grid?: number[];
    thresholds?: Record<string, number>;
    samples?: Record<string, unknown>[];
    events?: Record<string, unknown>[];
    green_fraction_mean?: number;
    limitations: string;
    error?: string;
  } | null;
  failure: string | null;
  privacy: string;
  disclaimer: string;
};

/** A passage reference from the knowledge corpus. `ref` is an in-app anchor, never a remote URL. */
export type KnowledgeRef = {
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
  ref: string;
};

/** `GET /tactics/{slug}/feedback` — statements that each carry a resolvable citation, plus the refusals. */
export type FeedbackResponse = TacticsProvenance & {
  system: { slug: string; name: string; formation: string; temperament_key: string; idea?: string; strengths: string[]; risks: string[] };
  points: {
    topic: string;
    label: string;
    statement: string;
    metric: { key: string; value: number; unit: string; formula: string; phase: string };
    citation: KnowledgeRef;
    score: number;
  }[];
  ungrounded: {
    topic: string;
    label: string;
    value?: number;
    unit?: string;
    reason: string;
    answerability?: { answerable: boolean; coverage: number; top_score: number };
  }[];
  reasons: string[];
  citations: KnowledgeRef[];
  retrieval_backend: string;
  scanned_chunks: number;
  demo_mode: boolean;
  provider: string;
  model: string;
  method: string;
};

/* ------------------------------------------------------------------- M6 simulation */

/** One of the engine's own rates: a formula string, and what it reads (spec §19 asks for both). */
export type SimFactor = { key: string; expression: string; reads: string };

/** A measurement that fed a side: value, unit, and the sentence that says how it was obtained. */
export type SimInputFactor = { key: string; label: string; value: number; unit: string; formula: string };

export type SimModel = {
  name: string;
  version: string;
  model_version: string;
  seed: number;
  minutes: number;
  block_minutes: number;
  blocks: number;
  calibration: string;
  coefficients: Record<string, number>;
  factors: SimFactor[];
  what_it_does_not_model: string[];
};

export type SimLineupRow = { player: string; position: string; band: string };

export type SimSide = {
  side: string;
  team_id: string;
  name: string;
  short_name: string;
  formation: string;
  system_slug: string;
  system_name: string;
  goals: number;
  possession_pct: number;
  shots: number;
  shots_on_target: number;
  big_chances: number;
  expected_goals: number;
  passes: number;
  pass_completions: number;
  pass_accuracy_pct: number;
  press_attempts: number;
  turnovers_won: number;
  high_turnovers_won: number;
  transitions: number;
  corners_conceded: number;
  fouls: number;
  yellow_cards: number;
  red_cards: number;
  injuries: number;
  lineup: SimLineupRow[];
  indices: Record<string, number>;
  inputs: { tactics: Record<string, number>; factors: SimInputFactor[] };
};

export type SimEvent = {
  minute: number;
  type: string;
  side: string;
  team: string;
  player: string;
  position?: string;
  chance?: string;
  expected_goals?: number;
  detail: string;
  score?: string;
  from_press?: boolean;
};

/** One block's line: the scoreboard plus every multiplier the model applied to it. */
export type SimBlockSide = {
  goals: number;
  expected_goals: number;
  shots: number;
  possession_pct: number;
  cumulative: string;
  attack_term: number;
  stretch: number;
  opponent_opening: number;
  fatigue: number;
  late_space: number;
  man_down_attack: number;
  man_down_concede: number;
  volume: number;
  chance_quality: number;
};

export type SimBlock = { minute_from: number; minute_to: number; home: SimBlockSide; away: SimBlockSide };

export type SimWinner = { side: string; name: string; team_id?: string };

export type SimScore = { home: number; away: number; winner: SimWinner };

export type SimReport = {
  status: string;
  model: SimModel;
  score: SimScore;
  sides: { home: SimSide; away: SimSide };
  totals: Record<string, number>;
  possession_share: { home: number; away: number; formula: string };
  events: SimEvent[];
  blocks: SimBlock[];
  provenance: { data_origin: string; is_demo_data: boolean; disclaimer: string; inputs_are_from: string[] };
  digest: string;
};

export type SimSummary = {
  name: string;
  short_name: string;
  system_name: string;
  formation: string;
  possession_pct: number;
  shots: number;
  shots_on_target: number;
  expected_goals: number;
};

/**
 * The match's event list as the `sim_events` table answers with it: the same events the report holds,
 * read one row per event, plus the three sentences that say where they came from and how far the names
 * in them can be trusted. Optional because it is the server that decides — a detail from an API that
 * predates the table simply has no rows to answer with.
 */
export type SimTimeline = {
  events: SimEvent[];
  count: number;
  stored_rows: number;
  report_events: number;
  source: string;
  source_note: string;
  consistency: string;
  by_type: Record<string, number>;
  identified: number;
  ambiguous_names: string[];
  unnamed_names: string[];
  formula: string;
  attribution_formula: string;
  disclaimer: string;
  data_origin: string;
  is_demo_data: boolean;
};

/** `GET /simulate` rows carry neither `report` nor `timeline`; `GET /simulate/{ident}` and a fresh play carry both. */
export type SimRow = {
  id: string;
  slug: string;
  path: string;
  model_version: string;
  seed: number;
  minutes: number;
  block_minutes: number;
  home_team_id: string | null;
  away_team_id: string | null;
  home_system: string;
  away_system: string;
  score: { home: number; away: number; winner_side: string };
  digest: string;
  created_at: string | null;
  data_origin: string;
  is_demo_data: boolean;
  disclaimer: string;
  home_summary: SimSummary;
  away_summary: SimSummary;
  report?: SimReport;
  timeline?: SimTimeline;
};

export type SimList = {
  items: SimRow[];
  total: number;
  limit_per_user: number;
  engine: SimEngine;
  data_origin: string;
  disclaimer: string;
};

/** The engine as the API describes it — the same strings a stored report carries. */
export type SimEngine = {
  name: string;
  version: string;
  disclaimer: string;
  calibration: string;
  factors: SimFactor[];
  minute_choices: number[];
  block_minutes: number;
  inputs_are_from: string[];
};

export type SimTeamOption = {
  team_id: string;
  slug: string;
  name: string;
  short_name: string;
  formation: string;
  overall: number;
  squad_size: number;
  path: string;
  data_origin: string;
};

export type SimSystemOption = { slug: string; name: string; formation: string; label: string; path: string };

export type SimOptions = {
  teams: SimTeamOption[];
  systems: SimSystemOption[];
  engine: SimEngine;
  ready: boolean;
  counts: { simulations: number };
  data_origin: string;
  disclaimer: string;
};

/** `GET /simulate/{ident}/replay` — the model's own reproducibility check, answered honestly. */
export type SimReplay = {
  possible: boolean;
  reason?: string;
  stored_digest?: string;
  replayed_digest?: string;
  identical?: boolean;
  stored_score?: SimScore;
  replayed_score?: SimScore;
  model_version?: string;
};

/** --- M6 Career Mode (spec §20). Mirrors `app/services/simulation/career.career_view`. --- */
export type CareerRow = {
  id: string;
  slug: string;
  manager_name: string;
  club_id: string | null;
  club_name: string;
  club_short: string;
  club_path: string | null;
  competition_name: string;
  season: string;
  philosophy: string;
  system_slug: string;
  system_path: string | null;
  budget: number;
  budget_units: string;
  rounds_played: number;
  status: string;
  /** Set when the career was opened from a live challenge (spec §21); empty for an open career. */
  challenge_slug?: string;
  challenge_window?: number;
  data_origin: string;
  is_demo_data: boolean;
};

/** Every figure here is summed from the career's own fixture rows on the request. */
export type CareerRecord = {
  played: number;
  won: number;
  drawn: number;
  lost: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  points_formula: string;
  goal_difference_formula: string;
  unbeaten_run: number;
  form: string[];
};

export type CareerObjective = {
  kind: string;
  label: string;
  target: number;
  actual: number;
  met: boolean;
  formula: string;
};

export type CareerTableRow = {
  position: number;
  club_id: string | null;
  name: string;
  short_name: string;
  played: number;
  goals_for: number;
  goals_against: number;
  goal_difference: number;
  points: number;
  is_career_club: boolean;
};

export type CareerFixtureRow = {
  round_index: number;
  side: "home" | "away";
  opponent_name: string;
  opponent_short: string;
  opponent_path: string;
  venue_name: string;
  club_goals: number;
  opponent_goals: number;
  outcome: "W" | "D" | "L";
  points: number;
  digest: string;
  seed: number;
  model_version: string;
  match_slug: string;
  match_path: string | null;
  match_still_stored: boolean;
};

export type CareerNextFixture = {
  available: boolean;
  reason?: string;
  round_index: number;
  side?: string;
  opponent_name?: string;
  opponent_short?: string;
  venue_name?: string;
  venue_club?: string;
  cycle?: number;
  of?: number;
  rotation?: string;
  seed?: number;
};

export type CareerView = {
  career: CareerRow;
  record: CareerRecord;
  objectives: CareerObjective[];
  table: CareerTableRow[];
  fixtures?: CareerFixtureRow[];
  consistency: string;
  model_versions: string[];
  /** §20: what this career's played rounds left on its players, summed from `career_appearances`. */
  carry_over: import("./carryOver").CarryOverView;
  /** ROADMAP item 10: this season per player, counted off `sim_events`. Absent on a list row or run view. */
  ledger?: import("./ledger").SeasonLedger;
  limitations: { budget: string; wages: string; carry_over: string; ledger: string; philosophy: string; table: string; objectives: string };
  next_fixture?: CareerNextFixture;
  played?: boolean;
  match?: { slug: string; path: string; digest: string; seed: number; model_version: string };
  /** The live verdict, present only when this career was opened from a live challenge (§21). */
  challenge_verdict?: ChallengeVerdict | null;
  status?: string;
  data_origin: string;
  is_demo_data: boolean;
  demo_data: boolean;
  disclaimer: string;
};

export type CareerList = {
  items: (CareerRow & { record: CareerRecord; objectives_met: number; objectives_total: number })[];
  total: number;
  limit_per_user: number;
  data_origin: string;
  is_demo_data: boolean;
  demo_data: boolean;
  disclaimer: string;
};

export type CareerOptions = {
  clubs: SimTeamOption[];
  systems: SimSystemOption[];
  philosophies: string[];
  objective_kinds: Record<string, string>;
  budget_ceiling: number;
  budget_units: string;
  max_careers_per_user: number;
  data_origin: string;
  is_demo_data: boolean;
  disclaimer: string;
};

/**
 * --- M6 Manager live challenges (spec §21). Mirrors `app/services/simulation/challenges`. ---
 *
 * A run is a career played under a scenario, so `ChallengeRunView` extends `CareerView` rather than
 * repeating it: the record, the fixtures and the table are the career's own sums, and the verdict is
 * recomputed from those same rows on every read.
 */
export type ChallengeConstraint = {
  key: string;
  label: string;
  /** The honest field: false means the scenario states the rule and nothing in the build applies it. */
  enforced: boolean;
  how: string;
};

export type ChallengeObjective = {
  kind: string;
  target: number;
  label: string;
};

export type ChallengeReward = {
  key?: string | null;
  label?: string | null;
  credits?: number | null;
  credits_units?: string;
  xp?: number | null;
  earned?: boolean;
  reason?: string;
};

export type ChallengeEntry = {
  slug: string;
  name: string;
  brief: string;
  difficulty: string;
  window_rounds: number;
  window: string;
  club_selector: string;
  philosophy: string;
  budget: number;
  budget_units: string;
  system_slug: string;
  objectives: ChallengeObjective[];
  constraints: ChallengeConstraint[];
  reward: Record<string, unknown>;
};

export type ChallengeClubChoice = {
  selector: string;
  chosen: { team_id: string; name: string; short_name: string; overall?: number };
  competition?: { id: string; slug: string; name: string };
  ranking?: { name: string; overall: number | null; measurable: boolean }[];
  gap_to_runner_up?: number | null;
  how: string;
};

export type ChallengeVerdict = {
  challenge_slug: string;
  challenge_name: string;
  status: "in_progress" | "met" | "missed";
  window_rounds: number;
  rounds_played: number;
  rounds_remaining: number;
  window_closed: boolean;
  objectives: (ChallengeObjective & { actual: number; met: boolean; formula: string })[];
  objectives_met: number;
  objectives_total: number;
  reward: ChallengeReward;
  judged_on: string;
  closed_by: string;
};

export type ChallengeCatalogue = {
  challenges: ChallengeEntry[];
  total: number;
  fingerprint: string;
  integrity: { problems: string[]; clean: boolean };
  objective_formulas: Record<string, string>;
  verdict_statuses: string[];
  how_a_verdict_is_decided: string;
  window_enforced_by: string;
  play_through: string;
  clubs: SimTeamOption[];
  competitions: { id: string; slug: string; name: string; kind: string; tier: number; season: string; clubs: number; path: string }[];
  systems: SimSystemOption[];
  reward_units: string;
  max_runs_per_user: number;
  limitations: Record<string, string>;
  data_origin: string;
  is_demo_data: boolean;
  demo_data: boolean;
  disclaimer: string;
};

export type ChallengeRunView = Omit<CareerView, "limitations"> & {
  /** The career's own limitations, plus the four the challenge layer adds on every read. */
  limitations: CareerView["limitations"] & Partial<Record<"window" | "reward" | "constraints" | "club", string>>;
  challenge?: ChallengeEntry | null;
  verdict?: ChallengeVerdict | null;
  run?: {
    id: string;
    slug: string;
    challenge_slug: string;
    challenge_window: number;
    scenario_known: boolean;
    fingerprint?: string;
    note?: string;
  };
  club_choice?: ChallengeClubChoice;
};

export type ChallengeRunList = {
  items: {
    id: string;
    slug: string;
    challenge_slug: string;
    challenge_name: string;
    club_name: string;
    season: string;
    rounds_played: number;
    verdict: ChallengeVerdict | null;
  }[];
  total: number;
  limit_per_user: number;
  verdict_statuses: string[];
  limitations: Record<string, string>;
  data_origin: string;
  is_demo_data: boolean;
  demo_data: boolean;
  disclaimer: string;
};
