"use client";

import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import type { Player } from "@/lib/types";

const POSITIONS = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST", "CF"];
// The value is the backend's own enum; the label is a catalogue key, so a locale switch repaints
// the option without the enum moving.
const LEVELS = [
  { value: "beginner", key: "levelBeginner" },
  { value: "intermediate", key: "levelIntermediate" },
  { value: "advanced", key: "levelAdvanced" },
  { value: "elite", key: "levelElite" },
];
const FEET = [
  { value: "right", key: "footRight" },
  { value: "left", key: "footLeft" },
  { value: "both", key: "footBoth" },
];
const GOALS = [
  { value: "improve_first_touch", key: "goalImproveFirstTouch" },
  { value: "improve_passing", key: "goalImprovePassing" },
  { value: "improve_dribbling", key: "goalImproveDribbling" },
  { value: "improve_finishing", key: "goalImproveFinishing" },
  { value: "improve_defending", key: "goalImproveDefending" },
  { value: "improve_pressing", key: "goalImprovePressing" },
  { value: "improve_weak_foot", key: "goalImproveWeakFoot" },
  { value: "improve_fitness", key: "goalImproveFitness" },
  { value: "improve_vision", key: "goalImproveVision" },
  { value: "become_box_to_box", key: "goalBecomeBoxToBox" },
  { value: "become_playmaker", key: "goalBecomePlaymaker" },
  { value: "become_inverted_winger", key: "goalBecomeInvertedWinger" },
];

/** Six sliders whose keys are guaranteed valid attribute names on the backend. */
const SELF_RATED: { key: string; labelKey: string }[] = [
  { key: "first_touch", labelKey: "attrFirstTouch" },
  { key: "passing", labelKey: "attrPassing" },
  { key: "dribbling", labelKey: "attrDribbling" },
  { key: "finishing", labelKey: "attrFinishing" },
  { key: "speed", labelKey: "attrSpeed" },
  { key: "vision", labelKey: "attrVision" },
];

export function OnboardingForm() {
  const t = useTranslations("onboarding");
  const router = useRouter();
  const [name, setName] = useState("");
  const [position, setPosition] = useState("CM");
  const [age, setAge] = useState("18");
  const [level, setLevel] = useState("intermediate");
  const [foot, setFoot] = useState("right");
  const [goal, setGoal] = useState("improve_passing");
  const [height, setHeight] = useState("");
  const [ratings, setRatings] = useState<Record<string, number>>({});
  const [touched, setTouched] = useState<Record<string, boolean>>({});
  const [errors, setErrors] = useState<string[]>([]);
  const [pending, setPending] = useState(false);

  function setRating(key: string, value: number) {
    setRatings((prev) => ({ ...prev, [key]: value }));
    setTouched((prev) => ({ ...prev, [key]: true }));
  }

  function validate(): string[] {
    const found: string[] = [];
    if (!name.trim()) found.push(t("errorName"));
    const ageNum = Number(age);
    if (!Number.isInteger(ageNum) || ageNum < 8 || ageNum > 45) found.push(t("errorAge"));
    if (height.trim()) {
      const heightNum = Number(height);
      if (!Number.isInteger(heightNum) || heightNum < 120 || heightNum > 215) {
        found.push(t("errorHeight"));
      }
    }
    return found;
  }

  async function onSubmit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const clientErrors = validate();
    if (clientErrors.length) {
      setErrors(clientErrors);
      return;
    }
    setErrors([]);
    setPending(true);

    const selfRated: Record<string, number> = {};
    for (const attr of SELF_RATED) {
      if (touched[attr.key]) selfRated[attr.key] = ratings[attr.key];
    }

    const body: Record<string, unknown> = {
      name: name.trim(),
      position,
      age: Number(age),
      level,
      preferred_foot: foot,
      goal,
      height_cm: height.trim() ? Number(height) : null,
    };
    if (Object.keys(selfRated).length > 0) body.self_rated_attributes = selfRated;

    const result = await browserFetch<Player>("/players", { method: "POST", body });
    if (result.ok) {
      router.push("/my-football");
      router.refresh();
      return;
    }
    setPending(false);
    if (result.status === 401) {
      setErrors([t("errorSession")]);
      return;
    }
    setErrors([errorMessage(result.error, t("errorSave"))]);
  }

  return (
    <form
      className="panel"
      onSubmit={onSubmit}
      style={{ display: "grid", gap: "1rem", padding: "1.15rem" }}
    >
      <div className="field">
        <label className="field__label" htmlFor="name">
          {t("labelName")}
        </label>
        <input
          id="name"
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder={t("placeholderName")}
        />
      </div>

      <div className="form-grid">
        <div className="field">
          <label className="field__label" htmlFor="position">
            {t("labelPosition")}
          </label>
          <select id="position" className="select" value={position} onChange={(e) => setPosition(e.target.value)}>
            {POSITIONS.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="level">
            {t("labelLevel")}
          </label>
          <select id="level" className="select" value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.key)}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="age">
            {t("labelAge")}
          </label>
          <input
            id="age"
            className="input"
            type="number"
            min={8}
            max={45}
            value={age}
            onChange={(e) => setAge(e.target.value)}
          />
          <span className="field__hint">{t("hintAge")}</span>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="foot">
            {t("labelFoot")}
          </label>
          <select id="foot" className="select" value={foot} onChange={(e) => setFoot(e.target.value)}>
            {FEET.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.key)}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="goal">
            {t("labelGoal")}
          </label>
          <select id="goal" className="select" value={goal} onChange={(e) => setGoal(e.target.value)}>
            {GOALS.map((option) => (
              <option key={option.value} value={option.value}>
                {t(option.key)}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="height">
            {t("labelHeight")}
          </label>
          <input
            id="height"
            className="input"
            type="number"
            min={120}
            max={215}
            value={height}
            onChange={(e) => setHeight(e.target.value)}
            placeholder={t("placeholderHeight")}
          />
          <span className="field__hint">{t("hintHeight")}</span>
        </div>
      </div>

      <div className="stack-sm">
        <span className="eyebrow">{t("selfRateEyebrow")}</span>
        <p className="field__hint">{t("selfRateHint")}</p>
        {SELF_RATED.map((attr) => {
          const isTouched = Boolean(touched[attr.key]);
          const value = ratings[attr.key] ?? 50;
          return (
            <div className="field" key={attr.key}>
              <label className="between" htmlFor={`rate-${attr.key}`} style={{ fontSize: "0.85rem" }}>
                <span className="muted">{t(attr.labelKey)}</span>
                <span className="mono num">
                  {isTouched ? value : t("derived")}
                </span>
              </label>
              <input
                id={`rate-${attr.key}`}
                type="range"
                min={1}
                max={99}
                defaultValue={50}
                onChange={(e) => setRating(attr.key, Number(e.target.value))}
                style={{ width: "100%" }}
              />
            </div>
          );
        })}
      </div>

      {errors.length > 0 && (
        <div className="notice notice--warn" role="alert">
          <ul className="reasons" style={{ margin: 0 }}>
            {errors.map((message, index) => (
              <li className="reasons__item" key={`${message}-${index}`}>
                {message}
              </li>
            ))}
          </ul>
        </div>
      )}

      <button className="btn btn--primary" type="submit" disabled={pending}>
        {pending ? t("submitting") : t("submit")}
      </button>
    </form>
  );
}
