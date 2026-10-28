"use client";

import Link from "next/link";
import { useTranslations } from "next-intl";
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
  const tc = useTranslations("club");
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
          <span>{tc("noticeAudienceLabel")}</span>
          <select aria-label={tc("noticeAudienceAria")} disabled={busy !== null} onChange={(event) => setChosen(event.target.value)} value={chosen}>
            {caps.audiences.map((word) => (
              <option key={word} value={word}>
                {word}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{tc("noticeTitleLabel", { max: caps.title_max })}</span>
          <input aria-label={tc("noticeTitleAria")} disabled={busy !== null} maxLength={caps.title_max} onChange={(event) => setTitle(event.target.value)} type="text" value={title} />
        </label>
      </div>
      <label className="field">
        <span>{tc("noticeBodyLabel", { max: caps.body_max })}</span>
        <textarea aria-label={tc("noticeBodyAria")} disabled={busy !== null} maxLength={caps.body_max} onChange={(event) => setBody(event.target.value)} rows={3} value={body} />
      </label>
      <div className="row wrap">
        <label className="row" style={{ gap: "0.4rem" }}>
          <input aria-label={tc("noticePinnedAria")} checked={pinned} disabled={busy !== null} onChange={(event) => setPinned(event.target.checked)} type="checkbox" />
          <span>{tc("noticePinLabel", { max: caps.pinned_max })}</span>
        </label>
        <button aria-label={tc("noticePostAria")} className="btn" data-testid="notice-post" disabled={busy !== null} onClick={post} type="button">
          {busy === "notice-post" ? tc("noticePosting") : tc("noticePostIt")}
        </button>
      </div>
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        {caps.audience_rule}
      </p>
      <CallNote note={note} />

      <div className="row wrap" data-testid="notice-totals">
        <span className="badge">{tc("noticeTotalListed", { count: list.total })}</span>
        <span className="badge">
          {tc("noticeHeldOnBoard", { held: list.announcements_held, max: list.limit })}
        </span>
        <span className="badge">{tc("noticeYouAre", { role: list.role })}</span>
        <span className="badge">{tc("noticeReadThrough", { count: list.read_through })}</span>
        <span className={list.total === list.items.length ? "badge badge--ok" : "badge badge--warn"} data-testid="notice-listed-agrees">
          {list.total === list.items.length
            ? tc("noticeTotalAgrees")
            : tc("noticeTotalDisagrees", { total: list.total, rows: list.items.length })}
        </span>
        <span className={brokenArithmetic.length === 0 ? "badge badge--ok" : "badge badge--warn"} data-testid="notice-arithmetic-agrees">
          {brokenArithmetic.length === 0
            ? tc("noticeUnreadAgrees")
            : tc("noticeUnreadDisagrees", { count: brokenArithmetic.length })}
        </span>
        <span className="badge" data-testid="notice-sees">
          {tc("noticeSeesYou", { seen: seen.length, total: list.total })}
        </span>
      </div>

      <div className="row wrap" data-testid="notice-filter" style={{ gap: "0.4rem" }}>
        <Link className={audience === null ? "btn btn--sm" : "btn btn--sm btn--ghost"} data-testid="notice-filter-all" href={`/club/${encodeURIComponent(ident)}`}>
          {tc("noticeAllAudiences")}
        </Link>
        {caps.audiences.map((word) => (
          <Link
            className={audience === word ? "btn btn--sm" : "btn btn--sm btn--ghost"}
            data-testid={`notice-filter-${word}`}
            href={`/club/${encodeURIComponent(ident)}?audience=${encodeURIComponent(word)}`}
            key={word}
          >
            {tc("noticeAudienceChip", {
              audience: word,
              count: list.pinned_by_audience[word] ?? 0,
              scope: audience === null ? "" : tc("noticeTenantWide"),
            })}
          </Link>
        ))}
      </div>
      {audience === null && (
        <span className={pinnedAgrees ? "muted" : "notice notice--warn"} data-testid="notice-pinned-agrees" style={{ fontSize: "0.82rem" }}>
          {pinnedAgrees
            ? tc("noticePinnedAgrees")
            : tc("noticePinnedDisagrees", {
                detail: caps.audiences
                  .map((word) => `${word} ${list.pinned_by_audience[word] ?? 0} vs ${pinnedCounted[word] ?? 0}`)
                  .join(" · "),
              })}
        </span>
      )}
      {audience !== null && (
        <p className="muted" style={{ fontSize: "0.82rem" }}>
          {tc("noticeFiltered", {
            audience,
            total: list.total,
            held: list.announcements_held,
          })}
        </p>
      )}

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th scope="col">{tc("thNotice")}</th>
              <th scope="col">{tc("thAudience")}</th>
              <th scope="col">{tc("thPostedBy")}</th>
              <th scope="col">{tc("thReadership")}</th>
              <th scope="col">{tc("thYourReceipt")}</th>
              <th scope="col" />
            </tr>
          </thead>
          <tbody>
            {list.items.map((row) => (
              <tr data-notice={row.id} key={row.id}>
                <td>
                  {row.pinned && <span className="badge badge--ok">{tc("noticePinned")}</span>}
                  <div style={{ fontWeight: 600 }}>{row.title}</div>
                  <div className="muted" style={{ fontSize: "0.8rem", whiteSpace: "pre-wrap" }}>{row.body || tc("noticeNoBody")}</div>
                </td>
                <td>{row.audience}</td>
                <td>
                  {row.author ? row.author.name : tc("noticeAuthorGone")}
                  <div className="muted mono" style={{ fontSize: "0.76rem" }}>
                    {tc("noticeAuthorRole", { role: row.author_role, date: row.published_on })}
                  </div>
                </td>
                <td data-testid={`notice-readership-${row.id}`}>
                  {tc("noticeReadCount", { read: row.read_by, recipients: row.recipients })}
                  <div className="muted mono" style={{ fontSize: "0.76rem" }}>
                    {tc("noticeUnreadCount", { unread: row.unread, receipts: row.receipts_on_row })}
                  </div>
                </td>
                <td>
                  {row.read === null ? (
                    <span className="muted">{tc("noticeListingDidNotAsk")}</span>
                  ) : row.read ? (
                    <span className="badge badge--ok">{tc("noticeYouHaveRead")}</span>
                  ) : list.sees.includes(row.id) ? (
                    <span className="badge badge--warn">{tc("noticeAddressedUnread")}</span>
                  ) : (
                    <span className="muted">{tc("noticeNotAddressed")}</span>
                  )}
                </td>
                <td className="row wrap" style={{ gap: "0.35rem" }}>
                  <button
                    aria-label={tc("noticeMarkReadAria", { title: row.title })}
                    className="btn btn--sm"
                    data-testid={`notice-read-${row.id}`}
                    disabled={busy !== null}
                    onClick={() => markRead(row)}
                    type="button"
                  >
                    {busy === `notice-read-${row.id}` ? tc("noticeRecording") : tc("noticeIHaveRead")}
                  </button>
                  <button
                    aria-label={tc("noticeEraseAria", { title: row.title })}
                    className="btn btn--sm btn--ghost"
                    data-testid={`notice-erase-${row.id}`}
                    disabled={busy !== null}
                    onClick={() => erase(row)}
                    type="button"
                  >
                    {busy === `notice-erase-${row.id}` ? tc("noticeErasing") : tc("noticeErase")}
                  </button>
                </td>
              </tr>
            ))}
            {list.items.length === 0 && (
              <tr>
                <td colSpan={6}>
                  <span className="muted">
                    {audience === null
                      ? tc("noticeEmptyBoard", {
                          held: list.announcements_held,
                          max: list.limit,
                        })
                      : tc("noticeEmptyAudience", {
                          audience,
                          held: list.announcements_held,
                        })}
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
