"use client";

import { useEffect, useRef, useState } from "react";

import { CallNote, useClubCall } from "@/components/ClubTools";
import type { ReportLimits, SessionLimits, TeamView } from "@/lib/club";

/**
 * §41's two writes: the session a team ran, and the question a tenant keeps.
 *
 * Both forms are built from figures the API publishes — `session_limits`, `report_kinds`, `report_limits` —
 * rather than from numbers chosen here, because a page whose own cap disagrees with the door's is a page that
 * teaches a caller to be refused. Where a write is refused, the figure behind the sentence is printed beside
 * it by `CallNote`; and no form paints a written row as the new state, since the runner re-reads the panel
 * from the server instead.
 *
 * Attendance is a checkbox per player on *that* team's sheet, because the door refuses a session naming
 * anybody else: a picker that could offer a player this tenant does not hold would be a form that cannot
 * succeed.
 */
export function SessionRecorder({ ident, limits, teams, today }: { ident: string; limits: SessionLimits | null; teams: TeamView[]; today: string }) {
  const { busy, call, note } = useClubCall();
  const [teamId, setTeamId] = useState(teams[0]?.id ?? "");
  const [date, setDate] = useState(today);
  const [duration, setDuration] = useState("90");
  const [rpe, setRpe] = useState("5");
  const [slot, setSlot] = useState("1");
  const [focus, setFocus] = useState("");
  const [held, setHeld] = useState<string[]>([]);
  const [text, setText] = useState("");

  // The door publishes the day it compares a `scheduled_on` against, and this page is read once but kept open.
  // Until a person types a date of their own, the field follows that published day, so a page opened at 23:58
  // does not walk into the next minute carrying yesterday as its default — the refusal would be true, and
  // avoidable. Once somebody has typed, what they typed is theirs and the door stops overriding it.
  const dateWasTyped = useRef(false);
  useEffect(() => {
    if (!dateWasTyped.current) setDate(today);
  }, [today]);

  const team = teams.find((row) => row.id === teamId) ?? null;
  const squad = team?.squad ?? [];
  const slots = limits ? Array.from({ length: limits.slot_range[1] - limits.slot_range[0] + 1 }, (_, index) => limits.slot_range[0] + index) : [1, 2, 3, 4];
  const toggle = (slug: string) => setHeld((current) => (current.includes(slug) ? current.filter((item) => item !== slug) : [...current, slug]));

  async function record() {
    const done = await call("session-record", `/club/academy/${encodeURIComponent(ident)}/sessions`, {
      body: {
        team: teamId,
        scheduled_on: date.trim(),
        duration_min: Number(duration),
        rpe: Number(rpe),
        slot: Number(slot),
        focus: focus.split(",").map((item) => item.trim()).filter((item) => item.length > 0),
        attendees: held,
        note: text.trim(),
      },
    });
    if (done) {
      // Attendance and the note are cleared, the team and the date stay: a second session in the same week
      // is two keystrokes rather than a form filled in again.
      setHeld([]);
      setText("");
    }
  }

  return (
    <div className="stack">
      <div className="grid grid-2">
        <label className="field">
          <span>Team whose sheet is the register</span>
          <select aria-label="Session team" disabled={busy !== null} onChange={(event) => { setTeamId(event.target.value); setHeld([]); }} value={teamId}>
            {teams.length === 0 && <option value="">no sheet exists yet</option>}
            {teams.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} — {row.squad_size} on the sheet
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Date — work already done, so never in the future</span>
          <input aria-label="Session date" data-session-date={today} disabled={busy !== null} onChange={(event) => { dateWasTyped.current = true; setDate(event.target.value); }} placeholder="2026-09-26" type="text" value={date} />
        </label>

        <label className="field">
          <span>Duration {limits ? `(${limits.duration_range[0]}–${limits.duration_range[1]} minutes)` : "(minutes)"}</span>
          <input aria-label="Session duration" disabled={busy !== null} onChange={(event) => setDuration(event.target.value)} type="text" value={duration} />
        </label>
        <label className="field">
          <span>RPE {limits ? `(${limits.rpe_range[0]}–${limits.rpe_range[1]})` : ""}</span>
          <input aria-label="Session RPE" disabled={busy !== null} onChange={(event) => setRpe(event.target.value)} type="text" value={rpe} />
        </label>
        <label className="field">
          <span>Slot on that date</span>
          <select aria-label="Session slot" disabled={busy !== null} onChange={(event) => setSlot(event.target.value)} value={slot}>
            {slots.map((row) => (
              <option key={row} value={String(row)}>
                slot {row}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Focus areas, comma separated (at most {limits ? limits.session_focus_max : 8})</span>
          <input aria-label="Session focus" disabled={busy !== null} onChange={(event) => setFocus(event.target.value)} placeholder="pressing, transitions" type="text" value={focus} />
        </label>
      </div>
      <label className="field">
        <span>Note (at most {limits ? limits.session_note_max : 280} characters)</span>
        <input aria-label="Session note" disabled={busy !== null} maxLength={limits?.session_note_max} onChange={(event) => setText(event.target.value)} type="text" value={text} />
      </label>

      <div className="stack-sm">
        <span className="muted" style={{ fontSize: "0.84rem" }}>
          Attendance — {held.length} of {squad.length} named, and at most {limits ? limits.attendance_max : 60} may be. A child on this
          sheet still needs their guardian&apos;s yes, which the door checks when the row is written.
        </span>
        <div className="row wrap">
          {squad.map((row) => (
            <label className="chip" key={row.player_id} style={{ gap: "0.4rem" }}>
              <input
                aria-label={`Attendee ${row.name}`}
                checked={held.includes(row.slug)}
                data-testid={`attendee-${row.slug}`}
                disabled={busy !== null}
                onChange={() => toggle(row.slug)}
                type="checkbox"
              />
              <span className="mono" style={{ fontSize: "0.78rem" }}>
                {row.name}
                {row.is_minor ? " (minor)" : ""}
              </span>
            </label>
          ))}
          {squad.length === 0 && <span className="muted">This team has nobody on its sheet yet.</span>}
        </div>
      </div>

      <div className="row wrap">
        <button
          className="btn"
          data-testid="session-record"
          disabled={busy !== null || teamId === "" || date.trim().length === 0 || held.length === 0}
          onClick={() => void record()}
          type="button"
        >
          {busy === "session-record" ? "Recording…" : "Record the session"}
        </button>
        <span className="muted" style={{ fontSize: "0.84rem" }}>
          load_units = duration_min × rpe ÷ 60 — computed by the API on every read, and never sent from here.
        </span>
      </div>
      <CallNote note={note} />
    </div>
  );
}

/**
 * Save a question about the tenant. No figure is sent, because none is stored: the row names a kind, a
 * window and (optionally) a sheet, and the answer is recomputed for whoever reads it afterwards.
 */
export function ReportSaver({ defaultFrom, ident, kinds, limits, teams, today }: { defaultFrom: string; ident: string; kinds: string[]; limits: ReportLimits | null; teams: TeamView[]; today: string }) {
  const { busy, call, note } = useClubCall();
  const [kind, setKind] = useState(kinds[0] ?? "");
  const [from, setFrom] = useState(defaultFrom);
  const [to, setTo] = useState(today);
  const [team, setTeam] = useState("");

  return (
    <div className="stack">
      <div className="grid grid-2">
        <label className="field">
          <span>What to read — the kinds this tier can produce</span>
          <select aria-label="Report kind" disabled={busy !== null} onChange={(event) => setKind(event.target.value)} value={kind}>
            {kinds.map((row) => (
              <option key={row} value={row}>
                {row}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Sheet — a tenant-wide question leaves this empty</span>
          <select aria-label="Report team" disabled={busy !== null} onChange={(event) => setTeam(event.target.value)} value={team}>
            <option value="">every sheet of this tenant</option>
            {teams.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Window start — an ISO date</span>
          <input aria-label="Report window start" disabled={busy !== null} onChange={(event) => setFrom(event.target.value)} placeholder="2026-08-01" type="text" value={from} />
        </label>
        <label className="field">
          <span>Window end — at most {limits ? limits.window_max_days : 366} days after the start</span>
          <input aria-label="Report window end" disabled={busy !== null} onChange={(event) => setTo(event.target.value)} placeholder="2026-09-26" type="text" value={to} />
        </label>
      </div>
      <div className="row wrap">
        <button
          className="btn"
          data-testid="report-save"
          disabled={busy !== null || kind === "" || from.trim().length === 0 || to.trim().length === 0}
          onClick={() => void call("report-save", `/club/academy/${encodeURIComponent(ident)}/reports`, { body: { kind, window_from: from.trim(), window_to: to.trim(), team: team === "" ? null : team } })}
          type="button"
        >
          {busy === "report-save" ? "Saving the question…" : "Save the question"}
        </button>
        <span className="muted" style={{ fontSize: "0.84rem" }}>
          {limits ? `${limits.max_reports_per_organization} reports per tenant` : ""} — and no figure is sent with it: the answer is
          computed when somebody reads it.
        </span>
      </div>
      <CallNote note={note} />
    </div>
  );
}


/**
 * One row's own erase door, with its answer painted in the cell.
 *
 * A refusal is printed as the code and the figure the API answered with rather than a shrug, and a success
 * does not announce the row as deleted: the runner re-reads the table, so the row that is gone is gone
 * because the server says so.
 */
export function EraseRow({ action, label, path, what }: { action: string; label: string; path: string; what: string }) {
  const { busy, call, note } = useClubCall();
  return (
    <span className="stack-sm">
      <button className="btn btn--sm btn--ghost" data-act={action} disabled={busy !== null} onClick={() => void call(action, path, { method: "DELETE" })} type="button">
        {busy === action ? "Erasing…" : label}
      </button>
      {note && (
        <span className="mono" data-note={action} style={{ display: "block", fontSize: "0.74rem" }}>
          {note.refused ? `refused: ${note.figures[0] ?? note.text}` : `${what} erased — the table was re-read`}
        </span>
      )}
    </span>
  );
}

