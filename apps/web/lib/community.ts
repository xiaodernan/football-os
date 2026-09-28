/**
 * §35's Community tier as the page sees it.
 *
 * Every shape here is the answer one of the twelve doors in `apps/api/app/api/v1/community.py` sends, and the
 * rule the tier publishes with it: **a post stores a pointer and words, and no figure about the thing it
 * shares**. So `likes`, `comments`, `reposts`, `followers` and `following` arrive as numbers the door counted
 * from the rows at the moment of the read, each with its formula printed beside it — and this file types them
 * as read-only numbers rather than as fields a page could edit or a client could cache.
 *
 * `caps` is the only place a ceiling, a kind or a prefix is written here: the compose form builds its selects
 * and its `maxLength` from it, so a page that printed a fifth visibility or a ninth kind would be inventing
 * vocabulary the door refuses (§49's one constant, applied to the browser).
 */

export type CommunityAuthor = {id: string; display_name: string};

export type CommunityPostRow = {
  id: string;
  kind: string;
  body: string;
  pointer: string;
  visibility: string;
  shared_on: string;
  has_pointer: boolean;
  likes: number;
  comments: number;
  reposts: number;
  author: CommunityAuthor;
  viewer_liked: boolean;
  formulas: Record<string, string>;
};

export type CommunityRoute = {method: string; path: string; door: string};

export type CommunityCaps = {
  post_max: number;
  post_body_max: number;
  pointer_max: number;
  comment_max: number;
  comment_body_max: number;
  following_max: number;
  kinds: string[];
  reactions: string[];
  visibilities: string[];
  pointer_prefixes: Record<string, string>;
  visibility_rule: string;
};

export type CommunityRules = {
  routes: CommunityRoute[];
  refusal_answers: Record<string, number>;
  caps: CommunityCaps;
  counts: Record<string, number>;
  formulas: Record<string, string>;
  refusals: string[];
  limitation: string;
};

export type CommunityFeed = {
  items: CommunityPostRow[];
  total: number;
  limit: number;
  wall: string | null;
  feed_authors: number | null;
  formulas: Record<string, string>;
  rule: string;
};

export type CommunityProfile = {
  member: CommunityAuthor;
  followers: number;
  following: number;
  posts: number;
  formulas: Record<string, string>;
  rule: string;
};

export type CommunityCommentRow = {id: string; body: string; author: CommunityAuthor; commented_on: string};

export type CommunityMeasures = {likes: number; comments: number; reposts: number};

export type CommunityPosted = {post: CommunityPostRow; posted: boolean; rule: string};

export type CommunityRecorded = CommunityMeasures & {recorded_now: boolean};

export type CommunityFollowed = CommunityProfile & {follow: string; recorded_now?: boolean; removed?: boolean};

export type CommunityErased = {erased: string; author_id: string} & CommunityMeasures;

/** The figures a door counts rather than stores, so a page can say which rows it re-read them from. */
export const DERIVED_FIGURES = ["likes", "comments", "reposts", "followers", "following", "feed_total", "post_total"] as const;

/**
 * A pointer is an address, and the tier refuses one that does not start with its kind's own prefix. The page
 * cannot check the prefix rule from the database, but it can check it over the rows the door sent and report
 * any row that disagrees — which is the only honest way a browser can hold a promise the server made.
 */
export function pointerAgreesWithKind(row: CommunityPostRow, caps: CommunityCaps): boolean {
  if (row.kind === "note") return row.pointer === "" && row.has_pointer === false;
  const prefix = caps.pointer_prefixes[row.kind];
  if (prefix === undefined) return false;
  return row.has_pointer === true && row.pointer.startsWith(prefix);
}

/** A refusal's figures, in the words the API sent them, for the note under a form. */
export function refusalFigures(details: unknown): string[] {
  if (!details || typeof details !== "object" || Array.isArray(details)) return [];
  return Object.entries(details as Record<string, unknown>)
    .filter(([, value]) => value !== null && value !== undefined && value !== "")
    .map(([key, value]) => `${key} ${Array.isArray(value) ? value.join(", ") || "none" : String(value)}`);
}
