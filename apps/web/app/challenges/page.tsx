import type { Metadata } from "next";
import Link from "next/link";
import { redirect } from "next/navigation";

import { Panel } from "@/components/ui";
import { ChallengeStartForm } from "@/components/ChallengeStartForm";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { useTranslations } from "next-intl";
import { getTranslations } from "next-intl/server";
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
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("challenges");
  return {
    title: t("title"),
    description: t("description"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/challenges") },
  };
}

export default async function ChallengesPage() {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fchallenges");
  const t = await getTranslations("challenges");

  const [catalogue, runs] = await Promise.all([serverFetch<ChallengeCatalogue>("/challenges"), serverFetch<ChallengeRunList>("/challenges/runs")]);
  if (!catalogue.ok) {
    return <WorldUnavailable eyebrow={t("title")} message={catalogue.error.message} title={t("title")} />;
  }
  const data = catalogue.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/career", label: t("backLabel") }}
        eyebrow={`${user.display_name}${t("runsPrivateSuffix")}`}
        lede={t("lede")}
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: data.disclaimer }}
        title={t("title")}
      />

      <Panel eyebrow={t("scenariosEyebrow", { total: data.total, fingerprint: data.fingerprint })} title={t("startRunTitle")}>
        <div className="stack-sm">
          {data.integrity.clean ? (
            <p className="notice">
              {t("integrityOk")}{" "}
              <span className="mono">{t("problems", { count: data.integrity.problems.length })}</span>
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
        <WorldUnavailable message={runs.error.message} title={t("yourRunsTitle")} />
      ) : runs.data.items.length === 0 ? (
        <div className="empty">
          <strong>{t("noRunYet")}</strong>
          <p className="muted">{t("noRunYetBody")}</p>
        </div>
      ) : (
        <Panel eyebrow={t("runsUsedEyebrow", { used: runs.data.items.length, limit: runs.data.limit_per_user })} title={t("yourRunsTitle")}>
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("tableScenario")}</th>
                  <th scope="col">{t("tableClub")}</th>
                  <th scope="col">{t("tableRoundsUsed")}</th>
                  <th scope="col">{t("tableObjectives")}</th>
                  <th scope="col">{t("tableReward")}</th>
                  <th scope="col">{t("tableVerdict")}</th>
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
                      {t("playedOfWindow", { played: item.verdict?.rounds_played ?? item.rounds_played, window: item.verdict?.window_rounds ?? "—" })}
                    </td>
                    <td className="num">
                      {item.verdict ? `${item.verdict.objectives_met} of ${item.verdict.objectives_total}` : "—"}
                    </td>
                    <td className="muted">{item.verdict?.reward.earned ? `${String(item.verdict.reward.label)}${t("earnedSuffix")}` : t("notEarned")}</td>
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

      <Panel eyebrow={t("scenariosChooseEyebrow", { total: data.total, competitions: data.competitions.length })} title={t("whatEachTitle")}>
        <div className="tac-cards">
          {data.challenges.map((scenario) => (
            <ScenarioCard key={scenario.slug} scenario={scenario} formulas={data.objective_formulas} />
          ))}
        </div>
      </Panel>

      <Panel eyebrow={t("recomputedEyebrow")} title={t("verdictDecidedTitle")}>
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              [t("kvVerdictStatuses"), data.verdict_statuses.join(" · ")],
              [t("kvWindowEnforcedBy"), <span className="mono" key="w">{data.window_enforced_by}</span>],
              [t("kvRoundsPlayedThrough"), <span className="mono" key="p">{data.play_through}</span>],
              [t("kvRewardUnits"), data.reward_units],
              [t("kvRunsPerAccount"), `${data.max_runs_per_user}`],
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
  const t = useTranslations("challenges");
  const enforced = scenario.constraints.filter((constraint) => constraint.enforced).length;
  return (
    <div className="tac-card">
      <div className="row wrap" style={{ gap: "0.5rem" }}>
        <strong>{scenario.name}</strong>
        <span className="badge badge--demo">{scenario.difficulty.toUpperCase()}</span>
        <span className="chip mono">{t("cardWindow", { rounds: scenario.window_rounds })}</span>
        <span className="chip mono">
          {t("cardConstraints", { enforced, total: scenario.constraints.length })}
        </span>
      </div>
      <p className="muted">{scenario.brief}</p>
      <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
        {scenario.objectives.map((objective) => (
          <li key={objective.kind}>
            <strong>{objective.label}</strong> {t("cardTarget", { target: objective.target })}
            <div className="muted mono">{formulas[objective.kind] ?? t("noFormula")}</div>
          </li>
        ))}
      </ul>
      <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
        {scenario.constraints.map((constraint) => (
          <li key={constraint.key}>
            <span className={constraint.enforced ? "badge badge--live" : "badge badge--demo"}>{constraint.enforced ? t("applied") : t("statedOnly")}</span> <strong>{constraint.label}</strong>
            <div className="muted">{constraint.how}</div>
          </li>
        ))}
      </ul>
      <p className="muted mono">
        {t("cardReward", { label: String(scenario.reward.label), credits: Number(scenario.reward.credits).toLocaleString("en-GB"), units: scenario.budget_units, xp: Number(scenario.reward.xp) })}
      </p>
    </div>
  );
}
