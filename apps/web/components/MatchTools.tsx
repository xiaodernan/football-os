"use client";

import { useEffect, useRef, useState } from "react";
import { useTranslations } from "next-intl";

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
  const tc = useTranslations("club");
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
          <span>{tc("fixtureSideLabel")}</span>
          <select aria-label={tc("fixtureSideAria")} disabled={busy !== null} onChange={(event) => setSide(event.target.value)} value={side}>
            {caps.sides.map((word) => (
              <option key={word} value={word}>
                {word}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{tc("fixtureTeamLabel")}</span>
          <select aria-label={tc("fixtureTeamAria")} disabled={busy !== null} onChange={(event) => setTeamId(event.target.value)} value={teamId}>
            {teams.length === 0 && <option value="">{tc("noSheetYet")}</option>}
            {teams.map((row) => (
              <option key={row.id} value={row.id}>
                {row.name} — {tc("onTheSheet", { count: row.squad_size })}
                {row.world_team
                  ? ` · ${tc("placedAs", { team: row.world_team.name })}`
                  : ` · ${tc("notPlacedInWorld")}`}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{tc("fixtureOpponentLabel")}</span>
          <input aria-label={tc("fixtureOpponentAria")} disabled={busy !== null} onChange={(event) => setOpponent(event.target.value)} placeholder={tc("fixtureOpponentPlaceholder")} type="text" value={opponent} />
        </label>
        <label className="field">
          <span>{tc("fixtureDateLabel", { today: list.today })}</span>
          <input aria-label={tc("fixtureDateAria")} data-fixture-date={list.today} disabled={busy !== null} onChange={(event) => { dateWasTyped.current = true; setDate(event.target.value); }} placeholder={list.today} type="text" value={date} />
        </label>
        <label className="field">
          <span>{tc("fixtureCompetitionLabel", { max: caps.competition_max })}</span>
          <input aria-label={tc("fixtureCompetitionAria")} disabled={busy !== null} maxLength={caps.competition_max} onChange={(event) => setCompetition(event.target.value)} type="text" value={competition} />
        </label>
      </div>
      <label className="field">
        <span>{tc("fixtureNoteLabel", { max: caps.fixture_note_max })}</span>
        <input aria-label={tc("fixtureNoteAria")} disabled={busy !== null} maxLength={caps.fixture_note_max} onChange={(event) => setText(event.target.value)} type="text" value={text} />
      </label>

      <p className="muted" style={{ fontSize: "0.84rem" }}>
        {tc("namesNote", {
          team: team ? ` — ${team.squad_size} on ${team.name}` : "",
          players: caps.needs_players,
          keepers: caps.needs_keepers,
          choices: caps.minute_choices.join(", "),
          default: caps.default_minutes,
        })}
      </p>

      <div className="row wrap">
        <button aria-label={tc("arrangeAria")} className="btn" data-testid="fixture-arrange" disabled={busy !== null || !teamId || !opponent.trim()} onClick={arrange} type="button">
          {busy === "fixture-arrange" ? tc("arranging") : tc("arrangeFixture")}
        </button>
      </div>
      <CallNote note={note} />
      <FixtureBoard busy={busy} list={list} onErase={erase} onPlay={play} />
    </div>
  );
}

/** The tenant's calendar, with the play and erase actions the doors answer. */
export function FixtureBoard({ busy, list, onErase, onPlay }: { busy: string | null; list: FixtureList; onErase: (fixture: FixtureRow) => void; onPlay: (fixture: FixtureRow) => void }) {
  const tc = useTranslations("club");
  const counted = list.items.reduce((sum, row) => sum + row.appearances, 0);
  return (
    <div className="stack">
      <div className="row wrap" data-testid="fixture-totals">
        <span className="badge">{tc("totalArranged", { count: list.total })}</span>
        <span className="badge">{tc("totalPlayed", { count: list.played })}</span>
        <span className="badge">{tc("totalToPlay", { count: list.unplayed })}</span>
        <span className="badge">{tc("totalAppearances", { count: list.appearances })}</span>
        <span className="badge">
          {tc("totalAllowed", { held: list.fixtures_held, max: list.limit })}
        </span>
        {/* The page adds its own column up and says whether the door's figure agrees, rather than printing the
            door's total on trust — the two are counts over the same rows, so a disagreement is a live defect. */}
        <span className={counted === list.appearances ? "badge badge--ok" : "badge badge--warn"} data-testid="fixture-count-agrees">
          {counted === list.appearances
            ? tc("appearancesAgree")
            : tc("appearancesDisagree", { counted, printed: list.appearances })}
        </span>
      </div>

      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>{tc("thFixture")}</th>
              <th>{tc("thSide")}</th>
              <th>{tc("thOpponent")}</th>
              <th>{tc("thCompetition")}</th>
              <th>{tc("thNames")}</th>
              <th>{tc("thAppearances")}</th>
              <th>{tc("thEngineRow")}</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {list.items.map((row) => (
              <tr data-fixture={row.id} key={row.id}>
                <td>
                  <span className={row.status === "played" ? "badge badge--ok" : "badge"}>{row.status}</span>
                  <div className="mono" style={{ fontSize: "0.78rem" }}>
                    {row.scheduled_on} · {row.team?.name ?? tc("noTeam")}
                  </div>
                </td>
                <td>{row.side}</td>
                <td>{row.opponent ? <Link href={row.opponent.path}>{row.opponent.name}</Link> : <span className="muted">{row.opponent_name || tc("nobody")}</span>}</td>
                <td>{row.competition || <span className="muted">{tc("uncupplied")}</span>}</td>
                <td data-testid={`fixture-named-${row.id}`}>
                  {row.named.length}
                  {row.named.some((person) => person.is_minor)
                    ? tc("minorCount", { count: row.named.filter((person) => person.is_minor).length })
                    : ""}
                  {row.named_gone > 0 ? tc("erasedSince", { count: row.named_gone }) : ""}
                </td>
                <td>{row.appearances}</td>
                <td>{row.match ? <Link href={row.match.path}>{row.match.slug}</Link> : <span className="muted">{tc("notPlayed")}</span>}</td>
                <td className="row wrap" style={{ gap: "0.35rem" }}>
                  {row.status !== "played" && (
                    <button
                      aria-label={tc("playAria", {
                        date: row.scheduled_on,
                        opponent: row.opponent?.name ?? row.opponent_name,
                      })}
                      className="btn btn--sm"
                      data-testid={`fixture-play-${row.id}`}
                      disabled={busy !== null}
                      onClick={() => onPlay(row)}
                      type="button"
                    >
                      {busy === `fixture-play-${row.id}` ? tc("playing") : tc("playIt")}
                    </button>
                  )}
                  <button aria-label={tc("eraseAria", { date: row.scheduled_on })} className="btn btn--sm btn--ghost" data-testid={`fixture-erase-${row.id}`} disabled={busy !== null} onClick={() => onErase(row)} type="button">
                    {busy === `fixture-erase-${row.id}` ? tc("erasing") : tc("eraseFixture")}
                  </button>
                </td>
              </tr>
            ))}
            {list.items.length === 0 && (
              <tr>
                <td colSpan={8}>
                  <span className="muted">{tc("nothingArranged")}</span>
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {Object.keys(list.by_competition).length > 0 && (
        <p className="muted" data-testid="fixture-competitions" style={{ fontSize: "0.82rem" }}>
          {tc("byCompetition", {
            value: Object.entries(list.by_competition).map(([key, value]) => `${key} ${value}`).join(" · "),
          })}
        </p>
      )}
      <p className="muted" style={{ fontSize: "0.82rem" }}>{list.rule}</p>
      <p className="muted" style={{ fontSize: "0.82rem" }}>
        {list.formulas.appearances}
      </p>
    </div>
  );
}
