import Link from "next/link";
import type { ReactNode } from "react";
import { useTranslations } from "next-intl";

import type { BoardMetric, ChangeCard, SystemBrief } from "@/lib/types";

import "../styles/tactics.css";

/**
 * Tactical Lab furniture (spec §11–§13, §62).
 *
 * The rule these components hold to: a measurement is never printed without the formula that made it,
 * and authored content is never labelled demo data — the corpus and the boards are things this
 * repository wrote, which is a different claim from "simulated football world" and both are different
 * from "the user's own data".
 */

/**
 * Provenance vocabulary lives in `OriginBadge` (components/world.tsx): one badge for one fact, so the
 * lab, the world and the library cannot label the same `data_origin` three different ways.
 */

const BANDS: { key: string; color: string }[] = [
  { key: "bandGoalkeeper", color: "#ffd166" },
  { key: "bandDefensive", color: "#5fa8ff" },
  { key: "bandMidfield", color: "#35f0a4" },
  { key: "bandAttacking", color: "#ff6b6b" },
];

export function BandLegend() {
  const t = useTranslations("tactics");
  return (
    <div className="band-legend">
      {BANDS.map((band) => (
        <span className="band-legend__key" key={band.key}>
          <span className="band-legend__dot" style={{ background: band.color }} />
          {t(band.key)}
        </span>
      ))}
    </div>
  );
}

/** Metric · value · formula. The formula column is the point: a number without it is a claim. */
export function MetricTable({ metrics }: { metrics: BoardMetric[] }) {
  const t = useTranslations("tactics");
  return (
    <div className="world-tablewrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">{t("tableMeasure")}</th>
            <th scope="col">{t("tableValue")}</th>
            <th scope="col">{t("tableFormula")}</th>
          </tr>
        </thead>
        <tbody>
          {metrics.map((metric) => (
            <tr key={metric.key}>
              <td>{metric.label}</td>
              <td className="num tac-metric mono">
                {/* A measure this payload does not carry is shown as absent, never borrowed from another row. */}
                {Number.isFinite(metric.value) ? `${metric.value.toFixed(2)} ${metric.unit}` : t("metricAbsent")}
              </td>
              <td className="tac-formula">{metric.formula}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function Verdicts({ strengths, risks }: { strengths: string[]; risks: string[] }) {
  const t = useTranslations("tactics");
  return (
    <div className="tac-verdicts">
      <div className="stack-sm">
        <p className="eyebrow">{t("verdictsStrengths")}</p>
        <ul className="reasons">
          {strengths.map((line, index) => (
            <li className="reasons__item" key={`strength-${index}`}>
              {line}
            </li>
          ))}
        </ul>
      </div>
      <div className="stack-sm">
        <p className="eyebrow">{t("verdictsCosts")}</p>
        <ul className="reasons">
          {risks.map((line, index) => (
            <li className="reasons__item" key={`risk-${index}`}>
              {line}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}

/** Server links, so the counterfactual is a URL you can send someone rather than a client state. */
export function ChangeNav({
  base,
  changes,
  active,
  query,
}: {
  base: string;
  changes: ChangeCard[];
  active?: string;
  query: Record<string, string>;
}) {
  const href = (key?: string) => {
    const params = new URLSearchParams(query);
    params.delete("change");
    if (key) params.set("change", key);
    const qs = params.toString();
    return qs ? `${base}?${qs}` : base;
  };
  const t = useTranslations("tactics");
  return (
    <div className="stack-sm">
      <span className="eyebrow">{t("changeNavEyebrow")}</span>
      <div className="tag-list">
        <Link className={`chip ${active ? "" : "chip--accent"}`} href={href()}>
          {t("changeNavNone")}
        </Link>
        {changes.map((change) => (
          <Link className={`chip ${active === change.key ? "chip--accent" : ""}`} href={href(change.key)} key={change.key} title={change.note}>
            {change.label}
          </Link>
        ))}
      </div>
    </div>
  );
}

export function SystemCard({ item, footnote }: { item: SystemBrief; footnote?: ReactNode }) {
  const t = useTranslations("tactics");
  return (
    <Link className="tac-card" href={item.path}>
      <span className="tac-card__name">{item.name}</span>
      <span className="tac-card__idea">{item.idea}</span>
      <div className="tac-card__metrics">
        <span className="chip num" title={t("cardWideTitle")}>
          {item.in_possession.width?.toFixed(1)} {t("cardWide")}
        </span>
        <span className="chip num" title={t("cardBehindTitle")}>
          {item.in_possession.space_behind?.toFixed(1)} {t("cardBehind")}
        </span>
        <span className="chip num" title={t("cardBlockTitle")}>
          {item.out_of_possession.spacing?.toFixed(1)} {t("cardBlock")}
        </span>
      </div>
      {footnote}
    </Link>
  );
}
