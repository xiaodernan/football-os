"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";
import type { Player } from "@/lib/types";

const POSITIONS = ["GK", "CB", "LB", "RB", "CDM", "CM", "CAM", "LM", "RM", "LW", "RW", "ST", "CF"];
const LEVELS = [
  { value: "beginner", label: "Beginner" },
  { value: "intermediate", label: "Intermediate" },
  { value: "advanced", label: "Advanced" },
  { value: "elite", label: "Elite" },
];
const FEET = [
  { value: "right", label: "Right" },
  { value: "left", label: "Left" },
  { value: "both", label: "Both" },
];
const GOALS = [
  { value: "improve_first_touch", label: "Improve first touch" },
  { value: "improve_passing", label: "Improve passing" },
  { value: "improve_dribbling", label: "Improve dribbling" },
  { value: "improve_finishing", label: "Improve finishing" },
  { value: "improve_defending", label: "Improve defending" },
  { value: "improve_pressing", label: "Improve pressing" },
  { value: "improve_weak_foot", label: "Improve weak foot" },
  { value: "improve_fitness", label: "Improve fitness" },
  { value: "improve_vision", label: "Improve vision" },
  { value: "become_box_to_box", label: "Become box-to-box" },
  { value: "become_playmaker", label: "Become a playmaker" },
  { value: "become_inverted_winger", label: "Become an inverted winger" },
];

/** Six sliders whose keys are guaranteed valid attribute names on the backend. */
const SELF_RATED: { key: string; label: string }[] = [
  { key: "first_touch", label: "First touch" },
  { key: "passing", label: "Passing" },
  { key: "dribbling", label: "Dribbling" },
  { key: "finishing", label: "Finishing" },
  { key: "speed", label: "Speed" },
  { key: "vision", label: "Vision" },
];

export function OnboardingForm() {
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
    if (!name.trim()) found.push("Enter your player name.");
    const ageNum = Number(age);
    if (!Number.isInteger(ageNum) || ageNum < 8 || ageNum > 45) found.push("Age must be between 8 and 45.");
    if (height.trim()) {
      const heightNum = Number(height);
      if (!Number.isInteger(heightNum) || heightNum < 120 || heightNum > 215) {
        found.push("Height must be between 120 and 215 cm, or left blank.");
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
      setErrors(["Your session expired. Please sign in again."]);
      return;
    }
    setErrors([errorMessage(result.error, "We could not save your profile. Check the details and try again.")]);
  }

  return (
    <form
      className="panel"
      onSubmit={onSubmit}
      style={{ display: "grid", gap: "1rem", padding: "1.15rem" }}
    >
      <div className="field">
        <label className="field__label" htmlFor="name">
          Player name
        </label>
        <input
          id="name"
          className="input"
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Your name or nickname"
        />
      </div>

      <div className="form-grid">
        <div className="field">
          <label className="field__label" htmlFor="position">
            Position
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
            Level
          </label>
          <select id="level" className="select" value={level} onChange={(e) => setLevel(e.target.value)}>
            {LEVELS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="age">
            Age
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
          <span className="field__hint">Between 8 and 45.</span>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="foot">
            Preferred foot
          </label>
          <select id="foot" className="select" value={foot} onChange={(e) => setFoot(e.target.value)}>
            {FEET.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="goal">
            Main goal
          </label>
          <select id="goal" className="select" value={goal} onChange={(e) => setGoal(e.target.value)}>
            {GOALS.map((option) => (
              <option key={option.value} value={option.value}>
                {option.label}
              </option>
            ))}
          </select>
        </div>

        <div className="field">
          <label className="field__label" htmlFor="height">
            Height (cm) — optional
          </label>
          <input
            id="height"
            className="input"
            type="number"
            min={120}
            max={215}
            value={height}
            onChange={(e) => setHeight(e.target.value)}
            placeholder="e.g. 178"
          />
          <span className="field__hint">120–215, or leave blank.</span>
        </div>
      </div>

      <div className="stack-sm">
        <span className="eyebrow">Rate yourself (optional)</span>
        <p className="field__hint">
          Leave these untouched and the profile is fully derived from your position and level. Move a
          slider only to blend your own read of one attribute.
        </p>
        {SELF_RATED.map((attr) => {
          const isTouched = Boolean(touched[attr.key]);
          const value = ratings[attr.key] ?? 50;
          return (
            <div className="field" key={attr.key}>
              <label className="between" htmlFor={`rate-${attr.key}`} style={{ fontSize: "0.85rem" }}>
                <span className="muted">{attr.label}</span>
                <span className="mono num">
                  {isTouched ? value : "derived"}
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
        {pending ? "Building your profile…" : "Create my football identity"}
      </button>
    </form>
  );
}
