"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useRef, useState } from "react";

import { PITCH_VIEWBOX, PitchFrame, PlayerMarker, snapToGrass } from "@/components/pitch";
import { browserFetch, errorMessage } from "@/lib/api";
import type { BoardDetail, BoardMetrics, BoardPositions } from "@/lib/types";

/**
 * The board editor: drag the eleven, save, share (spec §13, §21, §65's "drag/draw/save/share").
 *
 * Two deliberate limits. First, the numbers on the right are **the server's**, from the last save —
 * they are not recomputed in the browser while you drag, because the formulas are a property of the
 * backend's geometry code and a second implementation would be free to disagree with the page that
 * cites it. The panel says when what is on screen is stale. Second, nothing here pretends a saved
 * arrangement is football knowledge: it is the user's drawing, labelled `data_origin: user`.
 */

type Phase = "in" | "out";

function zoneOf(x: number, y: number): string {
  return `${x >= 0 ? "+" : "-"}${Math.abs(x).toFixed(1)},${y.toFixed(1)}`;
}

export function BoardEditor({ board: initial }: { board: BoardDetail }) {
  const router = useRouter();
  const t = useTranslations("common");
  const tb = useTranslations("tactics");
  const svg = useRef<SVGSVGElement | null>(null);
  const [board, setBoard] = useState(initial);
  const [phase, setPhase] = useState<Phase>("in");
  const [dragging, setDragging] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [status, setStatus] = useState<{ kind: "ok" | "error"; text: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const positions: BoardPositions[] = phase === "in" ? board.phase_in : board.phase_out;

  function move(index: number, x: number, y: number) {
    setBoard((current) => {
      const key = phase === "in" ? "phase_in" : "phase_out";
      const next = current[key].map((row, rowIndex) => (rowIndex === index ? { ...row, x, y, zone: zoneOf(x, y) } : row));
      return { ...current, [key]: next };
    });
    setDirty(true);
  }

  function pointToMetres(event: React.PointerEvent): { x: number; y: number } | null {
    const element = svg.current;
    if (!element) return null;
    const ctm = element.getScreenCTM();
    if (!ctm) return null;
    const cursor = element.createSVGPoint();
    cursor.x = event.clientX;
    cursor.y = event.clientY;
    const local = cursor.matrixTransform(ctm.inverse());
    return { x: local.x, y: local.y };
  }

  async function send(path: string, init: { method?: string; body?: unknown } = {}) {
    setBusy(true);
    const result = await browserFetch<BoardDetail | { share_url?: string | null; visibility?: string }>(path, init);
    setBusy(false);
    if (!result.ok) {
      const problems = (result.error as unknown as { details?: { problems?: string[] } })?.details?.problems;
      setStatus({ kind: "error", text: problems?.length ? problems.join(" · ") : errorMessage(result.error, tb("boardSaveFailed")) });
      return null;
    }
    return result.data;
  }

  async function save() {
    const saved = await send(`/boards/${encodeURIComponent(board.slug)}`, {
      method: "PATCH",
      body: { phase_in: board.phase_in, phase_out: board.phase_out },
    });
    if (saved && "slug" in saved) {
      setBoard(saved as BoardDetail);
      setDirty(false);
      setStatus({ kind: "ok", text: tb("boardSaved") });
    }
  }

  async function derive() {
    const saved = await send(`/boards/${encodeURIComponent(board.slug)}`, { method: "PATCH", body: { phase_in: board.phase_in, derive_block: true } });
    if (saved && "slug" in saved) {
      setBoard(saved as BoardDetail);
      setPhase("out");
      setDirty(false);
      setStatus({ kind: "ok", text: tb("blockDerived") });
    }
  }

  async function share() {
    const result = await send(`/boards/${encodeURIComponent(board.slug)}/share`, { method: "POST" });
    if (result && "share_url" in result) {
      setBoard((current) => ({ ...current, share_url: result.share_url ?? current.share_url, visibility: "shared" }));
      setStatus({ kind: "ok", text: `Sharing is on. Anyone with the link can read this board; nobody can change it.` });
    }
  }

  async function revoke() {
    const result = await send(`/boards/${encodeURIComponent(board.slug)}/revoke`, { method: "POST" });
    if (result && "share_url" in result) {
      setBoard((current) => ({ ...current, share_url: null, visibility: "private" }));
      setStatus({ kind: "ok", text: tb("linkRevoked") });
    }
  }

  async function remove() {
    const gone = await send(`/boards/${encodeURIComponent(board.slug)}`, { method: "DELETE" });
    if (gone !== null) router.push("/tactics/boards");
  }

  async function resetToAuthored() {
    if (!board.origin_system) return;
    const source = await browserFetch<{ phase_in: BoardPositions[]; phase_out: BoardPositions[] }>(`/tactics/${encodeURIComponent(board.origin_system)}`);
    if (!source.ok) {
      setStatus({ kind: "error", text: errorMessage(source.error, tb("systemReReadFailed")) });
      return;
    }
    setBoard((current) => ({ ...current, phase_in: source.data.phase_in, phase_out: source.data.phase_out }));
    setDirty(true);
    setStatus({ kind: "ok", text: tb("positionsReset") });
  }

  const shown: BoardMetrics[] = phase === "in" ? board.metrics_in : board.metrics_out;

  return (
    <div className="stack">
      <div className="tac-boards">
        <svg
          aria-label={tb("boardEditorAria", { name: board.name, phase: phase === "in" ? tb("phaseInLower") : tb("phaseOutLower") })}
          onPointerUp={() => setDragging(null)}
          onPointerLeave={() => setDragging(null)}
          onPointerMove={(event) => {
            if (dragging === null) return;
            event.preventDefault();
            const metres = pointToMetres(event);
            if (!metres) return;
            const snapped = snapToGrass(metres.x, metres.y);
            move(dragging, snapped.x, snapped.y);
          }}
          preserveAspectRatio="xMidYMid meet"
          ref={svg}
          role="img"
          style={{ touchAction: "none" }}
          viewBox={PITCH_VIEWBOX}
        >
          <PitchFrame axisOpponent={tb("pitchAxisOpponent")} axisOwn={tb("pitchAxisOwn")} />
          {positions.map((slot, index) => (
            <PlayerMarker
              grabbable
              index={index}
              key={`${slot.role}-${index}`}
              onPointerDown={(index) => {
                setDragging(index);
                setCopied(false);
              }}
              ring={dragging === index}
              slot={slot}
            />
          ))}
        </svg>

        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.4rem" }}>
            <span className="eyebrow">{tb("editing")}</span>
            <button className={`chip ${phase === "in" ? "chip--accent" : ""}`} onClick={() => setPhase("in")} type="button">
              {tb("inPossession")}
            </button>
            <button className={`chip ${phase === "out" ? "chip--accent" : ""}`} onClick={() => setPhase("out")} type="button">
              {tb("outOfPossession")}
            </button>
          </div>

          <div className="row wrap" style={{ gap: "0.4rem" }}>
            <button className="btn btn--primary btn--sm" disabled={busy || !dirty} onClick={save} type="button">
              {busy ? `${t("save")}…` : dirty ? tb("saveBoard") : tb("saved")}
            </button>
            <button className="btn btn--sm" disabled={busy} onClick={derive} type="button">
              {tb("deriveFromThis")}
            </button>
            {board.origin_system && (
              <button className="btn btn--ghost btn--sm" disabled={busy} onClick={resetToAuthored} type="button">
                {tb("resetTo", { system: board.origin_system })}
              </button>
            )}
          </div>

          <div className="row wrap" style={{ gap: "0.4rem" }}>
            {board.share_url ? (
              <>
                <a className="chip" href={board.share_url} target="_blank">
                  {board.share_url.replace("/tactics/shared/", "link " + "").slice(0, 28)}…
                </a>
                <button
                  className="btn btn--ghost btn--sm"
                  onClick={() => {
                    if (!navigator.clipboard) {
                      setStatus({ kind: "error", text: tb("copyLinkManual") });
                      return;
                    }
                    void navigator.clipboard.writeText(`${window.location.origin}${board.share_url}`);
                    setCopied(true);
                  }}
                  type="button"
                >
                  {copied ? tb("copied") : tb("copyLink")}
                </button>
                <button className="btn btn--sm" disabled={busy} onClick={revoke} type="button">
                  {tb("revokeLink")}
                </button>
              </>
            ) : (
              <button className="btn btn--sm" disabled={busy} onClick={share} type="button">
                {tb("createShareLink", { create: t("create") })}
              </button>
            )}
            <button className="btn btn--danger btn--sm" disabled={busy} onClick={remove} type="button">
              {tb("deleteBoard", { delete: t("delete") })}
            </button>
          </div>

          {status && (
            <p className={`notice ${status.kind === "error" ? "notice--warn" : ""}`} role="status">
              {status.text}
            </p>
          )}

          <p className="muted world-section-note">
            {dirty ? tb("unsavedChanges") : tb("positionsSaved")}{" "}
            {tb("measurementsNote")}
          </p>
        </div>
      </div>

      <div className="world-tablewrap">
        <table className="table">
          <thead>
            <tr>
              <th scope="col">{tb("thMeasure")}</th>
              <th scope="col">{tb("thValue")}</th>
              <th scope="col">{tb("thHowObtained")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((metric) => (
              <tr key={metric.key}>
                <td>{metric.label}</td>
                <td className="num mono">
                  {metric.value.toFixed(2)} {metric.unit}
                </td>
                <td className="tac-formula">{metric.formula}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
