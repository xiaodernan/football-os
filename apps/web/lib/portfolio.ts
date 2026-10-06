/**
 * §38's portfolio tier as the page sees it.
 *
 * Two doors (`apps/api/app/api/v1/portfolio.py`): a public rulebook and the account's own CV. The tier owns no
 * table — `build_cv` reads rows the other tiers write — so nothing here is typed as a field a page could edit:
 * every figure arrives as the answer to a published formula, recomputed at the moment of the read, and a section
 * the build cannot fill arrives as **a reason**, not as a zero.
 *
 * `_section` gives all ten members of the tuple the same shape, so the page never special-cases one of them:
 * `available` decides which half of the union a section carries, and the walk holds the painted cells against
 * the door's own JSON rather than against a number typed in TSX.
 */

export type PortfolioFigureValue = string | number | boolean | null | string[] | Record<string, number>;

export type PortfolioRoute = {method: string; path: string; door: string};

/** The vocabulary door's entry for one section: its key, the spec's word for it, the rows behind it, and whether this build fills it. */
export type PortfolioVocabulary = {section: string; title: string; source: string; fillable: boolean};

export type PortfolioSection = {
  section: string;
  title: string;
  available: boolean;
  source: string;
  data_origin: string;
  missing_because?: string;
  would_be_read_from?: string;
  figures?: Record<string, PortfolioFigureValue>;
  formulas?: Record<string, string>;
  items?: Record<string, string | number | null>[];
};

export type PortfolioCv = {
  account: {user_id: string; display_name: string};
  player: {id: string; name: string; position: string; visibility: string; data_origin: string} | null;
  has_player: boolean;
  sections: PortfolioSection[];
  counts: {sections: number; filled: number; unfilled: string[]};
  unfilled_reasons: Record<string, string>;
  formulas: Record<string, string>;
  limitation: string;
};

export type PortfolioRules = {
  routes: PortfolioRoute[];
  refusal_answers: Record<string, number>;
  sections: PortfolioVocabulary[];
  unfilled: Record<string, string>;
  would_read_from: Record<string, string>;
  formulas: Record<string, string>;
  public_outputs: Record<string, string>;
  share: {
    publishable: string[];
    minor_blocked: string[];
    minor_age: number;
    token_shape: string;
    private_keys_dropped: string[];
  };
  limitation: string;
};

/** One row in the account's own share ledger. A closed row carries no token back to the browser. */
export type PortfolioShareRecord = {
  share: string;
  token: string | null;
  sections: string[];
  opened_at: string | null;
  revoked_at: string | null;
  live: boolean;
};

export type PortfolioShareLedger = {
  shares: PortfolioShareRecord[];
  counts: { opened: number; live: number; revoked: number };
  publishable: string[];
  minor_blocked: string[];
  minor_age: number;
};

/** The token door's projection: no account, no token, no unpublished section, and no stored copy of a figure. */
export type PortfolioPublicCv = {
  player: { name: string; position: string; data_origin: string } | null;
  has_player: boolean;
  sections: PortfolioSection[];
  withheld: { section: string; title: string; reason: string }[];
  unfilled_reasons: Record<string, string>;
  counts: { sections: number; filled: number; unfilled: string[] };
  published_sections: string[];
  formulas: Record<string, string>;
  opened_at: string | null;
  limitation: string;
};

/**
 * A figure printed the way the door sent it.
 *
 * A list becomes its members, a mapping becomes `key value` pairs in the door's own order, and `null` stays the
 * literal token `null` — because `null` is what the door says when the formula it names had no rows to fold,
 * and a page that turned it into `0` would be answering a question the tier refused to answer.
 */
export function figureText(value: PortfolioFigureValue | unknown): string {
  if (Array.isArray(value)) return value.map(entry => String(entry)).join(", ");
  if (value !== null && typeof value === "object") {
    return Object.entries(value as Record<string, unknown>).map(([key, inner]) => `${key} ${String(inner)}`).join(" · ");
  }
  return String(value);
}

/** The columns an item table needs, taken from the rows the door sent rather than from a list written here. */
export function itemColumns(items: Record<string, string | number | null>[]): string[] {
  const seen: string[] = [];
  for (const row of items) {
    for (const key of Object.keys(row)) if (!seen.includes(key)) seen.push(key);
  }
  return seen;
}
