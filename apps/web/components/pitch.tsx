import type { BoardSlot } from "@/lib/types";

import "../styles/tactics.css";

/**
 * The pitch, drawn from metres — shared by the server pages and the client editors.
 *
 * The `viewBox` is the lawn itself: 68 × 105 (Law 1), so a player plotted at `{x: 26, y: 24}` is
 * 26 m across and 24 m up from this team's own goal line, and a ruler on the screen measures the
 * distance the API's metrics claim. Screen coordinates: `x = metres + 34` (this team's left is on
 * the left), `y = 105 − metres` (own goal line at the bottom, attacking upward).
 *
 * `PitchFrame`, `PlayerMarker` and the mapping functions are exported so the draggable board and the
 * phase player draw the same grass with the same markings. Two copies of those numbers is how a
 * picture and a measurement would start meaning different things.
 */

/** What a dot needs: a role to label it, a band to colour it, and a position in metres. */
export type SlotLike = Pick<BoardSlot, "role" | "band" | "x" | "y">;

export const PITCH_WIDTH = 68;
export const PITCH_LENGTH = 105;
const HALF = PITCH_WIDTH / 2;

/** Law 1 measurements, in metres. */
const PENALTY_DEPTH = 16.5;
const PENALTY_WIDTH = 40.32;
const SIX_YARD_DEPTH = 5.5;
const SIX_YARD_WIDTH = 18.32;
const CENTRE_CIRCLE = 9.15;
const PENALTY_SPOT = 11;
const GOAL_WIDTH = 7.32;

export const toX = (metres: number) => metres + HALF;
export const toY = (metres: number) => PITCH_LENGTH - metres;

/** The arc the centre circle draws outside each penalty area. */
const arcHalfWidth = Math.sqrt(CENTRE_CIRCLE ** 2 - (PENALTY_DEPTH - PENALTY_SPOT) ** 2);
/** A quadratic's apex sits halfway between its chord and its control point, so double the bulge. */
const arcBulge = CENTRE_CIRCLE - PENALTY_SPOT;

export const PITCH_VIEWBOX = `${-HALF - 4} -3 ${PITCH_WIDTH + 8} ${PITCH_LENGTH + 14}`;

/** A screen point back into metres, snapped to the half-metre the metrics are quoted to. */
export function snapToGrass(x: number, y: number): { x: number; y: number } {
  const metres = { x: x - HALF, y: PITCH_LENGTH - y };
  return {
    x: Math.max(-HALF, Math.min(HALF, Math.round(metres.x * 2) / 2)),
    y: Math.max(0, Math.min(PITCH_LENGTH, Math.round(metres.y * 2) / 2)),
  };
}

/** Turf, markings, goals and the two captions. No players, no behaviour. */
export function PitchFrame() {
  return (
    <>
      <rect className="pitch-turf" x={-HALF} y={0} width={PITCH_WIDTH} height={PITCH_LENGTH} rx={1.5} />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((band) => (
        <line className="pitch-mow" key={band} x1={-HALF} x2={HALF} y1={band * 10.5} y2={band * 10.5} />
      ))}
      <g className="pitch-lines">
        <rect x={-HALF} y={0} width={PITCH_WIDTH} height={PITCH_LENGTH} />
        <line x1={-HALF} x2={HALF} y1={PITCH_LENGTH / 2} y2={PITCH_LENGTH / 2} />
        <circle cx={0} cy={PITCH_LENGTH / 2} r={CENTRE_CIRCLE} />
        <rect x={-PENALTY_WIDTH / 2} y={0} width={PENALTY_WIDTH} height={PENALTY_DEPTH} />
        <rect x={-PENALTY_WIDTH / 2} y={PITCH_LENGTH - PENALTY_DEPTH} width={PENALTY_WIDTH} height={PENALTY_DEPTH} />
        <rect x={-SIX_YARD_WIDTH / 2} y={0} width={SIX_YARD_WIDTH} height={SIX_YARD_DEPTH} />
        <rect x={-SIX_YARD_WIDTH / 2} y={PITCH_LENGTH - SIX_YARD_DEPTH} width={SIX_YARD_WIDTH} height={SIX_YARD_DEPTH} />
        <path d={`M ${-arcHalfWidth} ${PENALTY_DEPTH} Q 0 ${PENALTY_DEPTH + 2 * arcBulge} ${arcHalfWidth} ${PENALTY_DEPTH}`} />
        <path
          d={`M ${-arcHalfWidth} ${PITCH_LENGTH - PENALTY_DEPTH} Q 0 ${PITCH_LENGTH - PENALTY_DEPTH - 2 * arcBulge} ${arcHalfWidth} ${PITCH_LENGTH - PENALTY_DEPTH}`}
        />
      </g>
      <g className="pitch-goals">
        <rect x={-GOAL_WIDTH / 2} y={-2} width={GOAL_WIDTH} height={2} />
        <rect x={-GOAL_WIDTH / 2} y={PITCH_LENGTH} width={GOAL_WIDTH} height={2} />
      </g>
      <g className="pitch-spots">
        <circle cx={0} cy={PITCH_LENGTH / 2} r={0.5} />
        <circle cx={0} cy={toY(PENALTY_SPOT)} r={0.5} />
        <circle cx={0} cy={PITCH_LENGTH - toY(PENALTY_SPOT)} r={0.5} />
      </g>
      <text className="pitch-axis" x={-HALF} y={-1}>
        opponent&apos;s goal · 105 m up the pitch
      </text>
      <text className="pitch-axis" x={-HALF} y={PITCH_LENGTH + 4}>
        own goal line · 0 m — the team attacks upward
      </text>
    </>
  );
}

