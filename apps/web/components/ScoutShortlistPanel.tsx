"use client";

import { useCallback, useEffect, useState } from "react";

import { Panel } from "@/components/ui";
import { browserFetch, errorMessage } from "@/lib/api";
import { money } from "@/lib/scout";
import type { ApiError } from "@/lib/types";
import type { Candidate, ShortlistList, ShortlistRules, ShortlistView } from "@/lib/scout";

/**
 * §23's shortlist, on the same screen as the search that suggests names for it.
 *
 * The panel deliberately shows no figure it has computed. Every number in the table comes from the read, and
 * the read takes it from the stored player row again — which is the whole design of the tier:
 *
 *  - **Nothing about a player is saved.** A list keeps a name, the sentence it came from, and who is on it. So
 *    the figures printed here are today's, and the page can say where they came from without qualification.
 *  - **A list can be stale, and says so in its own words.** The stored sentence is parsed again for every
 *    member: the chips under *Answers* and *No longer answers* are what the request would still filter on,
 *    computed now, not remembered from the day somebody pressed Add.
 *  - **A refusal arrives with its arithmetic.** A 409 says how many are held and what the cap is; a 422 says
 *    the length it was given and the length allowed. Those figures are printed, because a refusal the reader
 *    cannot check is a dead end.
 *  - **Order is insertion, not rank.** The `position` column is the order the list was built in, which is the
 *    only number this tier stores. Ranking two players against each other is §27's comparison, above.
 */
