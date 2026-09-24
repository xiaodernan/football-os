/**
 * What a career's played rounds leave on its players — `GET /api/v1/careers/{slug}`'s `carry_over` block.
 *
 * Every figure here is summed from stored rows on the request: `career_appearances`, one per player the
 * engine selected per round, and the player's own sessions in `real_training_sessions`. The four formula
 * strings are the same sentences the match report's factors print, so a page can show the arithmetic
 * rather than a number whose origin it cannot name.
 */

export type CarryLoadEntry = {
  player_id: string;
  player_name: string;
  position: string;
  /** Minutes in the most recent traced round this player appears in. */
  minutes_recent: number;
  rounds_in_window: number;
  load_units: number;
  training_load_units: number;
  condition: number;
};

export type CarryAppearanceRow = {
  round_index: number;
  player_name: string;
  player_path: string | null;
  position: string;
  band: string;
  side: string;
  minutes: number;
  minutes_units: string;
  opponent_name: string;
  note: string;
};

export type CarryOverView = {
  rounds_played: number;
  rounds_traced: number;
  untraced_rounds: number[];
  appearances: number;
  players_traced: number;
  last_traced_round: number;
  next_round: number;
  window_rounds: number;
  decay_per_round: number;
  carrying_load: number;
  mean_condition_of_last_xi: number;
  condition_floor: number;
  training_records_found: number;
  most_loaded: CarryLoadEntry[];
  rows: CarryAppearanceRow[];
  load_formula: string;
  reserve_formula: string;
  condition_formula: string;
  form_formula: string;
  note: string;
  disclaimer: string;
  data_origin: string;
  is_demo_data: boolean;
};
