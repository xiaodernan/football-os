import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

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
export const metadata: Metadata = {
  title: "Simulated match report",
  description: "A block-by-block report from the possession-block model, with the inputs, formulas and seed that produced it.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/simulate") },
};

function pct(value: number): string {
  return `${value.toFixed(1)}%`;
}

export default async function SimulationReportPage({ params }: Props) {
  const user = await currentUser();
  if (!user) redirect("/login?next=%2Fsimulate");

  const { slug } = await params;
  const result = await serverFetch<SimRow>(`/simulate/${encodeURIComponent(slug)}`);
  if (!result.ok) {
    if (result.status === 404) notFound();
    return <WorldUnavailable eyebrow="Match simulator" message={result.error.message} title="Simulated match report" />;
  }
  const match = result.data;
  const report = match.report;
  if (!report) {
    return (
      <WorldUnavailable
        eyebrow="Match simulator"
        message="The stored row came back without its report, so nothing on this page is rendered from memory."
        title="Simulated match report"
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
        back={{ href: "/simulate", label: "Match simulator" }}
        eyebrow={`${report.model.model_version} · ${report.model.minutes}′ · seed ${report.model.seed}`}
        lede="Every figure below is a model output, printed with the rate that produced it. The scoreline is what this model did with these two squads — not what a real match would have produced."
        provenance={{ data_origin: match.data_origin, is_demo_data: match.is_demo_data, disclaimer: match.disclaimer }}
        title={`${home.short_name} ${report.score.home} – ${report.score.away} ${away.short_name}`}
      >
        <div className="tag-list" style={{ marginTop: "0.7rem" }}>
          <span className="chip mono" title="SHA-256 prefix of the report, taken before the digest key existed.">
            digest {match.digest}
          </span>
          <span className="chip num">{report.blocks.length} blocks of {report.model.block_minutes}′</span>
          <span className="chip num">{report.events.length} events</span>
          <span className="chip num">{scored.length} goals scored in the model</span>
          <span className="badge badge--sim">simulation</span>
        </div>
      </WorldHead>

      <Panel eyebrow="The scoreline" title={`${home.name} v ${away.name}`}>
        <div className="stack">
          <ScoreLine hrefs={hrefs} report={report} />
          <div className="sim-possession">
            <span className="num mono">{pct(home.possession_pct)}</span>
            <span className="muted" style={{ fontSize: "0.78rem" }}>
              possession
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
            Goals in the model: {report.totals.goal_events} of {report.totals.shots} shots, against {report.totals.expected_goals}{" "}
            expected goals. A model that scores fewer goals than its own xG is not broken — the xG is a sum of probabilities and
            each chance was rolled once.
          </p>
        </div>
      </Panel>

      <Panel eyebrow={`${home.short_name} v ${away.short_name} · as the engine counted them`} title="Match totals">
        <SideComparison report={report} />
      </Panel>

      <Panel eyebrow={timeline ? `${timeline.count} events · read from ${timeline.source}` : `${report.events.length} events · in minute order`} title="Timeline">
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
                  {timeline.stored_rows} stored rows
                </span>
                <span className="chip num" title="An event names a player only when that side's eleven holds the name once.">
                  {timeline.identified} of {timeline.count} traced to a player
                </span>
              </div>
              {timeline.ambiguous_names.length > 0 && (
                <p className="notice notice--warn">
                  {timeline.ambiguous_names.length} name{timeline.ambiguous_names.length > 1 ? "s" : ""} on this timeline belong to
                  two players in the same eleven ({timeline.ambiguous_names.join(", ")}), so those events are kept without a player
                  rather than guessed at.
                </p>
              )}
              {timeline.unnamed_names.length > 0 && (
                <p className="muted world-section-note">
                  {timeline.unnamed_names.length} event{timeline.unnamed_names.length > 1 ? "s" : ""} named the club rather than a
                  player ({timeline.unnamed_names.join(", ")}), which is what the engine prints when a side has no eleven to name
                  from.
                </p>
              )}
              <p className="muted world-section-note">{timeline.consistency}</p>
            </div>
          )}
        </div>
      </Panel>

      <Panel eyebrow={`${report.blocks.length} blocks · the model rolls inside a block, not minute by minute`} title="Block by block">
        <div className="stack">
          <BlockTable blocks={report.blocks} />
          <p className="muted world-section-note">
            Each multiplier is printed exactly as the model applied it, including the ones that did nothing: a
            <span className="mono"> man_down_attack </span>of 1.00 means nobody was sent off in that block, and a
            <span className="mono"> fatigue </span>below 1.00 is the model reducing shot volume as the match runs on.
          </p>
        </div>
      </Panel>

      <Panel eyebrow="Measured from stored rows, not chosen for the page" title={`What went into ${home.name}`}>
        <div className="stack">
          <InputList side={home} />
          <LineupList side={home} />
        </div>
      </Panel>

      <Panel eyebrow="Measured from stored rows, not chosen for the page" title={`What went into ${away.name}`}>
        <div className="stack">
          <InputList side={away} />
          <LineupList side={away} />
        </div>
      </Panel>

      <Panel eyebrow={report.model.model_version} title="The model behind this report">
        <ModelPanel model={report.model} />
      </Panel>

      <Panel eyebrow="owner-only" title="Re-check it, or delete it">
        <div className="stack-sm">
          <SimTools digest={match.digest} ident={match.slug} />
          <p className="muted world-section-note">
            Only this account can read a stored match. Nothing here is a forecast:{" "}
            <Link className="world-link" href="/tactics">
              the Tactical Lab
            </Link>{" "}
            is where the shapes come from, and{" "}
            <Link className="world-link" href="/knowledge">
              the knowledge library
            </Link>{" "}
            is where the terms mean something.
          </p>
        </div>
      </Panel>

      <Provenance
        provenance={{ data_origin: match.data_origin, is_demo_data: match.is_demo_data, disclaimer: match.disclaimer }}
        extra={
          <span className="chip mono" title="The tables the inputs were read from">
            inputs from: {report.provenance.inputs_are_from.join(", ")}
          </span>
        }
      />
    </div>
  );
}
