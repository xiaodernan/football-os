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
/**
 * The axis labels the frame draws.
 *
 * The grass is shared by the server pages and the client editors, so the words on it cannot come from
 * this module: a module that reads a catalogue needs to know whether it is rendered on the server or
 * in the browser, and this one is both. So the caller passes the reader's own words in, and a caller
 * that forgets is a type error rather than an English sentence in a Chinese page.
 *
 * `axisOpponent` is the far end — the opponent's goal, and how far up the pitch it is. `axisOwn` is
 * the near end on the flat view, where "up" is up the pitch; `axisOwnScreen` is the near end on the
 * projected view, where "up" is up the screen.
 */
export function PitchFrame({ axisOpponent, axisOwn }: { axisOpponent: string; axisOwn: string }) {
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
        {axisOpponent}
      </text>
      <text className="pitch-axis" x={-HALF} y={PITCH_LENGTH + 4}>
        {axisOwn}
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
  axisOpponent,
  axisOwn,
}: {
  slots: SlotLike[];
  before?: SlotLike[];
  title: string;
  /** The caption is the caller's own sentence about this board, so it has no default to fall back on. */
  caption: string;
  axisOpponent: string;
  axisOwn: string;
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
        <PitchFrame axisOpponent={axisOpponent} axisOwn={axisOwn} />
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
      <figcaption className="pitch__caption muted">{caption}</figcaption>
    </figure>
  );
}

/* ------------------------------------------------------------------ §13's third view: the same metres, projected

Spec §13 asks for 2D **and** 3D. This is the 3D view, and it is a projection rather than a renderer: every point
goes through the two lines below, from the same `x`/`y` metres the board above reads. There is no scene graph and
no dependency, because a picture that could not be recomputed from its numbers would be a second source of truth
— and this project has exactly one rule about those.

The transform is the textbook isometric one, applied to the ground-plane coordinates the 2D view already uses
(`gx = x + 34`, `gy = 105 − y`):

    screen_x = (gx − gy) × cos30 + 105 × cos30
    screen_y = (gx + gy) × sin30

which puts this team's own goal line at the bottom-left and the opponent's at the top-right, so "attacking" still
reads as "up the screen". `ISO_CONSTANTS` rides on the `<svg>` so a reader — and the walk — can recompute any
point from its own metres rather than trusting the drawing.
*/

/** cos 30° and sin 30°, kept as expressions of the angle so the printed formula and the code cannot drift. */
export const ISO_COS30 = Math.cos(Math.PI / 6);
export const ISO_SIN30 = Math.sin(Math.PI / 6);
/** Shifts the projected lawn so its leftmost point sits at x = 0; without it the diamond starts at −91. */
export const ISO_OFFSET_X = PITCH_LENGTH * ISO_COS30;

export const ISO_FORMULA =
  "screen_x = ((x + 34) − (105 − y)) × cos30 + 105 × cos30   ·   screen_y = ((x + 34) + (105 − y)) × sin30";
export const ISO_CONSTANTS = `${ISO_COS30},${ISO_SIN30},${ISO_OFFSET_X}`;
/** The projected diamond's corners are (0, 52.5), (58.89, 86.5), (149.82, 34) and (90.93, 0): x 0…149.82, y 0…86.5. */
export const ISO_VIEWBOX = "-6 -8 162 100";

/** A metre coordinate in the ground plane, projected. The only mapping this view uses. */
export function toIsoX(metresX: number, metresY: number): number {
  return (toX(metresX) - toY(metresY)) * ISO_COS30 + ISO_OFFSET_X;
}

export function toIsoY(metresX: number, metresY: number): number {
  return (toX(metresX) + toY(metresY)) * ISO_SIN30;
}

const iso = (x: number, y: number) => ({ x: toIsoX(x, y), y: toIsoY(x, y) });

/** Four ground-plane corners, projected and closed. A rectangle on the grass is a parallelogram here. */
function isoRectPoints(x0: number, y0: number, x1: number, y1: number): string {
  return [iso(x0, y0), iso(x1, y0), iso(x1, y1), iso(x0, y1)].map((p) => `${p.x.toFixed(2)},${p.y.toFixed(2)}`).join(" ");
}

/**
 * A circle on the grass, sampled rather than converted.
 *
 * A circle in the ground plane is an ellipse in this projection, and working out that ellipse's axes would be a
 * second piece of maths to keep in step with the first. Sampling the circle in metres and projecting each point
 * keeps one transform for the whole drawing — which is the only reason the walk can check any of it.
 */
