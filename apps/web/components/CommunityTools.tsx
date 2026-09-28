"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import { pointerAgreesWithKind, refusalFigures, type CommunityCaps, type CommunityCommentRow, type CommunityFeed, type CommunityPostRow, type CommunityProfile } from "@/lib/community";

/**
 * §35's community wall: publish a post that points at one of your own artifacts, read the feed the tier says you
 * can reach, and hold the three verbs that make it a community — a reaction, a reply, a follow.
 *
 * The panel is shaped by one decision in the tier. A post stores a **pointer and words**, never a figure about
 * the thing it shares, so every number on this screen (`likes`, `comments`, `reposts`, `followers`, `following`)
 * arrived counted from rows at the moment of the read. The page keeps none of them: after a verb it re-reads the
 * wall through the door (`router.refresh()`) and prints whatever the tier counted again, which is the only way a
 * second press of "like" can be seen as one row rather than two.
 *
 * Nothing here chooses a number or a word. The kinds, the visibility list, the pointer prefixes and the four
 * length ceilings all come from `caps`, which is what `GET /community/rules` printed; the form's `maxLength` is
 * the published ceiling rather than a guess, and a pointer is sent as the kind's own prefix plus the address the
 * author typed, because the door refuses any other pair. Where the page *can* check a promise it does: a row
 * whose pointer is not under its own kind's prefix, or a door whose `total` is not the number of rows it printed,
 * is reported on the panel as a mismatch instead of being quietly filtered out of the picture.
 */

type Note = {figures: string[]; ok: boolean; text: string};

/**
 * `announce` copies the note into a slot the caller owns.
 *
 * A row-scoped note cannot outlive the verb it reports: erasing a post or withdrawing a follow unmounts the row
 * the refresh leaves behind, and with it goes the sentence that said what happened. The wall keeps a copy, so the
 * answer to those two verbs is still on screen when the re-read lands.
 */
function useCommunityCall(announce?: (value: Note) => void) {
  const router = useRouter();
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState<Note | null>(null);
  function paint(value: Note) {
    setNote(value);
    announce?.(value);
  }

  async function call(key: string, path: string, init: { body?: unknown; method?: string } = {}, said = "recorded"): Promise<boolean> {
    setBusy(key);
    // `browserFetch` defaults to GET and a GET with a body is a fetch that throws in the browser, so a write
    // here names its verb the way §39's `useClubCall` does. The community walk found this: every write the page
    // pressed was answered by its own client, not by the door.
    const method = (init.method ?? "POST").toUpperCase();
    const result = await browserFetch<Record<string, unknown>>(path, {body: init.body, method});
    setBusy(null);
    if (result.ok) {
      const digest = digestOf(result.data ?? {});
      paint({ figures: [], ok: true, text: `${key}: ${said}${digest.length > 0 ? ` — ${digest.join(" ")}` : ""}` });
      // Every figure the verb moved is re-counted by the door on the next read, not adjusted here.
      router.refresh();
      return true;
    }
    paint({ figures: refusalFigures(result.error.details), ok: false, text: `${result.error.code} · ${errorMessage(result.error)}` });
    return false;
  }

  return {busy, call, note};
}

/**
 * The facts the door answered the write with, appended to the note.
 *
 * A note that says only `publish: posted` is the same sentence for every post, so a walk cannot tell two presses
 * of the same verb apart; the id and the `recorded_now` the door itself returns make each press legible.
 */
function digestOf(body: Record<string, unknown>): string[] {
  const out: string[] = [];
  for (const name of ["post", "comment"] as const) {
    const nested = body[name] as {id?: string} | undefined;
    if (nested?.id) out.push(nested.id);
  }
  for (const name of ["erased", "reaction", "repost", "follow", "recorded_now", "removed", "posted"] as const) {
    if (name in body) out.push(`${name} ${String(body[name])}`);
  }
  return out;
}

function CallNote({id, note}: {id: string; note: Note | null}) {
  if (!note) return null;
  return (
    <p className={note.ok ? "muted" : "notice notice--warn"} data-note={id} data-testid="community-note" style={{fontSize: "0.82rem"}}>
      {note.text}
      {note.figures.length > 0 && <span className="mono"> — {note.figures.join(" · ")}</span>}
    </p>
  );
}

