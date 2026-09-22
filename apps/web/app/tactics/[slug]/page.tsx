import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Pitch } from "@/components/pitch";
import { BandLegend, ChangeNav, MetricTable, Verdicts } from "@/components/tactics";
import { Meter, Panel } from "@/components/ui";
import { JsonLd, OriginBadge, Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute, pageMetadata } from "@/lib/site";
import { cleanParams, readWorld } from "@/lib/world";
import type { CounterfactualResponse, SystemDetail, SystemList } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ slug: string }>; searchParams: Promise<Record<string, string | string[] | undefined>> };

async function load(slug: string) {
  return readWorld<SystemDetail>(`/tactics/${encodeURIComponent(slug)}`);
}

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { slug } = await params;
  const result = await load(slug);
  const system = result.ok ? result.data : null;
  const width = system?.metrics_in.find((metric) => metric.key === "width")?.value;
  const behind = system?.metrics_in.find((metric) => metric.key === "space_behind")?.value;
  return pageMetadata({
    title: system ? `${system.name} — tactical system` : slug.replace(/-/g, " "),
    description: system
      ? `${system.idea} In possession: ${width?.toFixed(1)} m wide with ${behind?.toFixed(1)} m behind the back line; out of possession the same eleven players form a ${system.block_depth} m block with its top at ${system.press_line_y} m.`
      : "A tactical system in the FOOTBALL OS Tactical Lab: authored coordinates, measured in metres.",
    path: `/tactics/${slug}`,
  });
}