export function PlayerMarker({
  slot,
  index = 0,
  hollow = false,
  ring = false,
  grabbable = false,
  onPointerDown,
}: {
  slot: SlotLike;
  index?: number;
  hollow?: boolean;
  ring?: boolean;
  grabbable?: boolean;
  onPointerDown?: (index: number, event: React.PointerEvent) => void;
}) {
  return (
    <g
      className={`pitch-dot pitch-dot--${slot.band} ${hollow ? "pitch-dot--ghost" : ""} ${grabbable ? "pitch-dot--grabbable" : ""}`}
      data-index={index}
      data-role={slot.role}
      onPointerDown={onPointerDown ? (event) => onPointerDown(index, event) : undefined}
    >
      {ring && <circle cx={toX(slot.x)} cy={toY(slot.y)} r={4.6} className="pitch-ring" />}
      <circle cx={toX(slot.x)} cy={toY(slot.y)} r={hollow ? 2.3 : 2.9} />
      <text x={toX(slot.x)} y={toY(slot.y) + (hollow ? 0.9 : 1.1)} className={hollow ? "pitch-label pitch-label--ghost" : "pitch-label"}>
        {slot.role}
      </text>
    </g>
  );
}

function Markers({
  slots,
  hollow = false,
  ring = false,
  grabbable = false,
  onPointerDown,
}: {
  slots: SlotLike[];
  hollow?: boolean;
  ring?: boolean;
  grabbable?: boolean;
  onPointerDown?: (index: number, event: React.PointerEvent) => void;
}) {
  return (
    <>
      {slots.map((slot, index) => (
        <PlayerMarker
          grabbable={grabbable}
          hollow={hollow}
          index={index}
          key={`${hollow ? "before" : "after"}-${slot.role}-${index}`}
          onPointerDown={onPointerDown}
          ring={ring}
          slot={slot}
        />
      ))}
    </>
  );
}

export function Pitch({
  slots,
  before,
  title,
  caption,
}: {
  slots: SlotLike[];
  before?: SlotLike[];
  title: string;
  caption?: string;
}) {
  const moved = before
    ? slots.map((slot, index) => ({ slot, from: before[index] })).filter((pair) => pair.from && (pair.from.x !== pair.slot.x || pair.from.y !== pair.slot.y))
    : [];
  return (
    <figure className="pitch">
      <svg aria-label={title} role="img" viewBox={PITCH_VIEWBOX} preserveAspectRatio="xMidYMid meet">
        <defs>
          <marker id="pitch-arrow" markerHeight="6" markerWidth="6" orient="auto" refX="5" refY="3" viewBox="0 0 6 6">
            <path d="M 0 0 L 6 3 L 0 6 z" />
          </marker>
        </defs>
        <PitchFrame />
        {moved.length > 0 && (
          <g className="pitch-moves">
            {moved.map(({ slot, from }) => (
              <line key={`move-${slot.role}-${toY(from.y)}`} markerEnd="url(#pitch-arrow)" x1={toX(from.x)} x2={toX(slot.x)} y1={toY(from.y)} y2={toY(slot.y)} />
            ))}
          </g>
        )}
        {before && <Markers hollow slots={before} />}
        <Markers ring={moved.length > 0} slots={slots} />
      </svg>
      <figcaption className="pitch__caption muted">{caption ?? `${slots.length} positions · metres, 68 × 105 (Law 1) · attack upward`}</figcaption>
    </figure>
  );
}
