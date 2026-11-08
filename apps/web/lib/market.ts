/**
 * The §22 transfer market's own response shapes, as `GET /api/v1/transfers/{career}` returns them.
 *
 * A field appears here only because the API sends it: every figure below is one the service layer
 * computed from stored rows and published with the expression beside it, so the page has nothing to
 * invent and nothing to re-derive in the browser.
 */

import type { CareerStadium, CareerTickets, SigningImpact } from "./types";

export type MarketCareer = {
  slug: string;
  club_name: string;
  club_id: string | null;
  competition_name: string | null;
  season: string;
  rounds_played: number;
  market_round: number;
  status: string;
  challenge_slug: string | null;
};

export type Transferable = {
  ok: boolean;
  code: string;
  message: string;
  constraint: string;
  rounds_played?: number;
  window_rounds?: number;
  challenge_slug?: string;
  enforced?: boolean;
  enforced_by?: string;
};

/**
 * One of a season's signing windows, as `season_windows()` clips it to the season and merges it with its
 * neighbour when the two ranges touch. The round numbers are *rounds of the season being judged*, not of the
 * career: `transfer_window` re-dates them through `season_index` when a career has played past its first season.
 */
export type MarketSigningWindow = { from_round: number; to_round: number; label: string };

/**
 * Where this career's next round falls against its season's signing windows — the block `GET /transfers/{career}`
 * answers with as `window`, and the same arithmetic `POST` refusals are built from.
 *
 * A career whose season board publishes no length has no window to police: that branch answers `state: "open"`
 * with an empty `windows` list, so the block always carries this whole shape — the four range-measured fields
 * included, at zero and null rather than missing — and never a smaller one.
 */
export type MarketWindow = {
  /** `open` or `closed`, for whether a deal could be struck in the round the next one would be made in. */
  state: "open" | "closed";
  round: number;
  round_in_season: number;
  season_index: number;
  season_rounds: number;
  /** Which table the season length came from, so a reader can tell a stored competition from a fallback. */
  season_source: string;
  windows: MarketSigningWindow[];
  /** The label of the range holding this round, or empty when none does. */
  in_window: string;
  /** The bounds of the range holding this round; both null when the window is closed. */
  window_from_round: number | null;
  window_to_round: number | null;
  /** Rounds of the holding range already stored, and the rounds it can still sign in, this one included. */
  played_in_window: number;
  signing_rounds_left: number;
  opens_at_round: number | null;
  opens_at_season: number | null;
  opens_in_rounds: number;
  formula: string;
};

export type MarketNeed = {
  needed_band: string;
  bands: Record<string, number>;
  positions_in_band: string[];
  judged_on: string[];
  formation: string;
  system_slug: string;
  squad_applied: string;
  formula: string;
};

export type MarketBudget = {
  budget: number;
  spent: number;
  /** Every cent that arrived: sales plus home gates. `received_sales` and `received_gate` split it. */
  received: number;
  received_sales: number;
  received_gate: number;
  gate_rows: number;
  /** One clause per home round, `round N: amount`, so the gate sum can be read as its own rows. */
  gate_detail: string;
  /** What the board has paid for the seasons this career closed — the sum of its `career_budget_awards` rows. */
  granted: number;
  grant_rows: number;
  /** One clause per paid season, `season N: amount`, so the sum above can be read as its own rows. */
  grant_detail: string;
  /** What met objectives have paid (M13 Phase 9 item 36) — the board's other income, beside the grant. */
  received_objectives: number;
  objective_rows: number;
  /** One clause per paid objective, `season N <kind>: amount`, so the sum can be read as its own rows. */
  objective_detail: string;
  /** What the rounds already played have cost in wages — a sum of `career_wage_charges` rows. */
  wages_paid: number;
  /** What stands have cost (M13 Phase 9 item 37), the ledger's other spending row. */
  stadium_spent: number;
  stadium_rows: number;
  stadium_detail: string;
  /** What running the ground has cost so far (M13 Phase 10 item 45). */
  upkeep_spent: number;
  upkeep_rows: number;
  upkeep_detail: string;
  remaining: number;
  units: string;
  moves: number;
  wage_rows: number;
  wage_rounds: number[];
  /** The standing rate: what the next round would cost with the deals held right now. */
  wage_committed_per_week: number;
  wage_players: number;
  wage_detail: string;
  wage_note: string;
  formula: string;
};