function isoCirclePath(cx: number, cy: number, r: number, steps = 64): string {
  return `${Array.from({ length: steps }, (_, index) => {
    const angle = (index / steps) * Math.PI * 2;
    const point = iso(cx + Math.cos(angle) * r, cy + Math.sin(angle) * r);
    return `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  }).join(" ")} Z`;
}

/** The penalty arc: the part of the circle around the spot that lies outside the area. */
function isoArcPath(spotY: number, outward: 1 | -1, steps = 40): string {
  const from = Math.acos((PENALTY_DEPTH - PENALTY_SPOT) / CENTRE_CIRCLE);
  return Array.from({ length: steps + 1 }, (_, index) => {
    const angle = from + (index / steps) * (Math.PI - 2 * from);
    const point = iso(Math.cos(angle) * CENTRE_CIRCLE, spotY + outward * Math.sin(angle) * CENTRE_CIRCLE);
    return `${index === 0 ? "M" : "L"} ${point.x.toFixed(2)} ${point.y.toFixed(2)}`;
  }).join(" ");
}

/** Turf, markings, goals and the two captions — the 2D frame's own measurements, projected. */
export function PitchFrame3D({ axisOpponent, axisOwnScreen }: { axisOpponent: string; axisOwnScreen: string }) {
  const near = iso(-HALF, PITCH_LENGTH);
  const far = iso(HALF, 0);
  return (
    <>
      <polygon className="pitch-turf" points={isoRectPoints(-HALF, 0, HALF, PITCH_LENGTH)} />
      {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9].map((band) => {
        const y = band * 10.5;
        const a = iso(-HALF, y);
        const b = iso(HALF, y);
        return <line className="pitch-mow" key={band} x1={a.x} x2={b.x} y1={a.y} y2={b.y} />;
      })}
      <g className="pitch-lines">
        <polygon points={isoRectPoints(-HALF, 0, HALF, PITCH_LENGTH)} />
        {(() => {
          const a = iso(-HALF, PITCH_LENGTH / 2);
          const b = iso(HALF, PITCH_LENGTH / 2);
          return <line x1={a.x} x2={b.x} y1={a.y} y2={b.y} />;
        })()}
        <path d={isoCirclePath(0, PITCH_LENGTH / 2, CENTRE_CIRCLE)} />
        <polygon points={isoRectPoints(-PENALTY_WIDTH / 2, 0, PENALTY_WIDTH / 2, PENALTY_DEPTH)} />
        <polygon points={isoRectPoints(-PENALTY_WIDTH / 2, PITCH_LENGTH - PENALTY_DEPTH, PENALTY_WIDTH / 2, PITCH_LENGTH)} />
        <polygon points={isoRectPoints(-SIX_YARD_WIDTH / 2, 0, SIX_YARD_WIDTH / 2, SIX_YARD_DEPTH)} />
        <polygon points={isoRectPoints(-SIX_YARD_WIDTH / 2, PITCH_LENGTH - SIX_YARD_DEPTH, SIX_YARD_WIDTH / 2, PITCH_LENGTH)} />
        <path d={isoArcPath(PENALTY_SPOT, 1)} />
        <path d={isoArcPath(PITCH_LENGTH - PENALTY_SPOT, -1)} />
      </g>
      <g className="pitch-goals">
        <polygon points={isoRectPoints(-GOAL_WIDTH / 2, -2, GOAL_WIDTH / 2, 0)} />
        <polygon points={isoRectPoints(-GOAL_WIDTH / 2, PITCH_LENGTH, GOAL_WIDTH / 2, PITCH_LENGTH + 2)} />
      </g>
      <g className="pitch-spots">
        <circle cx={iso(0, PITCH_LENGTH / 2).x} cy={iso(0, PITCH_LENGTH / 2).y} r={0.5} />
        <circle cx={iso(0, PENALTY_SPOT).x} cy={iso(0, PENALTY_SPOT).y} r={0.5} />
        <circle cx={iso(0, PITCH_LENGTH - PENALTY_SPOT).x} cy={iso(0, PITCH_LENGTH - PENALTY_SPOT).y} r={0.5} />
      </g>
      <text className="pitch-axis" x={far.x} y={far.y - 2.5}>
        {axisOpponent}
      </text>
      <text className="pitch-axis" x={near.x} y={near.y + 4}>
        {axisOwnScreen}
      </text>
    </>
  );
}

/**
 * One player, projected.
 *
 * The metres are published beside the projected point on purpose: a check that compared two projected numbers
 * with each other would pass on a drawing that had drifted as a whole. `data-metres-x`/`-y` are what the walk
 * recomputes *from*, using the constants the same `<svg>` carries.
 */
export function PlayerMarker3D({ slot, index = 0 }: { slot: SlotLike; index?: number }) {
  const point = iso(slot.x, slot.y);
  return (
    <g
      className={`pitch-dot pitch-dot--${slot.band}`}
      data-index={index}
      data-iso-x={point.x.toFixed(2)}
      data-iso-y={point.y.toFixed(2)}
      data-metres-x={slot.x}
      data-metres-y={slot.y}
      data-role={slot.role}
    >
      <circle cx={point.x} cy={point.y} r={2.9} />
      <text className="pitch-label" x={point.x} y={point.y + 1.1}>
        {slot.role}
      </text>
    </g>
  );
}

/** The third view as a figure: the projected frame plus the projected eleven. */
export function Pitch3D({
  slots,
  title,
  caption,
  axisOpponent,
  axisOwnScreen,
}: {
  slots: SlotLike[];
  title: string;
  caption: string;
  axisOpponent: string;
  axisOwnScreen: string;
}) {
  return (
    <figure className="pitch">
      <svg aria-label={title} data-iso-constants={ISO_CONSTANTS} role="img" viewBox={ISO_VIEWBOX} preserveAspectRatio="xMidYMid meet">
        <PitchFrame3D axisOpponent={axisOpponent} axisOwnScreen={axisOwnScreen} />
        {slots.map((slot, index) => (
          <PlayerMarker3D index={index} key={`${slot.role}-${index}`} slot={slot} />
        ))}
      </svg>
      <figcaption className="pitch__caption muted">{caption}</figcaption>
    </figure>
  );
}
