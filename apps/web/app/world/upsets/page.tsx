import type { Metadata } from "next";

import { Provenance, WorldHead, WorldUnavailable, formatDay } from "@/components/world";
import { UpsetsCoachRead } from "@/components/UpsetsCoachRead";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/upsets.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldUpsets");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/upsets",
    images: [{ url: absolute("/world/upsets/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

type SideBrief = { id: string; slug: string; name: string; path: string } | null;
type UpsetRow = {
  slug: string;
  path: string;
  kickoff_at: string | null;
  round_label: string;
  home: SideBrief;
  away: SideBrief;
  home_goals: number;
  away_goals: number;
  favorite: "home" | "away";
  rating_gap: number;
  kind: "upset" | "fortress";
};
type UpsetsPayload = WorldEnvelope & {
  available: boolean;
  season: { label: string; kind: string };
  competition?: string;
  competition_slug?: string;
  judged?: number;
  upset_count?: number;
  fortress_count?: number;
  fortress_gap?: number;
  mean_upset_gap?: number;
  upset_rate_pct?: number;
  biggest_upset?: UpsetRow | null;
  fortress?: UpsetRow | null;
  upsets?: UpsetRow[];
  fortresses?: UpsetRow[];
  recent_upsets?: UpsetRow[];
};

export default async function UpsetsPage() {
  const t = await getTranslations("worldUpsets");
  const tw = await getTranslations("world");

  const result = await readWorld<UpsetsPayload>("/world/upsets");
  if (!result.ok) return <WorldUnavailable message={result.message} />;
  if (!result.data.available) return <WorldUnavailable message={t("unavailable")} />;

  const {
    judged,
    upset_count,
    fortress_count,
    mean_upset_gap,
    upset_rate_pct,
    biggest_upset,
    fortresses = [],
    upsets = [],
  } = result.data;

  const rate = upset_rate_pct?.toFixed(1) ?? "0.0";
  const gap = mean_upset_gap?.toFixed(2) ?? "0.00";

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div className="upsets__stats">
        <div className="upsets__tile">
          <span className="upsets__tile-eyebrow">{t("statUpsetLabel")}</span>
          <p className="upsets__big">{upset_count ?? 0}</p>
          <p className="upsets__sub">{t("upsetCaption", { count: upset_count ?? 0, judged: judged ?? 0 })}</p>
        </div>
        <div className="upsets__tile">
          <span className="upsets__tile-eyebrow">{t("statFortressLabel")}</span>
          <p className="upsets__big">{fortress_count ?? 0}</p>
          <p className="upsets__sub">{t("fortressCaption")}</p>
        </div>
        <div className="upsets__tile">
          <span className="upsets__tile-eyebrow">{t("statMeanLabel")}</span>
          <p className="upsets__big">{gap}</p>
          <p className="upsets__sub">{t("meanCaption")}</p>
        </div>
      </div>

      <p className="upsets__verdict">{t("verdictBody", { rate })}</p>

      {biggest_upset ? (
        <section className="upsets__hero">
          <span className="upsets__hero-eyebrow">{t("biggestUpsetTitle")}</span>
          <div className="upsets__hero-score">
            <strong>{biggest_upset.home?.name}</strong>
            <span className="upsets__hero-goals">
              {biggest_upset.home_goals} – {biggest_upset.away_goals}
            </span>
            <strong>{biggest_upset.away?.name}</strong>
          </div>
          <p className="upsets__hero-meta">
            <em>{biggest_upset.rating_gap.toFixed(2)}</em> {t("biggestUpsetGapLabel")} · {biggest_upset.round_label}
          </p>
        </section>
      ) : null}

      <section>
        <h2 className="upsets__title">{t("boardTitle")}</h2>
        <p className="muted" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0.5rem" }}>{t("boardLede")}</p>
        <div className="upsets__board">
          {upsets.map((row) => (
            <Link key={row.slug} href={row.path} className="upsets__row">
              <span className="upsets__row-date">{formatDay(row.kickoff_at)}</span>
              <span className="upsets__row-fixture">
                <strong>{row.home?.name}</strong>
                <span className="upsets__row-goals">{row.home_goals} – {row.away_goals}</span>
                <strong>{row.away?.name}</strong>
              </span>
              <span className="upsets__row-fav">
                {t("rowUpsetLabel")} · <em>{row.favorite === "home" ? t("favoriteHome") : t("favoriteAway")}</em>
              </span>
              <span className="upsets__row-fav">{row.round_label}</span>
              <span className="upsets__row-gap">{row.rating_gap.toFixed(1)}</span>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="upsets__title">{t("fortressTitle")}</h2>
        <p className="muted" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0.5rem" }}>{t("fortressLede")}</p>
        <div className="upsets__board">
          {fortresses.map((row) => (
            <Link key={row.slug} href={row.path} className="upsets__row">
              <span className="upsets__row-date">{formatDay(row.kickoff_at)}</span>
              <span className="upsets__row-fixture">
                <strong>{row.home?.name}</strong>
                <span className="upsets__row-goals">{row.home_goals} – {row.away_goals}</span>
                <strong>{row.away?.name}</strong>
              </span>
              <span className="upsets__row-fav">
                {t("rowFortressLabel")} · <em>{row.favorite === "home" ? t("favoriteHome") : t("favoriteAway")}</em>
              </span>
              <span className="upsets__row-fav">{row.round_label}</span>
              <span className="upsets__row-gap">{row.rating_gap.toFixed(1)}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="upsets__method">
        <span className="upsets__tile-eyebrow">{t("methodEyebrow")}</span>
        <p>{t("methodBody")}</p>
      </section>

      <UpsetsCoachRead />

      <Provenance provenance={result.data} />
    </div>
  );
}
