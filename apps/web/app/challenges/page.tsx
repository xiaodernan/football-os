import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { ChallengeStartForm } from "@/components/ChallengeStartForm";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { ChallengeCatalogue, ChallengeEntry, ChallengeRunList } from "@/lib/types";

import "../../styles/tactics.css";
import "../../styles/simulate.css";

export const dynamic = "force-dynamic";

/**
 * The scenario catalogue is authored fiction and the API serves it without a session; this page is not
 * published, because the same screen also starts a run and lists this account's verdicts. So it is
 * `noindex`, disallowed in robots.ts and absent from the sitemap, exactly like `/career` and `/simulate`.
 */
export const metadata: Metadata = {
  title: "Manager live challenges",
  description: "Six authored scenarios — a round window the engine enforces, goals you cannot move, and a verdict summed from the run's own fixtures.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/challenges") },
};

export default async function ChallengesPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fchallenges");

  const [catalogue, runs] = await Promise.all([serverFetch<ChallengeCatalogue>("/challenges"), serverFetch<ChallengeRunList>("/challenges/runs")]);
  if (!catalogue.ok) {
    return <WorldUnavailable eyebrow="Manager live challenges" message={catalogue.error.message} title="Manager live challenges" />;
  }
  const data = catalogue.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/career", label: "Career mode" }}
        eyebrow={`${user.display_name} · your runs are private to this account`}
        lede="A scenario picks the club, fixes the goal and closes the window; the engine plays the rounds. Nothing about a challenge is stored except which scenario it is and how many rounds it allows — the verdict, the goal and the reward are recomputed from the run's own fixtures every time you read it."
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: data.disclaimer }}
        title="Manager live challenges"
      />

      <Panel eyebrow={`${data.total} scenarios · catalogue ${data.fingerprint}`} title="Start a run">
        <div className="stack-sm">
          {data.integrity.clean ? (
            <p className="notice">
              The catalogue passes its own integrity check: every scenario has a window of at least one round, at least one objective, an objective kind the build can measure, and a reward with a name.{" "}
              <span className="mono">problems: {data.integrity.problems.length}</span>
            </p>
          ) : (
            <ul className="notice notice--warn">
              {data.integrity.problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
          <ChallengeStartForm catalogue={data} />
        </div>
      </Panel>

      {!runs.ok ? (
        <WorldUnavailable message={runs.error.message} title="Your runs" />
      ) : runs.data.items.length === 0 ? (
        <div className="empty">
          <strong>No run started yet</strong>
          <p className="muted">Nothing is simulated until you start one and press play on its rounds. The form above chooses a club and a system; the scenario chooses the goal and the window.</p>
        </div>
      ) : (
        <Panel eyebrow={`${runs.data.items.length} of ${runs.data.limit_per_user} used`} title="Your runs">
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">Scenario</th>
                  <th scope="col">Club</th>
                  <th scope="col">Rounds used</th>
                  <th scope="col">Objectives</th>
                  <th scope="col">Reward</th>
                  <th scope="col">Verdict</th>
                </tr>
              </thead>
              <tbody>
                {runs.data.items.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link className="world-link" href={`/challenges/runs/${item.slug}`}>
                        {item.challenge_name}
                      </Link>
                    </td>
                    <td>{item.club_name}</td>
                    <td className="num">
                      {item.verdict?.rounds_played ?? item.rounds_played} of {item.verdict?.window_rounds ?? "—"}
                    </td>
                    <td className="num">
                      {item.verdict ? `${item.verdict.objectives_met} of ${item.verdict.objectives_total}` : "—"}
                    </td>
                    <td className="muted">{item.verdict?.reward.earned ? `${String(item.verdict.reward.label)} · earned` : "not earned"}</td>
                    <td>
                      <span className={item.verdict?.status === "met" ? "badge badge--live" : "badge badge--demo"}>{(item.verdict?.status ?? "unknown").toUpperCase()}</span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="muted">{runs.data.items.length > 0 ? runs.data.items[0].verdict?.judged_on : ""}</p>
        </Panel>
      )}

      <Panel eyebrow={`${data.total} scenarios · ${data.competitions.length} competitions to choose a weakest club from`} title="What each scenario asks for">
        <div className="tac-cards">
          {data.challenges.map((scenario) => (
            <ScenarioCard key={scenario.slug} scenario={scenario} formulas={data.objective_formulas} />
          ))}
        </div>
      </Panel>

      <Panel eyebrow="recomputed on every read" title="How a verdict is decided">
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              ["Verdict statuses", data.verdict_statuses.join(" · ")],
              ["Window enforced by", <span className="mono" key="w">{data.window_enforced_by}</span>],
              ["Rounds are played through", <span className="mono" key="p">{data.play_through}</span>],
              ["Reward units", data.reward_units],
              ["Runs per account", `${data.max_runs_per_user}`],
            ]}
          />
          <p className="notice">{data.how_a_verdict_is_decided}</p>
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {Object.entries(data.limitations).map(([key, sentence]) => (
              <li className="muted" key={key}>
                <span className="mono">{key}</span> — {sentence}
              </li>
            ))}
          </ul>
        </div>
      </Panel>

      <Provenance provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: data.disclaimer }} />
    </div>
  );
}

/**
 * One scenario, with the two facts a reader cannot get from a heading: which of its constraints the
 * build actually applies, and the formula each objective will be compared against.
 */
function ScenarioCard({ scenario, formulas }: { scenario: ChallengeEntry; formulas: Record<string, string> }) {
  const enforced = scenario.constraints.filter((constraint) => constraint.enforced).length;
  return (
    <div className="tac-card">
      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <strong>{scenario.name}</strong>
        <span className="badge badge--demo">{scenario.difficulty.toUpperCase()}</span>
        <span className="chip mono">window: {scenario.window_rounds} rounds</span>
        <span className="chip mono">
          constraints applied: {enforced} of {scenario.constraints.length}
        </span>
      </div>
      <p className="muted">{scenario.brief}</p>
      <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
        {scenario.objectives.map((objective) => (
          <li key={objective.kind}>
            <strong>{objective.label}</strong> — target {objective.target}
            <div className="muted mono">{formulas[objective.kind] ?? "no formula published for this kind"}</div>
          </li>
        ))}
      </ul>
      <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
        {scenario.constraints.map((constraint) => (
          <li key={constraint.key}>
            <span className={constraint.enforced ? "badge badge--live" : "badge badge--demo"}>{constraint.enforced ? "APPLIED" : "STATED ONLY"}</span> <strong>{constraint.label}</strong>
            <div className="muted">{constraint.how}</div>
          </li>
        ))}
      </ul>
      <p className="muted mono">
        reward: {String(scenario.reward.label)} · {Number(scenario.reward.credits).toLocaleString("en-GB")} {scenario.budget_units} · {Number(scenario.reward.xp)} xp
      </p>
    </div>
  );
}
