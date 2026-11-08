"use client";

import { useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { Panel } from "@/components/ui";
import { KeyValueGrid } from "@/components/world";
import { browserFetch, errorMessage } from "@/lib/api";
import type { CareerTraining, CareerTrainingWork } from "@/lib/types";

const money = (value: number) => value.toLocaleString("en-GB");

/**
 * The training ground (M13 Phase 11 item 47).
 *
 * A level is bought from the balance like a stand, and each one makes the world's training sessions
 * count 10% more toward a player's development. This panel prints the level, the bonus and the next
 * price, then posts the number of levels to `/careers/{slug}/training`.
 */
export function CareerTrainingPanel({
  ident,
  view,
  remaining,
  limitation,
}: {
  ident: string;
  view: CareerTraining;
  remaining: number;
  limitation: string;
}) {
  const t = useTranslations("careerDetail");
  const tCommon = useTranslations("common");
  const router = useRouter();
  const [levels, setLevels] = useState(1);
  const [busy, setBusy] = useState(false);
  const [answer, setAnswer] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const room = view.max_level - view.level;
  const offRange = !Number.isInteger(levels) || levels < 1 || levels > room;
  const affordable = view.next_cost !== null && view.next_cost <= remaining;

  async function build() {
    setBusy(true);
    setAnswer(null);
    setError(null);
    const result = await browserFetch<{
      built: boolean;
      levels: CareerTrainingWork[];
      training: CareerTraining;
    }>(`/careers/${encodeURIComponent(ident)}/training`, {
      method: "POST",
      body: { levels },
    });
    if (!result.ok) {
      setError(`${result.error.code} — ${errorMessage(result.error, tCommon("requestFailed"))}`);
      setBusy(false);
      return;
    }
    const spent = result.data.levels.reduce((sum, row) => sum + row.amount, 0);
    setAnswer(
      t("trainingBuilt", {
        levels: result.data.levels.length,
        amount: money(spent),
        units: result.data.training.units,
        level: result.data.training.level,
      }),
    );
    router.refresh();
    setBusy(false);
  }

  return (
    <Panel eyebrow={t("trainingEyebrow", { level: view.level, max: view.max_level })} title={t("trainingTitle")}>
      <div className="stack-sm">
        <p className="muted">{t("trainingIntro")}</p>

        <KeyValueGrid
          rows={[
            [t("trainingKvLevel"), t("trainingLevelValue", { level: view.level, max: view.max_level })],
            [t("trainingKvBonus"), t("trainingBonusValue", { bonus: view.bonus_pct })],
            [
              t("trainingKvNext"),
              view.next_cost !== null && view.next_bonus_pct !== null
                ? t("trainingNextValue", {
                    cost: money(view.next_cost),
                    bonus: view.next_bonus_pct - view.bonus_pct,
                    units: view.units,
                  })
                : t("trainingMaxed"),
            ],
            [t("trainingKvSpent"), `${money(view.spent)} ${view.units}`],
          ]}
        />

        {view.available ? (
          <div className="stack-sm">
            <label className="muted" htmlFor="training-levels">
              {t("trainingLevelsLabel", { max: room })}
            </label>
            <input
              id="training-levels"
              className="input"
              type="number"
              min={1}
              max={room}
              step={1}
              value={levels}
              onChange={(event) => setLevels(Number(event.target.value))}
            />
            {offRange ? <p className="notice notice--warn">{t("trainingOffRange", { max: room })}</p> : null}
            <button
              className="button button--ghost"
              type="button"
              onClick={build}
              disabled={busy || offRange || !affordable}
            >
              {busy ? t("trainingBusy") : t("trainingButton", { levels })}
            </button>
            {!affordable ? <p className="notice notice--warn">{t("trainingTooDear")}</p> : null}
            {answer ? <p className="notice">{answer}</p> : null}
            {error ? <p className="notice notice--warn">{error}</p> : null}
          </div>
        ) : (
          <div className="empty">
            <strong>{t("trainingClosedTitle")}</strong>
            <p className="muted">{view.reason ?? t("trainingClosedBody")}</p>
          </div>
        )}

        {view.rows.length > 0 ? (
          <ul className="stack-sm">
            {view.rows.map((row) => (
              <li key={row.id} className="muted">
                {t("trainingRow", {
                  before: row.level_before,
                  after: row.level_after,
                  bonus: row.bonus_pct_after,
                  amount: money(row.amount),
                  units: row.amount_units,
                })}
              </li>
            ))}
          </ul>
        ) : null}

        <p className="muted">{view.note}</p>
        <p className="mono muted">
          {t("trainingFormulaLabel")}: {view.formula}
        </p>
        <p className="notice notice--warn">{limitation}</p>
      </div>
    </Panel>
  );
}
