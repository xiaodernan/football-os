import type { Metadata } from "next";
import Link from "next/link";

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
export const metadata: Metadata = {
  title: "Compare two tactical systems",
  description: "The same eight measurements, computed for two systems from the same phase, side by side.",
  robots: { index: false, follow: true },
  alternates: { canonical: absolute("/tactics/compare") },
};

const PHASES: { key: string; label: string }[] = [
  { key: "in", label: "In possession" },
  { key: "out", label: "Out of possession" },
];

export default async function TacticsComparePage({ searchParams }: Props) {
  const query = cleanParams(await searchParams);
  const phase = query.phase === "out" ? "out" : "in";
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
        eyebrow="Tactical Lab"
        message={options.message}
        title="Compare two systems"
        detail="The comparison reads the stored catalogue; start the API with scripts/dev.sh."
      />
    );
  }

  const systems = options.data.items;
  const boardOf = (detail: SystemDetail | undefined) =>
    detail ? (phase === "out" ? detail.phase_out : detail.phase_in) : [];
  const sides = pair?.ok && left?.ok && right?.ok ? [{ detail: left.data, tag: "A" }, { detail: right.data, tag: "B" }] : [];

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: "Tactical Lab" }}
        eyebrow="Same measurements · different systems"
        lede="Two authored structures, the eight measurements, and the difference between them. Nothing is averaged across the pair: each side is computed from its own coordinates."
        provenance={options.data}
        title="Compare two tactical systems"
      >
        <form action="/tactics/compare" className="stack-sm" method="get" style={{ marginTop: "1rem", gap: "0.6rem" }}>
          <div className="grid grid-2">
            <label className="field">
              <span className="field__label">System A</span>
              <select className="select" defaultValue={query.a ?? ""} name="a">
                <option value="">choose…</option>
                {systems.map((item) => (
                  <option key={item.slug} value={item.slug}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="field">
              <span className="field__label">System B</span>
              <select className="select" defaultValue={query.b ?? ""} name="b">
                <option value="">choose…</option>
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
              <span className="field__label">Phase</span>
              <select className="select" defaultValue={phase} name="phase">
                {PHASES.map((option) => (
                  <option key={option.key} value={option.key}>
                    {option.label}
                  </option>
                ))}
              </select>
            </label>
            <button className="btn btn--primary" type="submit">
              Compare
            </button>
          </div>
        </form>
      </WorldHead>

      {!pair && (
        <div className="empty">
          <strong>Pick two different systems</strong>
          <span className="muted">
            {systems.length} systems are loaded for the dropdowns. Until both are chosen nothing is computed — an empty comparison would have
            to invent a row to show you.
          </span>
        </div>
      )}

      {pair && !pair.ok && pair.status === 404 && (
        <div className="notice notice--warn">
          “{query.a}” or “{query.b}” is not a stored system, so nothing was measured. Pick from the list above.
        </div>
      )}
      {pair && !pair.ok && pair.status !== 404 && <WorldUnavailable eyebrow="Tactical Lab" message={pair.message} title="Compare two systems" />}

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
                    caption={`${boardOf(detail).length} positions · ${phase === "out" ? "out of" : "in"} possession`}
                    slots={boardOf(detail)}
                    title={`${detail.name} ${phase === "out" ? "out of possession" : "in possession"}`}
                  />
                  <p className="muted" style={{ fontSize: "0.88rem" }}>
                    {detail.idea}
                  </p>
                  <Link className="btn btn--ghost btn--sm" href={detail.path}>
                    Open {tag}
                  </Link>
                </div>
              </Panel>
            ))}
          </div>

          <Panel
            action={
              <div className="row wrap" style={{ gap: "0.4rem" }}>
                <OriginBadge provenance={pair.data} />
                <span className="chip">{phase === "out" ? "out of possession" : "in possession"}</span>
              </div>
            }
            eyebrow={`${pair.data.a.name} vs ${pair.data.b.name}`}
            title="Eight measurements, side by side"
          >
            <div className="stack">
              <div className="world-tablewrap">
                <table className="table">
                  <thead>
                    <tr>
                      <th scope="col">Measure</th>
                      <th scope="col">A · {pair.data.a.name}</th>
                      <th scope="col">B · {pair.data.b.name}</th>
                      <th scope="col">B − A</th>
                      <th scope="col">How it is obtained</th>
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
                          {Math.abs(row.delta) < 0.05 ? "level" : `${row.delta > 0 ? "+" : ""}${row.delta.toFixed(2)} ${row.unit}`}
                        </td>
                        <td className="tac-formula">{row.formula}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <BandLegend />
              <p className="muted world-section-note">{pair.data.note}</p>
              <p className="muted world-section-note">
                Both dropdowns are plain HTML with a GET form, so this page is reachable and shareable without JavaScript; it is
                <span className="mono"> noindex</span> because a comparison is a question, not a document.
              </p>
            </div>
          </Panel>

          <Provenance provenance={pair.data} />
        </>
      )}
    </div>
  );
}
