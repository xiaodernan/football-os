/**
 * The §22 transfer market's own response shapes, as `GET /api/v1/transfers/{career}` returns them.
 *
 * A field appears here only because the API sends it: every figure below is one the service layer
 * computed from stored rows and published with the expression beside it, so the page has nothing to
 * invent and nothing to re-derive in the browser.
 */

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
  received: number;
  remaining: number;
  units: string;
  moves: number;
  wage_committed_per_week: number;
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
  clause_required: boolean;
};

export type Move = {
  id: string;
  round_index: number;
  kind: string;
  side: "in" | "out";
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
  counterparty_name: string | null;
  budget_after: number;
  effect: string;
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
  market: { round_index: number; opened: boolean; size: number; note: string };
  need: MarketNeed;
  budget: MarketBudget;
  squad: { account: SquadAccount; players: SquadPlayer[]; fielding: Fielding };
  listings: Listing[];
  deals: Listing[];
  moves: Move[];
  totals: { listed: number; signed: number; withdrawn: number; moves: number };
  rules: Record<string, string>;
  constants: {
    market_size: number;
    negotiation_rounds: number;
    negotiation_floor_share: number;
    release_clause_share: number;
    loan_fee_share: number;
    sell_proceeds_share: number;
    default_loan_rounds: number;
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
