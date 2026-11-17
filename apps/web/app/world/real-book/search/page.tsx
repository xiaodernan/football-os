import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations, getLocale } from "next-intl/server";

import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { readWorld, cleanParams } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/records.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldRealBook");
  return pageMetadata({
    title: t("searchMetaTitle"),
    description: t("searchMetaDescription"),
    path: "/world/real-book/search",
  });
}

type HonoursEntry = {
  tournament: string;
  kind: string;
  title: string;
  host: string;
  date?: string;
  venue?: string;
  champion: string;
  champion_note: string;
  runner_up: string;
  score_regular: [number, number];
  score_extra_time: [number, number];
  score_penalties: [number, number];
  has_penalties: boolean;
  went_extra_time: boolean;
  on_field: number;
  goals_scored: number;
  total_matches: number;
};

type SearchPayload = {
  available: true;
  query: string;
  matches: HonoursEntry[];
  source: string;
  attribution: string;
  provenance: { data_origin: string; is_demo_data: boolean; license: string };
};

export default async function RealBookSearchPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}) {
  const [t, tw, tc, th] = await Promise.all([
    getTranslations("worldRealBook"),
    getTranslations("world"),
    getTranslations("common"),
    getTranslations("worldHonours"),
  ]);
  const locale = await getLocale();
  const raw = await searchParams;
  const query = (Array.isArray(raw.q) ? raw.q[0] : raw.q)?.trim() ?? "";

  const result = await readWorld<SearchPayload>("/world/real-book/search", { q: query || undefined });

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world/real-book", label: tw("backToWorld") }}
        eyebrow={t("searchEyebrow")}
        lede={t("searchLede")}
        provenance={result.ok ? result.data.provenance : undefined}
        title={t("searchTitle")}
      />

      <form method="get" action="/world/real-book/search" className="records__fixture-row" aria-label={t("searchFormLabel")}>
        <label className="records__team" style={{ flex: "1 1 320px" }}>
          <span className="records__team-name" style={{ fontSize: "0.78rem", letterSpacing: "0.08em", textTransform: "uppercase", color: "var(--text-2)" }}>
            {t("searchFieldLabel")}
          </span>
          <input
            type="search"
            name="q"
            defaultValue={query}
            placeholder={t("searchPlaceholder")}
            className="input"
            aria-label={t("searchPlaceholder")}
            autoFocus
          />
        </label>
        <button
          type="submit"
          className="btn btn--primary"
        >
          {tc("search")}
        </button>
      </form>

      {result.ok ? (
        <>
          <p className="muted" style={{ fontSize: "0.85rem", margin: 0 }} aria-live="polite">
            {query
              ? t("searchCount", { count: result.data.matches.length, query })
              : t("searchCountAll", { count: result.data.matches.length })}
          </p>

          {result.data.matches.length === 0 ? (
            <p className="muted">{t("searchNoMatches")}</p>
          ) : (
            <div className="records__panel">
              <span className="records__panel-eyebrow">{t("searchEyebrowResults")}</span>
              <div className="records__fixture-row" aria-hidden="true">
                <div className="records__team">
                  <span className="records__team-name">{th("thYear")}</span>
                </div>
                <div className="records__team"><span className="records__team-name">{th("thHost")}</span></div>
                <div className="records__team"><span className="records__team-name">{th("thChampion")}</span></div>
                <div className="records__team"><span className="records__team-name">{th("thRunnerUp")}</span></div>
                <div className="records__team"><span className="records__team-name">{th("thScore")}</span></div>
              </div>
              {result.data.matches.map((entry) => (
                <div className="records__fixture-row" key={entry.tournament}>
                  <div className="records__team">
                    <Link
                      href={`/world/real-book?tournament=${encodeURIComponent(entry.tournament)}`}
                      className="records__team-name world-link num"
                    >
                      {entry.tournament} · {entry.kind === "worldcup" ? th("kindWorldCup") : th("kindEuro")}
                    </Link>
                  </div>
                  <div className="records__team">
                    <span className="records__team-name">{entry.host}</span>
                  </div>
                  <div className="records__team">
                    <span className="records__team-name">{entry.champion}</span>
                    <span className="records__team-name" style={{ fontSize: "0.78rem", color: "var(--text-3)" }}>{entry.champion_note}</span>
                  </div>
                  <div className="records__team">
                    <span className="records__team-name">{entry.runner_up}</span>
                  </div>
                  <div className="records__team">
                    <span className="records__team-name num" style={{ fontWeight: 750, letterSpacing: "0.02em" }}>
                      {entry.score_extra_time[0]}–{entry.score_extra_time[1]}
                      {entry.score_penalties.length === 2 || entry.has_penalties ? ` (${entry.score_penalties[0]}–${entry.score_penalties[1]} pens)` : ""}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </>
      ) : (
        <WorldUnavailable message={result.message} title={t("searchUnavailable")} />
      )}
    </div>
  );
}
