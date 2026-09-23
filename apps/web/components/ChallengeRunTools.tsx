"use client";

import { useRouter } from "next/navigation";
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
          {busy === "play" ? "Playing the round…" : "Play the next round"}
        </button>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={remove} type="button">
          {busy === "delete" ? "Deleting…" : "Delete this run"}
        </button>
      </div>

      {windowStopped && !closed && (
        <p className="notice notice--warn" role="status">
          The window closed at {windowRounds} rounds, so there is no round left to ask for. The run page still reads its verdict from the rounds it played.
        </p>
      )}

      {!available && status === "active" && !windowStopped && (
        <p className="notice notice--warn" role="status">
          The engine has no round to offer: this club has no competition to rotate through. The window is not the reason — it closes at {windowRounds} rounds.
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
            {closed.message} The window is enforced by the route that plays a round, so there is no other door to try.{" "}
            {closed.verdict
              ? `Final verdict: ${closed.verdict.objectives_met} of ${closed.verdict.objectives_total} objectives, and the reward is ${closed.verdict.reward.earned ? "earned" : "not earned"}.`
              : "No verdict came back with it, so nothing here pretends to have re-derived one."}
          </p>
          {closed.verdict && (
            <ul className="stack-sm" style={{ listStyle: "none", padding: 0 }}>
              {closed.verdict.objectives.map((objective) => (
                <li key={objective.kind}>
                  <span className={objective.met ? "badge badge--live" : "badge badge--demo"}>{objective.met ? "MET" : "MISSED"}</span> {objective.label} — {objective.actual} of {objective.target}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {played && last && (
        <div className="stack-sm" data-testid="challenge-round" role="status">
          <p className="notice">
            Round {last.round_index} played: {played.career.club_short} {last.club_goals}–{last.opponent_goals} {last.opponent_short}. The record now reads {played.record.played} played,{" "}
            {played.record.points} points. {verdict ? `${verdict.rounds_played} of ${verdict.window_rounds} rounds used, ${verdict.rounds_remaining} left in the window.` : ""}
          </p>
          <div className="tag-list">
            <span className="chip mono">digest: {last.digest}</span>
            <span className="chip mono">seed: {last.seed}</span>
            <span className="chip mono">status: {verdict?.status ?? "no verdict returned"}</span>
          </div>
          <Link className="world-link" href={`/career/${encodeURIComponent(ident)}`}>
            see the season this run is played in
          </Link>
        </div>
      )}
    </div>
  );
}
