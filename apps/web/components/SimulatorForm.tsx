"use client";

import { useRouter } from "next/navigation";
import { useMemo, useState } from "react";

import { browserFetch } from "@/lib/api";
import type { SimOptions, SimRow } from "@/lib/types";

/**
 * The fixture picker. It asks the API to play the match and then navigates to the stored report
 * rather than rendering the JSON it just received: the numbers on the page arrive through the same
 * read path as every other page, so the client cannot show a version of a match that was not kept.
 *
 * The club and system lists come from the server-rendered payload. This form does not know any
 * football — it sends two slugs, two system slugs, a length and an optional seed, and it reports the
 * server's own refusal if it cannot play.
 */

const NO_SYSTEM = "";

export function SimulatorForm({ options }: { options: SimOptions }) {
  const router = useRouter();
  const [home, setHome] = useState(options.teams[0]?.slug ?? "");
  const [away, setAway] = useState(options.teams[1]?.slug ?? "");
  const [homeSystem, setHomeSystem] = useState(NO_SYSTEM);
  const [awaySystem, setAwaySystem] = useState(NO_SYSTEM);
  const [minutes, setMinutes] = useState(90);
  const [seed, setSeed] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Systems are authored against a shape, so the useful short list is the one a club can actually staff.
  const homeFormation = options.teams.find((team) => team.slug === home)?.formation ?? "";
  const awayFormation = options.teams.find((team) => team.slug === away)?.formation ?? "";
  const homeSystems = useMemo(
    () => options.systems.filter((system) => system.formation === homeFormation),
    [options.systems, homeFormation],
  );
  const awaySystems = useMemo(
    () => options.systems.filter((system) => system.formation === awayFormation),
    [options.systems, awayFormation],
  );

  function swap() {
    setHome(away);
    setAway(home);
    setHomeSystem(awaySystem);
    setAwaySystem(homeSystem);
  }

  async function submit() {
    setBusy(true);
    setError(null);
    const parsed = seed.trim() === "" ? undefined : Number(seed.trim());
    if (parsed !== undefined && (!Number.isInteger(parsed) || parsed < 0 || parsed > 2_147_483_647)) {
      setError("A seed has to be a whole number between 0 and 2,147,483,647 — or blank, so the server picks one and stores it.");
      setBusy(false);
      return;
    }
    const result = await browserFetch<SimRow>("/simulate", {
      method: "POST",
      body: {
        home_team: home,
        away_team: away,
        home_system: homeSystem === NO_SYSTEM ? null : homeSystem,
        away_system: awaySystem === NO_SYSTEM ? null : awaySystem,
        minutes,
        seed: parsed,
      },
    });
    if (!result.ok) {
      setError(`${result.error.code}: ${result.error.message}`);
      setBusy(false);
      return;
    }
    if (!result.data.path) {
      setError("The server played the match but returned no link to its report.");
      setBusy(false);
      return;
    }
    router.push(result.data.path);
    router.refresh();
  }

  return (
    <div className="stack sim-form">
      <div className="sim-fixtures">
        <label className="stack-sm">
          <span className="eyebrow">Home</span>
          <select aria-label="Home club" className="input" onChange={(event) => setHome(event.target.value)} value={home}>
            {options.teams.map((team) => (
              <option key={team.team_id} value={team.slug}>
                {team.name} · {team.formation} · {team.overall} overall
              </option>
            ))}
          </select>
        </label>
        <button className="btn btn--ghost btn--sm sim-swap" onClick={swap} title="Play the tie the other way round" type="button">
          ⇄ Swap
        </button>
        <label className="stack-sm">
          <span className="eyebrow">Away</span>
          <select aria-label="Away club" className="input" onChange={(event) => setAway(event.target.value)} value={away}>
            {options.teams.map((team) => (
              <option key={team.team_id} value={team.slug}>
                {team.name} · {team.formation} · {team.overall} overall
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="sim-fixtures">
        <label className="stack-sm">
          <span className="eyebrow">Home tactical system</span>
          <select aria-label="Home tactical system" className="input" onChange={(event) => setHomeSystem(event.target.value)} value={homeSystem}>
            <option value={NO_SYSTEM}>Club&apos;s own formation — no authored shape</option>
            {homeSystems.map((system) => (
              <option key={system.slug} value={system.slug}>
                {system.name}
              </option>
            ))}
          </select>
        </label>
        <label className="stack-sm">
          <span className="eyebrow">Away tactical system</span>
          <select aria-label="Away tactical system" className="input" onChange={(event) => setAwaySystem(event.target.value)} value={awaySystem}>
            <option value={NO_SYSTEM}>Club&apos;s own formation — no authored shape</option>
            {awaySystems.map((system) => (
              <option key={system.slug} value={system.slug}>
                {system.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="row wrap sim-controls">
        <label className="stack-sm">
          <span className="eyebrow">Minutes</span>
          <select aria-label="Match length" className="input" onChange={(event) => setMinutes(Number(event.target.value))} value={minutes}>
            {options.engine.minute_choices.map((choice) => (
              <option key={choice} value={choice}>
                {choice}&apos; · {Math.ceil(choice / options.engine.block_minutes)} blocks
              </option>
            ))}
          </select>
        </label>
        <label className="stack-sm">
          <span className="eyebrow">Seed (optional)</span>
          <input
            aria-label="Seed"
            className="input"
            inputMode="numeric"
            onChange={(event) => setSeed(event.target.value)}
            placeholder="blank: the server picks and stores one"
            value={seed}
          />
        </label>
        <button className="btn btn--primary" disabled={busy || options.teams.length < 2} onClick={submit} type="button">
          {busy ? "Playing…" : "Play match"}
        </button>
      </div>

      <p className="muted world-section-note">
        A tactical system adds the metres the Tactical Lab measured from its eleven coordinates; without one the match is played
        from the club&apos;s own formation and those inputs stay empty. The seed is kept with the match, so the same fixture and
        seed replay to the same report — {options.engine.calibration}
      </p>
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
