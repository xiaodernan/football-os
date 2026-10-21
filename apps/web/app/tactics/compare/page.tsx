import type { Metadata } from "next";
import Link from "next/link";
import { getTranslations } from "next-intl/server";

import { Pitch } from "@/components/pitch";
import { BandLegend } from "@/components/tactics";
import { Panel } from "@/components/ui";
import { JsonLd, OriginBadge, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { CompareResponse, SystemDetail, SystemList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { searchParams: Promise<Record<string, string | string[] | undefined>> };

/** A comparison is a question asked of two pages, not a page of its own: kept out of the index. */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("tactics");
  return {
    title: t("compareMetaTitle"),
    description: t("compareMetaDescription"),
    robots: { index: false, follow: true },
    alternates: { canonical: absolute("/tactics/compare") },
  };
}

const PHASES: { key: string; labelKey: string }[] = [
  { key: "in", labelKey: "phaseIn" },
  { key: "out", labelKey: "phaseOut" },
];

export default async function TacticsComparePage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const phase = query.phase === "out" ? "out" : "in";
  const tn = await getTranslations("nav");
  const t = await getTranslations("tactics");
  const options = await readWorld<SystemList>("/tactics", { page_size: 50 });

  const pair =
    query.a && query.b && query.a !== query.b
      ? await readWorld<CompareResponse>("/tactics/compare", { a: query.a, b: query.b, phase })
      : null;
  const [left, right] =
    pair?.ok && query.a && query.b
      ? await Promise.all([
          readWorld<SystemDetail>(`/tactics/${encodeURIComponent(query.a)}`),
          readWorld<SystemDetail>(`/tactics/${encodeURIComponent(query.b)}`),
        ])
      : [null, null];

  if (!options.ok) {
    return (
      <WorldUnavailable
        eyebrow={tn("tactics")}
        message={options.message}
        title={t("compareUnavailableTitle")}
        detail={t("compareUnavailableDetail")}
      />
    );
  }

  const systems = options.data.items;
  const boardOf = (detail: SystemDetail | undefined) =>
    detail ? (phase === "out" ? detail.phase_out : detail.phase_in) : [];
  const sides = pair?.ok && left?.ok && right?.ok ? [{ detail: left.data, tag: "A" }, { detail: right.data, tag: "B" }] : [];
  const phaseWord = phase === "out" ? t("phaseOutLower") : t("phaseInLower");

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: tn("tactics") }}
        eyebrow={t("compareEyebrow")}
        lede={t("compareLede")}
        provenance={options.data}
        title={t("compareMetaTitle")}
      >
        <form action="/tactics/compare" className="stack-sm" method="get" style={{ marginTop: "1rem", gap: "0.6rem" }}>
          <div className="grid grid-2">
            <label className="field">
              <span className="field__label">{t("systemA")}</span>
              <select className="select" defaultValue={query.a ?? ""} name="a">
                <option value="">{t("chooseOption")}</option>
                {systems.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">{t("systemB")}</span>
              <select className="select" defaultValue={query.b ?? ""} name="b">
                <option value="">{t("chooseOption")}</option>
                {systems.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="row wrap" style={{ gap: "0.6rem" }}>
            <label className="field grow">
              <span className="field__label">{t("phaseLabel")}</span>
              <select className="select" defaultValue={phase} name="phase">
                {PHASES.map((option) => (
                  <option key={option.key} value={option.key}>
                    {t(option.labelKey)}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn btn--primary" type="submit">
              {t("compareButton")}
            </button>
          </div>
        </form>
      </WorldHead>

      {!pair && (
        <div className="empty">
          <strong>{t("compareEmptyTitle")}</strong>
          <span className="muted">{t("compareEmptyNote", { count: systems.length })}</span>
        </div>
      )}

      {pair && !pair.ok && pair.status === 404 && (
        <div className="notice notice--warn">
          {t("unknownNotice", { a: query.a ?? "", b: query.b ?? "" })}
        </div>
      )}
      {pair && !pair.ok && pair.status !== 404 && <WorldUnavailable eyebrow={tn("tactics")} message={pair.message} title={t("compareUnavailableTitle")} />}

      {pair?.ok && left?.ok && right?.ok && (
        <>
          <JsonLd
            data={{
              "@context": "https://schema.org",
              "@type": "WebPage",
              name: `${pair.data.a.name} vs ${pair.data.b.name}`,
              description: pair.data.note,
              url: `${absolute("/tactics/compare")}?a=${encodeURIComponent(pair.data.a.slug)}&b=${encodeURIComponent(pair.data.b.slug)}&phase=${phase}`,
              isAccessibleForFree: true,
            }}
          />

          <div className="tac-boards">
            {sides.map(({ detail, tag }) => (
              <Panel
                action={<span className={`chip ${tag === "A" ? "chip--accent" : ""}`}>{tag}</span>}
                eyebrow={`${detail.formation} · ${detail.temperament_label}`}
                key={detail.slug}
                title={detail.name}
              >
                <div className="stack-sm">
                  <Pitch
                    axisOpponent={t("pitchAxisOpponent")}
                    axisOwn={t("pitchAxisOwn")}
                    caption={t("sideBoardCaption", { count: boardOf(detail).length, phase: phaseWord })}
                    slots={boardOf(detail)}
                    title={t(phase === "out" ? "pitchTitleOut" : "pitchTitleIn", { name: detail.name })}
                  />
                  <p className="muted" style={{ fontSize: "0.88rem" }}>
                    {detail.idea}
                  </p>
                  <Link className="btn btn--ghost btn--sm" href={detail.path}>
                    {t("openSide", { tag })}
                  </Link>
                </div>
              </Panel>
            ))}
          </div>

          <Panel
            action={
              <div className="row wrap" style={{ gap: "0.4rem" }}>
                <OriginBadge provenance={pair.data} />
                <span className="chip">{phaseWord}</span>
              </div>
            }
            eyebrow={t("measuresEyebrow", { a: pair.data.a.name, b: pair.data.b.name })}
            title={t("measuresTitle")}
          >
            <div className="stack">
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">{t("tableMeasure")}</th>
                      <th scope="col">{t("tableA", { name: pair.data.a.name })}</th>
                      <th scope="col">{t("tableB", { name: pair.data.b.name })}</th>
                      <th scope="col">{t("tableDelta")}</th>
                      <th scope="col">{t("tableFormula")}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {pair.data.metrics.map((row) => (
                      <tr key={row.key}>
                        <td>{row.label}</td>
                        <td className="num mono">
                          {row.a.toFixed(2)} {row.unit}
                        </td>
                        <td className="num mono">
                          {row.b.toFixed(2)} {row.unit}
                        </td>
                        <td className={`num mono ${row.delta > 0.05 ? "tac-metric--up" : row.delta < -0.05 ? "tac-metric--down" : "muted"}`}>
                          {Math.abs(row.delta) < 0.05 ? t("level") : `${row.delta > 0 ? "+" : ""}${row.delta.toFixed(2)} ${row.unit}`}
                        </td>
                        <td className="tac-formula">{row.formula}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <BandLegend />
              <p className="muted world-section-note">{pair.data.note}</p>
              <p className="muted world-section-note">{t("noindexNote")}</p>
            </div>
          </Panel>

          <Provenance provenance={pair.data} />
        </>
      )}
    </div>
  );
}
