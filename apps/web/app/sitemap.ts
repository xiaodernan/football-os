import type { MetadataRoute } from "next";

import { absolute } from "@/lib/site";
import { serverFetch } from "@/lib/server";
import type {
  CompetitionList,
  KnowledgeDocumentList,
  MatchList,
  NewsList,
  PlayerList,
  TeamList,
  WorldEnvelope,
} from "@/lib/types";

/**
 * Only routes that render real content for a signed-out visitor are listed. `/` and every
 * `My Football` area 302 to /login without a session, so pointing a crawler at them would
 * publish redirect chains as if they were pages.
 *
 * The world rows are read from the same list endpoints the pages use — with the API's own
 * `path` field — so the sitemap cannot advertise a slug that no page answers.
 */

export const dynamic = "force-dynamic";

const PUBLIC: { path: string; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"]; priority: number }[] = [
  { path: "/knowledge", changeFrequency: "weekly", priority: 0.9 },
  { path: "/world", changeFrequency: "daily", priority: 0.9 },
  { path: "/world/competitions", changeFrequency: "weekly", priority: 0.8 },
  { path: "/world/teams", changeFrequency: "weekly", priority: 0.8 },
  { path: "/world/players", changeFrequency: "weekly", priority: 0.8 },
  { path: "/world/matches", changeFrequency: "daily", priority: 0.8 },
  { path: "/world/news", changeFrequency: "daily", priority: 0.8 },
];

/** `/world/search` is deliberately absent: a query page is not content (see its own `robots`). */

type Row = { path: string };
type StampRow = Row & { kickoff_at?: string | null; published_at?: string | null };
type Page<T> = WorldEnvelope & { items: T[]; page: number; pages: number };

/** Walk every page of a list route. The cap bounds one bad `total` rather than trusting it. */
async function collect<T extends Row>(path: string, pageSize: number): Promise<T[]> {
  const rows: T[] = [];
  let page = 1;
  let pages = 1;
  do {
    const result = await serverFetch<Page<T>>(path, { query: { page, page_size: pageSize } });
    if (!result.ok) return rows;
    rows.push(...result.data.items);
    pages = Math.min(result.data.pages, 50);
    page += 1;
  } while (page <= pages && rows.length < 5000);
  return rows;
}

function entries(rows: StampRow[], dateKey?: "kickoff_at" | "published_at", priority = 0.7): MetadataRoute.Sitemap {
  return rows.map((row) => {
    const stamp = dateKey ? row[dateKey] : null;
    return {
      url: absolute(row.path),
      ...(stamp ? { lastModified: new Date(stamp) } : {}),
      changeFrequency: "weekly" as const,
      priority,
    };
  });
}

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const [documents, competitions, teams, players, matches, articles] = await Promise.all([
    serverFetch<KnowledgeDocumentList>("/knowledge/documents"),
    collect<CompetitionList["items"][number]>("/world/competitions", 100),
    collect<TeamList["items"][number]>("/world/teams", 100),
    collect<PlayerList["items"][number]>("/world/players", 200),
    collect<MatchList["items"][number]>("/world/matches", 200),
    collect<NewsList["items"][number]>("/world/news", 100),
  ]);

  const fixed = PUBLIC.map((entry) => ({
    url: absolute(entry.path),
    changeFrequency: entry.changeFrequency,
    priority: entry.priority,
  }));

  const world = [
    ...entries(competitions, undefined, 0.8),
    ...entries(teams, undefined, 0.8),
    ...entries(players, undefined, 0.7),
    ...entries(matches, "kickoff_at", 0.6),
    ...entries(articles, "published_at", 0.6),
  ];

  if (!documents.ok) return [...fixed, ...world];
  return [
    ...fixed,
    ...world,
    ...documents.data.items.map((doc) => ({
      url: absolute(`/knowledge/${encodeURIComponent(doc.slug)}`),
      lastModified: new Date(doc.last_reviewed ?? doc.ingested_at ?? Date.now()),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
