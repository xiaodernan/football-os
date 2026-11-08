"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CareerCup, CareerCupRun, CareerCupTie, CareerView } from "@/lib/types";

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * The career's cup run (M13 Phase 8 item 32).
 *
 * The bracket is the world's own knockout draw, so this panel prints what the API read from
 * `real_matches` rather than offering a choice of opponents: the next tie, the side, the venue and the
 * prize it pays. Playing one posts to `/careers/{slug}/cup` and then re-reads the page, so the tie list
 * and the balance are the server's rows and not this component's guess.
 *
 * A cup tie is not a league round: the round counter does not move, and the panel says so beside the
 * record. A career the world did not enter, a season the world drew no cup for and a challenge career
 * each print the reason the API gave instead of a disabled button with no explanation.
 */
export function CareerCup({ ident, view, limitation }: { ident: string; view: CareerCup; limitation: string }) {
  const t = useTranslations("careerDetail");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [played, setPlayed] = useState<CareerCupTie | null>(null);

  const statusLabel = (run: CareerCupRun) =>
    run.status === "live"
      ? t("cupStatusLive")
      : run.status === "won"
        ? t("cupStatusWon")
        : run.status === "eliminated"
          ? t("cupStatusEliminated")
          : t("cupStatusUnavailable");

  async function play(cup: string) {
    setBusy(cup);
    setError(null);
    setPlayed(null);
    const result = await browserFetch<CareerView & { tie: CareerCupTie }>(`/careers/${encodeURIComponent(ident)}/cup`, {
      method: "POST",
      body: { cup },
    });
    if (!result.ok) {
      setError(`${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`);
      setBusy(null);
      return;
    }
    setPlayed(result.data.tie);
    router.refresh();
    setBusy(null);
  }

  return (
    <Panel eyebrow={t("cupEyebrow", { season: view.season })} title={t("cupTitle")}>
      <div className="stack-sm">
        <p className="muted">{t("cupIntro")}</p>

        {!view.available || view.runs.length === 0 ? (
          <div className="empty">
            <strong>{t("cupNoRunTitle")}</strong>
            <p className="muted">{view.reason ?? t("cupNoRunBody")}</p>
          </div>
        ) : (
          view.runs.map((run) => (
            <div className="stack-sm" data-testid="career-cup-run" key={run.cup_slug}>
              <KeyValueGrid
                rows={[
                  [t("cupKvCup"), run.cup_name],
                  [t("cupKvStatus"), statusLabel(run)],
                  [t("cupKvStage"), t("cupStageValue", { stage: run.stage.label, index: run.stage.index, of: run.stage.of })],
                  [
                    t("cupKvRecord"),
                    t("cupRecordValue", {
                      played: run.record.played,
                      won: run.record.won,
                      lost: run.record.lost,
                      goals: run.record.goals_for,
                      against: run.record.goals_against,
                    }),
                  ],
                  [t("cupKvPrizes"), t("cupPrizeTotal", { amount: money(run.prizes.total), rows: run.prizes.rows })],
                  [t("cupKvGates"), t("cupGateTotal", { amount: money(run.gates.total), rows: run.gates.rows })],
                ]}
              />

              {run.next ? (
                <div className="stack-sm" data-testid="career-cup-next">
                  <strong>{t("cupNextTitle")}</strong>
                  <p className="muted">
                    {t("cupNextLine", {
                      stage: run.next.stage,
                      side: run.next.side === "home" ? t("cupSideHome") : t("cupSideAway"),
                      opponent: run.next.opponent_name,
                      venue: run.next.venue_name || t("cupVenueUnknown"),
                    })}
                  </p>
                  <p className="mono muted">{run.next.basis}</p>
                  <p className="notice">{t("cupPrizeNotice", { amount: money(prizeFor(run.next.stage_index)) })}</p>
                  {run.next.side === "home" && run.next.stage !== "Final" ? (
                    <p className="notice">{t("cupGateNotice")}</p>
                  ) : null}
                  <button className="button" disabled={busy !== null} onClick={() => play(run.cup_slug)} type="button">
                    {busy === run.cup_slug ? t("cupPlaying") : t("cupPlay")}
                  </button>
                </div>
              ) : (
                <p className="notice">{run.reason ?? (run.status === "won" ? t("cupWonNotice") : t("cupOverNotice"))}</p>
              )}

              {run.ties.length > 0 ? (
                <div className="world-tablewrap">
                  <table className="table">
                    <thead>
                      <tr>
                        <th scope="col">{t("cupThStage")}</th>
                        <th scope="col">{t("cupThTie")}</th>
                        <th scope="col">{t("cupThScore")}</th>
                        <th scope="col">{t("cupThResult")}</th>
                        <th scope="col">{t("cupThPrize")}</th>
                        <th scope="col">{t("cupThGate")}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {run.ties.map((tie) => (
                        <tr key={tie.id}>
                          <td>{tie.stage}</td>
                          <td>
                            <span className="world-pos">{tie.side === "home" ? t("cupSideHomeShort") : t("cupSideAwayShort")}</span>{" "}
                            {tie.opponent_name}
                            <div className="muted mono">{tie.venue_name}</div>
                          </td>
                          <td className="num">
                            {tie.club_goals}–{tie.opponent_goals}
                            {tie.decided_by === "penalties" ? <div className="muted">{t("cupPenalties")}</div> : null}
                          </td>
                          <td>
                            <span className={tie.outcome === "W" ? "badge badge--live" : "badge badge--demo"}>{tie.outcome}</span>
                          </td>
                          <td className="num">
                            {tie.prize ? `${money(tie.prize.amount)} ${tie.prize.units}` : "—"}
                          </td>
                          <td className="num">
                            {tie.gate ? `${money(tie.gate.amount)} ${tie.gate.units}` : "—"}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mono muted">{t("cupFormulaLabel")}: {run.formula}</p>
                </div>
              ) : null}
            </div>
          ))
        )}

        {played ? (
          <p className="notice" data-testid="career-cup-played" role="status">
            {t("cupTiePlayed", {
              stage: played.stage,
              club: played.side === "home" ? t("cupSideHomeShort") : t("cupSideAwayShort"),
              goals: played.club_goals,
              against: played.opponent_goals,
              opponent: played.opponent_name,
              outcome: played.outcome,
            })}
          </p>
        ) : null}

        {error ? (
          <p className="notice notice--warn" role="status">
            {error}
          </p>
        ) : null}

        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}

/** The prize a stage pays, mirrored from `market.CUP_PRIZE_BY_STAGE` so the panel can promise it. */
function prizeFor(stageIndex: number): number {
  return stageIndex === 1 ? 40_000 : stageIndex === 2 ? 90_000 : 220_000;
}
