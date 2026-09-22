import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { CareerTools } from "@/components/CareerTools";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CareerView } from "@/lib/types";

import "../../../styles/tactics.css";
import "../../../styles/simulate.css";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Season",
  description: "One career's rounds, the record summed from them, and the objectives it is judged against.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/career") },
};

type Props = { params: Promise<{ slug: string }> };

export default async function CareerDetailPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcareer");
  const { slug } = await params;
  if (!slug || slug.length > 80) notFound();

  const result = await serverFetch<CareerView>(`/careers/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable message={result.error.message} title="Season" />;
  }

  const view = result.data;
  const career = view.career;
  const record = view.record;
  const fixtures = view.fixtures ?? [];
  const next = view.next_fixture;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/career", label: "All careers" }}
        eyebrow={`${career.manager_name} · ${career.competition_name || "no competition"} · private to this account`}
        lede="Every number below is summed from the rounds this career has played, and each one prints the formula it used. The results come from the labelled simulation engine — no fixture here reports a real match."
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }}
        title={`${career.club_name} · ${career.season}`}
      />

      <Panel eyebrow={career.status === "active" ? "the season is open" : "retired"} title="Play it out">
        <div className="stack-sm">
          <CareerTools available={Boolean(next?.available) && career.status === "active"} ident={career.slug} status={career.status} />
          {next?.available ? (
            <p className="muted">
              Next up: round {next.round_index}, {next.side === "home" ? "at home against" : "away at"} {next.opponent_name}
              {next.venue_name ? ` at ${next.venue_name}` : ""}. {next.rotation} The seed for the round is {next.seed}, which is derived from the career and the round number
              before the engine is asked anything.
            </p>
          ) : (
            <p className="muted">{next?.reason ?? "No further round is scheduled."}</p>
          )}
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow="summed from the rounds listed below" title="Record">
          <KeyValueGrid
            rows={[
              ["Rounds", `${record.played}`],
              ["Won / drawn / lost", `${record.won} / ${record.drawn} / ${record.lost}`],
              ["Goals", `${record.goals_for} – ${record.goals_against}`],
              [
                "Goal difference",
                <span key="gd">
                  {record.goal_difference} · <span className="mono">{record.goal_difference_formula}</span>
                </span>,
              ],
              [
                "Points",
                <span key="pts">
                  {record.points} · <span className="mono">{record.points_formula}</span>
                </span>,
              ],
              ["Longest unbeaten run", `${record.unbeaten_run}`],
              ["Form (oldest first)", record.form.join(" ") || "—"],
              ["Budget (stated, unspent)", `${career.budget.toLocaleString("en-GB")} ${career.budget_units}`],
            ]}
          />
        </Panel>

        <Panel eyebrow={`${objectivesSummary(view)}`} title="Objectives you set">
          {view.objectives.length === 0 ? (
            <p className="muted">No objective is stored on this career, so nothing below can be called success.</p>
          ) : (
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {view.objectives.map((objective) => (
                <li key={objective.kind}>
                  <span className={objective.met ? "badge badge--live" : "badge badge--demo"}>{objective.met ? "MET" : "NOT YET"}</span>{" "}
                  <strong>{objective.label}</strong> — {objective.actual} of {objective.target}
                  <div className="muted mono">{objective.formula}</div>
                </li>
              ))}
            </ul>
          )}
          <p className="muted">{view.limitations.objectives}</p>
        </Panel>
      </div>

      <Panel eyebrow={`${fixtures.length} rounds`} title="The fixture list">
        {fixtures.length === 0 ? (
          <div className="empty">
            <strong>No round played yet</strong>
            <p className="muted">Press “Play the next round” above: the engine will pick the eleven from stored squads and keep every number it used.</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Round</th>
                  <th scope="col">Fixture</th>
                  <th scope="col">Score</th>
                  <th scope="col">Venue</th>
                  <th scope="col">Pts</th>
                  <th scope="col">Digest</th>
                  <th scope="col">Seed</th>
                  <th scope="col">Model</th>
                  <th scope="col">Report</th>
                </tr>
              </thead>
              <tbody>
                {fixtures.map((fixture) => (
                  <tr key={fixture.round_index}>
                    <td className="num">{fixture.round_index}</td>
                    <td>
                      <span className="world-pos">{fixture.side === "home" ? career.club_short : fixture.opponent_short}</span>{" "}
                      <span className="muted">vs</span>{" "}
                      <Link className="world-link" href={fixture.opponent_path}>
                        {fixture.side === "home" ? fixture.opponent_short : career.club_short}
                      </Link>
                    </td>
                    <td className="num">
                      {fixture.club_goals}–{fixture.opponent_goals} <span className={fixture.outcome === "W" ? "badge badge--live" : "badge badge--demo"}>{fixture.outcome}</span>
                    </td>
                    <td className="muted">{fixture.venue_name || "—"}</td>
                    <td className="num">{fixture.points}</td>
                    <td className="mono">{fixture.digest}</td>
                    <td className="mono">{fixture.seed}</td>
                    <td className="mono muted">{fixture.model_version}</td>
                    <td>
                      {fixture.match_path ? (
                        <Link className="world-link" href={fixture.match_path}>
                          open
                        </Link>
                      ) : (
                        <span className="unavailable">report deleted</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <p className="muted">{view.consistency}</p>
      </Panel>

      <Panel eyebrow={view.limitations.table} title="Table of the clubs this career has met">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">Club</th>
                <th scope="col">Played</th>
                <th scope="col">Goals</th>
                <th scope="col">GD</th>
                <th scope="col">Points</th>
              </tr>
            </thead>
            <tbody>
              {view.table.map((row) => (
                <tr key={row.club_id ?? row.name}>
                  <td className="num">{row.position}</td>
                  <td>
                    {row.is_career_club ? <strong>{row.name}</strong> : <span>{row.name}</span>}{" "}
                    <span className="muted">({row.short_name})</span>
                  </td>
                  <td className="num">{row.played}</td>
                  <td className="num">
                    {row.goals_for}–{row.goals_against}
                  </td>
                  <td className="num">{row.goal_difference}</td>
                  <td className="num">{row.points}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <Panel eyebrow={career.system_path ? <Link href={career.system_path}>{career.system_slug}</Link> : career.system_slug || "club default"} title="What the engine was told, and what it was not">
        <div className="stack-sm">
          <p className="notice">{view.limitations.philosophy}</p>
          <p className="notice notice--warn">{view.limitations.budget}</p>
          <KeyValueGrid
            rows={[
              ["Model versions", view.model_versions.join(" · ") || "none yet"],
              ["Stated philosophy", career.philosophy],
              ["Tactical system", career.system_slug || "the club's own formation default"],
              ["Club row in the world", career.club_path ? career.club_path : "the club is no longer in the generated world"],
            ]}
          />
        </div>
      </Panel>

      <Provenance provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }} />
    </div>
  );
}

function objectivesSummary(view: CareerView): string {
  const met = view.objectives.filter((objective) => objective.met).length;
  return `${met} of ${view.objectives.length} met`;
}
