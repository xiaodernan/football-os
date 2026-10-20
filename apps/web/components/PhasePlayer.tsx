"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

import { PITCH_VIEWBOX, PitchFrame, PlayerMarker, toX, toY } from "@/components/pitch";
import type { BoardSlot } from "@/lib/types";

/**
 * The phase player: the two stored boards of one tactical system, with a control that walks between
 * them (spec §13 "animation").
 *
 * The honest constraint, stated on screen as well as here: a project stores two arrangements — in
 * possession and out of it — and nothing in between. Every intermediate frame is therefore a linear
 * interpolation between those two, i.e. a *simulation* of a transition, not a recorded sequence, and
 * it is badged that way. The endpoints are the measured boards; the labels, positions and the
 * transform sentence all come from the same payload the metrics were computed from.
 */

const CYCLE_MS = 1600;

function lerp(from: BoardSlot, to: BoardSlot, t: number): BoardSlot {
  return {
    ...to,
    x: Math.round((from.x + (to.x - from.x) * t) * 100) / 100,
    y: Math.round((from.y + (to.y - from.y) * t) * 100) / 100,
  };
}

export function PhasePlayer({ inPhase, outPhase, transform }: { inPhase: BoardSlot[]; outPhase: BoardSlot[]; transform: string }) {
const tt = useTranslations("tactics");
  const [progress, setProgress] = useState(0);
  const [playing, setPlaying] = useState(false);
  const frame = useRef<number | null>(null);
  const started = useRef(0);
  const offset = useRef(0);

  const matched = inPhase.length === outPhase.length && inPhase.length > 0;

  useEffect(() => {
    if (!playing) return;
    started.current = performance.now();
    const tick = (now: number) => {
      const elapsed = now - started.current + offset.current;
      const cycle = elapsed % (CYCLE_MS * 2);
      // Triangle wave: up to their goal line and back, so the loop reads as a phase change.
      const raw = cycle > CYCLE_MS ? 2 - cycle / CYCLE_MS : cycle / CYCLE_MS;
      setProgress(Math.round(raw * 1000) / 1000);
      frame.current = requestAnimationFrame(tick);
    };
    frame.current = requestAnimationFrame(tick);
    return () => {
      if (frame.current !== null) cancelAnimationFrame(frame.current);
      offset.current = performance.now() - started.current + offset.current;
    };
  }, [playing]);

  if (!matched) {
    return (
      <p className="notice notice--warn">
        {tt("phasesDiffer", { inPhase: inPhase.length, outPhase: outPhase.length })}
      </p>
    );
  }

  const shown = inPhase.map((from, index) => lerp(from, outPhase[index], progress));
  const at =
    progress <= 0.001
      ? tt("inPossession")
      : progress >= 0.999
        ? tt("outOfPossession")
        : tt("percentOfWay", { value: Math.round(progress * 100) });

  return (
    <div className="stack-sm">
      <svg aria-label={tt("boardAria")} role="img" viewBox={PITCH_VIEWBOX} preserveAspectRatio="xMidYMid meet">
        <PitchFrame />
        <g className="pitch-path">
          {inPhase.map((from, index) =>
            from.x === shown[index].x && from.y === shown[index].y ? null : (
              <line key={`trail-${from.role}-${index}`} x1={toX(from.x)} x2={toX(shown[index].x)} y1={toY(from.y)} y2={toY(shown[index].y)} />
            ),
          )}
        </g>
        {shown.map((slot, index) => (
          <PlayerMarker index={index} key={`player-${slot.role}-${index}`} slot={slot} />
        ))}
      </svg>

      <div className="between wrap" style={{ gap: "0.6rem" }}>
        <button
          className="btn btn--sm"
          onClick={() => setPlaying((current) => !current)}
          type="button"
          aria-pressed={playing}
        >
          {playing ? tt("pause") : tt("playPhaseChange")}
        </button>
        <label className="row grow" style={{ gap: "0.5rem", minWidth: 0 }}>
          <span className="eyebrow">{tt("scrub")}</span>
          <input
            aria-label={tt("scrubAria")}
            className="pitch-scrub"
            max={100}
            min={0}
            onChange={(event) => {
              setPlaying(false);
              setProgress(Number(event.target.value) / 100);
            }}
            type="range"
            value={Math.round(progress * 100)}
          />
        </label>
        <span className="chip" data-testid="phase-label">
          {at}
        </span>
        <span
          className="badge badge--sim"
          title={tt("simulationTitle")}
        >
          {tt("simulation")}
        </span>
      </div>

      <p className="muted world-section-note">
        {tt("simulationNote", { count: inPhase.length, transform })}
      </p>
    </div>
  );
}