function DeltaTable({ rows }: { rows: CounterfactualResponse["metrics"] }) {
  return (
    <div className="world-tablewrap">
      <table className="table">
        <thead>
          <tr>
            <th scope="col">Measure</th>
            <th scope="col">Before</th>
            <th scope="col">After</th>
            <th scope="col">Change</th>
            <th scope="col">How it is obtained</th>
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
                {Math.abs(row.delta) < 0.05 ? "no change" : `${row.delta > 0 ? "+" : ""}${row.delta.toFixed(2)} ${row.unit}`}
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
  const result = await load(slug);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable eyebrow="Tactical Lab" message={result.message} title="Tactical system" />;
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
  const phase = query.phase === "out" ? "out" : "in";
  const unknownChange = counterfactual && !counterfactual.ok && counterfactual.status === 422;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: "Tactical Lab" }}
        eyebrow={`Tactical Lab · ${system.formation} · ${system.temperament_label}`}
        lede={system.idea}
        provenance={system}
        title={system.name}
      >
        <div className="row wrap" style={{ gap: "0.6rem", marginTop: "0.75rem" }}>
          <OriginBadge provenance={system} />
          <div className="tag-list">
            <span className="chip">press line {system.press_line_y} m</span>
            <span className="chip">block {system.block_depth} m deep</span>
            <span className="chip">defensive width ×{system.defensive_narrowing}</span>
            <span className="chip mono" title="Content hash of the stored row: change a coordinate and it changes.">
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
          description: `${system.idea} Measured: ${system.metrics_in.map((metric) => `${metric.label.toLowerCase()} ${metric.value.toFixed(1)} ${metric.unit}`).join(", ")} in possession.`,
          url: absolute(system.path),
          mainEntityOfPage: { "@type": "WebPage", "@id": absolute(system.path) },
          author: { "@type": "Organization", name: "FOOTBALL OS" },
          publisher: { "@type": "Organization", name: "FOOTBALL OS" },
          inLanguage: "en",
          isAccessibleForFree: true,
          keywords: [system.formation, system.temperament_key, "tactical system", "in possession", "out of possession"].join(", "),
        }}
      />

      <Panel eyebrow="Choose a change" title="What happens if…">
        <div className="stack-sm">
          <ChangeNav
            active={changeKey}
            base={`/tactics/${system.slug}`}
            changes={system.counterfactuals}
            query={{ phase: query.phase ?? "" }}
          />
          <p className="muted world-section-note">
            Every change is applied to the stored coordinates and the eight measures are recomputed from the result — the answer is never a
            conclusion kept in a column.
          </p>
        </div>
      </Panel>

      {unknownChange && (
        <div className="notice notice--warn">
          “{changeKey}” is not one of the {system.counterfactuals.length} changes this lab offers.{" "}
          {counterfactual && !counterfactual.ok ? counterfactual.message : ""}
        </div>
      )}

      {counterfactual?.ok && (
        <Panel eyebrow={counterfactual.data.change.label} title="The board, before and after">
          <div className="tac-boards">
            <Pitch
              before={counterfactual.data.board_before}
              caption="hollow = before · dashed arrow = the displacement asked for"
              slots={counterfactual.data.board_after}
              title={`${system.name} after ${counterfactual.data.change.label.toLowerCase()}`}
            />
            <div className="stack-sm">
              <p className="muted" style={{ fontSize: "0.9rem" }}>
                {counterfactual.data.change.note}
              </p>
              <p className="muted world-section-note">
                Applies to: {counterfactual.data.change.target.join(", ")} · phase: {counterfactual.data.change.phase.replace("_", " ")} ·{" "}
                {counterfactual.data.moved_count} of {counterfactual.data.metrics.length} measures moved.
              </p>
              {counterfactual.data.clamped.length > 0 && (
                <div className="notice notice--warn">
                  {counterfactual.data.clamped.length} position{counterfactual.data.clamped.length === 1 ? "" : "s"} would have left the
                  pitch, so it was clamped to the touchline or goal line rather than moved the full distance. The table below reports where
                  each player actually ended up.
                </div>
              )}
              <Link className="btn btn--sm" href={`/tactics/${system.slug}`}>
                Show the unchanged board
              </Link>
            </div>
          </div>
          <div style={{ marginTop: "0.75rem" }}>
            <DeltaTable rows={counterfactual.data.metrics} />
          </div>
        </Panel>
      )}

      <Panel eyebrow="Both phases, one structure" title="The boards">
        <div className="tac-boards">
          <div className="stack-sm">
            <p className="eyebrow">In possession</p>
            <Pitch slots={system.phase_in} title={`${system.name} in possession`} />
          </div>
          <div className="stack-sm">
            <p className="eyebrow">Out of possession</p>
            <Pitch slots={system.phase_out} title={`${system.name} out of possession`} />
          </div>
        </div>
        <div className="stack-sm" style={{ marginTop: "0.75rem" }}>
          <BandLegend />
          <p className="muted" style={{ fontSize: "0.9rem" }}>
            {system.transform_note}
          </p>
          <p className="muted world-section-note">
            Both boards carry the same eleven roles. The defending side is not a second drawing: it is the possession board mapped onto a{" "}
            {system.block_depth} m block whose top edge is the {system.press_line_y} m press line.
          </p>
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow="In possession" title="Measured">
          <MetricTable metrics={system.metrics_in} />
        </Panel>
        <Panel eyebrow="Out of possession" title="Measured">
          <MetricTable metrics={system.metrics_out} />
        </Panel>
      </div>

      <Panel eyebrow="Decided by the numbers above" title="What this shape is for, and what it costs">
        <Verdicts risks={system.risks} strengths={system.strengths} />
      </Panel>

      <Panel eyebrow={`${system.roles.length} slots in the field`} title="Roles, both ways">
        <div className="world-tablewrap">
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Role</th>
                <th scope="col">Band</th>
                <th scope="col">In possession</th>
                <th scope="col">Out of possession</th>
                <th scope="col">What it risks</th>
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
        <Panel eyebrow="Method" title="How this side plays">
          <dl className="world-kv">
            <div className="world-kv__row">
              <dt>Build-up</dt>
              <dd>{system.build_up}</dd>
            </div>
            <div className="world-kv__row">
              <dt>Tempo</dt>
              <dd>{system.tempo}</dd>
            </div>
            <div className="world-kv__row">
              <dt>Pressing trigger</dt>
              <dd>{system.pressing_trigger}</dd>
            </div>
            <div className="world-kv__row">
              <dt>Width</dt>
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
          eyebrow="The highest demand in the field for each" title="What it asks of a player"
          action={
            <span className="chip" title="Compared with your player's own tactical attributes on My Football.">
              attribute demand
            </span>
          }
        >
          <div className="stack-sm">
            {Object.entries(system.demands)
              .sort(([, left], [, right]) => right - left)
              .map(([attribute, level]) => (
                <Meter key={attribute} label={attribute.replace(/_/g, " ")} max={99} value={level} />
              ))}
            <p className="muted world-section-note">
              Six tactical attributes, taken as the maximum demanded by any role this shape fields. They are the same six stored on a
              player, so fit is a comparison rather than an opinion — the page for your own player shows the pairing.
            </p>
          </div>
        </Panel>
      </div>

      {siblings.ok && siblings.data.items.length > 1 && (
        <Panel eyebrow="Same shape, different temperament" title="Compare the trade">
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
            Eleven other systems share this shape; each comparison prints all eight measures side by side, with the formula for every one.
          </p>
        </Panel>
      )}

      <Provenance provenance={system} />
    </div>
  );
}
