"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";
import Link from "next/link";

import { browserFetch } from "@/lib/api";
import type { CareerView, ChallengeVerdict } from "@/lib/types";

type ClosedDetail = { code?: string; message?: string; rounds_played?: number; window_rounds?: number; verdict?: ChallengeVerdict };

/**
 * What an owner can do with a run: play its next round, or delete it.
 *
 * Playing goes through `POST /api/v1/careers/{ident}/play` — the career route, not a challenge route —
 * because a run *is* a career and there is exactly one path that can play a round. That is also the path
 * that enforces the window, so this component has to be ready for `409 window_closed`: the scenario
 * finishing, which is the run's last word rather than an error with nothing to read. The API puts the
 * final verdict beside that code precisely so the page can print it.
 *
 * After a round the page is **re-read** rather than rendered from the response: the record, the fixture
 * list and the verdict are sums the server computes, so what a visitor sees is what the next request
 * would also produce.
 *
 * Once the run's own verdict reports the window closed the button stops offering a round. That is a
 * courtesy, not the mechanism — the enforcement is the 409 the route answers, which is why the evidence
 * walk asks for the refused round anyway.
 */
export function ChallengeRunTools({ ident, status, available, windowClosed, windowRounds }: { ident: string; status: string; available: boolean; windowClosed: boolean; windowRounds: number }) {
  const t = useTranslations("challenges");
  const router = useRouter();
  const [busy, setBusy] = useState<null | "play" | "delete">(null);
  const [error, setError] = useState<string | null>(null);
  const [closed, setClosed] = useState<ClosedDetail | null>(null);
  const [played, setPlayed] = useState<CareerView | null>(null);

  async function play() {
    setBusy("play");
    setError(null);
    const result = await browserFetch<CareerView>(`/careers/${encodeURIComponent(ident)}/play`, { method: "POST" });
    if (!result.ok) {
      const detail = (result.error.details ?? {}) as ClosedDetail;
      if (detail.code === "window_closed") setClosed(detail);
      else setError(`${result.error.code}: ${result.error.message}`);
      setBusy(null);
      return;
    }
    setPlayed(result.data);
    router.refresh();
    setBusy(null);
  }

  async function remove() {
    setBusy("delete");
    setError(null);
    const result = await browserFetch<null>(`/careers/${encodeURIComponent(ident)}`, { method: "DELETE" });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(null);
      return;
    }
    router.push("/challenges");
    router.refresh();
  }

  const last = played?.fixtures?.[played.fixtures.length - 1];
  const verdict = played?.challenge_verdict;
  // The server's own `window_closed`, not a count this component keeps: the page is told the window is
  // used up, and a refused round from the route says the same thing.
  const windowStopped = windowClosed || Boolean(closed);
  const stopped = windowStopped || !available || status !== "active";

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" disabled={busy !== null || stopped} onClick={play} type="button">
          {busy === "play" ? t("playButtonBusy") : t("playButton")}
        </button>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={remove} type="button">
          {busy === "delete" ? t("deleteButtonBusy") : t("deleteButton")}
        </button>
      </div>

      {windowStopped && !closed && (
        <p className="notice notice--warn" role="status">
          {t("windowStoppedNotice", { n: windowRounds })}
        </p>
      )}

      {!available && status === "active" && !windowStopped && (
        <p className="notice notice--warn" role="status">
          {t("noRoundNotice", { n: windowRounds })}
        </p>
      )}

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}

      {closed && (
        <div className="stack-sm" data-testid="challenge-window" role="status">
          <p className="notice notice--warn">
            {t("closedPrefix", { message: closed.message ?? "" })}
            {closed.verdict
              ? t("closedVerdict", { met: closed.verdict.objectives_met, total: closed.verdict.objectives_total, reward: closed.verdict.reward.earned ? t("earned") : t("notEarned") })
              : t("closedNoVerdict")}
          </p>
          {closed.verdict && (
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {closed.verdict.objectives.map((objective) => (
                <li key={objective.kind}>
                  <span className={objective.met ? "badge badge--live" : "badge badge--demo"}>{objective.met ? t("metMissed") : t("missed")}</span> {objective.label} {t("objectiveActual", { actual: objective.actual, target: objective.target })}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {played && last && (
        <div className="stack-sm" data-testid="challenge-round" role="status">
          <p className="notice">
            {t("playedPre", { idx: last.round_index, club: played.career.club_short, cg: last.club_goals, og: last.opponent_goals, opp: last.opponent_short, played: played.record.played, points: played.record.points })}
            {verdict ? t("playedWindow", { used: verdict.rounds_played, window: verdict.window_rounds, remaining: verdict.rounds_remaining }) : ""}
          </p>
          <div className="tag-list">
            <span className="chip mono">{t("digestChip", { digest: last.digest })}</span>
            <span className="chip mono">{t("seedChip", { seed: last.seed })}</span>
            <span className="chip mono">{t("statusChip", { status: verdict?.status ?? t("noVerdictReturned") })}</span>
          </div>
          <Link className="world-link" href={`/career/${encodeURIComponent(ident)}`}>
            {t("seeSeason")}
          </Link>
        </div>
      )}
    </div>
  );
}