export type SquadAccount = {
  club_id: string | null;
  club_name: string;
  as_of_round: number;
  stored_in_world: number;
  signed_in: number;
  departed: number;
  moves: number;
  squad_now: number;
  keepers: number;
  rule: string;
};

export type Fielding = {
  ok: boolean;
  players: number;
  keepers: number;
  needs_players: number;
  needs_keepers: number;
  rule: string;
};

export type SquadPlayer = {
  player_id: string;
  slug: string;
  name: string;
  position: string;
  band: string;
  age: number;
  overall: number;
  potential: number;
  asking_fee: number;
  sell_proceeds: number;
  weekly_wage: number;
  contract_years: number;
  player_path: string;
};

export type Listing = {
  id: string;
  player_id: string;
  player_slug: string;
  player_name: string;
  player_path: string;
  position: string;
  band: string;
  age: number;
  overall: number;
  potential: number;
  from_team_id: string | null;
  from_team_name: string | null;
  from_team_path: string | null;
  asking_fee: number;
  current_price: number;
  release_clause: number;
  weekly_wage: number;
  contract_years: number;
  tactical_fit: number;
  needed_band: string;
  status: string;
  listed_round: number;
  negotiations: number;
  attempts_left: number;
  last_offer: number;
  rival: boolean;
  price_to_pay: number;
  affordable: boolean;
  /** What signing this offer would leave: the same `signing_impact` the career's runway uses. */
  signing: SigningImpact;
  clause_required: boolean;
};

export type Move = {
  id: string;
  round_index: number;
  kind: string;
  /** Which way the *player* moved. A wage row has no player, so it says `out` and means the money. */
  side: "in" | "out";
  /** Which way the *money* moved, which is what signs the fee column. */
  cash: "in" | "out";
  player_id: string;
  player_slug: string | null;
  player_name: string | null;
  player_path: string | null;
  position: string | null;
  fee: number;
  fee_units: string;
  contract_years: number;
  weekly_wage: number;
  loan_until_round: number;
  /** The last round a permanent deal's stored terms name; `0` for a loan or a move without a term. */
  expiry_round: number;
  /** Only a `gate` row carries these: the seats sold and the authored price per seat. */
  attendance?: number;
  ticket_price?: number;
  /** Only a `gate` row carries these: the manager's price setting and the demand it drew. */
  price_pct?: number;
  demand_pct?: number;
  /** Only a `gate` row carries this: the seats already sold for the season, which are not charged again. */
  season_ticket_seats?: number;
  /** Only an `upkeep` row carries these: the seats it opened and the per-seat running rate. */
  capacity?: number;
  seat_rate_pct?: number;
  /** Only a `training` row carries these: the training-ground level it moved between. */
  level_before?: number;
  level_after?: number;
  counterparty_name: string | null;
  budget_after: number;
  effect: string;
  /** A wage row names the players it was raised on; a squad move row has nothing to add. */
  detail: string;
  /** Only a board grant carries these: the season it paid, and how much of it was the promotion bonus. */
  season_index?: number;
  promotion?: number;
  /** Only a cup prize row carries this: the cup stage it was won at. */
  stage?: string;
  /** Only a gate row carries this: the cup tie it was paid on. */
  tie_id?: string;
  /** Only a gate row carries this: the competition it was paid in. */
  competition?: string;
  /** Where the row's data came from: the simulation's own provenance metadata. */
  data_origin: string;
  /** Whether the row is demo data, carried on every ledger row. */
  is_demo_data: boolean;
  created_at: string | null;
};

export type NegotiationResult = {
  outcome: "accepted" | "countered" | "rejected";
  offer: number;
  price: number;
  floor: number;
  asking: number;
  attempts: number;
  attempts_left: number;
  player: string;
  seller: string;
  rival: boolean;
  formula: string;
  disclaimer: string;
};

