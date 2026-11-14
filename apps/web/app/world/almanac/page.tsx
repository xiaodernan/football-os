import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { OriginBadge, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { pageMetadata, absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { AlmanacResult } from "@/lib/types";

import "@/styles/almanac.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("almanac");
  return pageMetadata({
    title: t("metaTitle"),
    description: t("metaDescription"),
    path: "/world/almanac",
    images: [{ url: absolute("/world/almanac/opengraph-image"), width: 1200, height: 630, alt: "FOOTBALL OS" }],
  });
}

export default async function AlmanacPage() {
  const t = await getTranslations("almanac");
  const result = await readWorld<AlmanacResult>("/world/almanac");

  if (!result.ok) {
    return (
      <div className="container page stack">
        <WorldHead eyebrow={t("eyebrow")} title={t("title")} />
        <p className="almanac__unavailable">{t("unavailable")}</p>
      </div>
    );
  }

  const { awards, best_manager, portrait } = result.data;

  // Static calls: a template key would hide the message from the i18n gates (which is what the
  // ledger's t(`cat_${key}`) trap warns about in the duel page).
  const copy = {
    golden_boot: { label: t("goldenBoot"), hint: t("goldenBootHint"), unit: t("goalsUnit") },
    playmaker_crown: { label: t("playmaker"), hint: t("playmakerHint"), unit: t("assistsUnit") },
    complete_forward: { label: t("completeForward"), hint: t("completeForwardHint"), unit: t("involvementUnit") },
    golden_glove: { label: t("goldenGlove"), hint: t("goldenGloveHint"), unit: t("cleanSheetsUnit") },
    player_of_season: { label: t("playerOfSeason"), hint: t("playerOfSeasonHint"), unit: t("ratingUnit") },
    the_enforcer: { label: t("theEnforcer"), hint: t("theEnforcerHint"), unit: t("cardsUnit") },
    breakthrough: { label: t("breakthrough"), hint: t("breakthroughHint"), unit: t("involvementUnit") },
  } as const;

  return (
    <div className="container page stack">
      <WorldHead
        eyebrow={t("eyebrow")}
        title={t("title")}
        lede={t("lede")}
        provenance={result.data}
        back={{ href: "/world", label: t("backWorld") }}
      />

      {portrait && (
        <div className="almanac__hero">
          {(["golden_boot", "playmaker"] as const).map((key) => {
            const picked = portrait[key];
            if (!picked) {
              return null;
            }
            const isBoot = key === "golden_boot";
            return (
              <Link key={key} href={picked.path} className={`almanac__portrait almanac__portrait--${isBoot ? "boot" : "crown"}`}>
                <div>
                  <p className="almanac__portrait-label">{isBoot ? t("bootShort") : t("crownShort")}</p>
                  <strong className="almanac__portrait-name">{picked.name}</strong>
                  <span className="almanac__portrait-club">{picked.position} · #{picked.overall}</span>
                </div>
                <div className="almanac__portrait-figure">
                  <span className="almanac__portrait-number">{picked.stat ?? "–"}</span>
                  <span className="almanac__portrait-unit">{isBoot ? t("goalsUnit") : t("assistsUnit")}</span>
                </div>
              </Link>
            );
          })}
        </div>
      )}

      <div className="almanac__grid">
        {awards.map((award) => {
          const winner = award.winner;
          const meta = copy[award.key as keyof typeof copy];

          return (
            <article key={award.key} className="almanac__award">
              <span className="almanac__award-label">{meta.label}</span>
              {winner ? (
                <>
                  <strong className="almanac__award-name">
                    <Link href={winner.path}>{winner.name}</Link>
                  </strong>
                  <p className="almanac__award-hint">{meta.hint}</p>
                  <p className="almanac__award-stat">
                    <strong>{winner.stat}</strong> {meta.unit}
                  </p>
                  {award.runner_ups.length > 0 && (
                    <p className="almanac__runner-ups">
                      <span>{t("runnerUps")}:</span>{" "}
                      {award.runner_ups.map((r) => (
                        <Link key={r.id} href={r.path} className="almanac__runner-up">
                          {r.name}
                        </Link>
                      ))}
                    </p>
                  )}
                </>
              ) : (
                <p className="almanac__award-hint">{t("unavailable")}</p>
              )}
            </article>
          );
        })}
      </div>

      {best_manager && (
        <Panel eyebrow={t("managerLabel")} title={best_manager.team.name}>
          <p className="almanac__manager-caption">{t("managerHint")}</p>
          <div className="almanac__manager">
            <div>
              <p className="almanac__manager-label">{best_manager.competition_name}</p>
              <strong className="almanac__portrait-name">{best_manager.team.name}</strong>
              <p className="almanac__manager-caption">
                {t("managerFigures", { points: best_manager.points, won: best_manager.won, drawn: best_manager.drawn })}
              </p>
              <p className="almanac__manager-caption">
                {t("managerGoals", { goalsFor: best_manager.goals_for, goalsAgainst: best_manager.goals_against })}
              </p>
            </div>
            <div className="almanac__manager-stat">
              {best_manager.points}
              <span style={{ fontSize: "0.3em", display: "block", letterSpacing: "0.15em", color: "var(--text-2)" }}>
                PTS
              </span>
            </div>
          </div>
        </Panel>
      )}

      <Provenance provenance={result.data} />
    </div>
  );
}
