import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { MatchTicker } from "@/components/MatchTicker";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimRow } from "@/lib/types";

import "../../../styles/simulate.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const t = await getTranslations("live");
  const result = await serverFetch<SimRow>(`/simulate/${encodeURIComponent(slug)}`);
  return pageMetadata({
    title: result.ok
      ? `${result.data.home_summary.short_name} ${result.data.score.home} – ${result.data.score.away} ${result.data.away_summary.short_name} — ${t("metaTitle")}`
      : t("metaTitle"),
    description: t("metaDescription"),
    path: `/live/${slug}`,
  });
}

export default async function LiveReplayPage({ params }: Props) {
  const { slug } = await params;
  const t = await getTranslations("live");
  const user = await currentUser();
  if (!user) redirect(`/login?next=${encodeURIComponent(`/live/${slug}`)}`);

  const result = await serverFetch<SimRow>(`/simulate/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404 || result.error.code === "not_found") notFound();
    return (
      <div className="container page stack">
        <WorldHead back={{ href: "/live", label: t("metaTitle") }} eyebrow={t("eyebrow")} title={t("metaTitle")} lede={result.error.message} />
      </div>
    );
  }

  const match = result.data;
  if (!match.timeline) {
    // The timeline is the server's own read of `sim_events`; a detail that answers without
    // rows leaves the field absent, and the page says so instead of rebuilding one from
    // the report and calling it the same thing.
    return (
      <div className="container page stack">
        <WorldHead back={{ href: "/live", label: t("metaTitle") }} eyebrow={t("eyebrow")} title={t("noTimelineTitle")} lede={t("noTimelineNote")} />
      </div>
    );
  }

  const home = match.home_summary;
  const away = match.away_summary;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/live", label: t("metaTitle") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={{ data_origin: match.data_origin, is_demo_data: match.is_demo_data, disclaimer: match.disclaimer }}
        title={`${home.short_name} ${match.score.home} – ${match.score.away} ${away.short_name}`}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip num">{t("eventsChip", { count: match.timeline.count })}</span>
          <span className="chip num">{t("minutesChip", { minutes: match.minutes })}</span>
          <span className="badge badge--sim">{t("replayBadge")}</span>
        </div>
      </WorldHead>

      <MatchTicker
        events={match.timeline.events}
        minutes={match.minutes}
        sourceNote={match.timeline.source_note}
        finalScore={{ home: match.score.home, away: match.score.away }}
        homeShort={home.short_name}
        awayShort={away.short_name}
        byType={match.timeline.by_type}
      />

      <Panel eyebrow={t("provenanceEyebrow")} title={t("sourceTitle")}>
        <div className="stack-sm">
          <p className="muted">{match.timeline.source_note}</p>
          <p className="muted world-section-note">{match.disclaimer}</p>
          <Link className="btn btn--ghost btn--sm" href={`/simulate/${match.slug}`}>
            {t("reportLink")}
          </Link>
        </div>
      </Panel>

      <Provenance
        provenance={{ data_origin: match.data_origin, is_demo_data: match.is_demo_data, disclaimer: match.disclaimer }}
        extra={<span className="chip">{t("replayNoteChip")}</span>}
      />
    </div>
  );
}
