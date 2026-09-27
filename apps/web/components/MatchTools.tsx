"use client";

import { useEffect, useRef, useState } from "react";

import { CallNote, useClubCall } from "@/components/ClubTools";
import Link from "next/link";
import type { FixtureCaps, FixtureList, FixtureRow, TeamView } from "@/lib/club";

/**
 * §39's Matches, on the page that already holds the tenant's sheet.
 *
 * Two things decide the shape of this file. A fixture is an **arrangement**, so nothing here prints a scoreline:
 * the result lives in the engine's own row and is reached through `match.path`, which is the door that can explain
 * its numbers. And every figure a form offers comes from the caps the rulebook publishes (`fixture_caps`) or from
 * the listing's own answer — including the day a `scheduled_on` is compared against, which the listing prints as
 * `today`, because a date read from this process's clock at render time can be tomorrow by the time somebody
 * presses the button and the door would be right to refuse it. So `caps` is required, not nullable: a page that
 * could not read the door's vocabulary shows no form at all rather than a form built on numbers chosen here.
 *
 * No form paints a written row as the new state: the runner re-reads the page from the server after a write, so
 * what appears is what a `GET` says the tenant now is.
 */
export function FixtureArranger({ caps, ident, list, teams }: { caps: FixtureCaps; ident: string; list: FixtureList; teams: TeamView[] }) {
  const { busy, call, note } = useClubCall();
  const [teamId, setTeamId] = useState(teams[0]?.id ?? "");
  const [opponent, setOpponent] = useState("");
  const [date, setDate] = useState(list.today);
  const [side, setSide] = useState(caps.sides[0] ?? "home");
  const [competition, setCompetition] = useState("");
  const [text, setText] = useState("");

  // Same rule §41's session form follows: the field follows the door's published day until somebody types.
  const dateWasTyped = useRef(false);
  useEffect(() => {
    if (!dateWasTyped.current) setDate(list.today);
  }, [list.today]);

  const team = teams.find((row) => row.id === teamId) ?? null;

  async function arrange() {
    const done = await call("fixture-arrange", `/club/${encodeURIComponent(ident)}/fixtures`, {
      body: {
        competition: competition.trim(),
        note: text.trim(),
        opponent: opponent.trim(),
        scheduled_on: date.trim(),
        side,
        team: teamId,
      },
    });
    if (done) {
      setOpponent("");
      setCompetition("");
      setText("");
    }
  }

  async function play(fixture: FixtureRow) {
    await call(`fixture-play-${fixture.id}`, `/club/${encodeURIComponent(ident)}/fixtures/${encodeURIComponent(fixture.id)}/play`, { body: { minutes: caps.default_minutes } });
  }

  async function erase(fixture: FixtureRow) {
    await call(`fixture-erase-${fixture.id}`, `/club/${encodeURIComponent(ident)}/fixtures/${encodeURIComponent(fixture.id)}`, { method: "DELETE" });
  }

  return (
    <div className="stack">
      <div className="grid-cards">
        <label className="field">
          <span>Side of the fixture</span>
          <select aria-label="Fixture side" disabled={busy !== null} onChange={(event) => setSide(event.target.value)} value={side}>
            {caps.sides.map((word) => (
              <option key={word} value={word}>
                {word}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Team whose sheet plays it</span>
          <select aria-label="Fixture team" disabled={busy !== null} onChange={(event) => setTeamId(event.target.value)} value={teamId}>
            {teams.length === 0 && <option value="">no sheet exists yet</option>}
            {teams.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} — {row.squad_size} on the sheet{row.world_team ? ` · placed as ${row.world_team.name}` : " · not placed in the world"}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>Opponent — a club in the generated world, by slug</span>
          <input aria-label="Fixture opponent" disabled={busy !== null} onChange={(event) => setOpponent(event.target.value)} placeholder="a club slug from /world/teams" type="text" value={opponent} />
        </label>
        <label className="field">
          <span>Date — the door compares a fixture against {list.today}, and refuses a day that has not happened</span>
          <input aria-label="Fixture date" data-fixture-date={list.today} disabled={busy !== null} onChange={(event) => { dateWasTyped.current = true; setDate(event.target.value); }} placeholder={list.today} type="text" value={date} />
        </label>
        <label className="field">
          <span>Competition (at most {caps.competition_max} characters)</span>
          <input aria-label="Fixture competition" disabled={busy !== null} maxLength={caps.competition_max} onChange={(event) => setCompetition(event.target.value)} type="text" value={competition} />
        </label>
      </div>
      <label className="field">
        <span>Note (at most {caps.fixture_note_max} characters)</span>
        <input aria-label="Fixture note" disabled={busy !== null} maxLength={caps.fixture_note_max} onChange={(event) => setText(event.target.value)} type="text" value={text} />
      </label>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        Which names play defaults to the whole sheet{team ? ` — ${team.squad_size} on ${team.name}` : ""}; this page does not narrow the list, so a side is fielded only while the
        sheet reaches {caps.needs_players} names with {caps.needs_keepers} goalkeeper among them. Arranging is not fielding: a promise about a side too small to field stands, and the
        play door is the one that refuses it. A match is played over one of the engine&apos;s own block lengths — {caps.minute_choices.join(", ")} minutes — and this form sends the
        {caps.default_minutes} the rulebook prints.
      </p>

      <div className="row wrap">
        <button aria-label="Arrange fixture" className="btn" data-testid="fixture-arrange" disabled={busy !== null || !teamId || !opponent.trim()} onClick={arrange} type="button">
          {busy === "fixture-arrange" ? "Arranging…" : "Arrange the fixture"}
        </button>
      </div>
      <CallNote note={note} />
      <FixtureBoard busy={busy} list={list} onErase={erase} onPlay={play} />
    </div>
  );
}

/** The tenant's calendar, with the play and erase actions the doors answer. */
export function FixtureBoard({ busy, list, onErase, onPlay }: { busy: string | null; list: FixtureList; onErase: (fixture: FixtureRow) => void; onPlay: (fixture: FixtureRow) => void }) {
  const counted = list.items.reduce((sum, row) => sum + row.appearances, 0);
  return (
    <div className="stack">
      <div className="row wrap" data-testid="fixture-totals">
        <span className="badge">{list.total} arranged</span>
        <span className="badge">{list.played} played</span>
        <span className="badge">{list.unplayed} to play</span>
        <span className="badge">{list.appearances} appearance rows</span>
        <span className="badge">
          {list.fixtures_held} of {list.limit} allowed
        </span>
        {/* The page adds its own column up and says whether the door's figure agrees, rather than printing the
            door's total on trust — the two are counts over the same rows, so a disagreement is a live defect. */}
        <span className={counted === list.appearances ? "badge badge--ok" : "badge badge--warn"} data-testid="fixture-count-agrees">
          {counted === list.appearances ? "the appearances column adds up to the total the door printed" : `the column sums to ${counted} against the door's ${list.appearances}`}
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Fixture</th>
              <th>Side</th>
              <th>Opponent</th>
              <th>Competition</th>
              <th>Names</th>
              <th>Appearances</th>
              <th>The engine&apos;s row</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.items.map((row) => (
              <tr data-fixture={row.id} key={row.id}>
                <td>
                  <span className={row.status === "played" ? "badge badge--ok" : "badge"}>{row.status}</span>
                  <div className="mono" style={{ fontSize: "0.78rem" }}>
                    {row.scheduled_on} · {row.team?.name ?? "no team"}
                  </div>
                </td>
                <td>{row.side}</td>
                <td>{row.opponent ? <Link href={row.opponent.path}>{row.opponent.name}</Link> : <span className="muted">{row.opponent_name || "nobody"}</span>}</td>
                <td>{row.competition || <span className="muted">uncupplied</span>}</td>
                <td data-testid={`fixture-named-${row.id}`}>
                  {row.named.length}
                  {row.named.some((person) => person.is_minor) ? ` · ${row.named.filter((person) => person.is_minor).length} minor` : ""}
                  {row.named_gone > 0 ? ` · ${row.named_gone} erased since` : ""}
                </td>
                <td>{row.appearances}</td>
                <td>{row.match ? <Link href={row.match.path}>{row.match.slug}</Link> : <span className="muted">not played</span>}</td>
                <td className="row wrap" style={{ gap: "0.35rem" }}>
                  {row.status !== "played" && (
                    <button
                      aria-label={`Play fixture ${row.scheduled_on} ${row.opponent?.name ?? row.opponent_name}`}
                      className="btn btn--sm"
                      data-testid={`fixture-play-${row.id}`}
                      disabled={busy !== null}
                      onClick={() => onPlay(row)}
                      type="button"
                    >
                      {busy === `fixture-play-${row.id}` ? "Playing…" : "Play it"}
                    </button>
                  )}
                  <button aria-label={`Erase fixture ${row.scheduled_on}`} className="btn btn--sm btn--ghost" data-testid={`fixture-erase-${row.id}`} disabled={busy !== null} onClick={() => onErase(row)} type="button">
                    {busy === `fixture-erase-${row.id}` ? "Erasing…" : "Erase"}
                  </button>
                </td>
              </tr>
            ))}
            {list.items.length === 0 && (
              <tr>
                <td colSpan={8}>
                  <span className="muted">Nothing arranged yet. A fixture is an arrangement, so it can be made for a day that has already happened — and only for one.</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {Object.keys(list.by_competition).length > 0 && (
        <p className="muted" data-testid="fixture-competitions" style={{ fontSize: "0.82rem" }}>
          by competition: {Object.entries(list.by_competition).map(([key, value]) => `${key} ${value}`).join(" · ")}
        </p>
      )}
      <p className="muted" style={{ fontSize: "0.82rem" }}>{list.rule}</p>
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        {list.formulas.appearances}
      </p>
    </div>
  );
}
