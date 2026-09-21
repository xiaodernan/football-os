import type { MetadataRoute } from "next";

import { absolute } from "@/lib/site";
import { serverFetch } from "@/lib/server";
import type { KnowledgeDocumentList } from "@/lib/types";

/**
 * Only routes that render real content for a signed-out visitor are listed. `/` and every
 * `My Football` area 302 to /login without a session, so pointing a crawler at them would
 * publish redirect chains as if they were pages.
 */

export const dynamic = "force-dynamic";

const PUBLIC: { path: string; changeFrequency: MetadataRoute.Sitemap[number]["changeFrequency"]; priority: number }[] = [
  { path: "/knowledge", changeFrequency: "weekly", priority: 0.9 },
];

export default async function sitemap(): Promise<MetadataRoute.Sitemap> {
  const documents = await serverFetch<KnowledgeDocumentList>("/knowledge/documents");

  const entries = PUBLIC.map((entry) => ({
    url: absolute(entry.path),
    changeFrequency: entry.changeFrequency,
    priority: entry.priority,
  }));

  if (!documents.ok) return entries;
  return [
    ...entries,
    ...documents.data.items.map((doc) => ({
      url: absolute(`/knowledge/${encodeURIComponent(doc.slug)}`),
      lastModified: new Date(doc.last_reviewed ?? doc.ingested_at ?? Date.now()),
      changeFrequency: "monthly" as const,
      priority: 0.8,
    })),
  ];
}
