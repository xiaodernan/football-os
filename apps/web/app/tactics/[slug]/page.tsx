import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { ISO_FORMULA, Pitch, Pitch3D } from "@/components/pitch";
import { PhasePlayer } from "@/components/PhasePlayer";
import { BandLegend, ChangeNav, MetricTable, Verdicts } from "@/components/tactics";
import { Meter, Panel } from "@/components/ui";
import { JsonLd, OriginBadge, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { CounterfactualResponse, FeedbackResponse, SystemDetail, SystemList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

async function load(slug: string) {
  return readWorld<SystemDetail>(`/tactics/${encodeURIComponent(slug)}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const t = await getTranslations("tactics");
  const result = await load(slug);
  const system = result.ok ? result.data : null;
  const width = system?.metrics_in.find((metric) => metric.key === "width")?.value;
  const behind = system?.metrics_in.find((metric) => metric.key === "space_behind")?.value;
  return pageMetadata({
    title: system ? `${system.name} — tactical system` : slug.replace(/-/g, " "),
    description: system
      ? t("metaDescriptionSystem", { idea: system.idea, width: width?.toFixed(1) ?? "", behind: behind?.toFixed(1) ?? "", depth: system.block_depth, top: system.press_line_y })
      : t("metaDescriptionFallback"),
    path: `/tactics/${slug}`,
  });
}

function DeltaTable({ rows, t }: { rows: CounterfactualResponse["metrics"]; t: (key: string) => string }) {
  return (
    <div className="world-tablewrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">{t("tableMeasure")}</th>
            <th scope="col">{t("deltaBefore")}</th>
            <th scope="col">{t("deltaAfter")}</th>
            <th scope="col">{t("deltaChange")}</th>
            <th scope="col">{t("tableFormula")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.key}>
              <td>{row.label}</td>
              <td className="num mono">
                {row.before.toFixed(2)} {row.unit}
              </td>
              <td className="num mono">
                {row.after.toFixed(2)} {row.unit}
              </td>
              <td className={`num mono ${row.delta > 0.05 ? "tac-metric--up" : row.delta < -0.05 ? "tac-metric--down" : "muted"}`}>
                {Math.abs(row.delta) < 0.05 ? t("noChange") : `${row.delta > 0 ? "+" : ""}${row.delta.toFixed(2)} ${row.unit}`}
              </td>
              <td className="tac-formula">{row.formula}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default async function TacticsDetailPage({ params, searchParams }: Props) {
  const [{ slug }, rawQuery] = await Promise.all([params, searchParams]);
  const query = cleanParams(rawQuery);
  const tn = await getTranslations("nav");
  const t = await getTranslations("tactics");
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable eyebrow={tn("tactics")} message={result.message} title={t("unavailableTitle")} />;
  }

  const system = result.data;
  const changeKey = query.change;
  const counterfactual = changeKey
    ? await readWorld<CounterfactualResponse>(`/tactics/${encodeURIComponent(system.slug)}/counterfactual`, {
        change: changeKey,
        phase: query.phase === "out" ? "out" : "in",
      })
    : null;
  const siblings = await readWorld<SystemList>("/tactics", { formation: system.formation, page_size: 20 });
  const analysis = await readWorld<FeedbackResponse>(`/tactics/${encodeURIComponent(system.slug)}/feedback`);
  const phase = query.phase === "out" ? "out" : "in";
  const unknownChange = counterfactual && !counterfactual.ok && counterfactual.status === 422;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: tn("tactics") }}
        eyebrow={`Tactical Lab · ${system.formation} · ${system.temperament_label}`}
        lede={system.idea}
        provenance={system}
        title={system.name}
      >
        <div className="row wrap" style={{ gap: "0.6rem", marginTop: "0.75rem" }}>
          <OriginBadge provenance={system} />
          <div className="tag-list">
            <span className="chip">{t("chipPressLine", { value: system.press_line_y })}</span>
            <span className="chip">{t("chipBlock", { value: system.block_depth })}</span>
            <span className="chip">{t("chipNarrowing", { value: system.defensive_narrowing })}</span>
        <span className="chip mono" title={t("contentHashTitle")}>
              {system.content_hash.slice(0, 12)}…
            </span>
          </div>
        </div>
      </WorldHead>

      <JsonLd
        data={{
          "@context": "https://schema.org",
          "@type": "Article",
          headline: system.name,
          description: t("jsonLdDescription", { idea: system.idea, metrics: system.metrics_in.map((metric) => `${metric.label.toLowerCase()} ${metric.value.toFixed(1)} ${metric.unit}`).join(", ") }),
          url: absolute(system.path),
          mainEntityOfPage: { "@type": "WebPage", "@id": absolute(system.path) },
          author: { "@type": "Organization", name: "FOOTBALL OS" },
          publisher: { "@type": "Organization", name: "FOOTBALL OS" },
          inLanguage: "en",
          isAccessibleForFree: true,
          keywords: [system.formation, system.temperament_key, t("keywordTacticalSystem"), t("inPossession"), t("outOfPossession")].join(", "),
        }}
      />

      <Panel eyebrow={t("counterfactualEyebrow")} title={t("counterfactualTitle")}>
        <div className="stack-sm">
          <ChangeNav
            active={changeKey}
            base={`/tactics/${system.slug}`}
            changes={system.counterfactuals}
            query={{ phase: query.phase ?? "" }}
          />
          <p className="muted world-section-note">{t("counterfactualNote")}</p>
        </div>
      </Panel>

      {unknownChange && (
        <div className="notice notice--warn">
          {t("unknownChange", { change: changeKey ?? "", count: system.counterfactuals.length })}{" "}
          {counterfactual && !counterfactual.ok ? counterfactual.message : ""}
        </div>
      )}

      {counterfactual?.ok && (
        <Panel eyebrow={counterfactual.data.change.label} title={t("boardBeforeAfterTitle")}>
          <div className="tac-boards">
            <Pitch
              before={counterfactual.data.board_before}
              caption={t("boardBeforeAfterCaption")}
              slots={counterfactual.data.board_after}
              title={t("boardAfterTitle", { name: system.name, change: counterfactual.data.change.label.toLowerCase() })}
            />
            <div className="stack-sm">
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                {counterfactual.data.change.note}
              </p>
              <p className="muted world-section-note">
                {t("appliesTo", {
                  targets: counterfactual.data.change.target.join(", "),
                  phase: counterfactual.data.change.phase.replace("_", " "),
                  moved: counterfactual.data.moved_count,
                  total: counterfactual.data.metrics.length,
                })}
              </p>
              {counterfactual.data.clamped.length > 0 && (
                <div className="notice notice--warn">
                  {t("clampedNotice", { count: counterfactual.data.clamped.length })}
                </div>
              )}
              <Link className="btn btn--sm" href={`/tactics/${system.slug}`}>
                {t("showUnchanged")}
              </Link>
            </div>
          </div>
          <div style={{ marginTop: "0.75rem" }}>
            <DeltaTable rows={counterfactual.data.metrics} t={t} />
          </div>
        </Panel>
      )}

      <Panel eyebrow={t("phasesEyebrow")} title={t("phasesTitle")}>
        <div className="tac-boards">
          <div className="stack-sm">
            <p className="eyebrow">{t("phaseIn")}</p>
            <Pitch slots={system.phase_in} title={t("pitchTitleIn", { name: system.name })} />
          </div>
          <div className="stack-sm">
            <p className="eyebrow">{t("phaseOut")}</p>
            <Pitch slots={system.phase_out} title={t("pitchTitleOut", { name: system.name })} />
          </div>
        </div>
        <div className="stack-sm" style={{ marginTop: "0.75rem" }}>
          <BandLegend />
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {system.transform_note}
          </p>
          <p className="muted world-section-note">
            {t("bothBoardsNote", { block_depth: system.block_depth, press_line: system.press_line_y })}
          </p>
        </div>
      </Panel>

      <Panel eyebrow={t("framesEyebrow")} title={t("framesTitle")}>
        <PhasePlayer inPhase={system.phase_in} outPhase={system.phase_out} transform={system.transform_note} />
      </Panel>

      {/* §13 asks for 2D and 3D. A `<details>` rather than a toggle button: the view is a second way of reading
          numbers that are already on the page, so it needs no client state to open, and it stays in the
          document for a reader who has no JavaScript. */}
      <Panel eyebrow={t("isoEyebrow")} title={t("isoTitle")}>
        <details className="stack-sm" data-testid="pitch-3d">
          <summary>{t("isoSummary")}</summary>
          <div className="stack-sm" style={{ marginTop: "0.75rem" }}>
            <Pitch3D slots={system.phase_in} title={t("pitchTitleIn", { name: system.name })} />
            <p className="muted mono" style={{ fontSize: "0.82rem" }} data-iso-formula={ISO_FORMULA}>
              {ISO_FORMULA}
            </p>
            <p className="muted" style={{ fontSize: "0.86rem" }}>
              {t("isoNote")}
            </p>
            <p className="muted world-section-note">{t("isoNotNote")}</p>
          </div>
        </details>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={t("phaseIn")} title={t("measuredTitle")}>
          <MetricTable metrics={system.metrics_in} />
        </Panel>
        <Panel eyebrow={t("phaseOut")} title={t("measuredTitle")}>
          <MetricTable metrics={system.metrics_out} />
        </Panel>
      </div>

      <Panel eyebrow={t("verdictEyebrow")} title={t("verdictTitle")}>
        <Verdicts risks={system.risks} strengths={system.strengths} />
      </Panel>

      <Panel
        action={
          analysis.ok ? (
            <span className="chip mono" title={t("analysisChipTitle")}>
              {analysis.data.demo_mode ? t("analysisChipDemo") : t("analysisChipModel", { model: analysis.data.model })}
            </span>
          ) : null
        }
        eyebrow={t("analysisEyebrow", {
          grounded: analysis.ok ? analysis.data.points.length : 0,
          refused: analysis.ok ? analysis.data.ungrounded.length : 0,
        })}
        title={t("analysisTitle")}
      >
        {analysis.ok ? (
          <div className="stack">
            {analysis.data.points.map((point) => (
              <article className="tac-point" key={point.topic}>
                <p className="eyebrow">
                  {point.label} · {point.metric.value.toFixed(1)} {point.metric.unit} ·{" "}
                  {point.metric.phase === "out" ? t("phaseOutLower") : t("phaseInLower")}
                </p>
                <p>{point.statement}</p>
                <blockquote className="tac-quote">
                  “{point.citation.quote}”
                  <footer>
                    <Link className="world-link" href={point.citation.ref}>
                      {point.citation.title} · passage {point.citation.ordinal}
                    </Link>{" "}
                    <span className="muted mono">score {point.score.toFixed(3)}</span>
                  </footer>
                </blockquote>
                <p className="tac-formula">{point.metric.formula}</p>
              </article>
            ))}

            {analysis.data.ungrounded.length > 0 && (
              <div className="notice notice--warn">
                <p className="eyebrow">{t("refusedEyebrow")}</p>
                <ul className="reasons">
                  {analysis.data.ungrounded.map((item) => (
                    <li className="reasons__item" key={item.topic}>
                      <strong>{item.label}</strong>
                      {typeof item.value === "number" ? ` (${item.value.toFixed(1)} ${item.unit})` : ""} — {item.reason}
                    </li>
                  ))}
                </ul>
                <p style={{ marginTop: "0.4rem" }}>{t("refusedNote")}</p>
              </div>
            )}

            <p className="muted world-section-note">
              {t("analysisMethod", {
                method: analysis.data.method,
                scanned: analysis.data.scanned_chunks.toLocaleString("en-GB"),
                backend: analysis.data.retrieval_backend,
                provider: analysis.data.provider,
              })}
            </p>
          </div>
        ) : (
          <div className="notice notice--warn">{analysis.message}</div>
        )}
      </Panel>

      <Panel eyebrow={t("rolesEyebrow", { count: system.roles.length })} title={t("rolesTitle")}>
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">{t("tableRole")}</th>
                <th scope="col">{t("tableBand")}</th>
                <th scope="col">{t("phaseIn")}</th>
                <th scope="col">{t("phaseOut")}</th>
                <th scope="col">{t("tableRisks")}</th>
              </tr>
            </thead>
            <tbody>
              {system.roles.map((role, index) => (
                <tr key={`${role.key}-${index}`}>
                  <td className="mono">{role.key}</td>
                  <td className="muted">{role.band}</td>
                  <td>{role.in_possession}</td>
                  <td>{role.out_of_possession}</td>
                  <td className="muted">{role.risk}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={t("methodEyebrow")} title={t("methodTitle")}>
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>{t("labelBuildUp")}</dt>
              <dd>{system.build_up}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelTempo")}</dt>
              <dd>{system.tempo}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelPressing")}</dt>
              <dd>{system.pressing_trigger}</dd>
            </div>
            <div className="world-kv__row">
              <dt>{t("labelWidth")}</dt>
              <dd>{system.width_note}</dd>
            </div>
          </dl>
          <ul className="reasons" style={{ marginTop: "0.7rem" }}>
            {system.instructions.map((line, index) => (
              <li className="reasons__item" key={`instruction-${index}`}>
                {line}
              </li>
            ))}
          </ul>
        </Panel>

        <Panel
          eyebrow={t("demandsEyebrow")} title={t("demandsTitle")}
          action={
            <span className="chip" title={t("demandsChipTitle")}>
              {t("demandsChip")}
            </span>
          }
        >
          <div className="stack-sm">
            {Object.entries(system.demands)
              .sort(([, left], [, right]) => right - left)
              .map(([attribute, level]) => (
                <Meter key={attribute} label={attribute.replace(/_/g, " ")} max={99} value={level} />
              ))}
            <p className="muted world-section-note">{t("demandsNote")}</p>
          </div>
        </Panel>
      </div>

      {siblings.ok && siblings.data.items.length > 1 && (
        <Panel eyebrow={t("siblingsEyebrow")} title={t("siblingsTitle")}>
          <div className="tag-list">
            {siblings.data.items
              .filter((item) => item.slug !== system.slug)
              .map((item) => (
                <Link className="chip" href={`/tactics/compare?a=${encodeURIComponent(system.slug)}&b=${encodeURIComponent(item.slug)}&phase=${phase}`} key={item.slug}>
                  {item.temperament_label}
                </Link>
              ))}
          </div>
          <p className="muted world-section-note" style={{ marginTop: "0.6rem" }}>
            {t("siblingsNote")}
          </p>
        </Panel>
      )}

      <Provenance provenance={system} />
    </div>
  );
}
