import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";

import { Pitch } from "@/components/pitch";
import { BandLegend } from "@/components/tactics";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { absolute } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { SharedBoard } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/** A shared link is sent to a person, not to a crawler: no index, and no way to reach it by guessing. */
export const metadata: Metadata = {
  title: "Shared tactical board",
  description: "A board arranged by a FOOTBALL OS account, with the eight measurements recomputed from its saved positions.",
  robots: { index: false, follow: false },
  alternates: { canonical: absolute("/tactics") },
};

export default async function SharedBoardPage({ params }: Props) {
  const { token } = await params;
  const result = await readWorld<SharedBoard>(`/boards/shared/${encodeURIComponent(token)}`);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable eyebrow="Tactical Lab" message={result.message} title="Shared tactical board" />;
  }

  const board = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: "Tactical Lab" }}
        eyebrow={`Shared by ${board.owner.name} · read-only`}
        lede={board.note || "The account that arranged this board left no note with it."}
        provenance={board}
        title={board.name}
      />

      <Panel eyebrow={`${board.phase_in.length} positions · ${board.origin_system ? `copied from ${board.origin_system}` : "drawn from scratch"}`} title="Both phases as the owner saved them">
        <div className="tac-boards">
          <div className="stack-sm">
            <p className="eyebrow">In possession</p>
            <Pitch caption={`${board.phase_in.length} positions · metres, 68 × 105`} slots={board.phase_in} title={`${board.name} in possession`} />
          </div>
          <div className="stack-sm">
            <p className="eyebrow">Out of possession</p>
            <Pitch caption={`${board.phase_out.length} positions · metres, 68 × 105`} slots={board.phase_out} title={`${board.name} out of possession`} />
          </div>
        </div>
        <div style={{ marginTop: "0.7rem" }}>
          <BandLegend />
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow="Measured from the saved coordinates" title="In possession">
          <div className="world-tablewrap">
            <table className="table">
              <tbody>
                {board.metrics_in.map((metric) => (
                  <tr key={metric.key}>
                    <td>{metric.label}</td>
                    <td className="num mono">
                      {metric.value.toFixed(2)} {metric.unit}
                    </td>
                    <td className="tac-formula">{metric.formula}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
        <Panel eyebrow="Measured from the saved coordinates" title="Out of possession">
          <div className="world-tablewrap">
            <table className="table">
              <tbody>
                {board.metrics_out.map((metric) => (
                  <tr key={metric.key}>
                    <td>{metric.label}</td>
                    <td className="num mono">
                      {metric.value.toFixed(2)} {metric.unit}
                    </td>
                    <td className="tac-formula">{metric.formula}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Panel>
      </div>

      <p className="muted world-section-note">
        This page cannot be edited, and the account behind it is named only as “{board.owner.name}”.{" "}
        <Link className="world-link" href="/tactics">
          Browse the 50 authored systems
        </Link>{" "}
        — those are this project&apos;s own, with the reasoning written out on each page.
      </p>

      <Provenance provenance={board} extra={<span className="chip">shared by link, revocable by the owner at any time</span>} />
    </div>
  );
}