export function PostComposer({caps, profile}: {caps: CommunityCaps; profile: CommunityProfile}) {
  const {busy, call, note} = useCommunityCall();
  const [body, setBody] = useState("");
  const [kind, setKind] = useState(caps.kinds[0] ?? "note");
  const [visibility, setVisibility] = useState(caps.visibilities[0] ?? "public");
  const pointing = kind !== "note";
  const prefix = caps.pointer_prefixes[kind] ?? "";
  const [pointer, setPointer] = useState("");
  const room = caps.post_max - profile.posts;

  async function publish() {
    const done = await call("publish", "/community/posts", {body: {body: body.trim(), kind, pointer: pointing ? prefix + pointer.trim() : "", visibility}}, "posted");
    if (done) {
      setBody("");
      setPointer("");
    }
  }

  return (
    <div className="stack">
      <div className="grid-cards">
        <label className="field">
          <span>Kind — a note carries words, everything else carries the address of your own artifact</span>
          <select aria-label="Post kind" disabled={busy !== null} onChange={event => setKind(event.target.value)} value={kind}>
            {caps.kinds.map(word => (
              <option key={word} value={word}>
                {word}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Visibility — reach is decided by the follow rows, not by a list stored on the post</span>
          <select aria-label="Post visibility" disabled={busy !== null} onChange={event => setVisibility(event.target.value)} value={visibility}>
            {caps.visibilities.map(word => (
              <option key={word} value={word}>
                {word}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label className="field">
        <span>Words (at most {caps.post_body_max} characters, and never blank)</span>
        <textarea aria-label="Post body" disabled={busy !== null} maxLength={caps.post_body_max} onChange={event => setBody(event.target.value)} rows={3} value={body} />
      </label>

      {pointing && (
        <label className="field">
          <span>
            Points at <span className="mono">{prefix}</span> plus the artifact address — this kind names the {kind.replace("my_", "")} page, and the tier stores the address, never a figure read from it
          </span>
          <input
            aria-label="Post pointer tail"
            disabled={busy !== null}
            maxLength={Math.max(1, caps.pointer_max - prefix.length)}
            onChange={event => setPointer(event.target.value)}
            placeholder="press-high"
            type="text"
            value={pointer}
          />
        </label>
      )}

      <button aria-label="Publish post" className="btn" data-testid="community-publish" disabled={busy !== null || room <= 0} onClick={publish} type="button">
        {busy === "publish" ? "Publishing…" : `Publish it — ${room} of ${caps.post_max} posts left`}
      </button>
      {room <= 0 && <p className="notice notice--warn" data-testid="community-post-ceiling">This account holds the {caps.post_max} posts the tier allows, so the door is closed until one is erased.</p>}
      <CallNote id="composer" note={note} />
      <p className="muted" style={{fontSize: "0.82rem"}}>
        {caps.visibility_rule}
      </p>
    </div>
  );
}

function ReplyBox({caps, row}: {caps: CommunityCaps; row: CommunityPostRow}) {
  const {busy, call, note} = useCommunityCall();
  const [open, setOpen] = useState(false);
  const [items, setItems] = useState<CommunityCommentRow[] | null>(null);
  const [body, setBody] = useState("");
  const full = row.comments >= caps.comment_max;

  async function show() {
    setOpen(true);
    const result = await browserFetch<{items: CommunityCommentRow[]; total: number}>(`/community/posts/${encodeURIComponent(row.id)}/comments`);
    if (result.ok) setItems(result.data.items);
  }

  async function reply() {
    const done = await call(`reply-${row.id}`, `/community/posts/${encodeURIComponent(row.id)}/comments`, {body: {body: body.trim()}}, "answered");
    if (done) {
      setBody("");
      setItems(null);
      if (open) void show();
    }
  }

  return (
    <div className="stack-sm" data-testid={`community-replies-${row.id}`}>
      <button aria-label={`Replies on the post ${row.body.slice(0, 24)}`} className="btn btn--sm btn--ghost" data-testid={`community-replies-toggle-${row.id}`} disabled={busy !== null} onClick={show} type="button">
        {row.comments} repl{row.comments === 1 ? "y" : "ies"} — read them
      </button>
      {open && (
        <>
          {items === null ? (
            <span className="muted" data-testid="community-replies-loading" style={{fontSize: "0.78rem"}}>reading the replies…</span>
          ) : items.length === 0 ? (
            <span className="muted" data-testid="community-replies-empty" style={{fontSize: "0.78rem"}}>no reply has been written on this post</span>
          ) : (
            <ul className="stack-sm" style={{margin: 0, paddingLeft: "1.1rem"}}>
              {items.map(item => (
                <li className="muted" data-testid={`community-reply-${item.id}`} key={item.id} style={{fontSize: "0.78rem"}}>
                  <span className="mono">{item.commented_on}</span> {item.author.display_name}: {item.body}
                </li>
              ))}
            </ul>
          )}
          {full ? (
            <span className="notice notice--warn" data-testid="community-reply-ceiling" style={{fontSize: "0.78rem"}}>
              This post holds the {caps.comment_max} comments the tier allows; the door will refuse a further one and say so.
            </span>
          ) : (
            <>
              <label className="field">
                <span>Reply (at most {caps.comment_body_max} characters)</span>
                <textarea aria-label={`Reply on the post ${row.body.slice(0, 24)}`} disabled={busy !== null} maxLength={caps.comment_body_max} onChange={event => setBody(event.target.value)} rows={2} value={body} />
              </label>
              <button aria-label="Send reply" className="btn btn--sm" data-testid={`community-reply-send-${row.id}`} disabled={busy !== null} onClick={reply} type="button">
                {busy === `reply-${row.id}` ? "Sending…" : "Reply"}
              </button>
            </>
          )}
          <CallNote id={`reply-${row.id}`} note={note} />
        </>
      )}
    </div>
  );
}

function PostRow({announce, caps, following, row, viewer}: {announce: (value: Note) => void; caps: CommunityCaps; following: string[]; row: CommunityPostRow; viewer: string}) {
  const {busy, call, note} = useCommunityCall(announce);
  const mine = row.author.id === viewer;
  const followsAuthor = following.includes(row.author.id);

  return (
    <tr data-post={row.id}>
      <td>
        <div className="row wrap" style={{gap: "0.35rem"}}>
          <span className="badge badge--demo mono">{row.kind}</span>
          <span className="badge mono">{row.visibility}</span>
          {mine && <span className="badge badge--ok">yours</span>}
          {!pointerAgreesWithKind(row, caps) && <span className="badge badge--warn" data-testid={`community-pointer-broken-${row.id}`}>pointer is not under its kind prefix</span>}
        </div>
        <div style={{fontWeight: 600, whiteSpace: "pre-wrap"}}>{row.body}</div>
        {row.has_pointer ? (
          <Link className="world-link mono" data-testid={`community-pointer-${row.id}`} href={row.pointer} style={{fontSize: "0.78rem"}}>
            {row.pointer}
          </Link>
        ) : (
          <span className="muted mono" style={{fontSize: "0.76rem"}}>points at nothing — a note is words only</span>
        )}
        <div className="muted mono" style={{fontSize: "0.74rem"}}>
          {row.author.display_name} · {row.shared_on}
        </div>
      </td>
      <td className="num" data-testid={`community-likes-${row.id}`}>{row.likes}</td>
      <td className="num" data-testid={`community-comments-${row.id}`}>{row.comments}</td>
      <td className="num" data-testid={`community-reposts-${row.id}`}>{row.reposts}</td>
      <td className="row wrap" style={{gap: "0.35rem"}}>
        <button
          aria-label={`Like the post ${row.body.slice(0, 24)}`}
          className={row.viewer_liked ? "btn btn--sm" : "btn btn--sm btn--ghost"}
          data-testid={`community-like-${row.id}`}
          disabled={busy !== null}
          onClick={() => call(`like-${row.id}`, `/community/posts/${encodeURIComponent(row.id)}/reactions`, {body: {reaction: caps.reactions[0] ?? "like"}}, row.viewer_liked ? "already one row" : "recorded")}
          type="button"
        >
          {busy === `like-${row.id}` ? "Recording…" : row.viewer_liked ? "liked (one row)" : "Like"}
        </button>
        {mine ? (
          <button aria-label={`Erase the post ${row.body.slice(0, 24)}`} className="btn btn--sm btn--ghost" data-testid={`community-erase-${row.id}`} disabled={busy !== null} onClick={() => call(`erase-${row.id}`, `/community/posts/${encodeURIComponent(row.id)}`, {method: "DELETE"}, "erased")} type="button">
            {busy === `erase-${row.id}` ? "Erasing…" : "Erase"}
          </button>
        ) : (
          <>
            <button aria-label={`Repost the post ${row.body.slice(0, 24)}`} className="btn btn--sm btn--ghost" data-testid={`community-repost-${row.id}`} disabled={busy !== null} onClick={() => call(`repost-${row.id}`, `/community/posts/${encodeURIComponent(row.id)}/reposts`, {body: {}}, "carried")} type="button">
              {busy === `repost-${row.id}` ? "Carrying…" : "Repost"}
            </button>
            <button
              aria-label={`${followsAuthor ? "Unfollow" : "Follow"} ${row.author.display_name}`}
              className="btn btn--sm btn--ghost"
              data-testid={`community-follow-${row.author.id}`}
              disabled={busy !== null}
              onClick={() => call(`follow-${row.author.id}`, `/community/follows/${encodeURIComponent(row.author.id)}`, followsAuthor ? {method: "DELETE"} : {body: {}}, followsAuthor ? "reach withdrawn" : "following")}
              type="button"
            >
              {busy === `follow-${row.author.id}` ? "…" : followsAuthor ? "unfollow" : "follow"}
            </button>
          </>
        )}
        <ReplyBox caps={caps} row={row} />
        <CallNote id={`row-${row.id}`} note={note} />
      </td>
    </tr>
  );
}

export function CommunityWall({caps, feed, following, profile, viewer}: {caps: CommunityCaps; feed: CommunityFeed; following: string[]; profile: CommunityProfile; viewer: string}) {
  const [wallNote, setWallNote] = useState<Note | null>(null);
  const broken = feed.items.filter(row => !pointerAgreesWithKind(row, caps));
  return (
    <div className="stack">
      <div className="row wrap" data-testid="community-totals" style={{gap: "0.4rem"}}>
        <span className="badge">{feed.total} reachable</span>
        <span className="badge">{feed.items.length} printed</span>
        <span className="badge">
          {profile.posts} of {caps.post_max} yours
        </span>
        <span className="badge">
          {profile.followers} follower(s) · following {profile.following} of {caps.following_max}
        </span>
        <span className={feed.wall === null ? "badge" : "badge badge--demo"}>
          {feed.wall === null ? `a feed of ${feed.feed_authors} author(s)` : "one author wall"}
        </span>
        <span className={feed.total === feed.items.length ? "badge badge--ok" : "badge badge--warn"} data-testid="community-total-agrees">
          {feed.total === feed.items.length ? "the door total is the number of rows it printed" : `total ${feed.total} against ${feed.items.length} row(s)`}
        </span>
        <span className={broken.length === 0 ? "badge badge--ok" : "badge badge--warn"} data-testid="community-pointers-agree">
          {broken.length === 0 ? "every row pointer sits under its own kind prefix" : `${broken.length} row(s) whose pointer is not under its kind prefix`}
        </span>
      </div>

      <CallNote id="wall" note={wallNote} />

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Post</th>
              <th>Likes</th>
              <th>Replies</th>
              <th>Reposts</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {feed.items.map(row => (
              <PostRow announce={setWallNote} caps={caps} following={following} key={row.id} row={row} viewer={viewer} />
            ))}
            {feed.items.length === 0 && (
              <tr>
                <td colSpan={5}>
                  <span className="muted">
                    Nothing reaches you yet. Follow an account, or publish the first post — {profile.posts} of {caps.post_max} used.
                  </span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <p className="muted" style={{fontSize: "0.82rem"}}>{feed.rule}</p>
      <ul className="stack-sm" style={{margin: 0, paddingLeft: "1.1rem"}}>
        {Object.entries(feed.formulas).map(([key, sentence]) => (
          <li className="muted" key={key} style={{fontSize: "0.78rem"}}>
            <span className="mono">{key}</span> — {sentence}
          </li>
        ))}
      </ul>
    </div>
  );
}
