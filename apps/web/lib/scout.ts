/**
 * The §23–§27 scouting shapes, as `POST /api/v1/scout/{parse,search,report,compare}` answer them.
 *
 * Every field below was read off a live response from the running API rather than from the service module's
 * return statement — a page typed against a shape the route never sends is how a user-visible lie survives a
 * green test file. A field appears because the API sends it; the sentences that explain a figure (`rule`,
 * `formula`, `note`, `source`) are part of the payload, so the page quotes them instead of paraphrasing the
 * arithmetic in the browser.
 */

export type ScoutRequirement = {
  kind: string;
  field?: string;
  value?: string | number | string[];
  phrase: string;
  rule: string;
  source: string;
};

/** What the parser could not read: the phrase, why, and the catalogue entries that came closest. */
export type ScoutRefusal = {
  phrase: string;
  code: string;
  message: string;
  suggestions: string[];
};

export type ParseView = {
  query: string;
  request: string;
  requirements: ScoutRequirement[];
  filters_applied: number;
  sort: string | null;
  refused: ScoutRefusal[];
  assumptions: string[];
  connectors_ignored: string[];
  unaccounted: string[];
  rule: string;
  search_would_apply: number;
  search_would_rank_by: string | null;
  note: string;
  data_origin: string;
  is_demo_data: boolean;
};

/** One filter's place in the waterfall: how many rows entered, how many the cut removed. */
export type WaterfallStep = {
  kind: string;
  field: string;
  phrase: string;
  rows_in: number;
  rows_out: number;
  cut: number;
  rule: string;
  source: string;
  example_of_a_row_dropped?: Record<string, number | string>;
};

/** How one stored row answers one requirement — printed per candidate so a match is checkable. */
export type CandidateAnswer = {
  phrase: string;
  kind: string;
  [figure: string]: string | number | string[];
};

export type Candidate = {
  slug: string;
  name: string;
  path: string;
  age: number;
  position: string;
  positions: string[];
  band: string;
  preferred_foot: string;
  overall: number;
  potential: number;
  headroom: number;
  archetype: string;
  /** Only the keys the role fit or a stated floor spoke about, not all twenty-seven. */
  attributes: Record<string, number>;
  club: { name: string; slug: string; path: string } | null;
  observed: boolean;
  season: { appearances: number; minutes: number; goals: number; assists: number; rating: number };
  valuation: {
    asking_fee: number;
    release_clause: number;
    weekly_wage: number;
    contract_years: number;
    quality_points: number;
    headroom_points: number;
    age_curve: number;
  };
  value_for_money: number;
  tactical_fit: number | null;
  role_fit: RoleFit | null;
  answers: CandidateAnswer[];
  data_origin: string;
  is_demo_data: boolean;
};

export type SearchView = {
  query: string | null;
  requirements: ScoutRequirement[];
  filters_applied: number;
  waterfall: WaterfallStep[];
  waterfall_rule: string;
  world: { players_stored: number; players_at_a_club: number; players_with_no_club: number; clubs_stored: number; rule: string };
  rows_examined: number;
  sort: { key: string; formula: string; applied_to: number; career_dependent: boolean };
  candidates: Candidate[];
  returned: number;
  total_matches: number;
  truncated: boolean;
  limit: number;
  max_limit: number;
  refused: ScoutRefusal[];
  assumptions: string[];
  connectors_ignored: string[];
  unaccounted: string[];
  need: Record<string, unknown> | null;
  career: Record<string, unknown> | null;
  duplicate_fields: { kind: string; phrases: string[]; rule: string }[];
  suggestion_formula: string;
  match_rule: string;
  observed_rule: string;
  valuation_note: string;
  scan_note: string;
  limitations: string[];
  rules: Record<string, string>;
  data_origin: string;
  is_demo_data: boolean;
  disclaimer: string;
  demo_data: boolean;
  asked_for: { query: string | null; stated: Record<string, unknown> | null; career: string | null; limit: number };
};