export type ListingReport = {
  round_index: number;
  created: number;
  repriced: number;
  withdrawn: number;
  kept_signed: number;
  negotiation_note: string;
} & SquadAccount;

export type MarketView = {
  career: MarketCareer;
  transfers_allowed: Transferable;
  window: MarketWindow;
  market: { round_index: number; opened: boolean; size: number; note: string };
  need: MarketNeed;
  budget: MarketBudget;
  /** The ground, what another seat costs and what has already been bought. */
  stadium: CareerStadium;
  /** The gate price the manager set and the demand it draws (M13 Phase 10 item 44). */
  tickets: CareerTickets;
  squad: { account: SquadAccount; players: SquadPlayer[]; fielding: Fielding };
  listings: Listing[];
  deals: Listing[];
  moves: Move[];
  totals: { listed: number; signed: number; withdrawn: number; moves: number; wage_rows: number; grant_rows: number; cup_prize_rows: number; bonus_rows: number; gate_rows: number; stadium_rows: number };
  rules: Record<string, string>;
  constants: {
    market_size: number;
    /** The last round of a season the opening window reaches — the figure `season_windows()` clips the first range to. */
    early_window_last_round: number;
    /** How far either side of the season's halfway round the mid-season window reaches. */
    mid_window_half_width: number;
    negotiation_rounds: number;
    negotiation_floor_share: number;
    release_clause_share: number;
    loan_fee_share: number;
    sell_proceeds_share: number;
    default_loan_rounds: number;
    /** The board's season grant, as the three authored numbers `rules.grant` spells out. */
    season_grant_per_round: number;
    season_grant_per_point: number;
    promotion_grant: number;
    /** What one bought seat costs, and the size of one purchase (M13 Phase 9 item 37). */
    stadium_seat_cost: number;
    stadium_min_seats: number;
    stadium_max_seats: number;
    /** The ground's running rate as a percentage of one credit per seat (M13 Phase 10 item 45). */
    stadium_upkeep_per_seat_pct: number;
    /** The gate price's published bounds and step (M13 Phase 10 item 44). */
    ticket_price_min_pct: number;
    ticket_price_max_pct: number;
    ticket_price_step_pct: number;
    ticket_price_neutral_pct: number;
    /** Season-ticket terms (M13 Phase 10 item 46): the discount, the block size and the ground's cap. */
    season_ticket_discount_pct: number;
    season_ticket_min_seats: number;
    season_ticket_max_share_pct: number;
    /** Training-ground terms (M13 Phase 11 item 47). */
    training_max_level: number;
    training_level_bonus_pct: number;
    training_upgrade_base_cost: number;
    /** What each cup stage pays when it is won (M13 Phase 8 item 32), keyed by stage index. */
    cup_prize_by_stage: Record<string, number>;
    /** What a met objective pays (M13 Phase 9 item 36), keyed by objective kind. */
    objective_bonus_by_kind: Record<string, number>;
    /** The authored price per seat: tier 1 pays more than tier 2 or a cup. */
    gate_ticket_price_tier_1: number;
    gate_ticket_price_tier_2: number;
    /** The share range a round on the career's own rotation sells, chosen from the fixture seed. */
    gate_rotation_attendance_floor: number;
    gate_rotation_attendance_ceiling: number;
    age_curve: { ages: string; weight: number }[];
  };
  data_origin: string;
  is_demo_data: boolean;
  demo_data: boolean;
  disclaimer: string;
};

/** What a refused move answers with: the code, the sentence, and the figures behind the sentence. */
export type MarketRefusalDetail = {
  code?: string;
  message?: string;
  career_slug?: string;
  listing_id?: string;
  player_id?: string;
  competition_id?: string;
  constraint?: string;
  challenge_slug?: string;
  squad_size?: number;
  as_of_round?: number;
  asking?: number;
  fee?: number;
  remaining?: number;
  price?: number;
  current_price?: number;
  release_clause?: number;
  attempts?: number;
  formula?: string;
  ok?: boolean;
  players?: number;
  keepers?: number;
  needs_players?: number;
  needs_keepers?: number;
  rule?: string;
};
