import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";
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
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("challenges");
  return {
    title: t("runTitle"),
    description: t("runDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/challenges") },
  };
}

type Props = { params: Promise<{ slug: string }> };

export default async function ChallengeRunPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fchallenges");
  const t = await getTranslations("challenges");
  const { slug } = await params;
  if (!slug || slug.length > 80) notFound();

  const result = await serverFetch<ChallengeRunView>(`/challenges/runs/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable message={result.error.message} title={t("runTitle")} />;
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
          back={{ href: "/challenges", label: t("runBackLabel") }}
          eyebrow={`${career.manager_name}${t("privateSuffix")}`}
          lede={view.run.note ?? t("unrecognisedLede")}
          provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }}
          title={t("unrecognisedTitle", { club: career.club_name })}
        />
        <Panel eyebrow={t("notJudgedEyebrow")} title={t("refusesTitle")}>
          <div className="stack-sm">
            <p className="notice notice--warn">
              {t("refPre")}
              <Link className="world-link" href={`/career/${encodeURIComponent(career.slug)}`}>{t("refLink")}</Link>
              {t("refPost")}
            </p>
            <p className="muted">
              <span className="mono">{t("catalogueFingerprint", { fp: view.run.fingerprint ?? "none" })}</span>
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
        back={{ href: "/challenges", label: t("runBackLabel") }}
        eyebrow={`${career.manager_name} · ${challenge?.name ?? t("scenarioFallback")}${t("privateSuffix")}`}
        lede={t("verdictLede")}
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }}
        title={t("windowTitle", { club: career.club_name, window: windowRounds })}
      />

      <Panel eyebrow={verdict ? verdict.status.toUpperCase() : t("noVerdict")} title={t("verdictTitle")}>
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <span className={verdict?.status === "met" ? "badge badge--live" : "badge badge--demo"}>{verdict ? t("objectivesCount", { met: verdict.objectives_met, total: verdict.objectives_total }) : t("nothingToJudge")}</span>
            <span className="chip mono">
              {t("roundsChip", { used, window: windowRounds })}
            </span>
            <span className="chip mono">{verdict ? t("leftInWindow", { remaining: verdict.rounds_remaining }) : t("noWindow")}</span>
          </div>
          <div aria-label={t("ariaRoundsUsed", { used, window: windowRounds })} className="bar" role="progressbar">
            <div className={verdict?.status === "missed" ? "bar__fill bar__fill--warn" : "bar__fill"} style={{ width: `${share}%` }} />
          </div>
          <p className="muted">
            {verdict?.closed_by} {verdict?.judged_on}
          </p>
          <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
            {(verdict?.objectives ?? []).map((objective) => (
              <li key={objective.kind}>
                <span className={objective.met ? "badge badge--live" : "badge badge--demo"}>{objective.met ? t("met") : t("short")}</span> <strong>{objective.label}</strong> {t("objectiveActual", { actual: objective.actual, target: objective.target })}
                <div className="muted mono">{objective.formula}</div>
              </li>
            ))}
          </ul>
          {verdict && (
            <p className="notice">
              {t("rewardPrefix")}<strong>{String(verdict.reward.label)}</strong>{verdict.reward.earned ? t("rewardEarned") : t("runNotEarned")} {verdict.reward.reason}{" "}
              <span className="mono">
                {verdict.reward.credits?.toLocaleString("en-GB")} {verdict.reward.credits_units} · {verdict.reward.xp} xp
              </span>
            </p>
          )}
        </div>
      </Panel>

      <Panel eyebrow={challenge ? `${challenge.window}` : t("noWindow")} title={t("playItOutTitle")}>
        <div className="stack-sm">
          <ChallengeRunTools available={Boolean(next?.available)} ident={career.slug} status={career.status} windowClosed={Boolean(verdict?.window_closed)} windowRounds={windowRounds} />
          {next?.available ? (
            <p className="muted">
              {t("nextUp", { round: next.round_index, side: next.side === "home" ? t("sideHome") : t("sideAway"), opponent: next.opponent_name ?? "", venue: next.venue_name ? ` at ${next.venue_name}` : "", rotation: next.basis ?? "", seed: next.seed ?? "" })}
            </p>
          ) : (
            <p className="muted">{next?.reason ?? t("noFurtherRound")}</p>
          )}
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={t("recordEyebrow")} title={t("recordTitle")}>
          <KeyValueGrid
            rows={[
              [t("kvRounds"), `${record.played}`],
              [t("kvWonDrawnLost"), `${record.won} / ${record.drawn} / ${record.lost}`],
              [t("kvGoals"), `${record.goals_for} – ${record.goals_against}`],
              [
                t("kvGoalDifference"),
                <span key="gd">
                  {record.goal_difference} · <span className="mono">{record.goal_difference_formula}</span>
                </span>,
              ],
              [
                t("kvPoints"),
                <span key="pts">
                  {record.points} · <span className="mono">{record.points_formula}</span>
                </span>,
              ],
              [t("kvLongestUnbeaten"), `${record.unbeaten_run}`],
              [t("kvBudgetScenario"), `${career.budget.toLocaleString("en-GB")} ${career.budget_units}`],
            ]}
          />
          <p className="muted">{view.limitations.budget}</p>
        </Panel>

        <Panel eyebrow={challenge ? t("appliedEyebrow", { applied: challenge.constraints.filter((item) => item.enforced).length, total: challenge.constraints.length }) : t("noScenario")} title={t("bindsTitle")}>
          <div className="stack-sm">
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {(challenge?.constraints ?? []).map((constraint) => (
                <li key={constraint.key}>
                  <span className={constraint.enforced ? "badge badge--live" : "badge badge--demo"}>{constraint.enforced ? t("applied") : t("statedOnly")}</span> <strong>{constraint.label}</strong>
                  <div className="muted">{constraint.how}</div>
                </li>
              ))}
            </ul>
            <p className="notice notice--warn">{view.limitations.window}</p>
            <p className="notice notice--warn">{view.limitations.reward}</p>
            <KeyValueGrid
              rows={[
                [t("clubGave"), career.club_path ? <Link className="world-link" key="club" href={career.club_path}>{career.club_name}</Link> : t("clubNoLonger")],
                [t("competition"), career.competition_name || "none"],
                [t("statedPhilosophy"), career.philosophy],
                [t("seasonPageForRun"), <Link className="world-link" key="season" href={`/career/${encodeURIComponent(career.slug)}`}>{t("openIt")}</Link>],
              ]}
            />
          </div>
        </Panel>
      </div>

      <Panel eyebrow={t("roundsEyebrow", { n: fixtures.length, window: windowRounds })} title={t("roundsVerdictTitle")}>
        {fixtures.length === 0 ? (
          <div className="empty">
            <strong>{t("noRoundYet")}</strong>
            <p className="muted">{t("noRoundYetBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tRound")}</th>
                  <th scope="col">{t("tFixture")}</th>
                  <th scope="col">{t("tScore")}</th>
                  <th scope="col">{t("tPts")}</th>
                  <th scope="col">{t("tDigest")}</th>
                  <th scope="col">{t("tSeed")}</th>
                  <th scope="col">{t("tReport")}</th>
                </tr>
              </thead>
              <tbody>
                {fixtures.map((fixture) => (
                  <tr key={fixture.round_index}>
                    <td className="num">{fixture.round_index}</td>
                    <td>
                      <span className="world-pos">{fixture.side === "home" ? career.club_short : fixture.opponent_short}</span> <span className="muted">{t("vs")}</span>{" "}
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
                          {t("openReport")}
                        </Link>
                      ) : (
                        <span className="unavailable">{t("reportDeleted")}</span>
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
