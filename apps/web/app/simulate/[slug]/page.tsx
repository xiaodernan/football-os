import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { SimTools } from "@/components/SimTools";
import { BlockTable, EventTimeline, InputList, LineupList, ModelPanel, ScoreLine, SideComparison, type SideHrefs } from "@/components/simulation";
import { absolute } from "@/lib/site";
import { currentUser, serverFetch } from "@/lib/server";
import type { SimOptions, SimRow } from "@/lib/types";

import "../../../styles/tactics.css";
import "../../../styles/simulate.css";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }> };

/** A stored simulation is the account's own working record, so it is not published (spec §61). */
export async function generateMetadata(): Promise<Metadata> {
  const t = await getTranslations("simulate");
  return {
    title: t("reportTitle"),
    description: t("reportDescription"),
    robots: { index: false, follow: false },
    alternates: { canonical: absolute("/simulate") },
  };
}

function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export default async function SimulationReportPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fsimulate");

  const t = await getTranslations("simulate");
  const { slug } = await params;
  const result = await serverFetch<SimRow>(`/simulate/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable eyebrow={t("backLabel")} message={result.error.message} title={t("reportTitle")} />;
  }
  const match = result.data;
  const report = match.report;
  if (!report) {
    return (
      <WorldUnavailable
        eyebrow={t("backLabel")}
        message={t("noReport")}
        title={t("reportTitle")}
      />
    );
  }

  // The report carries team ids; the club pages are addressed by slug, so the hrefs come from the public options route.
  const choices = await serverFetch<SimOptions>("/simulate/options");
  const hrefs: SideHrefs = choices.ok
    ? {
        home: choices.data.teams.find((team) => team.team_id === report.sides.home.team_id)?.path,
        away: choices.data.teams.find((team) => team.team_id === report.sides.away.team_id)?.path,
      }
    : {};

  const home = report.sides.home;
  const away = report.sides.away;
  const scored = report.events.filter((event) => event.type === "goal");
  // The timeline is read from `sim_events` where the server has rows, and from the report where it does
  // not — and the panel prints which of the two it did, because "one query per event" and "this match
  // predates the table" are different claims about the same list of minutes.
  const timeline = match.timeline;
  const shown = timeline?.events ?? report.events;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/simulate", label: t("backLabel") }}
        eyebrow={`${report.model.model_version} · ${report.model.minutes}′ · seed ${report.model.seed}`}
        lede={t("headLede")}
        provenance={{ data_origin: match.data_origin, is_demo_data: match.is_demo_data, disclaimer: match.disclaimer }}
        title={`${home.short_name} ${report.score.home} – ${report.score.away} ${away.short_name}`}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title={t("digestTitle")}>
            {t("digestChip", { digest: match.digest })}
          </span>
          <span className="chip num">{t("blocksChip", { count: report.blocks.length, minutes: report.model.block_minutes })}</span>
          <span className="chip num">{t("eventsChip", { count: report.events.length })}</span>
          <span className="chip num">{t("goalsChip", { count: scored.length })}</span>
          <span className="badge badge--sim">simulation</span>
        </div>
      </WorldHead>

      <Panel eyebrow={t("scorelineEyebrow")} title={`${home.name} v ${away.name}`}>
        <div className="stack">
          <ScoreLine hrefs={hrefs} report={report} />
          <div className="sim-possession">
            <span className="num mono">{pct(home.possession_pct)}</span>
            <span className="muted" style={{ fontSize: "0.78rem" }}>
              {t("possessionLabel")}
            </span>
            <span className="num mono" style={{ textAlign: "right" }}>
              {pct(away.possession_pct)}
            </span>
          </div>
          <div className="bar" aria-hidden="true">
            <div className="bar__fill" style={{ width: `${home.possession_pct}%` }} />
          </div>
          <p className="tac-formula">{report.possession_share.formula}</p>
          <div className="tag-list">
            {Object.entries(report.totals).map(([key, value]) => (
              <span className="chip mono" key={key}>
                {key} {value}
              </span>
            ))}
          </div>
          <p className="muted world-section-note">
            {t("totalsNote", { goals: report.totals.goal_events, shots: report.totals.shots, xg: report.totals.expected_goals })}
          </p>
        </div>
      </Panel>

      <Panel
        eyebrow={t("totalsEyebrow", { home: home.short_name, away: away.short_name })}
        title={t("totalsTitle")}
      >
        <SideComparison report={report} />
      </Panel>

      <Panel
        eyebrow={timeline ? t("timelineEyebrowDb", { count: timeline.count, source: timeline.source }) : t("timelineEyebrowNo", { count: report.events.length })}
        title={t("timelineTitle")}
      >
        <div className="stack">
          <EventTimeline events={shown} />
          {timeline && (
            <div className="stack-sm" data-testid="timeline-provenance">
              <p className="tac-formula">{timeline.attribution_formula}</p>
              <div className="tag-list">
                {Object.entries(timeline.by_type).map(([type, count]) => (
                  <span className="chip mono" key={type}>
                    {type} {count}
                  </span>
                ))}
                <span className="chip num" title={timeline.formula}>
                  {t("storedRowsChip", { count: timeline.stored_rows })}
                </span>
                <span className="chip num" title={t("tracedTitle")}>
                  {t("tracedChip", { identified: timeline.identified, total: timeline.count })}
                </span>
              </div>
              {timeline.ambiguous_names.length > 0 && (
                <p className="notice notice--warn">
                  {t("ambiguousNames", { count: timeline.ambiguous_names.length, names: timeline.ambiguous_names.join(", ") })}
                </p>
              )}
              {timeline.unnamed_names.length > 0 && (
                <p className="muted world-section-note">
                  {t("unnamedNames", { count: timeline.unnamed_names.length, names: timeline.unnamed_names.join(", ") })}
                </p>
              )}
              <p className="muted world-section-note">{timeline.consistency}</p>
            </div>
          )}
        </div>
      </Panel>

      <Panel
        eyebrow={t("blocksEyebrow", { count: report.blocks.length })}
        title={t("blocksTitle")}
      >
        <div className="stack">
          <BlockTable blocks={report.blocks} />
          <p className="muted world-section-note">
            {t.rich("blocksNote", { mono: (chunks) => <span className="mono">{chunks}</span> })}
          </p>
        </div>
      </Panel>

      <Panel eyebrow={t("inputsEyebrow")} title={t("inputsTitle", { name: home.name })}>
        <div className="stack">
          <InputList side={home} />
          <LineupList side={home} />
        </div>
      </Panel>

      <Panel eyebrow={t("inputsEyebrow")} title={t("inputsTitle", { name: away.name })}>
        <div className="stack">
          <InputList side={away} />
          <LineupList side={away} />
        </div>
      </Panel>

      <Panel eyebrow={report.model.model_version} title={t("modelPanelTitle")}>
        <ModelPanel model={report.model} />
      </Panel>

      <Panel eyebrow={t("ownerEyebrow")} title={t("ownerTitle")}>
        <div className="stack-sm">
          <SimTools digest={match.digest} ident={match.slug} />
          <p className="muted world-section-note">
            {t.rich("ownerNote", {
              lab: (chunks) => <Link className="world-link" href="/tactics">{chunks}</Link>,
              lib: (chunks) => <Link className="world-link" href="/knowledge">{chunks}</Link>,
            })}
          </p>
        </div>
      </Panel>

      <Provenance
        provenance={{ data_origin: match.data_origin, is_demo_data: match.is_demo_data, disclaimer: match.disclaimer }}
        extra={
          <span className="chip mono" title={t("inputsFromTitle")}>
            {t("inputsFromChip", { sources: report.provenance.inputs_are_from.join(", ") })}
          </span>
        }
      />
    </div>
  );
}
