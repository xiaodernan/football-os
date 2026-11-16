import type { Metadata } from "next";

import { Provenance, WorldHead, WorldUnavailable, formatDay } from "@/components/world";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { absolute, pageMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { WorldEnvelope } from "@/lib/types";
import "@/styles/dynasties.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("worldDynasties");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/dynasties",
    images: [{ url: absolute("/world/dynasties/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

type SideBrief = { id: string; slug: string; name: string; path: string } | null;
type StreakRow = {
  kind: "win" | "unbeaten";
  length: number;
  start_kickoff_at: string | null;
  end_kickoff_at: string | null;
  start_round: string | null;
  end_round: string | null;
  team: SideBrief;
};
type DynastiesPayload = WorldEnvelope & {
  available: boolean;
  season: { label: string; kind: string };
  competition?: string;
  competition_slug?: string;
  judged?: number;
  longest_win?: StreakRow | null;
  longest_unbeaten?: StreakRow | null;
  win_streaks?: StreakRow[];
  unbeaten_runs?: StreakRow[];
  ablaze?: { team: SideBrief; current_win_run: number; matches?: number };
};

export default async function DynastiesPage() {
  const t = await getTranslations("worldDynasties");
  const tw = await getTranslations("world");

  const result = await readWorld<DynastiesPayload>("/world/dynasties");
  if (!result.ok) return <WorldUnavailable message={result.message} />;
  if (!result.data.available) return <WorldUnavailable message={t("unavailable")} />;

  const { judged, longest_win, longest_unbeaten, win_streaks = [], unbeaten_runs = [], ablaze } = result.data;
  const winLength = longest_win?.length ?? 0;
  const unbeatenLength = longest_unbeaten?.length ?? 0;
  const ablazeRun = ablaze?.current_win_run ?? 0;

  return (
    <div className="container page stack" style={{ gap: "2rem" }}>
      <WorldHead
        back={{ href: "/world", label: tw("backToWorld") }}
        eyebrow={t("eyebrow")}
        lede={t("lede")}
        provenance={result.data}
        title={t("title")}
      />

      <div className="dynasties__stats">
        <div className="dynasties__tile">
          <span className="dynasties__tile-eyebrow">{t("statWinLabel")}</span>
          <p className="dynasties__big">{winLength}</p>
          <p className="dynasties__sub">{t("winCaption", { team: longest_win?.team?.name ?? "—" })}</p>
        </div>
        <div className="dynasties__tile">
          <span className="dynasties__tile-eyebrow">{t("statUnbeatenLabel")}</span>
          <p className="dynasties__big">{unbeatenLength}</p>
          <p className="dynasties__sub">{t("unbeatenCaption", { team: longest_unbeaten?.team?.name ?? "—" })}</p>
        </div>
        <div className="dynasties__tile">
          <span className="dynasties__tile-eyebrow">{t("statAblazeLabel")}</span>
          <p className="dynasties__big">{ablazeRun}</p>
          <p className="dynasties__sub">{t("ablazeCaption", { team: ablaze?.team?.name ?? "—" })}</p>
        </div>
      </div>

      <section className="dynasties__ablaze">
        <span className="dynasties__ablaze-eyebrow">{t("ablazeTitle")}</span>
        {ablaze?.team ? (
          <>
            <h2 className="dynasties__ablaze-name">{ablaze.team.name}</h2>
            <p className="dynasties__ablaze-meta">{t("ablazeBody", { count: ablazeRun, matches: ablaze.matches ?? 0 })}</p>
          </>
        ) : (
          <p className="dynasties__ablaze-meta">{t("ablazeQuiet")}</p>
        )}
      </section>

      <section>
        <h2 className="dynasties__title">{t("boardWinTitle")}</h2>
        <p className="muted" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0.5rem" }}>{t("boardWinLede")}</p>
        <div className="dynasties__board">
          {win_streaks.map((row, index) => (
            <Link key={`win-${row.team?.slug}-${index}`} href={row.team?.path ?? "/world"} className="dynasties__row">
              <span className="dynasties__row-team"><strong>{row.team?.name}</strong></span>
              <span className="dynasties__row-streak">{row.length}</span>
              <span className="dynasties__row-meta">{t("rowStreakLabel")} · <em>{row.start_round} → {row.end_round}</em></span>
              <span className="dynasties__row-rounds">{formatDay(row.start_kickoff_at)} — {formatDay(row.end_kickoff_at)}</span>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <h2 className="dynasties__title">{t("boardUnbeatenTitle")}</h2>
        <p className="muted" style={{ fontSize: "0.82rem", margin: "0.15rem 0 0.5rem" }}>{t("boardUnbeatenLede")}</p>
        <div className="dynasties__board">
          {unbeaten_runs.map((row, index) => (
            <Link key={`unbeaten-${row.team?.slug}-${index}`} href={row.team?.path ?? "/world"} className="dynasties__row">
              <span className="dynasties__row-team"><strong>{row.team?.name}</strong></span>
              <span className="dynasties__row-streak">{row.length}</span>
              <span className="dynasties__row-meta">{t("rowUnbeatenLabel")} · <em>{row.start_round} → {row.end_round}</em></span>
              <span className="dynasties__row-rounds">{formatDay(row.start_kickoff_at)} — {formatDay(row.end_kickoff_at)}</span>
            </Link>
          ))}
        </div>
      </section>

      <section className="dynasties__method">
        <span className="dynasties__tile-eyebrow">{t("methodEyebrow")}</span>
        <p>{t("methodBody")}</p>
      </section>

      <Provenance provenance={result.data} />
    </div>
  );
}
