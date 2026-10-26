import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { CareerBoard } from "@/components/CareerBoard";
import { CareerFinance } from "@/components/CareerFinance";
import { CareerTools } from "@/components/CareerTools";
import { LEDGER_COLUMNS, type SeasonLedger } from "@/lib/ledger";
import { KeyValueGrid, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { CareerView } from "@/lib/types";

import "../../../styles/tactics.css";
import "../../../styles/simulate.css";

export const dynamic = "force-dynamic";

export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("careerDetail");
  return {
    title: t("metaTitle"),
    description: t("metaDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/career") },
  };
}

type Props = { params: Promise<{ slug: string }> };

/** The translator next-intl hands back, named once so a child component can take it. */
type CareerTranslator = (key: string, values?: Record<string, string | number | Date>) => string;

export default async function CareerDetailPage({ params }: Props) {
  const t = await getTranslations("careerDetail");
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fcareer");
  const { slug } = await params;
  if (!slug || slug.length > 80) notFound();

  const result = await serverFetch<CareerView>(`/careers/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable message={result.error.message} title={t("unavailableTitle")} />;
  }

  const view = result.data;
  const career = view.career;
  const record = view.record;
  const fixtures = view.fixtures ?? [];
  const next = view.next_fixture;
  const carry = view.carry_over;
  const unit = carry.rows.length > 0 ? carry.rows[carry.rows.length - 1].minutes_units : t("matchMinutes");

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/career", label: t("backLabel") }}
        eyebrow={t("eyebrow", {
          manager: career.manager_name,
          competition: career.competition_name || t("noCompetition"),
          privacy: t("privacyNote"),
        })}
        lede={t("lede")}
        provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }}
        title={`${career.club_name} · ${career.season}`}
      />

      <Panel eyebrow={career.status === "active" ? t("statusOpen") : t("statusRetired")} title={t("playTitle")}>
        <div className="stack-sm">
          <CareerTools available={Boolean(next?.available) && career.status === "active"} ident={career.slug} status={career.status} />
          {next?.available ? (
            <p className="muted">
              {t("nextUp", {
                round: next.round_index,
                venue: next.side === "home" ? t("venueHome") : t("venueAway"),
                opponent: next.opponent_name ?? "",
                at: next.venue_name ? t("atVenue", { venue: next.venue_name }) : "",
                rotation: next.rotation ?? "",
                seed: next.seed ?? 0,
              })}
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
              [t("rowRounds"), `${record.played}`],
              [t("rowWdl"), `${record.won} / ${record.drawn} / ${record.lost}`],
              [t("rowGoals"), `${record.goals_for} – ${record.goals_against}`],
              [
                t("rowGoalDifference"),
                <span key="gd">
                  {record.goal_difference} · <span className="mono">{record.goal_difference_formula}</span>
                </span>,
              ],
              [
                t("rowPoints"),
                <span key="pts">
                  {record.points} · <span className="mono">{record.points_formula}</span>
                </span>,
              ],
              [t("rowUnbeaten"), `${record.unbeaten_run}`],
              [t("rowForm"), record.form.join(" ") || "—"],
              [t("rowBudget"), `${career.budget.toLocaleString("en-GB")} ${career.budget_units}`],
              [
                t("rowBudgetLeft"),
                <Link className="world-link" href={`/career/${encodeURIComponent(career.slug)}/market`} key="market">
                  {t("marketSpendsIt")}
                </Link>,
              ],
            ]}
          />
        </Panel>

        <Panel eyebrow={objectivesSummary(t, view)} title={career.challenge_slug ? t("objectivesScenarioTitle") : t("objectivesYoursTitle")}>
          {career.challenge_slug && (
            <p className="notice">
              {t("challengeNotice", { slug: career.challenge_slug, window: career.challenge_window ?? 0 })}{" "}
              <Link className="world-link" href={`/challenges/runs/${encodeURIComponent(career.slug)}`}>
                {t("openRun")}
              </Link>
            </p>
          )}
          {view.objectives.length === 0 ? (
            <p className="muted">{t("noObjective")}</p>
          ) : (
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {view.objectives.map((objective) => (
                <li key={objective.kind}>
                  <span className={objective.met ? "badge badge--live" : "badge badge--demo"}>{objective.met ? t("met") : t("notYet")}</span>{" "}
                  <strong>{objective.label}</strong> — {t("objectiveProgress", { actual: objective.actual, target: objective.target })}
                  <div className="muted mono">{objective.formula}</div>
                </li>
              ))}
            </ul>
          )}
          <p className="muted">{view.limitations.objectives}</p>
        </Panel>
      </div>

      <CareerBoard t={t} view={view.board} limitation={view.limitations.projections} />

      <CareerFinance t={t} view={view.affordability} limitation={view.limitations.projections} />

      <Panel eyebrow={t("roundsCount", { count: fixtures.length })} title={t("fixtureListTitle")}>
        {fixtures.length === 0 ? (
          <div className="empty">
            <strong>{t("noRoundTitle")}</strong>
            <p className="muted">{t("noRoundBody")}</p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thRound")}</th>
                  <th scope="col">{t("thFixture")}</th>
                  <th scope="col">{t("thScore")}</th>
                  <th scope="col">{t("thVenue")}</th>
                  <th scope="col">{t("thPoints")}</th>
                  <th scope="col">{t("thDigest")}</th>
                  <th scope="col">{t("thSeed")}</th>
                  <th scope="col">{t("thModel")}</th>
                  <th scope="col">{t("thReport")}</th>
                </tr>
              </thead>
              <tbody>
                {fixtures.map((fixture) => (
                  <tr key={fixture.round_index}>
                    <td className="num">{fixture.round_index}</td>
                    <td>
                      <span className="world-pos">{fixture.side === "home" ? career.club_short : fixture.opponent_short}</span>{" "}
                      <span className="muted">{t("vs")}</span>{" "}
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
                          {t("open")}
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

      <Panel
        eyebrow={t("carryEyebrow", { count: carry.carrying_load, round: carry.next_round })}
        title={t("carryTitle")}
      >
        <div className="stack-sm">
          <KeyValueGrid
            rows={[
              [t("rowRoundsTraced"), `${carry.rounds_played} / ${carry.rounds_traced}`],
              [t("rowTraceRows"), t("traceRowsValue", { appearances: carry.appearances, players: carry.players_traced })],
              [
                t("rowLoadWindow"),
                <span key="win">
                  {t("carryDecay", {
                    rounds: carry.window_rounds,
                    decay: carry.decay_per_round,
                  })} ·{" "}
                  <span className="mono">{carry.load_formula}</span>
                </span>,
              ],
              [
                t("rowMeanCondition"),
                <span key="cond">
                  {carry.mean_condition_of_last_xi.toFixed(3)} · <span className="mono">{carry.condition_formula}</span>
                </span>,
              ],
              [
                t("rowSessionsFound"),
                t("tracedPlayers", {
                  found: carry.training_records_found,
                  carrying: carry.carrying_load,
                  formula: carry.reserve_formula,
                }),
              ],
            ]}
          />
          {carry.carrying_load === 0 ? (
            <div className="empty">
              <strong>{t("noLoadTitle")}</strong>
              <p className="muted">{t("noLoadBody", { formula: carry.form_formula })}</p>
            </div>
          ) : (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{t("thPlayer")}</th>
                    <th scope="col">{t("thPosition")}</th>
                    <th scope="col">{t("thRoundsInWindow")}</th>
                    <th scope="col">{t("thMinutesTraced")}</th>
                    <th scope="col">{t("thLoadUnits")}</th>
                    <th scope="col">{t("thTrainingLoad")}</th>
                    <th scope="col">{t("thCondition")}</th>
                  </tr>
                </thead>
                <tbody>
                  {carry.most_loaded.map((entry) => (
                    <tr key={entry.player_id}>
                      <td>{entry.player_name}</td>
                      <td className="muted">{entry.position}</td>
                      <td className="num">{entry.rounds_in_window}</td>
                      <td className="num">
                        {entry.minutes_recent} <span className="muted">{unit}</span>
                      </td>
                      <td className="num">{entry.load_units}</td>
                      <td className="num">{entry.training_load_units}</td>
                      <td className="num mono">
                        {entry.condition.toFixed(3)}
                        {entry.condition <= carry.condition_floor ? <span className="badge badge--demo">{t("atFloor")}</span> : null}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <p className="notice">{carry.note}</p>
          <p className="notice notice--warn">{view.limitations.carry_over}</p>
          <p className="muted">{carry.disclaimer}</p>
        </div>
      </Panel>

      {view.ledger ? <LedgerPanel t={t} ledger={view.ledger} limitation={view.limitations.ledger} /> : null}

      <Panel eyebrow={view.limitations.table} title={t("tableTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">#</th>
                <th scope="col">{t("thClub")}</th>
                <th scope="col">{t("thPlayed")}</th>
                <th scope="col">{t("thGoals")}</th>
                <th scope="col">{t("thGd")}</th>
                <th scope="col">{t("rowPoints")}</th>
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

      <Panel
        eyebrow={
          career.system_path ? (
            <Link href={career.system_path}>{career.system_slug}</Link>
          ) : (
            career.system_slug || t("clubDefault")
          )
        }
        title={t("engineTitle")}
      >
        <div className="stack-sm">
          <p className="notice">{view.limitations.philosophy}</p>
          <p className="notice notice--warn">{view.limitations.budget}</p>
          <KeyValueGrid
            rows={[
              [t("rowModelVersions"), view.model_versions.join(" · ") || t("noneYet")],
              [t("rowStatedPhilosophy"), career.philosophy],
              [t("rowTacticalSystem"), career.system_slug || t("ownFormationDefault")],
              [t("rowClubRow"), career.club_path ? career.club_path : t("clubGone")],
            ]}
          />
        </div>
      </Panel>

      <Provenance provenance={{ data_origin: "simulation", is_demo_data: true, disclaimer: view.disclaimer }} />
    </div>
  );
}

function objectivesSummary(t: CareerTranslator, view: CareerView): string {
  const met = view.objectives.filter((objective) => objective.met).length;
  return t("objectivesMet", { met, total: view.objectives.length });
}

/**
 * The season as `sim_events` answers for it: one row per name the rows could attribute, and the club's
 * totals set beside the figure they have to agree with. Rendered only when the API returned the block —
 * an older server answers a career detail without it, and an empty table would then read as a season of
 * nobody doing anything.
 */
function LedgerPanel({
  t,
  ledger,
  limitation,
}: {
  t: CareerTranslator;
  ledger: SeasonLedger;
  limitation: string;
}) {
  const unattributed = ledger.unattributed.events.ambiguous + ledger.unattributed.events.unnamed;
  return (
    <Panel
      eyebrow={t("ledgerEyebrow", {
        shown: ledger.players_shown,
        total: ledger.players_with_events,
        traced: ledger.fixtures_traced,
        played: ledger.fixtures_played,
      })}
      title={t("ledgerTitle")}
    >
      <div className="stack-sm">
        <KeyValueGrid
          rows={[
            [t("rowGoalsAttemptsXg"), `${ledger.totals.goals} · ${ledger.totals.attempts} · ${ledger.totals.expected_goals.toFixed(3)}`],
            [t("rowCardsInjuries"), `${ledger.totals.yellow_cards} · ${ledger.totals.red_cards} · ${ledger.totals.injuries}`],
            [
              t("rowEventsWithoutPlayer"),
              unattributed
                ? t("unattributedRow", {
                    unattributed,
                    ambiguous: ledger.unattributed.events.ambiguous,
                    unnamed: ledger.unattributed.events.unnamed,
                    names: ledger.unattributed.ambiguous_names.join(", ") || t("noRepeatedName"),
                  })
                : t("everyEventAttributed"),
            ],
            [
              t("rowHowFar"),
              ledger.scope,
            ],
          ]}
        />
        {ledger.players.length === 0 ? (
          <div className="empty">
            <strong>{t("ledgerEmptyTitle")}</strong>
            <p className="muted">
              {ledger.source === "no traced fixture"
                ? t("ledgerEmptyNoRows")
                : t("ledgerEmptyAmbiguous", { traced: ledger.fixtures_traced })}
            </p>
          </div>
        ) : (
          <div className="world-tablewrap">
            <table className="table">
              <thead>
                <tr>
                  <th scope="col">{t("thPlayer")}</th>
                  <th scope="col">{t("thPosition")}</th>
                  {LEDGER_COLUMNS.map((column) => (
                    <th key={column.key} scope="col" title={t(column.hintKey)}>
                      {t(column.labelKey)}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {ledger.players.map((entry) => (
                  <tr key={entry.player_id}>
                    <td>
                      {entry.player_path ? (
                        <Link className="world-link" href={entry.player_path}>
                          {entry.name}
                        </Link>
                      ) : (
                        <span>{entry.name}</span>
                      )}
                    </td>
                    <td className="muted">{entry.position || "—"}</td>
                    {LEDGER_COLUMNS.map((column) => (
                      <td className="num mono" key={column.key}>
                        {column.key === "expected_goals" ? entry[column.key].toFixed(3) : entry[column.key]}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            {ledger.truncated ? (
              <p className="muted">
                {t("ledgerTruncated", { shown: ledger.players_shown, total: ledger.players_with_events })}
              </p>
            ) : null}
          </div>
        )}
        <p className="notice">{ledger.consistency}</p>
        <p className="muted mono">{ledger.formula}</p>
        <p className="muted mono">{ledger.consistency_formula}</p>
        <p className="muted mono">{ledger.attribution_formula}</p>
        <p className="notice notice--warn">{limitation}</p>
        <p className="muted">{ledger.disclaimer}</p>
      </div>
    </Panel>
  );
}
