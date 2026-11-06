import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, WorldHead } from "@/components/world";
import { pageMetadata } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimList } from "@/lib/types";

export const dynamic = "force-dynamic";

/**
 * Live is a replay, and says so: the matches a career played, ticked through minute by minute
 * from the timeline the engine wrote. Nothing here is a broadcast — the engine is deterministic
 * and the events are stored rows — and the page carries that sentence beside the list.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("live");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/live",
  });
}

export default async function LiveIndexPage() {
  const t = await getTranslations("live");
  const tn = await getTranslations("nav");
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Flive");

  const result = await serverFetch<SimList>("/simulate");

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/my-football", label: tn("myFootball") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        title={t("metaTitle")}
      >
        <span className="badge badge--sim">{t("replayBadge")}</span>
      </WorldHead>

      <Panel eyebrow={t("listEyebrow")} title={t("listTitle")}>
        {result.ok ? (
          result.data.items.length === 0 ? (
            <div className="empty">
              <strong>{t("emptyTitle")}</strong>
              <span className="muted">{t("emptyNote")}</span>
              <Link className="btn btn--sm" href="/simulate">
                {t("playCta")}
              </Link>
            </div>
          ) : (
            <div className="tac-cards">
              {result.data.items.map((match) => (
                <Link className="tac-card" href={`/live/${match.slug}`} key={match.slug}>
                  <span className="tac-card__name">
                    {match.home_summary.short_name} {match.score.home} – {match.score.away} {match.away_summary.short_name}
                  </span>
                  <span className="tac-card__meta">
                    {t("playedOn", { date: match.created_at?.slice(0, 10) ?? "" })} · {t("minutesNote", { minutes: match.minutes })}
                  </span>
                  <div className="tac-card__metrics">
                    <span className="chip num">{t("replayChip")}</span>
                    <span className="chip mono">{match.data_origin}</span>
                  </div>
                </Link>
              ))}
            </div>
          )
        ) : (
          <div className="notice notice--warn">{result.error.message}</div>
        )}
      </Panel>

      <Provenance
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: result.ok ? result.data.disclaimer : "" }}
        extra={<span className="chip">{t("replayNoteChip")}</span>}
      />
    </div>
  );
}
