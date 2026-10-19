"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
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
  const t = useTranslations("simulate");
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
      setError(t("seedError"));
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
      setError(t("noPathError"));
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
          <span className="eyebrow">{t("home")}</span>
          <select aria-label={t("ariaHomeClub")} className="input" onChange={(event) => setHome(event.target.value)} value={home}>
            {options.teams.map((team) => (
              <option key={team.team_id} value={team.slug}>
                {t("teamOption", { name: team.name, formation: team.formation, overall: team.overall })}
              </option>
            ))}
          </select>
        </label>
        <button className="btn btn--ghost btn--sm sim-swap" onClick={swap} title={t("swapTitle")} type="button">
          {t("swap")}
        </button>
        <label className="stack-sm">
          <span className="eyebrow">{t("away")}</span>
          <select aria-label={t("ariaAwayClub")} className="input" onChange={(event) => setAway(event.target.value)} value={away}>
            {options.teams.map((team) => (
              <option key={team.team_id} value={team.slug}>
                {t("teamOption", { name: team.name, formation: team.formation, overall: team.overall })}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="sim-fixtures">
        <label className="stack-sm">
          <span className="eyebrow">{t("homeSystem")}</span>
          <select aria-label={t("homeSystem")} className="input" onChange={(event) => setHomeSystem(event.target.value)} value={homeSystem}>
            <option value={NO_SYSTEM}>{t("ownFormation")}</option>
            {homeSystems.map((system) => (
              <option key={system.slug} value={system.slug}>
                {system.name}
              </option>
            ))}
          </select>
        </label>
        <label className="stack-sm">
          <span className="eyebrow">{t("awaySystem")}</span>
          <select aria-label={t("awaySystem")} className="input" onChange={(event) => setAwaySystem(event.target.value)} value={awaySystem}>
            <option value={NO_SYSTEM}>{t("ownFormation")}</option>
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
          <span className="eyebrow">{t("minutes")}</span>
          <select aria-label={t("ariaMatchLength")} className="input" onChange={(event) => setMinutes(Number(event.target.value))} value={minutes}>
            {options.engine.minute_choices.map((choice) => (
              <option key={choice} value={choice}>
                {t("minuteOption", { minutes: choice, blocks: Math.ceil(choice / options.engine.block_minutes) })}
              </option>
            ))}
          </select>
        </label>
        <label className="stack-sm">
          <span className="eyebrow">{t("seedLabel")}</span>
          <input
            aria-label={t("ariaSeed")}
            className="input"
            inputMode="numeric"
            onChange={(event) => setSeed(event.target.value)}
            placeholder={t("seedPlaceholder")}
            value={seed}
          />
        </label>
        <button className="btn btn--primary" disabled={busy || options.teams.length < 2} onClick={submit} type="button">
          {busy ? t("playing") : t("playMatch")}
        </button>
      </div>

      <p className="muted world-section-note">
        {t("formNote", { calibration: options.engine.calibration })}
      </p>
      {error && (
        <p className="notice notice--warn" role="status">
          {error}
        </p>
      )}
    </div>
  );
}