export function ScoutShortlistPanel({ rules, candidates, searchedQuery }: { rules: ShortlistRules; candidates: Candidate[]; searchedQuery: string }) {
  const [lists, setLists] = useState<ShortlistList | null>(null);
  const [open, setOpen] = useState<ShortlistView | null>(null);
  const [name, setName] = useState("");
  const [carry, setCarry] = useState(true);
  const [career, setCareer] = useState("");
  const [player, setPlayer] = useState("");
  const [note, setNote] = useState("");
  const [fault, setFault] = useState<ApiError | null>(null);
  const [busy, setBusy] = useState<"load" | "create" | "open" | "add" | "remove" | "delete" | null>(null);

  const load = useCallback(async () => {
    setBusy("load");
    const result = await browserFetch<ShortlistList>("/scout/shortlists");
    if (result.ok) {
      setLists(result.data);
    } else {
      setFault(result.error);
    }
    setBusy(null);
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  /** A failed write prints its own figures rather than being retried quietly behind a spinner. */
  async function ask(route: string, method: "POST" | "PATCH" | "DELETE", body?: Record<string, unknown>) {
    const result = await browserFetch<Record<string, unknown>>(route, { method, body });
    if (!result.ok) {
      setFault(result.error);
      return null;
    }
    setFault(null);
    return result.data;
  }

  async function create() {
    if (!name.trim()) return;
    setBusy("create");
    const created = await ask("/scout/shortlists", "POST", { name: name.trim(), query: carry ? searchedQuery : "", career: career.trim() || undefined });
    setBusy(null);
    if (!created) return;
    setName("");
    setCareer("");
    await load();
    await openList(String((created as { shortlist: { id: string } }).shortlist.id));
  }

  async function openList(id: string) {
    setBusy("open");
    const result = await browserFetch<ShortlistView>(`/scout/shortlists/${id}`);
    setBusy(null);
    if (result.ok) {
      // Deliberately no `setFault(null)` here: this refresh runs *after* a write, and clearing the refusal on
      // a successful re-read would leave the page showing two rows when only one was added.
      setOpen(result.data);
    } else {
      setFault(result.error);
    }
  }

  async function add() {
    if (!open || !player) return;
    setBusy("add");
    await ask(`/scout/shortlists/${open.shortlist.id}/items`, "POST", { player, note: note.trim() });
    setNote("");
    setBusy(null);
    await openList(open.shortlist.id);
    await load();
  }

  async function remove(slug: string) {
    if (!open) return;
    setBusy("remove");
    await ask(`/scout/shortlists/${open.shortlist.id}/items/${slug}`, "DELETE");
    setBusy(null);
    await openList(open.shortlist.id);
    await load();
  }

  async function drop(id: string) {
    setBusy("delete");
    await ask(`/scout/shortlists/${id}`, "DELETE");
    setBusy(null);
    if (open?.shortlist.id === id) setOpen(null);
    await load();
  }

  const figures = fault?.details && typeof fault.details === "object" ? JSON.stringify(fault.details) : "";

  return (
    <div className="stack">
      <Panel eyebrow={`${lists?.total ?? 0} of ${rules.max_shortlists_per_user} lists · ${rules.max_items_per_shortlist} players each`} title="Your shortlists">
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <input aria-label="Shortlist name" className="grow" maxLength={rules.name_max} onChange={(event) => setName(event.target.value)} placeholder="e.g. Left-footed midfielders to watch" value={name} />
            <input aria-label="Career to read the list against" className="mono" maxLength={80} onChange={(event) => setCareer(event.target.value)} placeholder="career slug (optional)" value={career} />
            <button className="btn btn--primary" disabled={busy !== null || !name.trim() || (lists ? lists.total >= lists.limit : false)} onClick={() => void create()} type="button">
              {busy === "create" ? "Opening…" : "Open a list"}
            </button>
          </div>
          <label className="muted" style={{ display: "block" }}>
            <input checked={carry} onChange={(event) => setCarry(event.target.checked)} type="checkbox" /> store the sentence I just searched ({searchedQuery ? `“${searchedQuery}”` : "none yet"}) — it is re-applied to every member on each read
          </label>
          {lists && lists.total >= lists.limit && (
            <p className="notice notice--warn">
              This account holds the {lists.limit} lists it is allowed. Delete one before opening another — the cap is printed by the API, not invented here.
            </p>
          )}
          {fault && (
            <p className="notice notice--warn">
              <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault)}
              {figures ? <span className="mono"> {figures}</span> : null}
            </p>
          )}
          {!lists || lists.items.length === 0 ? (
            <p className="muted">No list yet. A list stores a name, an optional sentence and career, and which players are on it — nothing that measures a player, so nothing here can go out of date without saying so.</p>
          ) : (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">List</th>
                    <th scope="col">Sentence stored</th>
                    <th scope="col">Role</th>
                    <th scope="col">Career</th>
                    <th scope="col" className="num">
                      Players
                    </th>
                    <th scope="col" className="num">
                      Room
                    </th>
                    <th scope="col">Open</th>
                    <th scope="col">Delete</th>
                  </tr>
                </thead>
                <tbody>
                  {lists.items.map((row) => (
                    <tr data-list={row.id} key={row.id}>
                      <td>
                        <strong>{row.name}</strong>
                        <div className="muted mono">
                          stored: {row.stored.join(" · ")}
                        </div>
                      </td>
                      <td className="muted">{row.query || <span className="mono">no sentence</span>}</td>
                      <td className="mono">{row.role || "—"}</td>
                      <td className="mono">{row.career ?? "—"}</td>
                      <td className="num">{row.players_listed}</td>
                      <td className="num">{row.room_left}</td>
                      <td>
                        <button className="btn btn--sm" data-act="open" disabled={busy !== null} onClick={() => void openList(row.id)} type="button">
                          Open
                        </button>
                      </td>
                      <td>
                        <button className="btn btn--sm" data-act="delete" disabled={busy !== null} onClick={() => void drop(row.id)} type="button">
                          Delete
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {lists && (
            <p className="muted">
              <span className="mono">integrity</span>: {lists.integrity.clean ? "clean" : "problems reported"} · {lists.integrity.problems.length} problem{lists.integrity.problems.length === 1 ? "" : "s"} ·{" "}
              {lists.integrity.checked.shortlists} list{lists.integrity.checked.shortlists === 1 ? "" : "s"} and {lists.integrity.checked.membership_rows} membership row
              {lists.integrity.checked.membership_rows === 1 ? "" : "s"} checked against {lists.integrity.checked.players_in_pool} stored players. {lists.rule}
            </p>
          )}
        </div>
      </Panel>

      {open && (
        <Panel eyebrow={`${open.counts.printed} player${open.counts.printed === 1 ? "" : "s"} on it · ${open.counts.membership_rows} membership row${open.counts.membership_rows === 1 ? "" : "s"} stored · ${open.room_left} room left`} title={`Shortlist · ${open.shortlist.name}`}>
          <div className="stack-sm">
            <p className="notice">{open.figures_from}</p>
            <div className="row wrap" style={{ gap: "0.5rem" }}>
              <span className="chip mono">asked: {open.need?.needed_band ? `the career needs ${open.need.needed_band}` : "no career linked"}</span>
              <span className="chip mono">
                answers everything: {open.counts.answered_everything} · answers nothing: {open.counts.answered_nothing}
              </span>
              <span className="chip mono">
                stored: {open.shortlist.stored.join(" · ")} · not stored: {open.shortlist.not_stored}
              </span>
              {open.gone_from_the_world.length > 0 && <span className="badge badge--demo">{open.gone_from_the_world.length} NO LONGER IN THE WORLD</span>}
            </div>
            {open.need?.refused && (
              <p className="notice notice--warn">
                <strong>{open.need.refused.code}</strong> — {open.need.refused.message}
              </p>
            )}
            {open.need?.needed_band && open.need.positions_in_band && (
              <p className="muted">
                {open.career?.club_name} needs <span className="mono">{open.need.needed_band}</span> at round {open.career?.rounds_played}: {open.need.positions_in_band.join(", ")} · bands{" "}
                <span className="mono">{JSON.stringify(open.need.bands)}</span>
              </p>
            )}

            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <select aria-label="Player to add" className="grow mono" disabled={busy !== null || candidates.length === 0} onChange={(event) => setPlayer(event.target.value)} value={player}>
                <option value="">{candidates.length ? "add one of the players this search just returned" : "run a search first, or type nothing and use the note field"}</option>
                {candidates.map((candidate) => (
                  <option key={candidate.slug} value={candidate.slug}>
                    {candidate.name} · {candidate.age} · {candidate.band} · {candidate.overall}/{candidate.potential}
                  </option>
                ))}
              </select>
              <input aria-label="Note about this player" className="grow" maxLength={rules.note_max} onChange={(event) => setNote(event.target.value)} placeholder="your own words (optional)" value={note} />
              <button className="btn btn--primary" disabled={busy !== null || !player || open.room_left === 0} onClick={() => void add()} type="button">
                {busy === "add" ? "Adding…" : "Add to the list"}
              </button>
            </div>

            {open.items.length === 0 ? (
              <div className="empty">
                <strong>Nobody on it yet</strong>
                <p className="muted">Add a player from the search above. Nothing about him is copied into the list, so what you see tomorrow is what the stored row says tomorrow.</p>
              </div>
            ) : (
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col" className="num">
                        #
                      </th>
                      <th scope="col">Player</th>
                      <th scope="col" className="num">
                        Age
                      </th>
                      <th scope="col">Band</th>
                      <th scope="col">Foot</th>
                      <th scope="col" className="num">
                        Overall
                      </th>
                      <th scope="col" className="num">
                        Potential
                      </th>
                      <th scope="col" className="num">
                        Headroom
                      </th>
                      <th scope="col" className="num">
                        Asking fee
                      </th>
                      <th scope="col">Answers / no longer answers</th>
                      <th scope="col">Note</th>
                      <th scope="col">Off</th>
                    </tr>
                  </thead>
                  <tbody>
                    {open.items.map((item) => (
                      <tr data-listed={item.player.slug} key={item.player.slug}>
                        <td className="num">{item.position}</td>
                        <td>
                          <a className="world-link" href={item.player.path}>
                            {item.player.name}
                          </a>
                          <div className="muted mono">
                            {item.player.position} · {item.player.archetype}
                            {item.player.club ? ` · ${item.player.club.name}` : " · no club"}
                          </div>
                        </td>
                        <td className="num">{item.player.age}</td>
                        <td className="mono">{item.player.band}</td>
                        <td className="mono">{item.player.preferred_foot}</td>
                        <td className="num">{item.player.overall}</td>
                        <td className="num">{item.player.potential}</td>
                        <td className="num">{item.player.headroom}</td>
                        <td className="num">{money(item.player.valuation.asking_fee)}</td>
                        <td className="muted">
                          {item.recheck.asked ? (
                            <>
                              {item.recheck.answers.map((answer) => (
                                <span className="chip mono" key={`hit-${answer.kind}-${answer.phrase}`}>
                                  {answer.phrase}
                                </span>
                              ))}
                              {item.recheck.no_longer_answers.map((answer) => (
                                <span className="badge badge--demo" key={`lost-${answer.kind}-${answer.phrase}`}>
                                  LOST {answer.phrase}
                                </span>
                              ))}
                              {(item.recheck.refused?.length ?? 0) > 0 && (
                                <div className="muted mono">not understood: {item.recheck.refused?.map((refusal) => refusal.phrase).join(" · ")}</div>
                              )}
                            </>
                          ) : (
                            <span className="mono">{item.recheck.note}</span>
                          )}
                        </td>
                        <td className="muted">{item.note || <span className="mono">—</span>}</td>
                        <td>
                          <button aria-label={`Take ${item.player.name} off the list`} className="btn btn--sm" data-act="remove" disabled={busy !== null} onClick={() => void remove(item.player.slug)} type="button">
                            Off
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}

            {open.items.length > 0 && (
              <p className="muted">
                <span className="mono">position</span> is the order the list was built in, and the only number about a player this tier stores. {open.rules.position}. {open.account_content}.
              </p>
            )}
            <p className="muted">{open.limitations.join(" · ")}</p>
            <p className="muted mono">
              {open.data_origin} · is_demo_data: {String(open.is_demo_data)} · {open.disclaimer}
            </p>
          </div>
        </Panel>
      )}
    </div>
  );
}
