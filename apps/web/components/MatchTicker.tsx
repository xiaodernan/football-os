"use client";

import { useTranslations } from "next-intl";
import { useEffect, useRef, useState } from "react";

import { Panel } from "@/components/ui";
import type { SimEvent } from "@/lib/types";

/**
 * The replay ticker: the stored timeline played back minute by minute.
 *
 * The clock runs faster than the football did — one second of wall time per match minute —
 * and every event whose minute has arrived appears in the feed, with the score line tracking
 * the goal events only. This is a replay of stored rows, not a broadcast: the play head moves
 * through a list the engine already wrote, and the pause button is the honesty control.
 */
export function MatchTicker({
  events,
  minutes,
  sourceNote,
  finalScore,
  homeShort,
  awayShort,
  byType,
}: {
  events: SimEvent[];
  minutes: number;
  sourceNote: string;
  finalScore: { home: number; away: number };
  homeShort: string;
  awayShort: string;
  byType: Record<string, number>;
}) {
  const t = useTranslations("live");
  const [minute, setMinute] = useState(0);
  const [playing, setPlaying] = useState(false);
  const timer = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!playing) return;
    timer.current = setInterval(() => {
      setMinute((current) => {
        if (current >= minutes) {
          setPlaying(false);
          return minutes;
        }
        return current + 1;
      });
    }, 1000);
    return () => {
      if (timer.current) clearInterval(timer.current);
    };
  }, [playing, minutes]);

  const shown = events.filter((event) => event.minute <= minute);
  const goals = shown.filter((event) => event.type === "goal");
  const homeGoals = goals.filter((event) => event.side === "home").length;
  const awayGoals = goals.filter((event) => event.side === "away").length;
  const finished = minute >= minutes;

  return (
    <div className="stack">
      <Panel eyebrow={t("tickerEyebrow")} title={t("tickerTitle")}>
        <div className="stack-sm">
          <div className="sim-possession" aria-live="polite">
            <span className="num mono" style={{ fontSize: "1.2rem" }}>
              {homeShort}
            </span>
            <span className="num mono" style={{ fontSize: "1.6rem" }} data-testid="live-score">
              {homeGoals} – {awayGoals}
            </span>
            <span className="num mono" style={{ fontSize: "1.2rem" }}>
              {awayShort}
            </span>
          </div>
          <div className="row wrap" style={{ gap: "0.6rem", alignItems: "center" }}>
            <span className="chip num mono" data-testid="live-minute">
              {finished ? t("fullTime") : `${minute}′`}
            </span>
            <button
              className="btn btn--primary btn--sm"
              onClick={() => setPlaying(!playing)}
              type="button"
              disabled={finished}
            >
              {finished ? t("replayAgain") : playing ? t("pause") : minute > 0 ? t("resume") : t("kickOff")}
            </button>
            <button
              className="btn btn--ghost btn--sm"
              onClick={() => {
                setPlaying(false);
                setMinute(0);
              }}
              type="button"
              disabled={minute === 0}
            >
              {t("restart")}
            </button>
          </div>
          <p className="muted world-section-note">{t("tickerNote")}</p>
        </div>
      </Panel>

      <Panel eyebrow={t("feedEyebrow", { count: shown.length })} title={t("feedTitle")}>
        {shown.length === 0 ? (
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {t("feedEmpty")}
          </p>
        ) : (
          <ul className="list" data-testid="live-feed">
            {[...shown].reverse().map((event, index) => (
              <li className="list__item" key={`${event.minute}-${event.type}-${index}`}>
                <span className="chip num mono">{event.minute}′</span>
                <div className="grow">
                  <span style={{ fontSize: "0.9rem" }}>
                    {event.type === "goal" && <strong>{t("eventGoal")} — </strong>}
                    {event.player ? `${event.player} (${event.team})` : event.team}
                  </span>
                  <span className="muted" style={{ fontSize: "0.82rem", display: "block" }}>
                    {event.detail}
                  </span>
                </div>
              </li>
            ))}
          </ul>
        )}
      </Panel>

      <Panel eyebrow={t("indexEyebrow")} title={t("indexTitle")}>
        <dl className="world-kv">
          {Object.entries(byType).map(([type, count]) => (
            <div className="world-kv__row" key={type}>
              <dt>{type}</dt>
              <dd className="mono">{count}</dd>
            </div>
          ))}
        </dl>
        <p className="muted world-section-note" style={{ marginTop: "0.7rem" }}>
          {t("finalScoreNote", { home: finalScore.home, away: finalScore.away })}
        </p>
      </Panel>
    </div>
  );
}
