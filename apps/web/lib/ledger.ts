/**
 * A career's season as the event rows answer for it — `GET /api/v1/careers/{slug}`'s `ledger` block.
 *
 * The panel exists because a match report can only be read one match at a time. Every figure here is a
 * `GROUP BY` over `sim_events` for this career's own fixtures, computed on the request, so nothing can
 * drift from the table it summarises. What makes it worth trusting is the company it keeps: the club's
 * goal total is published beside `club_goals` summed off the fixture list, and `consistency` says which
 * way those two readings fell. `absent` here rather than zero: a list row, a challenge run and any API
 * that predates the ledger all answer without this block.
 */

export type LedgerEntry = {
  player_id: string;
  slug: string;
  player_path: string | null;
  name: string;
  position: string;
  /** How many of this career's traced fixtures the rows hold an event for — not appearances. */
  matches_with_events: number;
  goals: number;
  attempts: number;
  expected_goals: number;
  yellow_cards: number;
  red_cards: number;
  injuries: number;
  events_by_type: Record<string, number>;
};

export type LedgerTypeTotals = {
  events: number;
  identified: number;
  ambiguous: number;
  unnamed: number;
  expected_goals: number;
};

export type SeasonLedger = {
  club: { team_id: string | null; name: string; short: string };
  players: LedgerEntry[];
  /** Players the rows named at least once. An eleventh who never had a chance or a foul has no row. */
  players_with_events: number;
  players_shown: number;
  truncated: boolean;
  totals: {
    events: number;
    goals: number;
    attempts: number;
    expected_goals: number;
    yellow_cards: number;
    red_cards: number;
    injuries: number;
  };
  by_type: Record<string, LedgerTypeTotals>;
  fixtures_played: number;
  fixtures_traced: number;
  fixtures_untraced: number;
  club_goals_traced: number;
  unattributed: {
    events: { ambiguous: number; unnamed: number };
    ambiguous_names: string[];
    unnamed_names: string[];
  };
  consistency: string;
  scope: string;
  source: string;
  formula: string;
  consistency_formula: string;
  attribution_formula: string;
  disclaimer: string;
  data_origin: string;
  is_demo_data: boolean;
};

/** The seven counts a season's panel offers per player, in the order it prints them. */
export type LedgerStatKey = "matches_with_events" | "goals" | "attempts" | "expected_goals" | "yellow_cards" | "red_cards" | "injuries";

export const LEDGER_COLUMNS: { key: LedgerStatKey; label: string; hint: string }[] = [
  { key: "matches_with_events", label: "Matches", hint: "fixtures with at least one event for this player" },
  { key: "goals", label: "Goals", hint: "goal events naming this player" },
  { key: "attempts", label: "Attempts", hint: "goals, saved shots and shots off target" },
  { key: "expected_goals", label: "xG", hint: "the chance quality the engine gave those attempts" },
  { key: "yellow_cards", label: "Yellow", hint: "bookings naming this player" },
  { key: "red_cards", label: "Red", hint: "sendings-off naming this player" },
  { key: "injuries", label: "Injury", hint: "injuries recorded against this player" },
];
