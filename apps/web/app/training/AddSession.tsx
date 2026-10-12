"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { useState } from "react";

import { browserFetch, errorMessage } from "@/lib/api";

type Planned = { session_id: string; status: string };

const MINUTE_CHOICES = [10, 15, 20, 25, 30, 40, 45, 60];

export function AddSession({ drillId, title, durationMin }: { drillId: string; title: string; durationMin: number }) {
  const t = useTranslations("training");
  const router = useRouter();
  const options = MINUTE_CHOICES.includes(durationMin) ? MINUTE_CHOICES : [durationMin, ...MINUTE_CHOICES].sort((a, b) => a - b);
  const [minutes, setMinutes] = useState(durationMin);
  const [hasPitch, setHasPitch] = useState(true);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<Planned | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function add() {
    if (busy) return;
    setBusy(true);
    setError(null);
    const response = await browserFetch<Planned>("/trainings/sessions", {
      method: "POST",
      body: { drill_id: drillId, available_minutes: minutes, equipment: [], has_pitch: hasPitch },
    });
    if (response.ok) {
      setDone(response.data);
      router.refresh();
    } else if (response.status === 409 && response.error.code === "no_player") {
      setError(t("needProfile"));
    } else {
      setError(errorMessage(response.error, t("addFailed")));
    }
    setBusy(false);
  }

  if (done) {
    return (
      <div className="stack-sm">
        <div className="notice">
          {t("addedToToday", { title })}
        </div>
        <div>
          <Link className="btn btn--primary btn--sm" href="/training">
            {t("goLogIt")}
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="stack-sm">
      {error && <div className="notice notice--warn">{error}</div>}
      <div className="form-grid">
        <label className="field">
          <span className="field__label">{t("minutesLabel")}</span>
          <select className="select" value={minutes} onChange={(event) => setMinutes(Number(event.target.value))}>
            {options.map((value) => (
              <option value={value} key={value}>
                {t("minuteOption", { value, suffix: value === durationMin ? t("designLength") : "" })}
              </option>
            ))}
          </select>
        </label>
        <label className="check" style={{ alignSelf: "end" }}>
          <input type="checkbox" checked={hasPitch} onChange={(event) => setHasPitch(event.target.checked)} />
          <span>{t("pitchAccess")}</span>
        </label>
      </div>
      <div>
        <button type="button" className="btn btn--primary" onClick={add} disabled={busy}>
          {busy ? t("adding") : t("addToSessions")}
        </button>
      </div>
    </div>
  );
}