export type GroupScore = {
  group: string;
  attributes: Record<string, number>;
  mean: number;
  strongest: string;
  weakest: string;
  measured: number;
  missing: string[];
  rule: string;
};

export type RoleFitRow = { attribute: string; demanded: number; have: number; gap: number; verdict: string; rule: string };

/** §23's role fit, which §24's report prints through the same function, so both share one shape here. */
export type RoleFit = {
  role: string;
  label: string;
  board_band: string;
  occupiable_by: string[];
  risk: string;
  rows: RoleFitRow[];
  mean_gap: number;
  covered_attributes: number;
  shortfalls: string[];
  verdict: string;
  formula: string;
};

export type RiskFactor = { factor: string; value: number | string; rule: string };

export type ReportView = {
  player: {
    slug: string;
    name: string;
    path: string;
    age: number;
    position: string;
    positions: string[];
    band: string;
    preferred_foot: string;
    club: { name: string; slug: string; path: string } | null;
    observed: boolean;
  };
  current_level: {
    overall: number;
    players_in_pool: number;
    at_or_below: number;
    share_of_pool: number;
    band: string;
    players_in_band: number;
    share_of_band: number;
    recomputed: number;
    agrees_with_stored: boolean;
    archetype: string;
    archetype_match: number;
    rule: string;
  };
  potential: { potential: number; overall: number; headroom: number; age: number; age_curve: number; peak_age_end: number; years_past_peak: number; rule: string };
  technical: GroupScore;
  physical: GroupScore;
  mental: GroupScore;
  tactical: GroupScore;
  role_fit: RoleFit | null;
  team_fit: {
    career: string;
    club: { name: string; id: string };
    needed_band: string;
    bands: Record<string, number>;
    positions_in_band: string[];
    fit: number;
    formula: string;
    club_stores_in_band: number;
    candidate_already_lists_there: boolean;
    rule: string;
  } | null;
  risk: RiskFactor[];
  cost: {
    asking_fee: number;
    weekly_wage: number;
    season_wage: number;
    wage_share_of_fee: number;
    release_clause: number;
    contract_years: number;
    value_for_money: number;
    components: Record<string, number>;
    formula: string;
    note: string;
    against_career_budget?: { budget: number; units: string; share_of_budget: number | null; fits_without_selling: boolean; rule: string };
  };
  comparison: {
    other: { slug: string; name: string; overall: number; path: string };
    groups: Record<string, number>;
    overall: number;
    headroom: number;
    asking_fee: number;
    value_for_money: number;
    rule: string;
  } | null;
  recommendation: { verdict: string; decided_by: string[]; risk_factors_named: number; rule: string; note: string };
  fields: string[];
  world: { players_stored: number; players_at_a_club: number; players_with_no_club: number; clubs_stored: number; rule: string };
  groups: Record<string, string[]>;
  limitations: string[];
  data_origin: string;
  is_demo_data: boolean;
  asked_for: { player: string; role: string | null; career: string | null; compare_to: string | null; round_index: number | null };
  demo_data: boolean;
};

/** §27: one printed comparison. A `direction: none` measure has no leader and no delta, by design. */
export type Measure = {
  key: string;
  left: number | string | null;
  right: number | string | null;
  delta: number | null;
  direction: "higher_is_greater" | "lower_is_greater" | "none";
  leader: "left" | "right" | "even" | "unknown" | "not_scorable";
  source: string;
  unit?: string;
  note?: string;
  missing?: string[];
  unobserved?: string[];
};

export type CompareDimension = {
  dimension: string;
  source: string;
  counts: Record<string, number>;
  leader: "left" | "right" | "even" | "split" | "unresolved";
  measures: Measure[];
  rule: string;
  note?: string;
};

export type CompareSide = {
  slug: string;
  name: string;
  path: string;
  age: number;
  position: string;
  positions: string[];
  band: string;
  overall: number;
  potential: number;
  asking_fee: number;
  club: { name: string; slug: string; path: string; overall: number } | null;
  competition: { name: string; tier: number; slug: string } | null;
  observed: boolean;
  stat_lines: number;
  minutes_in_lines: number;
};

