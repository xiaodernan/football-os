"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch } from "@/lib/api";
import type { CareerView } from "@/lib/types";

/**
 * What an owner can do with a season: play the next round, stop the season, or delete it.
 *
 * Playing asks the server to run the engine and then **re-reads the page** rather than rendering the
 * response: the record, the table and the objective verdicts are sums the server computes, so the
 * numbers a visitor sees after a round are the ones the next request would also produce. The one
 * thing kept from the response is the round's own line — the score, the opponent and the digest of
 * the match that decided it — which is what a manager looked at the moment they pressed play.
 */
export function CareerTools({ ident, status, available }: { ident: string; status: string; available: boolean }) {
  const router = useRouter();
  const [busy, setBusy] = useState<null | "play" | "retire" | "delete">(null);
  const [error, setError] = useState<string | null>(null);
  const [played, setPlayed] = useState<CareerView | null>(null);

  async function post(path: string, kind: "play" | "retire") {
    setBusy(kind);
    setError(null);
    const result = await browserFetch<CareerView>(`/careers/${encodeURIComponent(ident)}${path}`, { method: "POST" });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(null);
      return;
    }
    if (kind === "play") setPlayed(result.data);
    router.refresh();
    setBusy(null);
  }

  async function remove() {
    setBusy("delete");
    setError(null);
    const result = await browserFetch<{ matches_kept: boolean }>(`/careers/${encodeURIComponent(ident)}`, { method: "DELETE" });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(null);
      return;
    }
    router.push("/career");
    router.refresh();
  }

  const last = played?.fixtures?.[played.fixtures.length - 1];

  return (
    <div className="stack-sm">
      <div className="row wrap" style={{ gap: "0.6rem" }}>
        <button className="btn" disabled={busy !== null || !available} onClick={() => post("/play", "play")} type="button">
          {busy === "play" ? "Playing the round…" : "Play the next round"}
        </button>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={() => post("/retire", "retire")} type="button">
          {busy === "retire" ? "Updating…" : status === "active" ? "Retire from this club" : "Take charge again"}
        </button>
        <button className="btn btn--ghost" disabled={busy !== null} onClick={remove} type="button">
          {busy === "delete" ? "Deleting…" : "Delete this career"}
        </button>
      </div>

      {!available && (
        <p className="notice notice--warn" role="status">
          There is no round to play: the club has no competition to rotate through, or the season is retired.
        </p>
      )}

      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}

      {played && last && (
        <div className="stack-sm" data-testid="career-round" role="status">
          <p className="notice">
            Round {last.round_index} played: {played.career.club_short} {last.club_goals}–{last.opponent_goals} {last.opponent_short} ({last.side},{" "}
            {last.venue_name || "venue unknown"}). {last.outcome === "W" ? "A win is 3 points" : last.outcome === "D" ? "A draw is 1 point" : "A loss is 0 points"} on the
            record, which now reads {played.record.played} played, {played.record.points} points.
          </p>
          <div className="tag-list">
            <span className="chip mono">digest: {last.digest}</span>
            <span className="chip mono">seed: {last.seed}</span>
            <span className="chip mono">model: {last.model_version}</span>
            <span className="chip mono">
              re-check: {played.consistency}
            </span>
          </div>
        </div>
      )}
    </div>
  );
}
