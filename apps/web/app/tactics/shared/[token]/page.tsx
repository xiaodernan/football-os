import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { getTranslations } from "next-intl/server";

import { Pitch } from "@/components/pitch";
import { BandLegend } from "@/components/tactics";
import { Panel } from "@/components/ui";
import { Provenance, WorldHead, WorldUnavailable } from "@/components/world";
import { sharedMetadata } from "@/lib/site";
import { readWorld } from "@/lib/world";
import type { SharedBoard } from "@/lib/types";

export const dynamic = "force-dynamic";

type Props = { params: Promise<{ token: string }> };

/**
 * A shared link is sent to a person, not to a crawler: no index, and no way to reach it by guessing. The card is
 * this board's own (§109) — before it had an `openGraph` of its own, the preview a reader saw named the site and
 * not the board somebody had just sent them.
 */
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { token } = await params;
  const t = await getTranslations("tactics");
  return sharedMetadata({
    title: t("sharedMetaTitle"),
    description: t("sharedMetaDescription"),
    sharePath: `/tactics/shared/${encodeURIComponent(token)}`,
    canonicalPath: "/tactics",
  });
}

export default async function SharedBoardPage({ params }: Props) {
  const { token } = await params;
  const tn = await getTranslations("nav");
  const t = await getTranslations("tactics");
  const result = await readWorld<SharedBoard>(`/boards/shared/${encodeURIComponent(token)}`);

  if (!result.ok) {
    if (result.notFound) notFound();
    return <WorldUnavailable eyebrow={tn("tactics")} message={result.message} title={t("sharedUnavailableTitle")} />;
  }

  const board = result.data;

  return (
    <div className="container page stack">
      <WorldHead
        back={{ href: "/tactics", label: tn("tactics") }}
        eyebrow={t("sharedEyebrow", { name: board.owner.name })}
        lede={board.note || t("sharedNoNote")}
        provenance={board}
        title={board.name}
      />

      <Panel
        eyebrow={t("sharedPanelEyebrow", {
          count: board.phase_in.length,
          origin: board.origin_system ? t("boardFromSystem", { system: board.origin_system }) : t("boardFromScratch"),
        })}
        title={t("sharedPanelTitle")}
      >
        <div className="tac-boards">
          <div className="stack-sm">
            <p className="eyebrow">{t("phaseIn")}</p>
            <Pitch caption={t("sharedPitchCaption", { count: board.phase_in.length })} slots={board.phase_in} title={t("pitchTitleIn", { name: board.name })} />
          </div>
          <div className="stack-sm">
            <p className="eyebrow">{t("phaseOut")}</p>
            <Pitch caption={t("sharedPitchCaption", { count: board.phase_out.length })} slots={board.phase_out} title={t("pitchTitleOut", { name: board.name })} />
          </div>
        </div>
        <div style={{ marginTop: "0.7rem" }}>
          <BandLegend />
        </div>
      </Panel>

      <div className="grid grid-2">
        <Panel eyebrow={t("sharedMeasuredEyebrow")} title={t("phaseIn")}>
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
        <Panel eyebrow={t("sharedMeasuredEyebrow")} title={t("phaseOut")}>
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
        {t.rich("sharedOwnerNote", { name: board.owner.name, link: (chunks) => (
          <Link className="world-link" href="/tactics">
            {chunks}
          </Link>
        ) })}
      </p>

      <Provenance provenance={board} extra={<span className="chip">{t("sharedRevocableChip")}</span>} />
    </div>
  );
}
