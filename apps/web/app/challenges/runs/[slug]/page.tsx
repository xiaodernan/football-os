import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { ChallengeRunTools } from "@/components/ChallengeRunTools";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { ChallengeRunView } from "@/lib/types";

import "../../../../styles/tactics.css";
import "../../../../styles/simulate.css";

export const dynamic = "force-dynamic";

/**
 * One run. `noindex` for the same reason the season page is: it is an account's own history with the
 * simulation engine, and a model's scoreline must not be crawlable as if it were a result.
 */
export const metadata: Metadata = {
  title: "Challenge run",
  description: "A live challenge played to its window: the objective, the rounds that count towards it, and the verdict summed from them.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/challenges") },
};

type Props = { params: Promise<{ slug: string }> };

export default async function ChallengeRunPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fchallenges");
  const { slug } = await params;
  if (!slug || slug.length > 80) notFound();

  const result = await serverFetch<ChallengeRunView>(`/challenges/runs/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable message={result.error.message} title="Challenge run" />;
  }

  const view = result.data;
  const career = view.career;
  const record = view.record;
  const verdict = view.verdict;
  const challenge = view.challenge;
  const fixtures = view.fixtures ?? [];
  const next = view.next_fixture;

  if (view.run && !view.run.scenario_known) {
    return (
      <div className="container page stack">
        <WorldHead
          back={{ href: "/challenges", label: "All scenarios" }}
          eyebrow={`${career.manager_name} · private to this account`}
          lede={view.run.note ?? "The scenario this run was started under is no longer in the catalogue."}
          provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }}
          title={`${career.club_name} · unrecognised scenario`}
        />
        <Panel eyebrow="not judged" title="Why this page refuses">
          <div className="stack-sm">
            <p className="notice notice--warn">
              A verdict is computed from the scenario&apos;s own objectives, so when the catalogue no longer contains the scenario, there is nothing to compute it from. The rounds this career played are
              still its own, and <Link className="world-link" href={`/career/${encodeURIComponent(career.slug)}`}>the season page</Link> reads them back.
            </p>
            <p className="muted">
              <span className="mono">catalogue fingerprint: {view.run.fingerprint ?? "none"}</span>
            </p>
          </div>
        </Panel>
        <Provenance provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }} />
      </div>
    );
  }

  const windowRounds = verdict?.window_rounds ?? career.challenge_window ?? 0;
  const used = verdict?.rounds_played ?? career.rounds_played;
  const share = windowRounds > 0 ? Math.min(100, Math.round((used / windowRounds) * 100)) : 0;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/challenges", label: "All scenarios" }}
        eyebrow={`${career.manager_name} · ${challenge?.name ?? "scenario"} · private to this account`}
        lede="The objective below is the scenario's, not yours: it was fixed when the run opened and cannot be moved. Every number beside it is summed from the rounds this run has played, and the window is enforced by the only route that can play a round."
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }}
        title={`${career.club_name} · ${windowRounds}-round window`}
      />

      <Panel eyebrow={verdict ? verdict.status.toUpperCase() : "no verdict"} title="The verdict, as it stands">
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <span className={verdict?.status === "met" ? "badge badge--live" : "badge badge--demo"}>{verdict ? `${verdict.objectives_met} of ${verdict.objectives_total} objectives` : "nothing to judge"}</span>
            <span className="chip mono">
              rounds {used} of {windowRounds}
            </span>
            <span className="chip mono">{verdict ? `${verdict.rounds_remaining} left in the window` : "no window"}</span>
          </div>
          <div aria-label={`rounds used ${used} of ${windowRounds}`} className="bar" role="progressbar">
            <div className={verdict?.status === "missed" ? "bar__fill bar__fill--warn" : "bar__fill"} style={{ width: `${share}%` }} />
          </div>
          <p className="muted">
            {verdict?.closed_by} {verdict?.judged_on}
          </p>
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {(verdict?.objectives ?? []).map((objective) => (
              <li key={objective.kind}>
                <span className={objective.met ? "badge badge--live" : "badge badge--demo"}>{objective.met ? "MET" : "SHORT"}</span> <strong>{objective.label}</strong> — {objective.actual} of {objective.target}
                <div className="muted mono">{objective.formula}</div>
              </li>
            ))}
          </ul>
          {verdict && (
            <p className="notice">
              Reward: <strong>{String(verdict.reward.label)}</strong> — {verdict.reward.earned ? "earned" : "not earned"}. {verdict.reward.reason}{" "}
              <span className="mono">
                {verdict.reward.credits?.toLocaleString("en-GB")} {verdict.reward.credits_units} · {verdict.reward.xp} xp
              </span>
            </p>
          )}
        </div>
      </Panel>

      <Panel eyebrow={challenge ? `${challenge.window}` : "no window"} title="Play it out">
        <div className="stack-sm">
          <ChallengeRunTools available={Boolean(next?.available)} ident={career.slug} status={career.status} windowClosed={Boolean(verdict?.window_closed)} windowRounds={windowRounds} />
          {next?.available ? (
            <p className="muted">
              Next up: round {next.round_index}, {next.side === "home" ? "at home against" : "away at"} {next.opponent_name}
              {next.venue_name ? ` at ${next.venue_name}` : ""}. {next.rotation} The seed for the round is {next.seed}.
            </p>
          ) : (
            <p className="muted">{next?.reason ?? "No further round is scheduled."}</p>
          )}
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow="summed from the rounds below" title="Record inside the window">
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
              ["Budget (set by the scenario)", `${career.budget.toLocaleString("en-GB")} ${career.budget_units}`],
            ]}
          />
          <p className="muted">{view.limitations.budget}</p>
        </Panel>

        <Panel eyebrow={challenge ? `${challenge.constraints.filter((item) => item.enforced).length} of ${challenge.constraints.length} applied` : "no scenario"} title="What the scenario binds, and what it only states">
          <div className="stack-sm">
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {(challenge?.constraints ?? []).map((constraint) => (
                <li key={constraint.key}>
                  <span className={constraint.enforced ? "badge badge--live" : "badge badge--demo"}>{constraint.enforced ? "APPLIED" : "STATED ONLY"}</span> <strong>{constraint.label}</strong>
                  <div className="muted">{constraint.how}</div>
                </li>
              ))}
            </ul>
            <p className="notice notice--warn">{view.limitations.window}</p>
            <p className="notice notice--warn">{view.limitations.reward}</p>
            <KeyValueGrid
              rows={[
                ["Club the scenario gave", career.club_path ? <Link className="world-link" key="club" href={career.club_path}>{career.club_name}</Link> : "the club is no longer in the generated world"],
                ["Competition", career.competition_name || "none"],
                ["Stated philosophy", career.philosophy],
                ["Season page for this run", <Link className="world-link" key="season" href={`/career/${encodeURIComponent(career.slug)}`}>open it</Link>],
              ]}
            />
          </div>
        </Panel>
      </div>

      <Panel eyebrow={`${fixtures.length} of ${windowRounds} rounds`} title="The rounds the verdict is summed from">
        {fixtures.length === 0 ? (
          <div className="empty">
            <strong>No round played yet</strong>
            <p className="muted">Press “Play the next round”: the engine picks the eleven from stored squads, decides the match block by block, and keeps every number it used.</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Round</th>
                  <th scope="col">Fixture</th>
                  <th scope="col">Score</th>
                  <th scope="col">Pts</th>
                  <th scope="col">Digest</th>
                  <th scope="col">Seed</th>
                  <th scope="col">Report</th>
                </tr>
              </thead>
              <tbody>
                {fixtures.map((fixture) => (
                  <tr key={fixture.round_index}>
                    <td className="num">{fixture.round_index}</td>
                    <td>
                      <span className="world-pos">{fixture.side === "home" ? career.club_short : fixture.opponent_short}</span> <span className="muted">vs</span>{" "}
                      <Link className="world-link" href={fixture.opponent_path}>
                        {fixture.side === "home" ? fixture.opponent_short : career.club_short}
                      </Link>
                    </td>
                    <td className="num">
                      {fixture.club_goals}–{fixture.opponent_goals} <span className={fixture.outcome === "W" ? "badge badge--live" : "badge badge--demo"}>{fixture.outcome}</span>
                    </td>
                    <td className="num">{fixture.points}</td>
                    <td className="mono">{fixture.digest}</td>
                    <td className="mono">{fixture.seed}</td>
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

      <Provenance provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }} />
    </div>
  );
}