export type CompareView = {
  left: CompareSide;
  right: CompareSide;
  dimensions: CompareDimension[];
  overall_line: { left: number; right: number; delta: number; note: string };
  counts: {
    dimensions: number;
    measures: number;
    by_leader: Record<string, number>;
    dimension_leaders: Record<string, number>;
  };
  totals_check: {
    left: TotalsCheck;
    right: TotalsCheck;
    rule: string;
  };
  dimensions_list: string[];
  no_single_score: string;
  measure_rule: string;
  world: { players_stored: number; players_at_a_club: number; players_with_no_club: number; clubs_stored: number; rule: string };
  limitations: string[];
  data_origin: string;
  is_demo_data: boolean;
  asked_for: { left: string; right: string };
  demo_data: boolean;
};

export type TotalsCheck = {
  slug: string;
  stored_minutes: number;
  lines_minutes: number;
  stored_goals: number;
  lines_goals: number;
  stored_appearances: number;
  lines: number;
  agree: boolean;
};

/** The public `GET /api/v1/scout/rules` payload, only as far as this page reads it. */
export type ScoutRulesView = {
  positions: Record<string, { label: string; band: string; aliases: string[] }>;
  positions_the_engine_names_and_the_world_does_not_staff: string[];
  roles: Record<string, { label: string; board_band: string; occupiable_by: string[]; demands: Record<string, number>; risk: string }>;
  band_vocabularies: Record<string, { keys: string[]; used_by: string; meaning: string }>;
  roles_no_stored_position_occupies: string[];
  role_names_that_read_as_a_position: string[];
  bands: Record<string, { codes: string[]; aliases: string[] }>;
  band_names_that_read_as_a_position: string[];
  feet: string[];
  attributes: string[];
  sorts: string[];
  fields: string[];
  rules: Record<string, string>;
  connectors_ignored: string[];
  example: { request: string; what_happens: string };
  data_origin: string;
  is_demo_data: boolean;
  disclaimer: string;
  integrity: { problems: string[]; clean: boolean; ready: boolean; counts: Record<string, unknown> };
  search: {
    default_limit: number;
    max_limit: number;
    sorts: string[];
    limits: string[];
    world: Record<string, unknown>;
    positions_stored: string[];
    positions_the_engine_names_and_the_world_does_not_staff: string[];
    roles_occupiable_by_a_stored_position: Record<string, string[]>;
  };
  connector_count: number;
  report: { fields: string[]; companion_fields: string[]; verdicts: string[]; ready: boolean; counts: Record<string, unknown>; limitations: string[]; refusals: Record<string, string>; note: string };
  comparison: {
    dimensions: string[];
    ready: boolean;
    stat_columns: string[];
    no_single_score: string;
    measure_leaders: string[];
    dimension_leaders: string[];
    counts: Record<string, unknown>;
    limitations: string[];
    refusals: Record<string, string>;
    note: string;
  };
  example_parse: Record<string, unknown>;
  shortlists: ShortlistRulesBlock;
  transfer_simulation: SimRulesBlock;
  routes: Record<string, string>;
};

/** The house label for a leader, so a page never invents its own translation of `split`. */
export const LEADER_LABELS: Record<string, string> = {  left: "left",
  right: "right",
  even: "even",
  split: "split",
  unresolved: "unresolved",
  unknown: "unknown",
  not_scorable: "not scorable",
};

export function leaderTone(leader: string): "live" | "demo" {
  return leader === "split" || leader === "unresolved" || leader === "unknown" || leader === "not_scorable" ? "demo" : "live";
}

export function money(value: number): string {
  return value.toLocaleString("en-GB");
}

/** A figure the API printed as `null` stays `null` on screen; only a real number is dressed up as one. */
export function figure(value: number | string | null | undefined): string {
  return value === null || value === undefined ? "—" : String(value);
}

