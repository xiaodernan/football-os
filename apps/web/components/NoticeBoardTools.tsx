"use client";

import Link from "next/link";
import { useState } from "react";

import { CallNote, useClubCall } from "@/components/ClubTools";
import type { AnnouncementCaps, AnnouncementList, AnnouncementRow } from "@/lib/club";

/**
 * §39's Communication row: a board of notices, each posted to an audience, with its readership beside it.
 *
 * The panel is shaped by one decision in the tier. A notice stores an **audience**, never a recipient, so every
 * readership figure on this screen is arithmetic over the roster as it stands — `recipients` is the active
 * memberships the predicate selects *now*, and `read_by` counts only receipts whose account is still among them.
 * That gives the page a check it can actually fail: `unread` is `recipients` minus `read_by` over the two figures
 * printed on the same row, so the page subtracts them itself and says whether the door's third figure holds.
 *
 * Nothing here chooses a number. The audience list, the two length ceilings and the pin ceiling all come from
 * `announcement_caps`; the filter links go through the door (`?audience=`), never through a client-side narrowing
 * of the rows already on screen, because a page that filtered locally would report a `total` the server never said.
 *
 * The "I have read it" button stays live on a notice whose audience does not select the caller. `not_an_audience`
 * is a published refusal with a sentence that explains the predicate, and a disabled button would hide the rule
 * the tier exists to teach.
 */
