import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { CareerForm } from "@/components/CareerForm";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CareerList, CareerOptions } from "@/lib/types";

import "../../styles/tactics.css";
import "../../styles/simulate.css";

export const dynamic = "force-dynamic";

/**
 * A career is an account's fiction: which generated club it took charge of and what it asked of the
 * season. So this page is private like `/simulate` — `noindex`, disallowed in robots.ts, absent from
 * the sitemap — while the clubs and systems the form offers are already public under `/world` and
 * `/tactics`.
 */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("career");
  return {
    title: t("title"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/career") },
  };
}

export default async function CareerIndexPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcareer");

  const t = await getTranslations("career");
  const tc = await getTranslations("common");
  const [choices, owned] = await Promise.all([serverFetch<CareerOptions>("/careers/options"), serverFetch<CareerList>("/careers")]);
  if (!choices.ok) return <WorldUnavailable message={choices.error.message} title={t("title")} />;
  const options = choices.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulate", label: t("backLabel") }}
        eyebrow={t("eyebrow", { name: user.display_name })}
        lede={t("lede")}
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }}
        title={t("title")}
      />

      <Panel
        eyebrow={t("panelEyebrow", {
          clubs: options.clubs.length,
          systems: options.systems.length,
          kinds: options.objective_kinds.points ? t("objectiveKinds") : t("noObjectiveKinds"),
        })}
        title={t("createCareer")}
      >
        <CareerForm options={options} />
      </Panel>

      <p className="muted">
        {t("challengeLead")} {" "}
        <Link className="world-link" href="/challenges">
          {t("challengeLink")}
        </Link>{" "}
        {t("challengeTail")}
      </p>

      {!owned.ok ? (
        <WorldUnavailable message={owned.error.message} title={t("unavailableTitle")} />
      ) : owned.data.items.length === 0 ? (
        <div className="empty">
          <strong>{t("emptyTitle")}</strong>
          <p className="muted">{t("emptyBody")}</p>
        </div>
      ) : (
        <Panel
          eyebrow={t("seasonsEyebrow", { used: owned.data.items.length, limit: owned.data.limit_per_user })}
          title={t("seasonsTitle")}
        >
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thManager")}</th>
                  <th scope="col">{t("thClub")}</th>
                  <th scope="col">{t("thCompetition")}</th>
                  <th scope="col">{t("thRounds")}</th>
                  <th scope="col">{t("thPlayed")}</th>
                  <th scope="col">{t("thWon")}</th>
                  <th scope="col">{t("thDrawn")}</th>
                  <th scope="col">{t("thLost")}</th>
                  <th scope="col">{t("thGd")}</th>
                  <th scope="col">{t("thPoints")}</th>
                  <th scope="col">{t("thObjectivesMet")}</th>
                  <th scope="col">{tc("status")}</th>
                </tr>
              </thead>
              <tbody>
                {owned.data.items.map((row) => (
                  <tr key={row.id}>
                    <td>
                      <Link className="world-link" href={`/career/${row.slug}`}>
                        {row.manager_name}
                      </Link>
                    </td>
                    <td>{row.club_name}</td>
                    <td className="muted">
                      {row.competition_name || <span className="unavailable">{t("noCompetition")}</span>}
                    </td>
                    <td className="num">{row.rounds_played}</td>
                    <td className="num">{row.record.played}</td>
                    <td className="num">{row.record.won}</td>
                    <td className="num">{row.record.drawn}</td>
                    <td className="num">{row.record.lost}</td>
                    <td className="num">{row.record.goal_difference}</td>
                    <td className="num">{row.record.points}</td>
                    <td className="num">
                      {t("objectivesMet", { met: row.objectives_met, total: row.objectives_total })}
                    </td>
                    <td>
                      <span className={row.status === "active" ? "badge badge--live" : "badge badge--demo"}>{row.status.toUpperCase()}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      )}

      <Provenance provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }} />
    </div>
  );
}