/**
 * §23's shortlist, as `GET|POST /api/v1/scout/shortlists` and its item routes return it.
 *
 * The types below are only as wide as the API's own answers, and one of the API's answers is worth saying out
 * loud here because it shapes this half of the screen: a list row stores a name, a sentence, an optional role
 * and career link, and which players are on it. Every figure a list prints arrives inside `player` — the same
 * candidate projection `POST /scout/search` returns — so a page has nothing to recompute and nothing to
 * remember from the last read.
 */
export type ShortlistRules = {
  max_shortlists_per_user: number;
  max_items_per_shortlist: number;
  name_max: number;
  note_max: number;
  query_max: number;
  stored: string;
  not_stored: string;
  why_not: string;
  rechecked_on_read: string;
  position: string;
  visibility: string;
  rule: string;
  codes: string[];
};

/**
 * What `GET /api/v1/scout/rules` publishes about the tier is the same block with two things added: the
 * limitations, and the eight codes a client has to branch on written out as sentences. A single list's read
 * echoes the plain block, so the wider shape is its own type rather than optional fields on the narrow one.
 */
export type ShortlistRulesBlock = ShortlistRules & { limitations: string[]; refusals: Record<string, string> };

/** One of the account's lists, as the list route prints it: words, counts of membership, and room left. */
export type ShortlistRow = {
  id: string;
  name: string;
  query: string;
  role: string;
  career_id: string | null;
  career: string | null;
  created_at: string | null;
  updated_at: string | null;
  stored: string[];
  not_stored: string;
  players_listed: number;
  room_left: number;
};

export type ShortlistList = {
  items: ShortlistRow[];
  total: number;
  limit: number;
  items_limit: number;
  room_left: number;
  rule: string;
  integrity: { clean: boolean; problems: string[]; checked: { shortlists: number; membership_rows: number; players_in_pool: number }; rule: string };
  demo_data: boolean;
};

/** The stored sentence, parsed and applied again to one member on this very request. */
export type ShortlistRecheck = {
  asked: string | null;
  answers: { phrase: string; kind: string }[];
  no_longer_answers: { phrase: string; kind: string }[];
  refused?: { phrase: string; code: string; message: string }[];
  unaccounted?: string[];
  filters_applied: number;
  note: string;
};

export type ShortlistItem = {
  position: number;
  note: string;
  added_at: string | null;
  player: Candidate;
  recheck: ShortlistRecheck;
};

/** The career's own need, in §22's words — printed beside a list that was opened against a career. */
export type ShortlistNeed = {
  needed_band?: string;
  bands?: Record<string, number>;
  positions_in_band?: string[];
  judged_on?: string[];
  formation?: string;
  system_slug?: string;
  refused?: { code: string; message: string };
};

export type ShortlistView = {
  shortlist: ShortlistRow;
  career: { slug: string; club_name: string; rounds_played: number } | null;
  need: ShortlistNeed | null;
  items: ShortlistItem[];
  gone_from_the_world: { player_id: string; position: number; note: string }[];
  counts: { membership_rows: number; printed: number; answered_everything: number; answered_nothing: number; no_sentence_to_answer: number };
  room_left: number;
  figures_from: string;
  rules: ShortlistRules;
  limitations: string[];
  data_origin: string;
  is_demo_data: boolean;
  account_content: string;
  disclaimer: string;
  demo_data: boolean;
};

/** What the list routes answer with when they refuse: the code, the sentence, and the figures behind it. */
export type ShortlistRefusal = { code?: string; message?: string; held?: number; limit?: number; length?: number; max?: number; name?: string; player?: string; ident?: string; shortlist?: string; listed?: string[]; career?: string };

/**
 * M7's transfer simulation, as `POST /api/v1/scout/simulate-transfer` returns it.
 *
 * The shapes below exist because the route's answer is a projection with evidence attached to it: every round
 * carries the seed it was replayed at and the digest the engine produced, so the two lines of a round can be
 * compared by a reader rather than trusted. Nothing here is computed in the browser — the page prints the
 * figures the route printed, beside the formulas the route printed with them.
 */
