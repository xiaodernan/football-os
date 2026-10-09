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
    description: "Take charge of a generated club, state an objective, and play the season through the labelled simulation engine.",
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
        back={{ href: "/simulate", label: "Match simulator" }}
        eyebrow={`${user.display_name} · careers are private to this account`}
        lede="One club out of the generated world, one tactical system out of the fifty authored here, and an objective you set before the first round. Each fixture is decided by the same engine the simulator uses, and every figure on the season page is a sum of the rounds it lists."
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: options.disclaimer }}
        title={t("title")}
      />

      <Panel eyebrow={`${options.clubs.length} clubs · ${options.systems.length} authored systems · ${options.objective_kinds.points ? "4 objective kinds" : "no objective kinds"}`} title={t("createCareer")}>
        <CareerForm options={options} />
      </Panel>

      <p className="muted">
        Rather than setting your own target, be judged by one that was fixed before you started:{" "}
        <Link className="world-link" href="/challenges">
          six authored scenarios
        </Link>{" "}
        name the objective, the round window and the reward, and the start route accepts no field for any of them.
      </p>

      {!owned.ok ? (
        <WorldUnavailable message={owned.error.message} title="Your careers" />
      ) : owned.data.items.length === 0 ? (
        <div className="empty">
          <strong>No career opened yet</strong>
          <p className="muted">Nothing is simulated until you press play on a season. The form above offers the choices; the engine decides the results.</p>
        </div>
      ) : (
        <Panel eyebrow={`${owned.data.items.length} of ${owned.data.limit_per_user} used`} title="Your seasons">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Manager</th>
                  <th scope="col">Club</th>
                  <th scope="col">Competition</th>
                  <th scope="col">Rounds</th>
                  <th scope="col">P</th>
                  <th scope="col">W</th>
                  <th scope="col">D</th>
                  <th scope="col">L</th>
                  <th scope="col">GD</th>
                  <th scope="col">Pts</th>
                  <th scope="col">Objectives met</th>
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
                    <td className="muted">{row.competition_name || <span className="unavailable">no competition</span>}</td>
                    <td className="num">{row.rounds_played}</td>
                    <td className="num">{row.record.played}</td>
                    <td className="num">{row.record.won}</td>
                    <td className="num">{row.record.drawn}</td>
                    <td className="num">{row.record.lost}</td>
                    <td className="num">{row.record.goal_difference}</td>
                    <td className="num">{row.record.points}</td>
                    <td className="num">
                      {row.objectives_met} of {row.objectives_total}
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