export function NoticeBoard({ audience, caps, ident, list }: { audience: string | null; caps: AnnouncementCaps; ident: string; list: AnnouncementList }) {
  const { busy, call, note } = useClubCall();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [chosen, setChosen] = useState(list.role === "parent" ? caps.audiences.find((word) => word === "parents") ?? caps.audiences[0] : caps.audiences[0]);
  const [pinned, setPinned] = useState(false);

  // `unread` is derived, so the page derives it again and reports any row where the two disagree.
  const brokenArithmetic = list.items.filter((row) => row.unread !== row.recipients - row.read_by);
  const seen = list.items.filter((row) => list.sees.includes(row.id));
  // The door counts pinned notices over the whole tenant, so its per-audience figure only matches the printed
  // rows while no filter narrowed them. Under a filter the page says so instead of claiming a mismatch.
  const pinnedCounted: Record<string, number> = {};
  for (const row of list.items) {
    if (row.pinned) pinnedCounted[row.audience] = (pinnedCounted[row.audience] ?? 0) + 1;
  }
  const pinnedAgrees = audience === null && caps.audiences.every((word) => (pinnedCounted[word] ?? 0) === (list.pinned_by_audience[word] ?? 0));

  async function post() {
    const done = await call("notice-post", `/club/${encodeURIComponent(ident)}/announcements`, {
      body: { audience: chosen, body: body.trim(), pinned, title: title.trim() },
    });
    if (done) {
      setTitle("");
      setBody("");
      setPinned(false);
    }
  }

  async function markRead(row: AnnouncementRow) {
    await call(`notice-read-${row.id}`, `/club/${encodeURIComponent(ident)}/announcements/${encodeURIComponent(row.id)}/read`, { body: {} });
  }

  async function erase(row: AnnouncementRow) {
    await call(`notice-erase-${row.id}`, `/club/${encodeURIComponent(ident)}/announcements/${encodeURIComponent(row.id)}`, { method: "DELETE" });
  }

  return (
    <div className="stack">
      <div className="grid-cards">
        <label className="field">
          <span>Audience — a predicate over the roster, not a list of people</span>
          <select aria-label="Notice audience" disabled={busy !== null} onChange={(event) => setChosen(event.target.value)} value={chosen}>
            {caps.audiences.map((word) => (
              <option key={word} value={word}>
                {word}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Title (at most {caps.title_max} characters, and never blank)</span>
          <input aria-label="Notice title" disabled={busy !== null} maxLength={caps.title_max} onChange={(event) => setTitle(event.target.value)} type="text" value={title} />
        </label>
      </div>
      <label className="field">
        <span>Body (at most {caps.body_max} characters)</span>
        <textarea aria-label="Notice body" disabled={busy !== null} maxLength={caps.body_max} onChange={(event) => setBody(event.target.value)} rows={3} value={body} />
      </label>
      <div className="row wrap">
        <label className="row" style={{ gap: "0.4rem" }}>
          <input aria-label="Notice pinned" checked={pinned} disabled={busy !== null} onChange={(event) => setPinned(event.target.checked)} type="checkbox" />
          <span>Pin it — at most {caps.pinned_max} per audience</span>
        </label>
        <button aria-label="Post notice" className="btn" data-testid="notice-post" disabled={busy !== null} onClick={post} type="button">
          {busy === "notice-post" ? "Posting…" : "Post it to the audience"}
        </button>
      </div>
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        {caps.audience_rule}
      </p>
      <CallNote note={note} />

      <div className="row wrap" data-testid="notice-totals">
        <span className="badge">{list.total} listed</span>
        <span className="badge">
          {list.announcements_held} of {list.limit} on this board
        </span>
        <span className="badge">you are {list.role} here</span>
        <span className="badge">read through {list.read_through}</span>
        <span className={list.total === list.items.length ? "badge badge--ok" : "badge badge--warn"} data-testid="notice-listed-agrees">
          {list.total === list.items.length ? "the door's total is the number of rows it printed" : `total ${list.total} against ${list.items.length} row(s)`}
        </span>
        <span className={brokenArithmetic.length === 0 ? "badge badge--ok" : "badge badge--warn"} data-testid="notice-arithmetic-agrees">
          {brokenArithmetic.length === 0
            ? "unread is recipients minus read_by on every row here"
            : `${brokenArithmetic.length} row(s) where unread is not recipients minus read_by`}
        </span>
        <span className="badge" data-testid="notice-sees">
          {seen.length} of {list.total} listed select you right now
        </span>
      </div>

      <div className="row wrap" data-testid="notice-filter" style={{ gap: "0.4rem" }}>
        <Link className={audience === null ? "btn btn--sm" : "btn btn--sm btn--ghost"} data-testid="notice-filter-all" href={`/club/${encodeURIComponent(ident)}`}>
          all audiences
        </Link>
        {caps.audiences.map((word) => (
          <Link
            className={audience === word ? "btn btn--sm" : "btn btn--sm btn--ghost"}
            data-testid={`notice-filter-${word}`}
            href={`/club/${encodeURIComponent(ident)}?audience=${encodeURIComponent(word)}`}
            key={word}
          >
            {word} ({list.pinned_by_audience[word] ?? 0} pinned{audience === null ? "" : " tenant-wide"})
          </Link>
        ))}
      </div>
      {audience === null && (
        <span className={pinnedAgrees ? "muted" : "notice notice--warn"} data-testid="notice-pinned-agrees" style={{ fontSize: "0.82rem" }}>
          {pinnedAgrees
            ? "the pinned counts per audience are the board's own rows counted again"
            : `the door's pinned_by_audience disagrees with the rows printed here: ${caps.audiences.map((word) => `${word} ${list.pinned_by_audience[word] ?? 0} vs ${pinnedCounted[word] ?? 0}`).join(" · ")}`}
        </span>
      )}
      {audience !== null && (
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          Filtered to {audience}: the door narrowed the rows, not the tenant — {list.total} listed against {list.announcements_held} held.
        </p>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Notice</th>
              <th>Audience</th>
              <th>Posted by</th>
              <th>Readership</th>
              <th>Your receipt</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.items.map((row) => (
              <tr data-notice={row.id} key={row.id}>
                <td>
                  {row.pinned && <span className="badge badge--ok">pinned</span>}
                  <div style={{ fontWeight: 600 }}>{row.title}</div>
                  <div className="muted" style={{ fontSize: "0.8rem", whiteSpace: "pre-wrap" }}>{row.body || "no body"}</div>
                </td>
                <td>{row.audience}</td>
                <td>
                  {row.author ? row.author.name : "an account that is gone"}
                  <div className="muted mono" style={{ fontSize: "0.76rem" }}>as {row.author_role} · {row.published_on}</div>
                </td>
                <td data-testid={`notice-readership-${row.id}`}>
                  {row.read_by} of {row.recipients} read
                  <div className="muted mono" style={{ fontSize: "0.76rem" }}>
                    {row.unread} unread · {row.receipts_on_row} receipt row(s)
                  </div>
                </td>
                <td>
                  {row.read === null ? (
                    <span className="muted">the listing did not ask</span>
                  ) : row.read ? (
                    <span className="badge badge--ok">you have read it</span>
                  ) : list.sees.includes(row.id) ? (
                    <span className="badge badge--warn">addressed to you, unread</span>
                  ) : (
                    <span className="muted">not addressed to your standing</span>
                  )}
                </td>
                <td className="row wrap" style={{ gap: "0.35rem" }}>
                  <button
                    aria-label={`Mark notice ${row.title} read`}
                    className="btn btn--sm"
                    data-testid={`notice-read-${row.id}`}
                    disabled={busy !== null}
                    onClick={() => markRead(row)}
                    type="button"
                  >
                    {busy === `notice-read-${row.id}` ? "Recording…" : "I have read it"}
                  </button>
                  <button
                    aria-label={`Erase notice ${row.title}`}
                    className="btn btn--sm btn--ghost"
                    data-testid={`notice-erase-${row.id}`}
                    disabled={busy !== null}
                    onClick={() => erase(row)}
                    type="button"
                  >
                    {busy === `notice-erase-${row.id}` ? "Erasing…" : "Erase"}
                  </button>
                </td>
              </tr>
            ))}
            {list.items.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <span className="muted">
                    {audience === null
                      ? `Nothing on this board yet. A notice is posted to an audience, so ${list.announcements_held} of ${list.limit} allowed are still free.`
                      : `No notice has been posted to ${audience} — the board holds ${list.announcements_held} notice(s) under every audience.`}
                  </span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="muted" style={{ fontSize: "0.82rem" }}>{list.rule}</p>
      <ul className="stack-sm" style={{ margin: 0, paddingLeft: "1.1rem" }}>
        {Object.entries(list.formulas).map(([key, sentence]) => (
          <li className="muted" key={key} style={{ fontSize: "0.78rem" }}>
            <span className="mono">{key}</span> — {sentence}
          </li>
        ))}
      </ul>
    </div>
  );
}