export type SimLine = { seed: number; for: number; against: number; outcome: string; possession: number; digest: string };

export type SimRound = {
  round_index: number;
  side: string;
  opponent: string;
  venue: string;
  seed: number;
  same_seed: boolean;
  without: SimLine;
  with_signing: SimLine;
};

export type SimTotals = { goals: number; against: number; points: number };

export type SimProjection = {
  rounds_asked: number;
  rounds_projected: number;
  rounds: SimRound[];
  totals: { without: SimTotals; with_signing: SimTotals };
  points_delta: number;
  goals_for_delta: number;
  goals_against_delta: number;
  better: number;
  same: number;
  worse: number;
  stopped_at: { round_index: number; reason: string } | null;
  rule: string;
  one_sample: string;
};

export type SimCost = {
  asking_fee: number;
  release_clause: number;
  weekly_wage: number;
  season_wage: number;
  contract_years: number;
  units: string;
  remaining_now: number;
  affordable_by_fee: boolean;
  headroom_after_fee: number;
  wage_committed_per_week: number;
  wage_after_this_player_per_week: number;
  season_wage_after: number;
  rounds_the_wage_bills_for: number;
  budget_formula: string;
  valuation_note: string;
  note: string;
};

export type SimElevenRow = { player_id: string; slug: string; name: string; position: string; band: string };

export type SimSide = {
  before: { indices: Record<string, number>; eleven: SimElevenRow[] };
  after: { indices: Record<string, number>; eleven: SimElevenRow[] };
  indices_delta: Record<string, number>;
  comes_in: SimElevenRow[];
  goes_out: SimElevenRow[];
  eleven_unchanged: boolean;
  rule: string;
};

export type SimPlayer = {
  slug: string;
  name: string;
  path: string;
  age: number;
  position: string;
  positions: string[];
  band: string;
  preferred_foot: string;
  overall: number;
  potential: number;
  headroom: number;
  archetype: string;
  from_club: { name: string; slug: string; path: string } | null;
  season: { appearances: number; minutes: number; goals: number; assists: number; rating: number } | null;
  observed: boolean;
};

export type SimRules = {
  default_rounds: number;
  max_rounds: number;
  writes: string;
  price_from: string;
  side_from: string;
  fixtures_from: string;
  seed_rule: string;
  refusals: string[];
};

/** The `/scout/rules` block adds the explanations and the live counts to the same shape. */
export type SimRulesBlock = SimRules & {
  ready: boolean;
  counts: { players_in_pool: number; careers_stored: number; default_rounds: number; max_rounds: number; rows_written_by_a_simulation: number; rule: string };
  limitations: string[];
  refusals: Record<string, string>;
  note: string;
};

export type TransferSimView = {
  career: { slug: string; club_name: string; club_id: string; rounds_played: number; system_slug: string; formation: string; challenge_slug: string; window: number | null },
  player: SimPlayer,
  need: { needed_band: string; this_player_fills_it: boolean; bands: Record<string, number>; positions_in_band: string[]; judged_on: string[]; formation: string; as_of_round: number; rule: string },
  fit: { fit: number; formula: string } & Record<string, unknown>,
  cost: SimCost,
  squad: { size_before: number; size_after: number; fielding_before: Record<string, unknown>; fielding_after: Record<string, unknown>; rule: string },
  side: SimSide,
  projection: SimProjection,
  what_this_does_not_do: string[],
  rules: SimRules,
  limitations: string[],
  data_origin: string;
  is_demo_data: boolean;
  disclaimer: string;
  demo_data: boolean;
  asked_for: { career: string; player: string; rounds: number };
};

/** The index names the side block reports, in the order a reader expects them. */
export const SIM_INDEX_ORDER: string[] = ["attack", "midfield", "defence", "keeper", "press", "form", "overall"];
