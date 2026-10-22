"use client";

import { useCallback, useEffect, useState } from "react";
import { useTranslations } from "next-intl";

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
  const t = useTranslations("common");
  const ts = useTranslations("scout");
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
    <div className="stack" data-testid="scout-shortlist">
      <Panel
        eyebrow={ts("listsEyebrow", {
          total: lists?.total ?? 0,
          max: rules.max_shortlists_per_user,
          each: rules.max_items_per_shortlist,
        })}
        title={ts("listsTitle")}
      >
        <div className="stack-sm">
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <input aria-label={ts("listNameAria")} className="grow" maxLength={rules.name_max} onChange={(event) => setName(event.target.value)} placeholder={ts("listNamePlaceholder")} value={name} />
            <input aria-label={ts("listCareerAria")} className="mono" maxLength={80} onChange={(event) => setCareer(event.target.value)} placeholder={ts("listCareerPlaceholder")} value={career} />
            <button className="btn btn--primary" disabled={busy !== null || !name.trim() || (lists ? lists.total >= lists.limit : false)} onClick={() => void create()} type="button">
              {busy === "create" ? ts("opening") : ts("openAList")}
            </button>
          </div>
          <label className="muted" style={{ display: "block" }}>
            <input checked={carry} onChange={(event) => setCarry(event.target.checked)} type="checkbox" />{" "}
            {ts("carrySentence", {
              query: searchedQuery ? `“${searchedQuery}”` : ts("noneYet"),
            })}
          </label>
          {lists && lists.total >= lists.limit && (
            <p className="notice notice--warn">
              {ts("limitNotice", { limit: lists.limit })}
            </p>
          )}
          {fault && (
            <p className="notice notice--warn">
              <strong>{fault.code ?? "error"}</strong> — {errorMessage(fault, t("requestFailed"))}
              {figures ? <span className="mono"> {figures}</span> : null}
            </p>
          )}
          {!lists || lists.items.length === 0 ? (
            <p className="muted">{ts("noListYet")}</p>
          ) : (
            <div className="world-tablewrap">
              <table className="table">
                <thead>
                  <tr>
                    <th scope="col">{ts("thList")}</th>
                    <th scope="col">{ts("thSentenceStored")}</th>
                    <th scope="col">{ts("thRole")}</th>
                    <th scope="col">{ts("thCareer")}</th>
                    <th scope="col" className="num">
                      {ts("thPlayers")}
                    </th>
                    <th scope="col" className="num">
                      {ts("thRoom")}
                    </th>
                    <th scope="col">{t("open")}</th>
                    <th scope="col">{t("delete")}</th>
                  </tr>
                </thead>
                <tbody>
                  {lists.items.map((row) => (
                    <tr data-list={row.id} key={row.id}>
                      <td>
                        <strong>{row.name}</strong>
                        <div className="muted mono">
                          {ts("storedLabel", { value: row.stored.join(" · ") })}
                        </div>
                      </td>
                      <td className="muted">{row.query || <span className="mono">{ts("noSentence")}</span>}</td>
                      <td className="mono">{row.role || "—"}</td>
                      <td className="mono">{row.career ?? "—"}</td>
                      <td className="num">{row.players_listed}</td>
                      <td className="num">{row.room_left}</td>
                      <td>
                        <button className="btn btn--sm" data-act="open" disabled={busy !== null} onClick={() => void openList(row.id)} type="button">
                          {t("open")}
                        </button>
                      </td>
                      <td>
                        <button className="btn btn--sm" data-act="delete" disabled={busy !== null} onClick={() => void drop(row.id)} type="button">
                          {t("delete")}
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
              <span className="mono">integrity</span>:{" "}
              {lists.integrity.clean ? ts("integrityClean") : ts("integrityProblems")} ·{" "}
              {ts("problemCount", { count: lists.integrity.problems.length })} ·{" "}
              {ts("checkedRows", {
                lists: lists.integrity.checked.shortlists,
                rows: lists.integrity.checked.membership_rows,
                players: lists.integrity.checked.players_in_pool,
              })}{" "}
              {lists.rule}
            </p>
          )}
        </div>
      </Panel>

      {open && (
        <Panel
          eyebrow={ts("openPanelEyebrow", {
            players: open.counts.printed,
            rows: open.counts.membership_rows,
            room: open.room_left,
          })}
          title={ts("openPanelTitle", { name: open.shortlist.name })}
        >
          <div className="stack-sm">
            <p className="notice">{open.figures_from}</p>
            <div className="row wrap" style={{ gap: "0.5rem" }}>
              <span className="chip mono">
                {ts("askedChip", {
                  value: open.need?.needed_band
                    ? ts("careerNeedsBand", { band: open.need.needed_band })
                    : ts("noCareerLinked"),
                })}
              </span>
              <span className="chip mono">
                {ts("answersChip", {
                  yes: open.counts.answered_everything,
                  no: open.counts.answered_nothing,
                })}
              </span>
              <span className="chip mono">
                {ts("storedChip", {
                  value: open.shortlist.stored.join(" · "),
                  count: open.shortlist.not_stored,
                })}
              </span>
              {open.gone_from_the_world.length > 0 && (
                <span className="badge badge--demo">{ts("goneBadge", { count: open.gone_from_the_world.length })}</span>
              )}
            </div>
            {open.need?.refused && (
              <p className="notice notice--warn">
                <strong>{open.need.refused.code}</strong> — {open.need.refused.message}
              </p>
            )}
            {open.need?.needed_band && open.need.positions_in_band && (
              <p className="muted">
                {ts("careerNeedsBandLine", {
                  club: open.career?.club_name ?? "",
                  band: open.need.needed_band,
                  rounds: open.career?.rounds_played ?? 0,
                  positions: open.need.positions_in_band.join(", "),
                  bands: JSON.stringify(open.need.bands),
                })}
              </p>
            )}

            <div className="row wrap" style={{ gap: "0.6rem" }}>
              <select aria-label={ts("playerToAddAria")} className="grow mono" disabled={busy !== null || candidates.length === 0} onChange={(event) => setPlayer(event.target.value)} value={player}>
                <option value="">{candidates.length ? ts("addOneOption") : ts("runSearchFirstOption")}</option>
                {candidates.map((candidate) => (
                  <option key={candidate.slug} value={candidate.slug}>
                    {candidate.name} · {candidate.age} · {candidate.band} · {candidate.overall}/{candidate.potential}
                  </option>
                ))}
              </select>
              <input aria-label={ts("noteAria")} className="grow" maxLength={rules.note_max} onChange={(event) => setNote(event.target.value)} placeholder={ts("notePlaceholder")} value={note} />
              <button className="btn btn--primary" disabled={busy !== null || !player || open.room_left === 0} onClick={() => void add()} type="button">
                {busy === "add" ? ts("adding") : ts("addToList")}
              </button>
            </div>

            {open.items.length === 0 ? (
              <div className="empty">
                <strong>{ts("nobodyYet")}</strong>
                <p className="muted">{ts("nobodyYetNote")}</p>
              </div>
            ) : (
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col" className="num">
                        #
                      </th>
                      <th scope="col">{ts("thPlayer")}</th>
                      <th scope="col" className="num">
                        {ts("thAge")}
                      </th>
                      <th scope="col">{ts("thBand")}</th>
                      <th scope="col">{ts("thFoot")}</th>
                      <th scope="col" className="num">
                        {ts("thOverall")}
                      </th>
                      <th scope="col" className="num">
                        {ts("thPotential")}
                      </th>
                      <th scope="col" className="num">
                        {ts("thHeadroom")}
                      </th>
                      <th scope="col" className="num">
                        {ts("thAskingFee")}
                      </th>
                      <th scope="col">{ts("thAnswers")}</th>
                      <th scope="col">{ts("thNote")}</th>
                      <th scope="col">{ts("thOff")}</th>
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
                            {item.player.club ? ` · ${item.player.club.name}` : ` · ${ts("noClub")}`}
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
                                  {ts("lostBadge", { phrase: answer.phrase })}
                                </span>
                              ))}
                              {(item.recheck.refused?.length ?? 0) > 0 && (
                                <div className="muted mono">
                                  {ts("notUnderstood", {
                                    phrases: item.recheck.refused?.map((refusal) => refusal.phrase).join(" · ") ?? "",
                                  })}
                                </div>
                              )}
                            </>
                          ) : (
                            <span className="mono">{item.recheck.note}</span>
                          )}
                        </td>
                        <td className="muted">{item.note || <span className="mono">—</span>}</td>
                        <td>
                          <button
                            aria-label={ts("takeOffAria", { name: item.player.name })}
                            className="btn btn--sm"
                            data-act="remove"
                            disabled={busy !== null}
                            onClick={() => void remove(item.player.slug)}
                            type="button"
                          >
                            {ts("off")}
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
                {ts("positionNote")} {open.rules.position}. {open.account_content}.
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
